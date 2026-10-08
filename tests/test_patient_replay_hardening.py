from patient_replay import parse_csv_bytes, parse_csv_text


def test_utf16_semicolon_and_aliases():
    text = """Time;MAP mmHg;HR bpm;SVV %;EtCO2;SpO2 %;CVP
10:00:00;82;76;9;36;99;7
10:00:30;79;78;10;35;99;7
10:01:00;75;81;12;34;98;6
"""
    telemetry, report = parse_csv_bytes(text.encode("utf-16"), patient_id="CSV-1")
    assert len(telemetry.telemetry) == 3
    assert report.rows_used == 3
    assert report.rows_skipped == 0
    assert report.sampling_interval_seconds == 30
    assert telemetry.telemetry[-1].minute == 1.0


def test_missing_required_signal_has_actionable_error():
    text = "timestamp,MAP,SVV\n2026-10-08T10:00:00,82,9\n2026-10-08T10:00:30,79,10\n"
    try:
        parse_csv_text(text)
    except ValueError as exc:
        assert "HR" in str(exc)
    else:
        raise AssertionError("Expected missing HR validation error")


def test_bad_rows_are_skipped_without_breaking_import():
    text = """minute,MAP,HR,SVV
0,82,76,9
0.5,not-a-number,78,10
1,75,81,12
"""
    telemetry, report = parse_csv_text(text)
    assert len(telemetry.telemetry) == 2
    assert report.rows_read == 3
    assert report.rows_skipped == 1


def test_explicit_minute_wins_over_ambiguous_timestamp():
    text = """timestamp,minute,MAP,HR
10:00:00,0,82,76
10:00:30,0.5,80,77
10:01:00,1,78,79
"""
    telemetry, report = parse_csv_text(text)
    assert [f.minute for f in telemetry.telemetry] == [0.0, 0.5, 1.0]
    assert report.sampling_interval_seconds == 30


def test_oversized_csv_is_safely_reduced():
    rows = ["minute,MAP,HR"] + [f"{i * 0.5},{82 - i * 0.01},70" for i in range(1500)]
    telemetry, report = parse_csv_text("\n".join(rows))
    assert len(telemetry.telemetry) == 1200
    assert report.rows_skipped == 300


def test_empty_csv_is_actionable():
    try:
        parse_csv_bytes(b"")
    except ValueError as exc:
        assert "empty" in str(exc).lower()
    else:
        raise AssertionError("Expected empty CSV error")
