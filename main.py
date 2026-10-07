import os

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from agent import evaluate_patient_risk
from schema import PatientTelemetry, PredictionResponse, SimulationRequest
from simulation import build_simulation


app = FastAPI(
    title="AnestheSense CDS API",
    description="AI-assisted intraoperative hemodynamic early-warning prototype.",
    version="4.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {
        "status": "online",
        "system": "AnestheSense",
        "mode": "advanced-early-warning-CDS",
        "version": app.version,
        "prototype": True,
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "anesthesense-backend",
        "version": app.version,
        "gemini_configured": bool(os.getenv("GEMINI_API_KEY")),
        "streaming": True,
        "forecasting": True,
        "simulation": True,
    }


def _prediction_response(telemetry: PatientTelemetry) -> PredictionResponse:
    assessment, features, pipeline, event_log = evaluate_patient_risk(telemetry)
    return PredictionResponse(
        patient_id=telemetry.patient_id,
        frames_processed=len(telemetry.telemetry),
        alert_triggered=(
            not assessment.suppress_alarm
            and assessment.hypotension_risk_level in {"HIGH", "CRITICAL"}
        ),
        pipeline=pipeline,
        features=features,
        clinical_assessment=assessment,
        event_log=event_log,
    )


@app.post("/api/v1/predict", response_model=PredictionResponse)
def predict(telemetry: PatientTelemetry):
    try:
        return _prediction_response(telemetry)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Assessment failed: {exc}") from exc


@app.post("/api/v1/simulate", response_model=PatientTelemetry)
def simulate(request: SimulationRequest):
    return build_simulation(request)


@app.post("/api/v1/simulate/analyze", response_model=PredictionResponse)
def simulate_and_analyze(request: SimulationRequest):
    telemetry = build_simulation(request)
    return _prediction_response(telemetry)


@app.websocket("/ws/telemetry")
async def telemetry_stream(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            payload = await websocket.receive_json()
            try:
                telemetry = PatientTelemetry.model_validate(payload)
                result = _prediction_response(telemetry)
                await websocket.send_json(result.model_dump())
            except Exception as exc:
                await websocket.send_json({"error": str(exc)})
    except WebSocketDisconnect:
        pass
