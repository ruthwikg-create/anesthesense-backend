from __future__ import annotations

from schema import ClinicalAssessment, FeatureSummary


RISK_RANK = {"LOW": 0, "MODERATE": 1, "HIGH": 2, "CRITICAL": 3}


def apply_safety_guardrails(
    baseline: ClinicalAssessment,
    candidate: ClinicalAssessment,
    features: FeatureSummary,
) -> ClinicalAssessment:
    # The deterministic safety layer is authoritative for severity and alarm state.
    if RISK_RANK[candidate.hypotension_risk_level] < RISK_RANK[baseline.hypotension_risk_level]:
        candidate.hypotension_risk_level = baseline.hypotension_risk_level

    candidate.hemodynamic_risk_score = max(
        candidate.hemodynamic_risk_score,
        baseline.hemodynamic_risk_score,
    )

    if baseline.hypotension_risk_level in {"HIGH", "CRITICAL"}:
        candidate.suppress_alarm = False

    if candidate.predicted_map_15min < 60 and candidate.hypotension_risk_level not in {"CRITICAL"}:
        candidate.hypotension_risk_level = "CRITICAL"
        candidate.suppress_alarm = False

    candidate.predicted_map_15min = max(30.0, min(140.0, candidate.predicted_map_15min))

    notes = list(filter(None, [candidate.guardrail_note]))
    if features.signal_quality.quality == "POOR":
        notes.append("Poor signal quality: interpret the advisory output cautiously and verify source signals.")
    if candidate.hypotension_risk_level in {"HIGH", "CRITICAL"}:
        notes.append("Risk level and alarm state are controlled by the deterministic safety layer.")
    candidate.guardrail_note = " ".join(dict.fromkeys(notes)) or None

    return candidate
