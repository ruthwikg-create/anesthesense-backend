from __future__ import annotations

from schema import ClinicalAssessment, FeatureSummary


RISK_RANK = {"LOW": 0, "MODERATE": 1, "HIGH": 2, "CRITICAL": 3}


def apply_safety_guardrails(
    baseline: ClinicalAssessment,
    candidate: ClinicalAssessment,
    features: FeatureSummary,
) -> ClinicalAssessment:
    # Deterministic severity, score, and alarm state are authoritative.
    if RISK_RANK[candidate.hypotension_risk_level] < RISK_RANK[baseline.hypotension_risk_level]:
        candidate.hypotension_risk_level = baseline.hypotension_risk_level

    candidate.hemodynamic_risk_score = max(
        candidate.hemodynamic_risk_score,
        baseline.hemodynamic_risk_score,
    )

    # Keep the displayed forecast consistent with the deterministic forecast.
    candidate.predicted_map_15min = min(
        candidate.predicted_map_15min,
        baseline.predicted_map_15min,
    )
    candidate.predicted_map_15min = max(30.0, min(140.0, candidate.predicted_map_15min))

    if baseline.hypotension_risk_level in {"HIGH", "CRITICAL"}:
        candidate.suppress_alarm = False

    if baseline.predicted_map_15min < 60:
        candidate.hypotension_risk_level = "CRITICAL"
        candidate.suppress_alarm = False
    elif baseline.predicted_map_15min < 65:
        candidate.hypotension_risk_level = "HIGH"
        candidate.suppress_alarm = False

    notes = list(filter(None, [candidate.guardrail_note]))
    if features.signal_quality.quality == "POOR":
        notes.append("Poor signal quality: verify source signals before interpreting the advisory output.")
    if candidate.hypotension_risk_level in {"HIGH", "CRITICAL"}:
        notes.append("Risk severity and alarm state are controlled by the deterministic safety layer.")
    candidate.guardrail_note = " ".join(dict.fromkeys(notes)) or None

    return candidate
