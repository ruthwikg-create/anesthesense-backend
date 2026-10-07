# AnestheSense v4

AnestheSense is an **AI-assisted intraoperative hemodynamic early-warning clinical decision-support prototype** for anesthesiology research/demo use.

It is designed to identify a deteriorating hemodynamic trajectory before a severe hypotensive state develops. It is not a clinical device and is not validated for patient care.

## What v4 adds

### Phase 1 — Real-time analytics
- Multiparameter telemetry ingestion
- Artifact rejection and signal-quality reporting
- MAP trend and acceleration
- MAP volatility and trend strength
- 10-minute and 15-minute MAP forecasts
- Transparent prototype hypotension probability
- Risk trajectory classification
- SVV, EtCO2, SpO2, CVP and optional waveform features
- WebSocket telemetry endpoint

### Phase 2 — Explainability and safety
- Deterministic clinical-risk engine
- Mechanism hypothesis: Normal / Vasodilation / Hypovolemia / Mixed
- Contributing-factor explanations
- Event timeline
- Gemini as an optional explanation layer
- Gemini cannot downgrade HIGH/CRITICAL risk
- Gemini cannot reduce the deterministic risk score
- HIGH/CRITICAL alarms cannot be suppressed by Gemini
- No autonomous medication dosing

### Phase 3 — Advanced dashboard
The Streamlit application contains:
- Live synthetic OR replay
- Dynamic MAP chart
- Forecast visualization
- Risk score
- Hypotension probability
- Mechanism
- Trend strength
- Signal quality
- Clinical advisory
- Event timeline
- Feature matrix
- Audit JSON export
- Manual telemetry stress testing

### Phase 4 — Verification and reproducibility
- Deterministic simulations using a fixed random seed
- API regression tests
- WebSocket tests
- Artifact rejection tests
- Poor-quality signal tests
- Simulator coverage across all scenarios
- Compile-time validation
- GitHub Actions CI

## Architecture

```text
Multiparameter telemetry
        |
        v
+----------------------------+
| Signal Preprocessor Agent  |
|----------------------------|
| artifact rejection         |
| signal quality             |
| waveform features          |
+-------------+--------------+
              |
              v
+----------------------------+
| Predictive Analytics Agent |
|----------------------------|
| trend + acceleration       |
| volatility                 |
| 10/15-min MAP forecast     |
| hypotension probability    |
| trajectory                 |
+-------------+--------------+
              |
              v
+----------------------------+
| Clinical Advisory Agent    |
|----------------------------|
| risk severity              |
| mechanism hypothesis       |
| contributing factors       |
| clinician-directed action  |
+-------------+--------------+
              |
              v
+----------------------------+
| Safety Guardrail           |
|----------------------------|
| severity floor             |
| alarm protection           |
| no medication dosing       |
+-------------+--------------+
              |
              v
      Clinician Dashboard
```

## Telemetry

Supported inputs:
- MAP
- HR
- SVV
- EtCO2
- SpO2
- optional CVP
- optional arterial waveform samples
- optional ECG waveform samples

## API

### Health

`GET /health`

### Prediction

`POST /api/v1/predict`

### Simulation

`POST /api/v1/simulate`

### Simulation + analysis

`POST /api/v1/simulate/analyze`

### WebSocket

`WS /ws/telemetry`

## Simulation laboratory

Supported deterministic scenarios:

- Vasodilation
- Hypovolemia
- Hemorrhage
- MixedShock
- HypoxiaStress
- Normotensive

Example:

```json
{
  "patient_id": "DEMO-OR-01",
  "scenario": "Hemorrhage",
  "frames": 31,
  "interval_seconds": 30
}
```

## Run locally

### Windows

```bat
python -m venv venv
venv\\Scripts\\activate
pip install -r requirements.txt
uvicorn main:app --reload
```

API: http://127.0.0.1:8000

Swagger: http://127.0.0.1:8000/docs

Health: http://127.0.0.1:8000/health

### Dashboard

Open another terminal:

```bat
venv\\Scripts\\activate
streamlit run dashboard.py
```

Then open the Streamlit URL shown in the terminal, normally http://localhost:8501.

## Optional Gemini

Set:

```text
GEMINI_API_KEY=your_key
GEMINI_MODEL=gemini-2.5-flash
```

Without the API key, AnestheSense remains fully operational using the deterministic engine.

Gemini is intentionally constrained to an assistive explanation role. It receives the deterministic baseline and cannot lower a HIGH/CRITICAL result or suppress a HIGH/CRITICAL alarm.

## Testing

Run locally:

```bat
pytest -q
```

CI also runs:

```bat
python -m compileall -q .
pytest -q
```

The latest v4 CI run completed successfully with all test stages passing.

## Safety and validation boundary

This software is a **research/demo prototype**. Its risk score, probability, forecasts and suggested actions are not clinically validated treatment recommendations.

It must not be connected to real patient care without:
- clinically representative datasets
- prospective validation
- calibration and performance analysis
- clinical workflow evaluation
- cybersecurity/privacy review
- formal medical-device/regulatory assessment
- appropriate institutional and clinician oversight

The project deliberately avoids autonomous drug dosing.
