from schema import (
    PatientBaseline,
    TelemetryFrame,
    bis_penalty,
    calculate_haii,
    map_from_bp,
    map_penalty,
    map_deviation_percent,
    pulse_pressure,
    shock_index,
)


def test_clinical_formulas():
    assert map_from_bp(120, 80) == 93.33333333333333
    assert pulse_pressure(120, 80) == 40
    assert round(shock_index(90, 120), 2) == 0.75
    assert round(map_deviation_percent(70, PatientBaseline().baseline_map), 1) == -25.0


def test_penalty_functions():
    assert map_penalty(49) == 1.0
    assert map_penalty(70) == 0.0
    assert bis_penalty(50) == 0.0
    assert bis_penalty(70) == 0.8


def test_haii_renormalizes_when_optional_signals_are_missing():
    score, coverage = calculate_haii(
        map_value=60,
        hr=120,
        spo2=None,
        etco2=None,
        bis=None,
    )
    assert score is not None
    assert 0 < score <= 1
    assert coverage == 0.45


def test_telemetry_derives_bp_metrics():
    frame = TelemetryFrame(minute=0, MAP=93.3, HR=90, SBP=120, DBP=80, BIS=50)
    assert frame.calculated_map == 93.3
    assert frame.pulse_pressure == 40
    assert frame.shock_index == 0.75
