import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from schema import PatientTelemetry, PredictionResponse
from agent import evaluate_patient_risk

app = FastAPI(
    title="AnestheSense CDS API",
    description="AI-driven clinical decision support system for intraoperative hypotension prediction.",
    version="1.0.0"
)

# Enable CORS for Streamlit frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"status": "online", "system": "AnestheSense CDS Engine"}

@app.post("/api/v1/predict", response_model=PredictionResponse)
def predict_hypotension(telemetry: PatientTelemetry):
    try:
        assessment = evaluate_patient_risk(telemetry)
        return PredictionResponse(
            patient_id=telemetry.patient_id,
            frames_processed=len(telemetry.telemetry),
            alert_triggered=assessment.hypotension_risk_level in ["CRITICAL", "HIGH"],
            clinical_assessment=assessment
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))