from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict, field_validator

RiskLevel = Literal["CRITICAL", "HIGH", "MODERATE", "LOW"]
Mechanism = Literal["Hypovolemia", "Vasodilation", "Mixed", "Normal", "Unknown"]
SignalQuality = Literal["GOOD", "FAIR", "POOR"]
Scenario = Literal["Vasodilation", "Hypovolemia", "Normotensive", "HypoxiaStress"]

class TelemetryFrame(BaseModel):
    model_config = ConfigDict(extra="ignore")
    timestamp: float | None = None
    minute: float
    MAP: float = Field(ge=0, le=1000)
    HR: float = Field(ge=0, le=500)
    SVV: float = Field(ge=0, le=150)
    EtCO2: float = Field(ge=0, le=150)
    SpO2: float | None = Field(default=None, ge=0, le=120)
    CVP: float | None = Field(default=None, ge=-20, le=100)
    arterial_waveform: list[float] | None = Field(default=None, min_length=4, max_length=2000)
    ecg_waveform: list[float] | None = Field(default=None, min_length=4, max_length=2000)

class PatientTelemetry(BaseModel):
    patient_id: str = Field(min_length=1, max_length=128)
    sampling_interval_seconds: float = Field(default=60.0, gt=0, le=60)
    telemetry: list[TelemetryFrame] = Field(min_length=2, max_length=1200)

    @field_validator("telemetry")
    @classmethod
    def ordered_frames(cls, value):
        if any(value[i].minute > value[i+1].minute for i in range(len(value)-1)):
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
    notes: list[str] = Field(default_factory=list)

class FeatureSummary(BaseModel):
    map_current: float
    map_slope_per_min: float
    map_drop: float
    hr_current: float
    hr_slope_per_min: float
    svv_current: float
    etco2_current: float
    spo2_current: float | None = None
    cvp_current: float | None = None
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

class PredictionResponse(BaseModel):
    patient_id: str
    frames_processed: int
    alert_triggered: bool
    pipeline: list[str]
    features: FeatureSummary
    clinical_assessment: ClinicalAssessment
