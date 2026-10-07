# AnestheSense Backend

AnestheSense is an AI-assisted intraoperative hemodynamic early-warning prototype for anesthesiology research. It analyzes multiparameter telemetry and provides a rolling 10–15 minute risk forecast rather than simply reacting to a threshold alarm.

## Pipeline

Multiparameter OT telemetry → Signal Preprocessor Agent → Predictive Analytics Agent → Clinical Advisory Agent → 15-minute dynamic risk + mechanism + clinician-directed guidance.

## Supported telemetry

- MAP
- Heart rate
- SVV
- EtCO2
- SpO2
- Optional CVP
- Optional arterial waveform samples
- Optional ECG waveform samples

The current prototype uses deterministic physiological features as the safety layer and optionally uses Gemini for structured reasoning. Gemini cannot downgrade a deterministic HIGH/CRITICAL assessment.

## Run locally

python -m venv venv

Windows PowerShell: venv\\Scripts\\Activate.ps1

pip install -r requirements.txt
uvicorn main:app --reload

API: http://127.0.0.1:8000
Swagger: http://127.0.0.1:8000/docs
Health: http://127.0.0.1:8000/health

## Optional Gemini

Set GEMINI_API_KEY and optionally GEMINI_MODEL=gemini-2.5-flash. Without the key, the deterministic predictive engine remains operational.

## Dashboard

streamlit run dashboard.py

Simulation scenarios include Vasodilation, Hypovolemia, Normotension, and combined hypoxia/hemodynamic stress.

## Scope

This is a research/prototype clinical decision-support system. The predictive score and suggested actions are not clinically validated treatment recommendations. No drug dose is autonomously prescribed. Qualified clinicians, formal validation datasets, prospective testing, and appropriate clinical/regulatory governance are required before real patient use.
