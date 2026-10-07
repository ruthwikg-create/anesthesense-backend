from __future__ import annotations

from schema import FeatureSummary


def build_contributors(features: FeatureSummary) -> list[str]:
    contributors: list[str] = []
    if features.map_slope_per_min <= -0.25:
        contributors.append(f"MAP trajectory is falling ({features.map_slope_per_min:.2f} mmHg/min).")
    if features.predicted_map_15min < 65:
        contributors.append(f"15-minute MAP forecast is {features.predicted_map_15min:.1f} mmHg.")
    if features.svv_current is not None and features.svv_current > 13:
        contributors.append(f"SVV is elevated at {features.svv_current:.1f}%.")
    if features.etco2_current is not None and features.etco2_current < 30:
        contributors.append(f"EtCO2 is reduced at {features.etco2_current:.1f} mmHg.")
    if features.spo2_current is not None and features.spo2_current < 92:
        contributors.append(f"SpO2 is reduced at {features.spo2_current:.1f}%.")
    if not contributors:
        contributors.append("No dominant instability contributor crossed the prototype thresholds.")
    return contributors


def build_event_log(features: FeatureSummary, assessment) -> list[str]:
    events = [
        f"Assessment: {assessment.hypotension_risk_level} risk; predicted MAP {assessment.predicted_map_15min:.1f} mmHg at 15 min.",
        f"Trajectory: {features.trajectory}; MAP slope {features.map_slope_per_min:.2f} mmHg/min.",
    ]
    if assessment.secondary_risk:
        events.append(f"Secondary signal: {assessment.secondary_risk}.")
    if assessment.suspected_mechanism != "Normal":
        events.append(f"Mechanism hypothesis: {assessment.suspected_mechanism}.")
    return events
