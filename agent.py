from __future__ import annotations

import json
import os
from statistics import mean, pstdev

from explainability import build_contributors, build_event_log
from forecasting import forecast_map
from safety import apply_safety_guardrails
from schema import (
    ClinicalAssessment,
    FeatureSummary,
    PatientTelemetry,
    SignalQualityReport,
    SafetyStatus,
    calculate_haii,
    map_deviation_percent,
)


MAP_HYPOTENSION = 65.0
HIGH_SVV = 13.0


def _slope(values, minutes):
    if len(values) < 2:
        return 0.0
    xm, ym = mean(minutes), mean(values)
    den = sum((x - xm) ** 2 for x in minutes)
    return sum((x - xm) * (y - ym) for x, y in zip(minutes, values)) / den if den else 0.0


def preprocess(telemetry):
    if not telemetry.telemetry:
        raise ValueError("No telemetry frames were supplied.")
    if len(telemetry.telemetry) < 2:
        raise ValueError("At least two telemetry frames are required for trajectory analysis.")

    valid = []
    rejected = 0
    optional_fields = ("SVV", "EtCO2", "SpO2", "CVP")

    for frame in telemetry.telemetry:
        valid_frame = (
            20 <= frame.MAP <= 220
            and 20 <= frame.HR <= 250
            and (frame.SVV is None or 0 <= frame.SVV <= 100)
            and (frame.EtCO2 is None or 0 <= frame.EtCO2 <= 100)
            and (frame.SpO2 is None or 70 <= frame.SpO2 <= 100)
            and (frame.CVP is None or -20 <= frame.CVP <= 100)
        )
        if valid_frame:
            valid.append(frame)
        else:
            rejected += 1

    if len(valid) < 2:
        raise ValueError(
            "Fewer than two valid telemetry frames remain after signal validation. "
            "Check MAP/HR values and the source data."
        )

    rate = rejected / len(telemetry.telemetry)
    availability = sum(
        sum(getattr(frame, field) is not None for field in optional_fields)
        for frame in valid
    )
    total_optional = max(1, len(valid) * len(optional_fields))
    completeness = availability / total_optional

    if rate > 0.20 or completeness < 0.50:
        quality = "POOR"
    elif rate > 0.05 or completeness < 0.75:
        quality = "FAIR"
    else:
        quality = "GOOD"

    notes = []
    if rejected:
        notes.append(f"{rejected} out-of-range frame(s) removed before inference.")
    if completeness < 1:
        missing = [
            field
            for field in optional_fields
            if not any(getattr(frame, field) is not None for frame in valid)
        ]
        if missing:
            notes.append("Unavailable signals: " + ", ".join(missing) + ".")
        else:
            notes.append("Some optional signal samples are missing.")
    if any(f.arterial_waveform for f in valid):
        notes.append("Arterial waveform samples received; prototype morphology range feature extracted.")
    if any(f.ecg_waveform for f in valid):
        notes.append("ECG waveform samples received; prototype variability feature extracted.")

    clean = PatientTelemetry(
        patient_id=telemetry.patient_id,
        sampling_interval_seconds=telemetry.sampling_interval_seconds,
        telemetry=valid,
    )
    return clean, SignalQualityReport(
        quality=quality,
        valid_frames=len(valid),
        rejected_frames=rejected,
        artifact_rate=rate,
        signal_completeness=round(completeness, 3),
        notes=notes,
    )


def extract_features(data, quality):
    frames = data.telemetry
    minutes = [f.minute for f in frames]
    maps = [f.MAP for f in frames]
    hrs = [f.HR for f in frames]
    last = frames[-1]

    arterial = [x for f in frames if f.arterial_waveform for x in f.arterial_waveform]
    ecg = [x for f in frames if f.ecg_waveform for x in f.ecg_waveform]
    forecast = forecast_map(maps, minutes)

    baseline_map = data.baseline.baseline_map
    haai_score, haai_coverage = calculate_haii(
        map_value=last.MAP,
        hr=last.HR,
        spo2=last.SpO2,
        etco2=last.EtCO2,
        bis=last.BIS,
    )

    return FeatureSummary(
        map_current=last.MAP,
        map_slope_per_min=forecast.map_slope_per_min,
        map_drop=round(maps[0] - last.MAP, 2),
        map_acceleration_per_min2=forecast.map_acceleration_per_min2,
        predicted_map_10min=forecast.predicted_map_10min,
        predicted_map_15min=forecast.predicted_map_15min,
        hypotension_probability=forecast.hypotension_probability,
        trajectory=forecast.trajectory,
        trend_strength=forecast.trend_strength,
        map_volatility=forecast.volatility,
        hr_current=last.HR,
        hr_slope_per_min=round(_slope(hrs, minutes), 3),
        svv_current=last.SVV,
        etco2_current=last.EtCO2,
        spo2_current=last.SpO2,
        cvp_current=last.CVP,
        sbp_current=last.SBP,
        dbp_current=last.DBP,
        calculated_map_current=last.calculated_map,
        pulse_pressure=last.pulse_pressure,
        shock_index=last.shock_index,
        map_baseline=round(baseline_map, 1),
        map_deviation_percent=round(map_deviation_percent(last.MAP, baseline_map), 1),
        haai_score=haai_score,
        haai_weight_coverage=haai_coverage,
        bis_current=last.BIS,
        tof_twitches=last.TOF_twitches,
        tof_ratio=last.TOF_ratio,
        arterial_waveform_range=round(max(arterial) - min(arterial), 3) if arterial else None,
        ecg_waveform_std=round(pstdev(ecg), 3) if len(ecg) > 1 else None,
        map_below_65_fraction=round(sum(x < 65 for x in maps) / len(maps), 3),
        signal_quality=quality,
    )


def deterministic_rule_check(features, surgical_phase):
    """Hard-coded research safety rules; never provides medication instructions."""
    alerts = []

    if features.map_current < 55:
        alerts.append(("CRITICAL_HYPOTENSION", f"MAP is below 55 mmHg ({features.map_current:.1f})."))
    if (
        features.map_deviation_percent is not None
        and features.map_deviation_percent <= -20
    ):
        alerts.append(("BASELINE_MAP_DROP", f"MAP is at least 20% below the configured baseline ({features.map_deviation_percent:.1f}%)."))
    if features.spo2_current is not None and features.spo2_current < 90:
        alerts.append(("CRITICAL_HYPOXEMIA", f"SpO2 is below 90% ({features.spo2_current:.1f}%)."))
    if (
        features.bis_current is not None
        and features.bis_current > 65
        and surgical_phase == "MAINTENANCE"
    ):
        alerts.append(("AWARENESS_RISK", f"BIS is above 65 during maintenance ({features.bis_current:.1f})."))
    if features.shock_index is not None and features.shock_index > 0.9:
        alerts.append(("ELEVATED_SHOCK_INDEX", f"Shock index is above 0.9 ({features.shock_index:.2f})."))

    return alerts


def _predict(f, surgical_phase="MAINTENANCE"):
    probability_component = f.hypotension_probability * 45
    trend_component = max(0, -f.map_slope_per_min) * 22
    current_component = max(0, 65 - f.map_current) * 2.2
    score = min(100, probability_component + trend_component + current_component + f.map_below_65_fraction * 15)

    overrides = deterministic_rule_check(f, surgical_phase)
    if any(code in {"CRITICAL_HYPOTENSION", "CRITICAL_HYPOXEMIA"} for code, _ in overrides):
        risk = "CRITICAL"
    elif overrides or f.predicted_map_15min < 65:
        risk = "HIGH"
    elif score >= 40:
        risk = "MODERATE"
    else:
        risk = "LOW"

    secondary = None
    if f.spo2_current is not None and f.spo2_current < 92:
        secondary = "Hypoxemia signal"
    elif f.etco2_current is not None and f.etco2_current < 30:
        secondary = "Low EtCO2 signal"

    svv_high = f.svv_current is not None and f.svv_current > HIGH_SVV
    low_etco2 = f.etco2_current is not None and f.etco2_current < 30

    if f.map_current < 70 and svv_high and low_etco2:
        mechanism = "Mixed"
        action = "Assess volume status, blood loss, anesthetic depth, and low-flow contributors; use clinician-directed management and reassessment."
    elif f.map_current < 70 and svv_high:
        mechanism = "Hypovolemia"
        action = "Assess volume status and surgical blood loss; consider clinician-directed fluid/blood management and reassess MAP/SVV."
    elif f.map_current < 70:
        mechanism = "Vasodilation"
        action = "Assess anesthetic depth and vasodilatory causes; consider clinician-directed hemodynamic support and reassess MAP."
    else:
        mechanism = "Normal"
        action = "Continue routine monitoring; reassess if trajectory worsens."

    confidence = 0.55 + 0.12 * f.trend_strength + 0.10 * f.signal_quality.signal_completeness - 0.10 * f.signal_quality.artifact_rate
    confidence = min(0.94, max(0.30, round(confidence, 3)))
    priority = "CRITICAL" if risk == "CRITICAL" else "HIGH" if risk == "HIGH" else "WATCH" if risk == "MODERATE" else "ROUTINE"
    safety_status = SafetyStatus.CRITICAL if risk == "CRITICAL" else SafetyStatus.WARNING if risk == "HIGH" else SafetyStatus.STABLE

    baseline = ClinicalAssessment(
        hemodynamic_risk_score=round(score, 1),
        prediction_window_mins=15,
        predicted_map_15min=f.predicted_map_15min,
        hypotension_risk_level=risk,
        secondary_risk=secondary,
        confidence_score=confidence,
        suspected_mechanism=mechanism,
        suggested_action=action,
        suppress_alarm=False,
        data_quality=f.signal_quality.quality,
        alert_priority=priority,
        safety_status=safety_status,
        deterministic_override=bool(overrides),
    )
    if overrides:
        baseline.guardrail_note = "Deterministic safety override: " + " ".join(f"{code}: {message}" for code, message in overrides)
    baseline.contributing_factors = build_contributors(f)
    baseline.explanation = (
        f"Current MAP {f.map_current:.1f} mmHg; 15-minute forecast {f.predicted_map_15min:.1f} mmHg; "
        f"trajectory {f.trajectory}; prototype hypotension probability {f.hypotension_probability:.0%}."
    )
    if f.haai_score is not None:
        baseline.explanation += f" HAII-style deterministic score: {f.haai_score:.3f} with {f.haai_weight_coverage:.0%} signal-weight coverage."
    if f.shock_index is not None:
        baseline.explanation += f" Shock index: {f.shock_index:.2f}."
    if f.map_deviation_percent is not None:
        baseline.explanation += f" MAP deviation from configured baseline: {f.map_deviation_percent:.1f}%."
    return baseline


def _gemini(f, baseline):
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        return baseline

    try:
        from google import genai
        from google.genai import types

        response = genai.Client(api_key=key).models.generate_content(
            model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
            contents=json.dumps({"features": f.model_dump(), "baseline": baseline.model_dump()}),
            config=types.GenerateContentConfig(
                system_instruction=(
                    "You are an assistive intraoperative CDS explanation layer. "
                    "Use only supplied features. Return structured JSON. "
                    "Never downgrade deterministic HIGH/CRITICAL risk, never reduce the "
                    "deterministic risk score, never suppress a deterministic HIGH/CRITICAL "
                    "alarm, and never prescribe a drug dose. Guidance requires clinician judgment."
                ),
                temperature=0,
                response_mime_type="application/json",
                response_schema=ClinicalAssessment,
            ),
        )
        candidate = ClinicalAssessment.model_validate_json(response.text)
        return apply_safety_guardrails(baseline, candidate, f)
    except Exception as exc:
        baseline.guardrail_note = f"Generative explanation unavailable; deterministic safety engine retained ({type(exc).__name__})."
        return baseline


def evaluate_patient_risk(telemetry):
    clean, quality = preprocess(telemetry)
    features = extract_features(clean, quality)
    assessment = _gemini(features, _predict(features, clean.surgical_phase.value))
    event_log = build_event_log(features, assessment)

    pipeline = [
        "Signal Preprocessor Agent",
        "Predictive Analytics Agent",
        "Clinical Advisory Agent",
    ]
    return assessment, features, pipeline, event_log
