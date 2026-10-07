from fastapi.testclient import TestClient
from main import app

client=TestClient(app)

def telemetry(maps,svv=8,hr=70,etco2=35,spo2=98):
    return {"patient_id":"TEST-001","telemetry":[{"minute":-5+i,"MAP":m,"HR":hr,"SVV":svv,"EtCO2":etco2,"SpO2":spo2} for i,m in enumerate(maps)]}

def test_health():
    r=client.get("/health")
    assert r.status_code==200
    assert r.json()["streaming"] is True

def test_early_warning_response():
    r=client.post("/api/v1/predict",json=telemetry([82,78,73,68,63,59]))
    assert r.status_code==200
    b=r.json()
    assert b["clinical_assessment"]["prediction_window_mins"]==15
    assert 0<=b["clinical_assessment"]["hemodynamic_risk_score"]<=100
    assert len(b["pipeline"])==3
    assert b["features"]["map_slope_per_min"]<0
    assert b["alert_triggered"] is True

def test_mechanisms():
    assert client.post("/api/v1/predict",json=telemetry([82,79,74,68,63,59],svv=18,hr=105)).json()["clinical_assessment"]["suspected_mechanism"]=="Hypovolemia"
    assert client.post("/api/v1/predict",json=telemetry([78,74,70,66,64,61],svv=8,hr=60)).json()["clinical_assessment"]["suspected_mechanism"]=="Vasodilation"

def test_waveforms():
    p=telemetry([85,84,83,82,81,80])
    for f in p["telemetry"]:
        f["arterial_waveform"]=[80,82,79,81]
        f["ecg_waveform"]=[.1,.2,0,.3]
    r=client.post("/api/v1/predict",json=p)
    assert r.status_code==200
    assert r.json()["features"]["arterial_waveform_range"] is not None
    assert r.json()["features"]["ecg_waveform_std"] is not None

def test_artifact_rejection():
    p=telemetry([80,78,76,74,72,70]); p["telemetry"][2]["MAP"]=500
    r=client.post("/api/v1/predict",json=p)
    assert r.status_code==200
    assert r.json()["features"]["signal_quality"]["rejected_frames"]==1

def test_simulator():
    r=client.post("/api/v1/simulate",json={"patient_id":"SIM-1","scenario":"Hypovolemia","frames":31,"interval_seconds":30})
    assert r.status_code==200
    assert len(r.json()["telemetry"])==31

def test_invalid_order():
    p=telemetry([80,78,76,74,72,70])
    p["telemetry"][3]["minute"]=-10
    assert client.post("/api/v1/predict",json=p).status_code==422

def test_empty_telemetry():
    assert client.post("/api/v1/predict",json={"patient_id":"TEST","telemetry":[]}).status_code==422

def test_websocket():
    with client.websocket_connect("/ws/telemetry") as ws:
        ws.send_json(telemetry([82,78,73,68,63,59]))
        result=ws.receive_json()
        assert result["clinical_assessment"]["prediction_window_mins"]==15
