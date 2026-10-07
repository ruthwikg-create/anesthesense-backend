from __future__ import annotations
import json, os
from statistics import mean
from google import genai
from google.genai import types
from schema import ClinicalAssessment, PatientTelemetry

MAP_HYPOTENSION_THRESHOLD=65.0
MAP_CRITICAL_THRESHOLD=60.0
HIGH_SVV_THRESHOLD=13.0

def _trend_slope(values:list[float])->float:
    n=len(values)
    if n<2:return 0.0
    xm=(n-1)/2; ym=mean(values)
    den=sum((i-xm)**2 for i in range(n))
    return sum((i-xm)*(y-ym) for i,y in enumerate(values))/den

def _deterministic_assessment(telemetry:PatientTelemetry)->ClinicalAssessment:
    frames=telemetry.telemetry; maps=[f.MAP for f in frames]; latest=frames[-1]
    slope=_trend_slope(maps); predicted=round(max(35.0,latest.MAP+slope*15.0),1)
    if predicted<MAP_CRITICAL_THRESHOLD:risk="CRITICAL"
    elif predicted<MAP_HYPOTENSION_THRESHOLD:risk="HIGH"
    elif predicted<70:risk="MODERATE"
    else:risk="LOW"
    if latest.SVV>HIGH_SVV_THRESHOLD and latest.MAP<70:
        mechanism="Hypovolemia"; action="Assess volume status and blood loss; consider clinician-directed fluid/blood management and reassess MAP/SVV."
    elif latest.SVV<=HIGH_SVV_THRESHOLD and latest.MAP<70:
        mechanism="Vasodilation"; action="Assess anesthetic depth and vasodilatory causes; consider clinician-directed vasopressor management and reassess MAP."
    elif latest.MAP<70:
        mechanism="Mixed"; action="Reassess hemodynamics, anesthetic depth, volume status, and ongoing blood loss."
    else:
        mechanism="Normal"; action="Continue routine intraoperative monitoring."
    confidence=min(0.75+(0.08 if len(frames)>=5 else 0)+(0.05 if abs(slope)>=0.5 else 0)+(0.04 if latest.MAP<65 else 0),0.92)
    return ClinicalAssessment(predicted_map_15min=predicted,hypotension_risk_level=risk,confidence_score=confidence,suspected_mechanism=mechanism,suggested_action=action,data_quality="GOOD" if len(frames)>=5 else "LIMITED")

def _gemini_assessment(telemetry:PatientTelemetry,baseline:ClinicalAssessment)->ClinicalAssessment:
    if not os.getenv("GEMINI_API_KEY"): return baseline
    try:
        client=genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        response=client.models.generate_content(
            model=os.getenv("GEMINI_MODEL","gemini-2.5-flash"),
            contents=json.dumps({"patient_id":telemetry.patient_id,"telemetry":[f.model_dump() for f in telemetry.telemetry],"deterministic_baseline":baseline.model_dump()}),
            config=types.GenerateContentConfig(system_instruction="You are an assistive intraoperative clinical decision-support component. Use only supplied telemetry. Return structured JSON. Recommendations are advisory. Never weaken a CRITICAL or HIGH deterministic alarm.",temperature=0.0,response_mime_type="application/json",response_schema=ClinicalAssessment))
        result=ClinicalAssessment.model_validate_json(response.text)
        rank={"LOW":0,"MODERATE":1,"HIGH":2,"CRITICAL":3}
        if rank[result.hypotension_risk_level]<rank[baseline.hypotension_risk_level]: result.hypotension_risk_level=baseline.hypotension_risk_level
        if baseline.hypotension_risk_level in {"HIGH","CRITICAL"}: result.suppress_alarm=False
        result.confidence_score=min(result.confidence_score,0.95)
        return result
    except Exception as exc:
        baseline.guardrail_note=f"Gemini unavailable; deterministic assessment retained: {type(exc).__name__}"
        return baseline

def evaluate_patient_risk(telemetry_data:PatientTelemetry)->ClinicalAssessment:
    return _gemini_assessment(telemetry_data,_deterministic_assessment(telemetry_data))
