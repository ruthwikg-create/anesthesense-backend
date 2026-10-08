from __future__ import annotations

from schema import ClinicalAssessment, FeatureSummary, SafetyStatus


RISK_RANK = {"LOW": 0, "MODERATE": 1, "HIGH": 2, "CRITICAL": 3}


def apply_safety_guardrails(
    baseline: ClinicalAssessment,
    candidate: ClinicalAssessment,
    features: FeatureSummary,
) -> ClinicalAssessment:
    # The deterministic layer is authoritative over generative explanations.
    if RISK_RANK[candidate.hypotension_risk_level] < RISK_RANK[baseline.hypotension_risk_level]:
        candidate.hypotension_risk_level = baseline.hypotension_risk_level

    candidate.hemodynamic_risk_score = max(
        candidate.hemodynamic_risk_score,
        baseline.hemodynamic_risk_score,
    )
    candidate.predicted_map_15min = min(
        candidate.predicted_map_15min,
        baseline.predicted_map_15min,
    )
    candidate.predicted_map_15min = max(30.0, min(140.0, candidate.predicted_map_15min))

    if baseline.deterministic_override:
        candidate.deterministic_override = True
        candidate.suppress_alarm = False
        candidate.safety_status = baseline.safety_status
        candidate.guardrail_note = baseline.guardrail_note

    if baseline.hypotension_risk_level in {"HIGH", "CRITICAL"}:
        candidate.suppress_alarm = False

    if baseline.predicted_map_15min < 60:
        candidate.hypotension_risk_level = "CRITICAL"
        candidate.suppress_alarm = False
    elif baseline.predicted_map_15min < 65:
        candidate.hypotension_risk_level = "HIGH"
        candidate.suppress_alarm = False

    if features.signal_quality.quality == "POOR":
        candidate.guardrail_note = " ".join(
            filter(
                None,
                [
                    candidate.guardrail_note,
                    "Poor signal quality: verify source signals before interpreting the advisory output.",
                ],
            )
        )

    return candidate
