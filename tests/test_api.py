from fastapi.testclient import TestClient
from main import app

client=TestClient(app)

def test_health():
    response=client.get("/health")
    assert response.status_code==200
    assert response.json()["status"]=="ok"

def test_prediction_contract_and_alert():
    payload={"patient_id":"TEST-001","telemetry":[
        {"minute":-5,"MAP":82,"HR":72,"SVV":8,"EtCO2":35},
        {"minute":-4,"MAP":78,"HR":70,"SVV":8,"EtCO2":35},
        {"minute":-3,"MAP":73,"HR":68,"SVV":9,"EtCO2":34},
        {"minute":-2,"MAP":68,"HR":65,"SVV":9,"EtCO2":34},
        {"minute":-1,"MAP":63,"HR":63,"SVV":9,"EtCO2":34},
        {"minute":0,"MAP":59,"HR":62,"SVV":8,"EtCO2":33}]}
    response=client.post("/api/v1/predict",json=payload)
    assert response.status_code==200
    body=response.json()
    assert body["frames_processed"]==6
    assert body["clinical_assessment"]["hypotension_risk_level"] in {"HIGH","CRITICAL"}
    assert body["alert_triggered"] is True

def test_invalid_telemetry_is_rejected():
    response=client.post("/api/v1/predict",json={"patient_id":"TEST","telemetry":[]})
    assert response.status_code==422
