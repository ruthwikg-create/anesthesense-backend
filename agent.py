from __future__ import annotations
import json, os
from statistics import mean, pstdev
from schema import ClinicalAssessment, FeatureSummary, PatientTelemetry, SignalQualityReport

MAP_HYPOTENSION=65.0
MAP_CRITICAL=60.0
HIGH_SVV=13.0

def _slope(values, minutes):
    if len(values)<2: return 0.0
    xm,ym=mean(minutes),mean(values)
    den=sum((x-xm)**2 for x in minutes)
    return sum((x-xm)*(y-ym) for x,y in zip(minutes,values))/den if den else 0.0

def preprocess(telemetry):
    valid=[]; rejected=0
    for frame in telemetry.telemetry:
        if 20<=frame.MAP<=220 and 20<=frame.HR<=250 and 0<=frame.SVV<=100 and 0<=frame.EtCO2<=100:
            valid.append(frame)
        else: rejected+=1
    rate=rejected/len(telemetry.telemetry)
    quality="GOOD" if rate<=.05 else "FAIR" if rate<=.20 else "POOR"
    notes=[]
    if rejected: notes.append("Out-of-range frames removed before inference.")
    if any(f.arterial_waveform for f in valid): notes.append("Arterial waveform samples received; prototype range feature extracted.")
    if any(f.ecg_waveform for f in valid): notes.append("ECG waveform samples received; prototype variability feature extracted.")
    return PatientTelemetry(patient_id=telemetry.patient_id,sampling_interval_seconds=telemetry.sampling_interval_seconds,telemetry=valid),SignalQualityReport(quality=quality,valid_frames=len(valid),rejected_frames=rejected,artifact_rate=rate,notes=notes)

def extract_features(data,quality):
    frames=data.telemetry; minutes=[f.minute for f in frames]; maps=[f.MAP for f in frames]; hrs=[f.HR for f in frames]; last=frames[-1]
    arterial=[x for f in frames if f.arterial_waveform for x in f.arterial_waveform]
    ecg=[x for f in frames if f.ecg_waveform for x in f.ecg_waveform]
    return FeatureSummary(
        map_current=last.MAP,map_slope_per_min=round(_slope(maps,minutes),3),map_drop=round(maps[0]-last.MAP,2),
        hr_current=last.HR,hr_slope_per_min=round(_slope(hrs,minutes),3),svv_current=last.SVV,etco2_current=last.EtCO2,
        spo2_current=last.SpO2,cvp_current=last.CVP,arterial_waveform_range=round(max(arterial)-min(arterial),3) if arterial else None,
        ecg_waveform_std=round(pstdev(ecg),3) if len(ecg)>1 else None,map_below_65_fraction=round(sum(x<65 for x in maps)/len(maps),3),signal_quality=quality)

def _predict(f):
    predicted=max(35.0,round(f.map_current+f.map_slope_per_min*15,1))
    score=min(100,45*max(0,-f.map_slope_per_min)+max(0,65-f.map_current)*2.5+f.map_below_65_fraction*20)
    secondary=None
    if f.spo2_current is not None and f.spo2_current<92: secondary="Hypoxemia signal"
    elif f.etco2_current<30: secondary="Low EtCO2 signal"
    if predicted<60:risk="CRITICAL"
    elif predicted<65:risk="HIGH"
    elif score>=40:risk="MODERATE"
    else:risk="LOW"
    if f.map_current<70 and f.svv_current>13 and f.etco2_current<30: mechanism="Mixed"; action="Assess volume status, blood loss, anesthetic depth, and low-flow contributors; clinician-directed management and reassessment are required."\n    elif f.map_current<70 and f.svv_current>13: mechanism="Hypovolemia"; action="Assess volume status and surgical blood loss; consider clinician-directed fluid/blood management and reassess MAP/SVV."
    elif f.map_current<70: mechanism="Vasodilation"; action="Assess anesthetic depth and vasodilatory causes; consider clinician-directed vasopressor support and reassess MAP."
    else: mechanism="Normal"; action="Continue routine monitoring; reassess if trajectory worsens."
    confidence=min(.94,.70+(.08 if f.signal_quality.quality=="GOOD" else 0)+(.08 if len([f.map_current]) else 0))
    return ClinicalAssessment(hemodynamic_risk_score=round(score,1),prediction_window_mins=15,predicted_map_15min=predicted,hypotension_risk_level=risk,secondary_risk=secondary,confidence_score=confidence,suspected_mechanism=mechanism,suggested_action=action,suppress_alarm=False,data_quality=f.signal_quality.quality)

def _gemini(f,baseline):
    key=os.getenv("GEMINI_API_KEY")
    if not key:return baseline
    try:
        from google import genai
        from google.genai import types
        response=genai.Client(api_key=key).models.generate_content(
            model=os.getenv("GEMINI_MODEL","gemini-2.5-flash"),
            contents=json.dumps({"features":f.model_dump(),"baseline":baseline.model_dump()}),
            config=types.GenerateContentConfig(system_instruction="You are an assistive intraoperative CDS reasoning layer. Use only supplied features. Return structured JSON. Never downgrade deterministic HIGH/CRITICAL risk and never prescribe a drug dose. Guidance requires clinician judgment.",temperature=0,response_mime_type="application/json",response_schema=ClinicalAssessment))
        result=ClinicalAssessment.model_validate_json(response.text)
        rank={"LOW":0,"MODERATE":1,"HIGH":2,"CRITICAL":3}
        if rank[result.hypotension_risk_level]<rank[baseline.hypotension_risk_level]: result.hypotension_risk_level=baseline.hypotension_risk_level
        result.hemodynamic_risk_score=max(result.hemodynamic_risk_score,baseline.hemodynamic_risk_score)
        if baseline.hypotension_risk_level in {"HIGH","CRITICAL"}: result.suppress_alarm=False
        return result
    except Exception as exc:
        baseline.guardrail_note=f"Gemini unavailable; deterministic safety engine retained ({type(exc).__name__})."
        return baseline

def evaluate_patient_risk(telemetry):
    clean,q=preprocess(telemetry)
    if not clean.telemetry: raise ValueError("No valid telemetry frames remain after preprocessing.")
    features=extract_features(clean,q)
    return _gemini(features,_predict(features)),features,["Signal Preprocessor Agent","Predictive Analytics Agent","Clinical Advisory Agent"]
