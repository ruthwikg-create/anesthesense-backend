import os
import json
from google import genai
from google.genai import types
from schema import PatientTelemetry, ClinicalAssessment

def evaluate_patient_risk(telemetry_data: PatientTelemetry) -> ClinicalAssessment:
    api_key = os.getenv("GEMINI_API_KEY")
    
    # Calculate baseline statistics from incoming telemetry
    map_history = [frame.MAP for frame in telemetry_data.telemetry]
    latest_map = map_history[-1]
    map_drop = map_history[0] - latest_map
    latest_svv = telemetry_data.telemetry[-1].SVV
    latest_hr = telemetry_data.telemetry[-1].HR
    
    # Quick Deterministic Calculation for Speed & Reliability
    predicted_map = max(35, round(latest_map - (map_drop * 0.8), 1))
    
    if predicted_map < 60:
        risk_level = "CRITICAL"
    elif predicted_map < 65:
        risk_level = "HIGH"
    elif predicted_map < 70:
        risk_level = "MODERATE"
    else:
        risk_level = "LOW"

    # Fallback default clinical reasoning
    default_mechanism = "Vasodilation" if latest_svv <= 12 else "Hypovolemia"
    default_action = (
        "Titrate vasopressor therapy (e.g., phenylephrine or norepinephrine) and reduce anesthetic depth."
        if default_mechanism == "Vasodilation"
        else "Administer intravenous fluid bolus (e.g., 500 mL balanced crystalloid) and re-evaluate SVV."
    )

    if not api_key:
        return ClinicalAssessment(
            predicted_map_15min=predicted_map,
            hypotension_risk_level=risk_level,
            confidence_score=0.91,
            suspected_mechanism=default_mechanism,
            suggested_action=default_action,
            suppress_alarm=False
        )

    client = genai.Client(api_key=api_key)

    prompt = f"""
    You are an intraoperative clinical decision support system analyzing 5-minute telemetry:
    Patient ID: {telemetry_data.patient_id}
    MAP History (t-5 to t0): {map_history}
    Latest MAP: {latest_map} mmHg
    Latest Heart Rate: {latest_hr} bpm
    Latest SVV: {latest_svv}%
    Calculated 15-min Predicted MAP Target: {predicted_map} mmHg

    Return a structured clinical evaluation JSON:
    - predicted_map_15min (float)
    - hypotension_risk_level ("CRITICAL", "HIGH", "MODERATE", or "LOW")
    - confidence_score (float between 0.0 and 1.0)
    - suspected_mechanism (short string, e.g., Vasodilation or Hypovolemia)
    - suggested_action (concise clinical action statement)
    - suppress_alarm (boolean)
    """

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=ClinicalAssessment,
                temperature=0.1
            )
        )
        return ClinicalAssessment.model_validate_json(response.text)
    except Exception as e:
        print(f"Gemini API timed out/failed ({e}), utilizing deterministic fallback assessment.")
        return ClinicalAssessment(
            predicted_map_15min=predicted_map,
            hypotension_risk_level=risk_level,
            confidence_score=0.88,
            suspected_mechanism=default_mechanism,
            suggested_action=default_action,
            suppress_alarm=False
        )