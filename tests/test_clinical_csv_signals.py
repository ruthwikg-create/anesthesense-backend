from patient_replay import parse_csv_text


def test_sbp_dbp_can_derive_map_and_clinical_signals():
    text = """minute,SBP,DBP,HR,BIS,TOF_twitches,TOF_ratio,SpO2,EtCO2
0,120,80,90,50,2,0.1,99,36
0.5,115,75,92,52,2,0.2,99,35
1,110,70,95,55,2,0.3,98,34
"""
    telemetry, report = parse_csv_text(text)
    last = telemetry.telemetry[-1]
    assert round(last.MAP, 1) == 83.3
    assert last.SBP == 110
    assert last.DBP == 70
    assert last.BIS == 55
    assert last.TOF_twitches == 2
    assert last.TOF_ratio == 0.3
    assert report.rows_used == 3
