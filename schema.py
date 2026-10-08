from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


RiskLevel = Literal["CRITICAL", "HIGH", "MODERATE", "LOW"]
Mechanism = Literal["Hypovolemia", "Vasodilation", "Mixed", "Normal", "Unknown"]
SignalQuality = Literal["GOOD", "FAIR", "POOR"]
Scenario = Literal["Vasodilation", "Hypovolemia", "Normotensive", "HypoxiaStress", "Hemorrhage", "MixedShock"]


class SurgicalPhase(str, Enum):
    INDUCTION = "INDUCTION"
    MAINTENANCE = "MAINTENANCE"
    EMERGENCE = "EMERGENCE"


class SafetyStatus(str, Enum):
    STABLE = "STABLE"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class PatientBaseline(BaseModel):
    baseline_sbp: float = Field(default=120, ge=70, le=220)
    baseline_dbp: float = Field(default=80, ge=40, le=130)
    baseline_hr: float = Field(default=70, ge=40, le=160)

    @property
    def baseline_map(self) -> float:
        return (self.baseline_sbp + 2 * self.baseline_dbp) / 3.0


def map_from_bp(sbp: float, dbp: float) -> float:
    return (sbp + 2 * dbp) / 3.0


def pulse_pressure(sbp: float, dbp: float) -> float:
    return sbp - dbp


def shock_index(hr: float, sbp: float) -> float:
    return hr / sbp if sbp > 0 else float("inf")


def map_deviation_percent(map_value: float, baseline_map: float) -> float:
    return ((map_value - baseline_map) / baseline_map) * 100.0 if baseline_map > 0 else 0.0


def map_penalty(map_value: float) -> float:
    if map_value < 50 or map_value > 130:
        return 1.0
    if map_value < 65:
        return 0.7
    if map_value <= 100:
        return 0.0
    return 0.4


def hr_penalty(hr: float) -> float:
    if hr < 40 or hr > 140:
        return 1.0
    if hr < 50 or hr > 100:
        return 0.5
    return 0.0


def spo2_penalty(spo2: float) -> float:
    if spo2 < 88:
        return 1.0
    if spo2 < 93:
        return 0.6
    return 0.0


def etco2_penalty(etco2: float) -> float:
    return 0.8 if etco2 < 25 or etco2 > 50 else 0.0


def bis_penalty(bis: float) -> float:
    if bis > 65:
        return 0.8
    if 40 <= bis <= 60:
        return 0.0
    if 20 <= bis < 40:
        return 0.6
    return 1.0


def calculate_haii(
    *,
    map_value: float,
    hr: float,
    spo2: float | None,
    etco2: float | None,
    bis: float | None,
) -> tuple[float | None, float]:
    """
    Transparent HAII-style composite.

    When all five signals are available, the weights are exactly:
    MAP .30, HR .15, SpO2 .25, EtCO2 .15, BIS .15.

    When optional signals are absent, the available weights are renormalized
    rather than treating missing data as zero risk. The returned coverage is
    the fraction of the original weight that was available.
    """
    weighted = [(0.30, map_penalty(map_value)), (0.15, hr_penalty(hr))]
    if spo2 is not None:
        weighted.append((0.25, spo2_penalty(spo2)))
    if etco2 is not None:
        weighted.append((0.15, etco2_penalty(etco2)))
    if bis is not None:
        weighted.append((0.15, bis_penalty(bis)))

    available_weight = sum(weight for weight, _ in weighted)
    if available_weight <= 0:
        return None, 0.0

    score = sum(weight * penalty for weight, penalty in weighted) / available_weight
    return round(score, 3), round(available_weight, 3)


class TelemetryFrame(BaseModel):
    model_config = ConfigDict(extra="ignore")

    timestamp: float | None = None
    minute: float

    # Existing normalized signals.
    MAP: float = Field(ge=0, le=1000)
    HR: float = Field(ge=0, le=500)
    SVV: float | None = Field(default=None, ge=0, le=150)
    EtCO2: float | None = Field(default=None, ge=0, le=150)
    SpO2: float | None = Field(default=None, ge=0, le=120)
    CVP: float | None = Field(default=None, ge=-20, le=100)

    # Optional raw clinical signals used by the deterministic clinical layer.
    SBP: float | None = Field(default=None, ge=30, le=300)
    DBP: float | None = Field(default=None, ge=10, le=200)
    BIS: float | None = Field(default=None, ge=0, le=100)
    TOF_twitches: int | None = Field(default=None, ge=0, le=4)
    TOF_ratio: float | None = Field(default=None, ge=0, le=1)

    arterial_waveform: list[float] | None = Field(default=None, min_length=4, max_length=2000)
    ecg_waveform: list[float] | None = Field(default=None, min_length=4, max_length=2000)

    calculated_map: float | None = None
    pulse_pressure: float | None = None
    shock_index: float | None = None

    @model_validator(mode="after")
    def derive_bp_metrics(self):
        if self.SBP is not None and self.DBP is not None:
            if self.SBP <= self.DBP:
                raise ValueError("SBP must be greater than DBP.")
            self.calculated_map = round(map_from_bp(self.SBP, self.DBP), 1)
            self.pulse_pressure = round(pulse_pressure(self.SBP, self.DBP), 1)
            self.shock_index = round(shock_index(self.HR, self.SBP), 3)
        return self


class PatientTelemetry(BaseModel):
    patient_id: str = Field(min_length=1, max_length=128)
    age: int | None = Field(default=None, ge=0, le=120)
    weight_kg: float | None = Field(default=None, ge=1.0, le=300.0)
    surgical_phase: SurgicalPhase = SurgicalPhase.MAINTENANCE
    baseline: PatientBaseline = Field(default_factory=PatientBaseline)
    sampling_interval_seconds: float = Field(default=60.0, gt=0, le=60)
    telemetry: list[TelemetryFrame] = Field(min_length=2, max_length=1200)

    @field_validator("telemetry")
    @classmethod
    def ordered_frames(cls, value):
        if any(value[i].minute > value[i + 1].minute for i in range(len(value) - 1)):
            raise ValueError("Telemetry frames must be ordered by minute.")
        return value


class SimulationRequest(BaseModel):
    patient_id: str = Field(default="SIM-001", min_length=1, max_length=128)
    scenario: Scenario = "Vasodilation"
    frames: int = Field(default=31, ge=6, le=120)
    interval_seconds: float = Field(default=30, gt=0, le=60)


class SignalQualityReport(BaseModel):
    quality: SignalQuality
    valid_frames: int
    rejected_frames: int
    artifact_rate: float = Field(ge=0, le=1)
    signal_completeness: float = Field(ge=0, le=1)
    notes: list[str] = Field(default_factory=list)


class FeatureSummary(BaseModel):
    map_current: float
    map_slope_per_min: float
    map_drop: float
    map_acceleration_per_min2: float = 0.0
    predicted_map_10min: float
    predicted_map_15min: float
    hypotension_probability: float = Field(ge=0, le=1)
    trajectory: str
    trend_strength: float = Field(ge=0, le=1)
    map_volatility: float = 0.0
    hr_current: float
    hr_slope_per_min: float
    svv_current: float | None = None
    etco2_current: float | None = None
    spo2_current: float | None = None
    cvp_current: float | None = None

    # Deterministic clinical metrics.
    sbp_current: float | None = None
    dbp_current: float | None = None
    calculated_map_current: float | None = None
    pulse_pressure: float | None = None
    shock_index: float | None = None
    map_baseline: float | None = None
    map_deviation_percent: float | None = None
    haai_score: float | None = None
    haai_weight_coverage: float = Field(default=0.0, ge=0, le=1)
    bis_current: float | None = None
    tof_twitches: int | None = None
    tof_ratio: float | None = None

    arterial_waveform_range: float | None = None
    ecg_waveform_std: float | None = None
    map_below_65_fraction: float
    signal_quality: SignalQualityReport


class ClinicalAssessment(BaseModel):
    hemodynamic_risk_score: float = Field(ge=0, le=100)
    prediction_window_mins: int = Field(ge=10, le=15)
    predicted_map_15min: float
    hypotension_risk_level: RiskLevel
    primary_risk: str = "Intraoperative Hypotension"
    secondary_risk: str | None = None
    confidence_score: float = Field(ge=0, le=1)
    suspected_mechanism: Mechanism
    suggested_action: str
    suppress_alarm: bool = False
    guardrail_note: str | None = None
    data_quality: SignalQuality
    alert_priority: str = "ROUTINE"
    safety_status: SafetyStatus = SafetyStatus.STABLE
    deterministic_override: bool = False
    contributing_factors: list[str] = Field(default_factory=list)
    explanation: str = ""
    disclaimer: str = "Prototype CDS for research/demo use; not clinically validated. Thresholds are configurable research rules and are not a substitute for validated clinical protocols."


class PredictionResponse(BaseModel):
    patient_id: str
    frames_processed: int
    alert_triggered: bool
    pipeline: list[str]
    features: FeatureSummary
    clinical_assessment: ClinicalAssessment
    event_log: list[str] = Field(default_factory=list)
