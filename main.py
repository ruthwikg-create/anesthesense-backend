import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from agent import evaluate_patient_risk
from schema import PatientTelemetry, PredictionResponse

app=FastAPI(title="AnestheSense CDS API",description="Assistive clinical decision-support API for intraoperative hemodynamic risk prediction.",version="2.0.0")
app.add_middleware(CORSMiddleware,allow_origins=["*"],allow_credentials=True,allow_methods=["*"],allow_headers=["*"])

@app.get("/")
def read_root(): return {"status":"online","system":"AnestheSense CDS Engine","version":app.version}

@app.get("/health")
def health(): return {"status":"ok","service":"anesthesense-backend","gemini_configured":bool(os.getenv("GEMINI_API_KEY"))}

@app.post("/api/v1/predict",response_model=PredictionResponse)
def predict_hypotension(telemetry:PatientTelemetry):
    try:
        assessment=evaluate_patient_risk(telemetry)
        return PredictionResponse(patient_id=telemetry.patient_id,frames_processed=len(telemetry.telemetry),alert_triggered=not assessment.suppress_alarm and assessment.hypotension_risk_level in {"CRITICAL","HIGH"},clinical_assessment=assessment)
    except Exception as exc:
        raise HTTPException(status_code=500,detail=f"Assessment failed: {exc}") from exc
