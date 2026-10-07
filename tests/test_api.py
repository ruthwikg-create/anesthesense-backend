from fastapi.testclient import TestClient
from main import app

client=TestClient(app)

def telemetry(maps, svv=8, hr=70, etco2=35, spo2=98):
    return {"patient_id":"TEST-001","telemetry":[{"minute":-5+i,"MAP":m,"HR":hr,"SVV":svv,"EtCO2":etco2,"SpO2":spo2} for i,m in enumerate(maps)]}

def test_health():
    r=client.get("/health")
    assert r.status_code==200 and r.json()["status"]=="ok"

def test_early_warning_response():
    r=client.post("/api/v1/predict",json=telemetry([82,78,73,68,63,59]))
    assert r.status_code==200
    body=r.json()
    assert body["clinical_assessment"]["prediction_window_mins"]==15
    assert 0 <= body["clinical_assessment"]["hemodynamic_risk_score"] <= 100
    assert len(body["pipeline"])==3
    assert body["features"]["map_slope_per_min"] < 0
    assert body["alert_triggered"] is True

def test_mechanism_hypovolemia():
    r=client.post("/api/v1/predict",json=telemetry([82,79,74,68,63,59],svv=18,hr=105))
    assert r.status_code==200
    assert r.json()["clinical_assessment"]["suspected_mechanism"]=="Hypovolemia"

def test_mechanism_vasodilation():
    r=client.post("/api/v1/predict",json=telemetry([78,74,70,66,64,61],svv=8,hr=60))
    assert r.status_code==200
    assert r.json()["clinical_assessment"]["suspected_mechanism"]=="Vasodilation"

def test_optional_spo2_and_waveforms():
    payload=telemetry([85,84,83,82,81,80])
    for frame in payload["telemetry"]:
        frame["arterial_waveform"]=[80,82,79,81]
        frame["ecg_waveform"]=[0.1,0.2,0.0,0.3]
    r=client.post("/api/v1/predict",json=payload)
    assert r.status_code==200
    assert "waveform" in " ".join(r.json()["features"]["signal_quality"]["notes"]).lower()

def test_bad_frames_are_filtered():
    payload=telemetry([80,78,76,74,72,70])
    payload["telemetry"][2]["MAP"]=500
    r=client.post("/api/v1/predict",json=payload)
    assert r.status_code==200
    q=r.json()["features"]["signal_quality"]
    assert q["rejected_frames"]==1

def test_empty_telemetry_rejected():
    r=client.post("/api/v1/predict",json={"patient_id":"TEST","telemetry":[]})
    assert r.status_code==422
