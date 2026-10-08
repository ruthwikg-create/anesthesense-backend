from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def _payload(maps):
    return {
        "patient_id": "ROBUST-1",
        "sampling_interval_seconds": 30,
        "telemetry": [
            {
                "minute": i * 0.5,
                "MAP": value,
                "HR": 75,
                "SVV": 10,
                "EtCO2": 35,
                "SpO2": 98,
            }
            for i, value in enumerate(maps)
        ],
    }


def test_all_invalid_frames_return_422_not_500():
    response = client.post("/api/v1/predict", json=_payload([500, 500, 500]))
    assert response.status_code == 422
    assert "valid telemetry frames" in response.json()["detail"]


def test_partial_artifacts_still_produce_output():
    payload = _payload([84, 82, 80, 78, 76, 74])
    payload["telemetry"][2]["MAP"] = 500
    response = client.post("/api/v1/predict", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["frames_processed"] == 6
    assert body["features"]["signal_quality"]["rejected_frames"] == 1


def test_health_advertises_replay_and_guardrails():
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["csv_replay"] is True
    assert body["safety_guardrails"] is True
