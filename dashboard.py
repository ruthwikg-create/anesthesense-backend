import io
import json
import time

import plotly.graph_objects as go
import requests
import streamlit as st

from patient_replay import parse_csv_bytes


st.set_page_config(
    page_title="AnestheSense | Clinician Monitor",
    page_icon="A",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    .block-container {padding-top: 1rem; max-width: 1500px;}
    div[data-testid="stMetric"] {padding: 0.35rem 0.5rem;}
    .clinician-title {font-size: 2rem; font-weight: 700; margin-bottom: 0;}
    .muted {color: #6b7280;}
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="clinician-title">AnestheSense</div>', unsafe_allow_html=True)
st.caption("Intraoperative hemodynamic early-warning CDS prototype")

with st.sidebar:
    st.subheader("Connection")
    API_URL = st.text_input("Backend URL", "http://127.0.0.1:8000")
    st.caption("For research/demo use. Do not connect to patient care without appropriate validation and oversight.")

    st.divider()
    st.subheader("Data source")
    source = st.radio(
        "Choose input",
        ["Patient data file", "Synthetic simulation", "Manual check"],
        label_visibility="collapsed",
    )


def post_predict(payload):
    response = requests.post(
        f"{API_URL.rstrip('/')}/api/v1/predict",
        json=payload,
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def status_banner(data):
    a = data["clinical_assessment"]
    f = data["features"]
    level = a["hypotension_risk_level"]

    if level == "CRITICAL":
        st.error(f"CRITICAL — predicted MAP {a['predicted_map_15min']:.1f} mmHg at +15 min")
    elif level == "HIGH":
        st.error(f"HIGH RISK — predicted MAP {a['predicted_map_15min']:.1f} mmHg at +15 min")
    elif level == "MODERATE":
        st.warning("WATCH — hemodynamic deterioration may be developing")
    else:
        st.success("STABLE — no HIGH/CRITICAL alert from the prototype engine")

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Risk", level)
    c2.metric("Risk score", f"{a['hemodynamic_risk_score']:.0f}/100")
    c3.metric("MAP now", f"{f['map_current']:.1f} mmHg")
    c4.metric("MAP +15 min", f"{a['predicted_map_15min']:.1f} mmHg")
    c5.metric("Confidence", f"{a['confidence_score']:.0%}")


def trajectory_chart(observed_frames, result):
    f = result["features"]
    observed_x = [frame["minute"] for frame in observed_frames]
    observed_y = [frame["MAP"] for frame in observed_frames]
    now = observed_x[-1]

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=observed_x,
            y=observed_y,
            mode="lines+markers",
            name="Observed MAP",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=[now, now + 10, now + 15],
            y=[f["map_current"], f["predicted_map_10min"], f["predicted_map_15min"]],
            mode="lines+markers",
            name="Forecast",
            line={"dash": "dash"},
        )
    )
    fig.add_hline(y=65, line_dash="dot", annotation_text="65 mmHg")
    fig.add_hline(y=60, line_dash="dot", annotation_text="60 mmHg")
    fig.update_layout(
        title="Hemodynamic trajectory",
        xaxis_title="Time (min)",
        yaxis_title="MAP (mmHg)",
        height=390,
        margin={"l": 20, "r": 20, "t": 55, "b": 20},
    )
    st.plotly_chart(fig, use_container_width=True)


def clinician_view(result, frames):
    status_banner(result)
    a = result["clinical_assessment"]
    f = result["features"]

    left, right = st.columns([1.7, 1])

    with left:
        trajectory_chart(frames, result)

    with right:
        st.subheader("Clinical context")
        st.metric("Likely pattern", a["suspected_mechanism"])
        st.metric("Trajectory", f["trajectory"])
        st.metric("Signal quality", a["data_quality"])
        st.metric("Signal completeness", f"{f['signal_quality']['signal_completeness']:.0%}")

        if a.get("secondary_risk"):
            st.info(a["secondary_risk"])

    st.subheader("What the system detected")
    for item in a["contributing_factors"]:
        st.write("•", item)

    st.subheader("Clinician-directed review")
    st.info(a["suggested_action"])

    if a.get("guardrail_note"):
        st.warning(a["guardrail_note"])

    st.caption(
        "This output is decision support only. Confirm the source signals and clinical context before acting."
    )


def research_view(result, frames, patient_id):
    a = result["clinical_assessment"]
    f = result["features"]

    with st.expander("Research / validation details"):
        st.write("### Prediction details")
        st.json(
            {
                "patient_id": patient_id,
                "frames_processed": len(frames),
                "current_map": f["map_current"],
                "predicted_map_10min": f["predicted_map_10min"],
                "predicted_map_15min": f["predicted_map_15min"],
                "prototype_hypotension_probability": f["hypotension_probability"],
                "map_slope_per_min": f["map_slope_per_min"],
                "trend_strength": f["trend_strength"],
                "signal_quality": f["signal_quality"],
            }
        )
        st.write("### Event timeline")
        for event in result.get("event_log", []):
            st.write("•", event)
        st.write("### Pipeline")
        for step in result["pipeline"]:
            st.write("✓", step)

        st.download_button(
            "Export audit JSON",
            json.dumps(result, indent=2),
            f"AnestheSense_{patient_id}_audit.json",
            "application/json",
        )


def actual_future_map(frames, now_minute, horizon):
    target = now_minute + horizon
    candidates = [frame for frame in frames if frame["minute"] >= target]
    if not candidates:
        return None
    return min(candidates, key=lambda frame: abs(frame["minute"] - target))["MAP"]


def evaluate_replay(frames, predictions):
    errors_10 = []
    errors_15 = []

    for item in predictions:
        now = item["now"]
        result = item["result"]
        actual10 = actual_future_map(frames, now, 10)
        actual15 = actual_future_map(frames, now, 15)

        if actual10 is not None:
            errors_10.append(abs(result["features"]["predicted_map_10min"] - actual10))
        if actual15 is not None:
            errors_15.append(abs(result["features"]["predicted_map_15min"] - actual15))

    mae10 = sum(errors_10) / len(errors_10) if errors_10 else None
    mae15 = sum(errors_15) / len(errors_15) if errors_15 else None
    return mae10, mae15


def run_replay(telemetry, patient_id, speed=10.0):
    chart = st.empty()
    status = st.empty()
    metrics = st.empty()
    final = None
    predictions = []

    for index in range(2, len(telemetry) + 1):
        prefix = telemetry[:index]
        payload = {
            "patient_id": patient_id,
            "sampling_interval_seconds": max(0.1, float(prefix[1]["minute"] - prefix[0]["minute"]) * 60),
            "telemetry": prefix,
        }

        try:
            result = post_predict(payload)
        except requests.RequestException as exc:
            st.error(f"Backend connection failed: {exc}")
            return None, predictions

        final = result
        predictions.append({"now": prefix[-1]["minute"], "result": result})

        with metrics.container():
            a = result["clinical_assessment"]
            f = result["features"]
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Risk", a["hypotension_risk_level"])
            c2.metric("MAP", f"{f['map_current']:.1f} mmHg")
            c3.metric("Forecast +15", f"{a['predicted_map_15min']:.1f} mmHg")
            c4.metric("Confidence", f"{a['confidence_score']:.0%}")

        with status.container():
            if result["alert_triggered"]:
                st.error(f"{a['alert_priority']} ALERT — review the patient's clinical state.")
            else:
                st.info(f"Monitoring — {f['trajectory']}")

        with chart.container():
            trajectory_chart(prefix, result)

        time.sleep(max(0.03, 0.8 / speed))

    return final, predictions


# ---------------------------------------------------------------------------
# Patient data mode
# ---------------------------------------------------------------------------
if source == "Patient data file":
    st.subheader("Patient data replay")
    st.write(
        "Upload a de-identified monitor export. AnestheSense replays it frame-by-frame "
        "through the same prediction engine used by the API."
    )

    uploaded = st.file_uploader(
        "Choose a patient CSV file",
        type=["csv"],
        accept_multiple_files=False,
        help="Required: MAP and HR. Optional: timestamp/minute, SVV, EtCO2, SpO2, CVP.",
    )
    patient_id = st.text_input("Patient / case ID", "CASE-001")

    if uploaded:
        try:
            file_bytes = uploaded.getvalue()
            st.caption(f"Selected: {uploaded.name} • {len(file_bytes) / 1024:.1f} KB")
            telemetry, report = parse_csv_bytes(file_bytes, patient_id=patient_id)

            st.success(
                f"CSV validated: {report.rows_used} usable rows from {report.rows_read}. "
                f"{report.rows_skipped} rows skipped."
            )

            preview_rows = [
                frame.model_dump(exclude_none=True)
                for frame in telemetry.telemetry[:10]
            ]
            with st.expander("Preview imported data", expanded=True):
                st.dataframe(preview_rows, use_container_width=True, hide_index=True)

            info1, info2, info3, info4 = st.columns(4)
            info1.metric("Frames", report.rows_used)
            info2.metric("Interval", f"{report.sampling_interval_seconds:.1f} s")
            info3.metric("Core signals", "MAP + HR")
            info4.metric("Optional signals", f"{4 - len(report.missing_optional_signals)}/4")

            if report.missing_optional_signals:
                st.warning(
                    "Unavailable optional signals: "
                    + ", ".join(report.missing_optional_signals)
                    + ". The system will not invent them."
                )

            with st.expander("Imported column mapping"):
                st.json(report.mapped_columns)

            st.download_button(
                "Download CSV template",
                "timestamp,minute,MAP,HR,SVV,EtCO2,SpO2,CVP\n"
                "2026-10-08T10:00:00,0,82,76,9,36,99,7\n"
                "2026-10-08T10:00:30,0.5,79,78,10,35,99,7\n",
                "AnestheSense_patient_template.csv",
                "text/csv",
            )

            speed = st.slider("Replay speed", 1.0, 30.0, 10.0, 1.0)
            if st.button("Start patient replay", type="primary"):
                final, predictions = run_replay(
                    [frame.model_dump(exclude_none=True) for frame in telemetry.telemetry],
                    patient_id,
                    speed,
                )
                if final:
                    st.success("Patient replay complete.")
                    clinician_view(final, [frame.model_dump(exclude_none=True) for frame in telemetry.telemetry])

                    mae10, mae15 = evaluate_replay(
                        [frame.model_dump(exclude_none=True) for frame in telemetry.telemetry],
                        predictions,
                    )
                    with st.expander("Validation result from this replay"):
                        c1, c2 = st.columns(2)
                        c1.metric("MAP +10 min MAE", "N/A" if mae10 is None else f"{mae10:.2f} mmHg")
                        c2.metric("MAP +15 min MAE", "N/A" if mae15 is None else f"{mae15:.2f} mmHg")
                        st.caption(
                            "These are retrospective replay errors for this file, not clinical validation or calibration."
                        )
                    research_view(final, [frame.model_dump(exclude_none=True) for frame in telemetry.telemetry], patient_id)

        except ValueError as exc:
            st.error(str(exc))


# ---------------------------------------------------------------------------
# Synthetic simulation mode
# ---------------------------------------------------------------------------
elif source == "Synthetic simulation":
    st.subheader("Simulation")
    patient_id = st.text_input("Patient / case ID", "SIM-001")
    scenario = st.selectbox(
        "Scenario",
        ["Vasodilation", "Hypovolemia", "Hemorrhage", "MixedShock", "HypoxiaStress", "Normotensive"],
    )

    if st.button("Start simulation", type="primary"):
        try:
            response = requests.post(
                f"{API_URL.rstrip('/')}/api/v1/simulate",
                json={
                    "patient_id": patient_id,
                    "scenario": scenario,
                    "frames": 31,
                    "interval_seconds": 30,
                },
                timeout=30,
            )
            response.raise_for_status()
            telemetry = response.json()["telemetry"]
            final, predictions = run_replay(telemetry, patient_id, speed=10)
            if final:
                st.success("Simulation complete.")
                clinician_view(final, telemetry)
                research_view(final, telemetry, patient_id)
        except requests.RequestException as exc:
            st.error(f"Backend connection failed: {exc}")


# ---------------------------------------------------------------------------
# Manual mode
# ---------------------------------------------------------------------------
else:
    st.subheader("Manual check")
    st.write("Use this only for development or demonstration; clinicians should not manually enter live monitor values.")

    patient_id = st.text_input("Patient / case ID", "MANUAL-001")
    maps = st.slider("Current MAP", 40, 110, 70)
    slope = st.slider("MAP trend (mmHg/min)", -3.0, 2.0, -0.5, 0.1)
    hr = st.slider("HR (bpm)", 40, 180, 90)
    svv = st.slider("SVV (%)", 0, 35, 12)
    etco2 = st.slider("EtCO2 (mmHg)", 15, 60, 34)
    spo2 = st.slider("SpO2 (%)", 70, 100, 98)

    frames = [
        {
            "minute": i - 5,
            "MAP": round(maps + slope * i, 1),
            "HR": hr,
            "SVV": svv,
            "EtCO2": etco2,
            "SpO2": spo2,
        }
        for i in range(6)
    ]

    if st.button("Analyze", type="primary"):
        try:
            result = post_predict(
                {
                    "patient_id": patient_id,
                    "sampling_interval_seconds": 60,
                    "telemetry": frames,
                }
            )
            clinician_view(result, frames)
            research_view(result, frames, patient_id)
        except requests.RequestException as exc:
            st.error(f"Backend connection failed: {exc}")


st.divider()
st.caption(
    "AnestheSense is a research/demo CDS prototype. It is not clinically validated, "
    "does not provide autonomous treatment, and must not be used to direct patient care."
)
