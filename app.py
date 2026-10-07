import os
import json
import time
from pydantic import BaseModel, Field
from google import genai
from google.genai import types
from google.genai import errors

# 1. Retrieve API key and initialize Google GenAI client
api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    raise ValueError("GEMINI_API_KEY environment variable is not set!")

client = genai.Client(api_key=api_key)

# Define Pydantic Schema for strict output formatting
class PredictionOutput(BaseModel):
    predicted_map_15min: float = Field(description="Predicted MAP in mmHg after 15 minutes")
    hypotension_risk_level: str = Field(description="Risk level: CRITICAL, HIGH, MEDIUM, or LOW")
    confidence_score: float = Field(description="Confidence score between 0.0 and 1.0")
    suspected_mechanism: str = Field(description="Mechanism: Hypovolemia, Vasodilation, or Normal")
    suggested_action: str = Field(description="Recommended clinical intervention")

SYSTEM_INSTRUCTION = """You are an expert Anesthesiology Clinical Decision Support AI.
Evaluate the provided 5-minute rolling window of vital telemetry.
RULES:
1. Define Intraoperative Hypotension (IOH) risk if MAP trend projects < 65 mmHg within 15 minutes.
2. Differentiate mechanisms: High SVV (>13%) = Hypovolemia; Low/Normal SVV + Normal/Low HR = Vasodilation.
3. hypotension_risk_level MUST be 'CRITICAL' or 'HIGH' if projected MAP is below 65 mmHg."""

# --- AGENT 1: Data Ingestion & Signal Filter ---
def agent_1_clean_data(raw_data_stream):
    cleaned_stream = []
    for frame in raw_data_stream:
        if 20 <= frame["MAP"] <= 220:
            cleaned_stream.append(frame)
    return cleaned_stream

# --- AGENT 2: Gemini Predictive Inference ---
def agent_2_predict_risk(clean_stream):
    prompt = f"Analyze this 5-minute rolling window: {json.dumps(clean_stream)}"
    
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_INSTRUCTION,
        temperature=0.0,
        response_mime_type="application/json",
        response_schema=PredictionOutput, # Enforces strict schema matching
    )

    model_name = "gemini-3.8-flash"
    max_retries = 5
    backoff = 2
    
    for attempt in range(1, max_retries + 1):
        try:
            print(f"[Agent 2]: Querying {model_name} (Attempt {attempt}/{max_retries})...")
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=config,
            )
            return json.loads(response.text)
        except (errors.ServerError, errors.ClientError) as err:
            err_msg = str(err)
            if "503" in err_msg or "UNAVAILABLE" in err_msg or "429" in err_msg:
                print(f"[Agent 2 Warning]: Server busy/rate-limited. Retrying in {backoff} seconds...")
                time.sleep(backoff)
                backoff *= 2
            else:
                raise err
                
    raise RuntimeError(f"Failed to get response from {model_name} after {max_retries} attempts.")

# --- AGENT 3: Clinical Safety Guardrail ---
def agent_3_safety_check(ai_prediction):
    confidence = ai_prediction.get("confidence_score", 0.0)
    
    if confidence < 0.85:
        ai_prediction["suppress_alarm"] = True
        ai_prediction["guardrail_note"] = "Suppressed due to low statistical confidence."
    else:
        ai_prediction["suppress_alarm"] = False
        
    return ai_prediction

# --- MAIN LOOP ---
def run_anesthesense_loop(simulated_telemetry):
    print("⚡ Starting AnestheSense Anti-Gravity Loop on D: Drive...\n")
    
    clean_data = agent_1_clean_data(simulated_telemetry)
    print(f"[Agent 1]: Filtered {len(simulated_telemetry)} raw frames down to {len(clean_data)} valid frames.")
    
    raw_prediction = agent_2_predict_risk(clean_data)
    print(f"[Agent 2]: Model predicted 15-min MAP of {raw_prediction.get('predicted_map_15min')} mmHg.")
    
    final_alert = agent_3_safety_check(raw_prediction)
    
    risk_level = str(final_alert.get("hypotension_risk_level", "")).upper()
    
    if not final_alert.get("suppress_alarm") and risk_level in ["HIGH", "CRITICAL"]:
        print(f"\n🚨 [DOCTOR DASHBOARD ALERT]: {risk_level} RISK DETECTED!")
        print(f"    Cause: {final_alert.get('suspected_mechanism')}")
        print(f"    Action: {final_alert.get('suggested_action')}")
    else:
        print("\n✅ [DOCTOR DASHBOARD]: Patient Stable / No Alert Needed.")

# --- TEST RUN ---
test_patient_vitals = [
    {"minute": -5, "MAP": 76, "HR": 72, "SVV": 8, "EtCO2": 35},
    {"minute": -4, "MAP": 73, "HR": 70, "SVV": 8, "EtCO2": 35},
    {"minute": -3, "MAP": 70, "HR": 68, "SVV": 9, "EtCO2": 34},
    {"minute": -2, "MAP": 67, "HR": 65, "SVV": 9, "EtCO2": 34},
    {"minute": -1, "MAP": 65, "HR": 63, "SVV": 9, "EtCO2": 34},
    {"minute": 0,  "MAP": 63, "HR": 62, "SVV": 8, "EtCO2": 33}
]

if __name__ == "__main__":
    run_anesthesense_loop(test_patient_vitals)