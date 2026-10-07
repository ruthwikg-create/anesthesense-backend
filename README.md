# AnestheSense Backend

FastAPI clinical decision-support prototype for intraoperative hemodynamic risk prediction.

## Architecture

Telemetry → Pydantic validation → deterministic MAP projection/risk engine → optional Gemini structured assessment → safety invariants → API response.

Gemini is optional. Without `GEMINI_API_KEY`, the deterministic assessment is used.

## Run

```bash
python -m venv venv
# Windows: venv\Scripts\activate
# macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

API: `http://127.0.0.1:8000`
Swagger: `http://127.0.0.1:8000/docs`
Health: `http://127.0.0.1:8000/health`

Optional Gemini configuration:

```bash
# Windows PowerShell
$env:GEMINI_API_KEY="YOUR_KEY"
$env:GEMINI_MODEL="gemini-2.5-flash"
```

## Dashboard

```bash
streamlit run dashboard.py
```

## Tests

```bash
pytest -q
```

## Safety note

This is a research/prototype clinical decision-support system. It is not a clinically validated autonomous alarm or treatment recommendation system. Outputs require qualified clinician review and appropriate validation before any real clinical use.
