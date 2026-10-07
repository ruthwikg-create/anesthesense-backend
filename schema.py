from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict

RiskLevel = Literal["CRITICAL", "HIGH", "MODERATE", "LOW"]
Mechanism = Literal["Hypovolemia", "Vasodilation", "Mixed", "Normal", "Unknown"]

class TelemetryFrame(BaseModel):
    model_config = ConfigDict(extra="ignore")
    minute: float
    MAP: float = Field(ge=20, le=220)
    HR: float = Field(ge=20, le=250)
    SVV: float = Field(ge=0, le=100)
    EtCO2: float = Field(ge=0, le=100)
    SpO2: float | None = Field(default=None, ge=0, le=100)

class PatientTelemetry(BaseModel):
    patient_id: str = Field(min_length=1, max_length=128)
    telemetry: list[TelemetryFrame] = Field(min_length=2, max_length=120)

class ClinicalAssessment(BaseModel):
    predicted_map_15min: float
    hypotension_risk_level: RiskLevel
    confidence_score: float = Field(ge=0.0, le=1.0)
    suspected_mechanism: Mechanism
    suggested_action: str = Field(min_length=1)
    suppress_alarm: bool = False
    guardrail_note: str | None = None
    data_quality: Literal["GOOD", "LIMITED"] = "GOOD"

class PredictionResponse(BaseModel):
    patient_id: str
    frames_processed: int
    alert_triggered: bool
    clinical_assessment: ClinicalAssessment
