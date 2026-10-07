from __future__ import annotations

import json
import os
from statistics import mean
from schema import ClinicalAssessment, FeatureSummary, PatientTelemetry, SignalQualityReport

MAP_HYPOTENSION = 65.0
MAP_CRITICAL = 60.0
HIGH_SVV = 13.0

def _slope(values: list[float], minutes: list[float]) -> float:
    if len(values) < 2: return 0.0
    xm, ym = mean(minutes), mean(values)
    den = sum((x-xm)**2 for x in minutes)
    return sum((x-xm)*(y-ym) for x,y in zip(minutes, values))/den if den else 0.0

def preprocess(telemetry: PatientTelemetry) -> tuple[PatientTelemetry, SignalQualityReport]:
    valid, rejected = [], 0
    for frame in telemetry.telemetry:
        if 20 <= frame.MAP <= 220 and 20 <= frame.HR <= 250 and 0 <= frame.SVV <= 100 and 0 <= frame.EtCO2 <= 100:
            valid.append(frame)
        else:
            rejected += 1
    artifact_rate = rejected / len(telemetry.telemetry)
    quality = "GOOD" if artifact_rate <= .05 else "FAIR" if artifact_rate <= .20 else "POOR"
    notes = []
    if artifact_rate: notes.append("Out-of-range telemetry frames removed before inference.")
    if any(f.arterial_waveform for f in valid): notes.append("Arterial waveform supplied; feature extraction can be extended with beat-level DSP.")
    if any(f.ecg_waveform for f in valid): notes.append("ECG waveform supplied; HRV feature extraction can be extended with beat detection.")
    return PatientTelemetry(patient_id=telemetry.patient_id, sampling_interval_seconds=telemetry.sampling_interval_seconds, telemetry=valid), SignalQualityReport(quality=quality, valid_frames=len(valid), rejected_frames=rejected, artifact_rate=artifact_rate, notes=notes)

def extract_features(data: PatientTelemetry, quality: SignalQualityReport) -> FeatureSummary:
    frames=data.telemetry
    minutes=[f.minute for f in frames]
    maps=[f.MAP for f in frames]
    hrs=[f.HR for f in frames]
    below=sum(v < MAP_HYPOTENSION for v in maps)/len(maps)
    last=frames[-1]
    return FeatureSummary(
        map_current=last.MAP, map_slope_per_min=round(_slope(maps,minutes),3),
        map_drop=round(maps[0]-last.MAP,2), hr_current=last.HR,
        hr_slope_per_min=round(_slope(hrs,minutes),3), svv_current=last.SVV,
        etco2_current=last.EtCO2, spo2_current=last.SpO2, cvp_current=last.CVP,
        map_below_65_fraction=round(below,3), signal_quality=quality)

def _predict(features: FeatureSummary) -> ClinicalAssessment:
    predicted=max(35.0, round(features.map_current + features.map_slope_per_min*15,1))
    trajectory_pressure=max(0.0, min(45.0, -features.map_slope_per_min*18))
    current_pressure=max(0.0, min(35.0, (65-features.map_current)*2.5))
    persistence=features.map_below_65_fraction*20
    score=round(min(100, trajectory_pressure+current_pressure+persistence),1)
    if predicted < MAP_CRITICAL: risk="CRITICAL"
    elif predicted < MAP_HYPOTENSION: risk="HIGH"
    elif score >= 40: risk="MODERATE"
    else: risk="LOW"
    if features.map_current < 70 and features.svv_current > HIGH_SVV:
        mechanism="Hypovolemia"; action="Assess volume status and surgical blood loss; consider clinician-directed fluid/blood management and reassess MAP/SVV."
    elif features.map_current < 70 and features.svv_current <= HIGH_SVV:
        mechanism="Vasodilation"; action="Assess anesthetic depth and vasodilatory causes; consider clinician-directed vasopressor support and reassess MAP."
    elif features.map_current < 70:
        mechanism="Mixed"; action="Reassess volume status, anesthetic depth, blood loss, and other causes of hemodynamic instability."
    else:
        mechanism="Normal"; action="Continue routine monitoring; no immediate intervention indicated by this prototype."
    confidence=min(.94, .62 + min(.18,len([1])) + (.08 if features.signal_quality.quality=="GOOD" else 0))
    return ClinicalAssessment(hemodynamic_risk_score=score,prediction_window_mins=15,predicted_map_15min=predicted,hypotension_risk_level=risk,confidence_score=confidence,suspected_mechanism=mechanism,suggested_action=action,suppress_alarm=features.signal_quality.quality=="POOR",data_quality=features.signal_quality.quality)

def _gemini(features: FeatureSummary, baseline: ClinicalAssessment) -> ClinicalAssessment:
    key=os.getenv("GEMINI_API_KEY")
    if not key: return baseline
    try:
        from google import genai
        from google.genai import types
        client=genai.Client(api_key=key)
        response=client.models.generate_content(
            model=os.getenv("GEMINI_MODEL","gemini-2.5-flash"),
            contents=json.dumps({"features":features.model_dump(),"baseline":baseline.model_dump()}),
            config=types.GenerateContentConfig(
                system_instruction="You are the reasoning layer of an assistive intraoperative CDS prototype. Use only supplied features. Return structured JSON. Never downgrade a deterministic HIGH/CRITICAL risk. Do not prescribe a dose. Recommendations must require clinician judgment.",
                temperature=0, response_mime_type="application/json", response_schema=ClinicalAssessment))
        result=ClinicalAssessment.model_validate_json(response.text)
        rank={"LOW":0,"MODERATE":1,"HIGH":2,"CRITICAL":3}
        if rank[result.hypotension_risk_level] < rank[baseline.hypotension_risk_level]: result.hypotension_risk_level=baseline.hypotension_risk_level
        if baseline.hemodynamic_risk_score > result.hemodynamic_risk_score: result.hemodynamic_risk_score=baseline.hemodynamic_risk_score
        if baseline.hypotension_risk_level in {"HIGH","CRITICAL"}: result.suppress_alarm=False
        result.confidence_score=min(result.confidence_score,.95)
        return result
    except Exception as exc:
        baseline.guardrail_note=f"Gemini unavailable; deterministic safety engine retained ({type(exc).__name__})."
        return baseline

def evaluate_patient_risk(telemetry_data: PatientTelemetry):
    clean, quality=preprocess(telemetry_data)
    if not clean.telemetry: raise ValueError("No valid telemetry frames remain after preprocessing.")
    features=extract_features(clean,quality)
    baseline=_predict(features)
    return _gemini(features,baseline), features, ["Signal Preprocessor Agent","Predictive Analytics Agent","Clinical Advisory Agent"]
