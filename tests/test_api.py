from fastapi.testclient import TestClient

from main import app


client = TestClient(app)


def telemetry(maps, svv=8, hr=70, etco2=35, spo2=98):
    return {
        "patient_id": "TEST-001",
        "telemetry": [
            {
                "minute": -5 + i,
                "MAP": m,
                "HR": hr,
                "SVV": svv,
                "EtCO2": etco2,
                "SpO2": spo2,
            }
            for i, m in enumerate(maps)
        ],
    }


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["streaming"] is True
    assert r.json()["forecasting"] is True


def test_early_warning_response():
    r = client.post("/api/v1/predict", json=telemetry([82, 78, 73, 68, 63, 59]))
    assert r.status_code == 200
    body = r.json()
    assessment = body["clinical_assessment"]
    features = body["features"]

    assert assessment["prediction_window_mins"] == 15
    assert 0 <= assessment["hemodynamic_risk_score"] <= 100
    assert len(body["pipeline"]) == 3
    assert features["map_slope_per_min"] < 0
    assert features["predicted_map_15min"] < features["map_current"]
    assert 0 <= features["hypotension_probability"] <= 1
    assert body["alert_triggered"] is True
    assert body["event_log"]


def test_mechanisms():
    hypovolemia = client.post(
        "/api/v1/predict",
        json=telemetry([82, 79, 74, 68, 63, 59], svv=18, hr=105),
    ).json()
    vasodilation = client.post(
        "/api/v1/predict",
        json=telemetry([78, 74, 70, 66, 64, 61], svv=8, hr=60),
    ).json()

    assert hypovolemia["clinical_assessment"]["suspected_mechanism"] == "Hypovolemia"
    assert vasodilation["clinical_assessment"]["suspected_mechanism"] == "Vasodilation"


def test_mixed_mechanism():
    body = client.post(
        "/api/v1/predict",
        json=telemetry([78, 74, 70, 66, 63, 60], svv=20, etco2=27),
    ).json()
    assert body["clinical_assessment"]["suspected_mechanism"] == "Mixed"
    assert body["clinical_assessment"]["secondary_risk"] == "Low EtCO2 signal"


def test_waveforms():
    p = telemetry([85, 84, 83, 82, 81, 80])
    for frame in p["telemetry"]:
        frame["arterial_waveform"] = [80, 82, 79, 81]
        frame["ecg_waveform"] = [0.1, 0.2, 0, 0.3]

    r = client.post("/api/v1/predict", json=p)
    assert r.status_code == 200
    assert r.json()["features"]["arterial_waveform_range"] is not None
    assert r.json()["features"]["ecg_waveform_std"] is not None


def test_artifact_rejection():
    p = telemetry([80, 78, 76, 74, 72, 70])
    p["telemetry"][2]["MAP"] = 500

    r = client.post("/api/v1/predict", json=p)
    assert r.status_code == 200
    assert r.json()["features"]["signal_quality"]["rejected_frames"] == 1


def test_poor_quality_when_majority_is_artifact():
    p = telemetry([80, 78, 76, 74, 72, 70])
    for index in [0, 1, 2, 3]:
        p["telemetry"][index]["MAP"] = 500

    r = client.post("/api/v1/predict", json=p)
    assert r.status_code == 200
    quality = r.json()["features"]["signal_quality"]
    assert quality["quality"] == "POOR"
    assert quality["rejected_frames"] == 4


def test_simulator_scenarios():
    for scenario in [
        "Vasodilation",
        "Hypovolemia",
        "Hemorrhage",
        "MixedShock",
        "HypoxiaStress",
        "Normotensive",
    ]:
        r = client.post(
            "/api/v1/simulate",
            json={
                "patient_id": "SIM-1",
                "scenario": scenario,
                "frames": 31,
                "interval_seconds": 30,
            },
        )
        assert r.status_code == 200
        assert len(r.json()["telemetry"]) == 31


def test_simulate_and_analyze():
    r = client.post(
        "/api/v1/simulate/analyze",
        json={
            "patient_id": "SIM-HYPO",
            "scenario": "Hypovolemia",
            "frames": 31,
            "interval_seconds": 30,
        },
    )
    assert r.status_code == 200
    assert r.json()["patient_id"] == "SIM-HYPO"
    assert r.json()["features"]["predicted_map_15min"] < 65


def test_invalid_order():
    p = telemetry([80, 78, 76, 74, 72, 70])
    p["telemetry"][3]["minute"] = -10
    assert client.post("/api/v1/predict", json=p).status_code == 422


def test_empty_telemetry():
    assert (
        client.post(
            "/api/v1/predict",
            json={"patient_id": "TEST", "telemetry": []},
        ).status_code
        == 422
    )


def test_websocket():
    with client.websocket_connect("/ws/telemetry") as ws:
        ws.send_json(telemetry([82, 78, 73, 68, 63, 59]))
        result = ws.receive_json()
        assert result["clinical_assessment"]["prediction_window_mins"] == 15
        assert "event_log" in result


def test_safety_never_downgrades_baseline():
    # The endpoint remains deterministic when Gemini is absent.
    body = client.post(
        "/api/v1/predict",
        json=telemetry([82, 78, 73, 68, 63, 59]),
    ).json()
    assert body["clinical_assessment"]["hypotension_risk_level"] in {"HIGH", "CRITICAL"}
    assert body["clinical_assessment"]["suppress_alarm"] is False
