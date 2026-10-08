import json
import time

import plotly.graph_objects as go
import requests
import streamlit as st

from patient_replay import parse_csv_bytes


st.set_page_config(
    page_title="AnestheSense | Intraoperative Monitor",
    page_icon="🏥",
    layout="wide",
)

st.markdown(
    """
    <style>
    .block-container {padding-top: 1.2rem; max-width: 1500px;}
    .risk-card {padding: 18px; border: 1px solid #333; border-radius: 14px;}
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("AnestheSense")
st.caption("Advanced intraoperative hemodynamic early-warning clinical decision-support prototype")

API_URL = st.sidebar.text_input("Backend URL", "http://127.0.0.1:8000")
patient_id = st.sidebar.text_input("Patient / Case ID", "OR-07")
scenario = st.sidebar.selectbox(
    "Simulation laboratory",
    [
        "Vasodilation",
        "Hypovolemia",
        "Hemorrhage",
        "MixedShock",
        "HypoxiaStress",
        "Normotensive",
    ],
)

st.sidebar.markdown("---")
st.sidebar.caption("Prototype safety boundary")
st.sidebar.info(
    "Deterministic risk severity and alarm state remain authoritative. "
    "Gemini, when configured, is an explanation layer only. No drug doses are generated."
)


def post_predict(payload):
    response = requests.post(
        f"{API_URL.rstrip('/')}/api/v1/predict",
        json=payload,
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def render_assessment(data, observed_maps, chart_key="assessment_chart"):
    a = data["clinical_assessment"]
    f = data["features"]

    cols = st.columns(5)
    cols[0].metric("Risk score", f"{a['hemodynamic_risk_score']:.0f}/100")
    cols[1].metric("Risk level", a["hypotension_risk_level"])
    cols[2].metric("MAP now", f"{f['map_current']:.1f}")
    cols[3].metric("MAP +15 min", f"{a['predicted_map_15min']:.1f}")
    cols[4].metric("Hypotension probability", f"{f['hypotension_probability']:.0%}")

    if data["alert_triggered"]:
        st.error(
            f"🔴 {a['alert_priority']} ALERT — {a['primary_risk']} · "
            f"trajectory: {f['trajectory']}"
        )
    elif a["hypotension_risk_level"] == "MODERATE":
        st.warning("🟠 WATCH — deterioration should be reassessed.")
    else:
        st.success("🟢 No HIGH/CRITICAL alert from the prototype engine.")

    left, right = st.columns([1.6, 1])

    with left:
        fig = go.Figure()
        x = list(range(-len(observed_maps) + 1, 1))
        fig.add_trace(
            go.Scatter(x=x, y=observed_maps, mode="lines+markers", name="Observed MAP")
        )
        fig.add_trace(
            go.Scatter(
                x=[0, 10, 15],
                y=[f["map_current"], f["predicted_map_10min"], f["predicted_map_15min"]],
                mode="lines+markers",
                name="Forecast",
                line={"dash": "dash"},
            )
        )
        fig.add_hline(y=65, line_dash="dot", annotation_text="MAP 65")
        fig.add_hline(y=60, line_dash="dot", annotation_text="MAP 60")
        fig.update_layout(
            title="Dynamic MAP trajectory",
            xaxis_title="Relative time (min)",
            yaxis_title="MAP (mmHg)",
            height=400,
            margin={"l": 20, "r": 20, "t": 50, "b": 20},
        )
        st.plotly_chart(fig, use_container_width=True, key=chart_key)

    with right:
        st.subheader("Mechanism")
        st.metric("Likely mechanism", a["suspected_mechanism"])
        st.metric("MAP slope", f"{f['map_slope_per_min']:.2f} mmHg/min")
        st.metric("Trend strength", f"{f['trend_strength']:.0%}")
        st.metric("Signal quality", a["data_quality"])

    st.subheader("Why the system raised this state")
    for item in a["contributing_factors"]:
        st.write("•", item)

    st.subheader("Clinical advisory")
    st.info(a["suggested_action"])
    st.caption(a["explanation"])

    if a.get("guardrail_note"):
        st.warning("Safety guardrail: " + a["guardrail_note"])

    st.subheader("Event timeline")
    for event in data.get("event_log", []):
        st.write("•", event)

    with st.expander("Feature matrix"):
        st.json(f)

    with st.expander("Multi-agent pipeline"):
        for step in data["pipeline"]:
            st.write("✓", step)

    st.download_button(
        "Export audit JSON",
        json.dumps(data, indent=2),
        f"AnestheSense_{patient_id}_audit.json",
        "application/json",
        key=f"audit_{chart_key}",
    )


def render_csv_replay_result(result, frames, patient_id):
    a = result["clinical_assessment"]
    f = result["features"]

    st.success("Patient replay complete.")
    st.subheader("Replay assessment")

    cols = st.columns(5)
    cols[0].metric("Risk", a["hypotension_risk_level"])
    cols[1].metric("Risk score", f"{a['hemodynamic_risk_score']:.0f}/100")
    cols[2].metric("MAP now", f"{f['map_current']:.1f} mmHg")
    cols[3].metric("MAP +15 min", f"{a['predicted_map_15min']:.1f} mmHg")
    cols[4].metric("Confidence", f"{a['confidence_score']:.0%}")

    if result["alert_triggered"]:
        st.error(
            f"🔴 {a['alert_priority']} ALERT — {a['primary_risk']} · "
            f"predicted MAP {a['predicted_map_15min']:.1f} mmHg"
        )
    elif a["hypotension_risk_level"] == "MODERATE":
        st.warning("🟠 WATCH — deterioration should be reassessed.")
    else:
        st.success("🟢 No HIGH/CRITICAL alert from the prototype engine.")

    render_assessment(
        result,
        [frame["MAP"] for frame in frames],
        chart_key="csv_final_assessment_chart",
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
            errors_10.append(
                abs(result["features"]["predicted_map_10min"] - actual10)
            )
        if actual15 is not None:
            errors_15.append(
                abs(result["features"]["predicted_map_15min"] - actual15)
            )

    mae10 = sum(errors_10) / len(errors_10) if errors_10 else None
    mae15 = sum(errors_15) / len(errors_15) if errors_15 else None
    return mae10, mae15


def run_patient_replay(telemetry, patient_id, speed=10.0):
    chart = st.empty()
    metrics = st.empty()
    status = st.empty()
    final = None
    predictions = []

    for index in range(2, len(telemetry) + 1):
        prefix = telemetry[:index]
        payload = {
            "patient_id": patient_id,
            "sampling_interval_seconds": max(
                0.1,
                float(prefix[1]["minute"] - prefix[0]["minute"]) * 60,
            ),
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
            c3.metric("Forecast MAP", f"{a['predicted_map_15min']:.1f} mmHg")
            c4.metric("Probability", f"{f['hypotension_probability']:.0%}")

        with status.container():
            if result["alert_triggered"]:
                st.error(
                    f"🔴 {a['alert_priority']} ALERT — review the patient's clinical state."
                )
            else:
                st.info(
                    f"Monitoring — {f['trajectory']} · "
                    f"{a['suspected_mechanism']}"
                )

        with chart.container():
            fig = go.Figure()
            fig.add_trace(
                go.Scatter(
                    x=[frame["minute"] for frame in prefix],
                    y=[frame["MAP"] for frame in prefix],
                    mode="lines+markers",
                    name="Observed MAP",
                )
            )
            fig.add_hline(y=65, line_dash="dot", annotation_text="MAP 65")
            fig.add_hline(y=60, line_dash="dot", annotation_text="MAP 60")
            fig.update_layout(
                title=f"Patient replay — {patient_id}",
                xaxis_title="Time (min)",
                yaxis_title="MAP (mmHg)",
                yaxis_range=[30, 110],
                height=420,
            )
            st.plotly_chart(
                fig,
                use_container_width=True,
                key=f"patient_replay_chart_{index}",
            )

        time.sleep(max(0.03, 0.8 / speed))

    return final, predictions


def run_simulation():
    try:
        sim = requests.post(
            f"{API_URL.rstrip('/')}/api/v1/simulate",
            json={
                "patient_id": patient_id,
                "scenario": scenario,
                "frames": 31,
                "interval_seconds": 30,
            },
            timeout=30,
        )
        sim.raise_for_status()
        return sim.json()["telemetry"]
    except requests.RequestException as exc:
        st.error(f"Backend connection failed: {exc}")
        return None


tab_live, tab_csv, tab_manual, tab_about = st.tabs(
    ["Live simulation", "Patient CSV replay", "Manual telemetry", "System"]
)

with tab_live:
    st.subheader("Intraoperative Simulation Laboratory")
    st.write(
        "Generate a deterministic synthetic case, then replay it through the same "
        "prediction endpoint used for live telemetry."
    )

    if st.button("Run 15-minute simulation", type="primary"):
        telemetry = run_simulation()

        if telemetry:
            chart = st.empty()
            metrics = st.empty()
            status = st.empty()
            last_result = None
            maps = []

            for i in range(2, len(telemetry) + 1):
                prefix = telemetry[:i]
                payload = {
                    "patient_id": patient_id,
                    "sampling_interval_seconds": 30,
                    "telemetry": prefix,
                }

                try:
                    result = post_predict(payload)
                except requests.RequestException as exc:
                    st.error(f"Backend connection failed: {exc}")
                    break

                last_result = result
                maps = [frame["MAP"] for frame in prefix]
                a = result["clinical_assessment"]

                with chart.container():
                    fig = go.Figure()
                    fig.add_trace(
                        go.Scatter(
                            x=[f["minute"] for f in prefix],
                            y=maps,
                            mode="lines+markers",
                            name="Observed MAP",
                        )
                    )
                    fig.add_hline(y=65, line_dash="dot", annotation_text="MAP 65")
                    fig.add_hline(y=60, line_dash="dot", annotation_text="MAP 60")
                    fig.update_layout(
                        title=f"Live replay — {patient_id} — {scenario}",
                        xaxis_title="Simulation time (min)",
                        yaxis_title="MAP (mmHg)",
                        yaxis_range=[30, 110],
                        height=420,
                    )
                    st.plotly_chart(
                        fig,
                        use_container_width=True,
                        key=f"live_simulation_chart_{i}",
                    )

                with metrics.container():
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Risk", a["hypotension_risk_level"])
                    c2.metric("Score", f"{a['hemodynamic_risk_score']:.0f}/100")
                    c3.metric("Forecast MAP", f"{a['predicted_map_15min']:.1f}")
                    c4.metric(
                        "Probability",
                        f"{result['features']['hypotension_probability']:.0%}",
                    )

                if result["alert_triggered"]:
                    status.error(
                        f"🔴 {a['alert_priority']} — {a['suspected_mechanism']} · "
                        f"predicted MAP {a['predicted_map_15min']:.1f}"
                    )
                else:
                    status.info(
                        f"Monitoring · {a['suspected_mechanism']} · "
                        f"trajectory {result['features']['trajectory']}"
                    )

                time.sleep(0.12)

            if last_result:
                st.success("Simulation replay complete.")
                render_assessment(
                    last_result,
                    maps,
                    chart_key="simulation_final_assessment_chart",
                )


with tab_csv:
    st.subheader("Patient Data Replay")
    st.write(
        "Upload a de-identified monitor export. The file is replayed frame-by-frame "
        "through the same deterministic prediction engine used by the API."
    )

    uploaded = st.file_uploader(
        "Choose a patient CSV file",
        type=["csv"],
        accept_multiple_files=False,
        help="Required: MAP and HR. Optional: timestamp/minute, SVV, EtCO2, SpO2, CVP.",
    )

    csv_patient_id = st.text_input(
        "CSV Patient / Case ID",
        "CASE-001",
        key="csv_patient_id",
    )

    if uploaded:
        try:
            file_bytes = uploaded.getvalue()
            st.caption(
                f"Selected: {uploaded.name} • {len(file_bytes) / 1024:.1f} KB"
            )

            telemetry, report = parse_csv_bytes(
                file_bytes,
                patient_id=csv_patient_id,
            )

            st.success(
                f"CSV validated: {report.rows_used} usable rows from "
                f"{report.rows_read}. {report.rows_skipped} rows skipped."
            )

            preview_rows = [
                frame.model_dump(exclude_none=True)
                for frame in telemetry.telemetry[:10]
            ]

            with st.expander("Preview imported data", expanded=True):
                st.dataframe(
                    preview_rows,
                    use_container_width=True,
                    hide_index=True,
                )

            info1, info2, info3, info4 = st.columns(4)
            info1.metric("Frames", report.rows_used)
            info2.metric("Sampling interval", f"{report.sampling_interval_seconds:.1f} s")
            info3.metric("Core signals", "MAP + HR")
            info4.metric(
                "Optional signals",
                f"{4 - len(report.missing_optional_signals)}/4",
            )

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
                key="csv_template_download",
            )

            speed = st.slider(
                "Replay speed",
                1.0,
                30.0,
                10.0,
                1.0,
                key="csv_replay_speed",
            )

            if st.button(
                "Start patient replay",
                type="primary",
                key="start_csv_replay",
            ):
                frames = [
                    frame.model_dump(exclude_none=True)
                    for frame in telemetry.telemetry
                ]

                final, predictions = run_patient_replay(
                    frames,
                    csv_patient_id,
                    speed,
                )

                if final:
                    render_csv_replay_result(
                        final,
                        frames,
                        csv_patient_id,
                    )

                    mae10, mae15 = evaluate_replay(frames, predictions)

                    with st.expander("Retrospective replay validation"):
                        c1, c2 = st.columns(2)
                        c1.metric(
                            "MAP +10 min MAE",
                            "N/A" if mae10 is None else f"{mae10:.2f} mmHg",
                        )
                        c2.metric(
                            "MAP +15 min MAE",
                            "N/A" if mae15 is None else f"{mae15:.2f} mmHg",
                        )
                        st.caption(
                            "These are retrospective replay errors for this file, "
                            "not clinical validation or calibration."
                        )

        except ValueError as exc:
            st.error(str(exc))


with tab_manual:
    st.subheader("Manual telemetry stress test")
    maps = st.slider("Current MAP", 40, 110, 70)
    map_slope = st.slider(
        "Synthetic MAP trend (mmHg/min)",
        -3.0,
        2.0,
        -0.5,
        0.1,
    )
    hr = st.slider("HR (bpm)", 40, 180, 90)
    svv = st.slider("SVV (%)", 0, 35, 12)
    etco2 = st.slider("EtCO₂ (mmHg)", 15, 60, 34)
    spo2 = st.slider("SpO₂ (%)", 70, 100, 98)

    manual_maps = [maps + map_slope * i for i in range(-5, 1)]

    payload = {
        "patient_id": patient_id,
        "sampling_interval_seconds": 60,
        "telemetry": [
            {
                "minute": i - 5,
                "MAP": round(value, 1),
                "HR": hr,
                "SVV": svv,
                "EtCO2": etco2,
                "SpO2": spo2,
            }
            for i, value in enumerate(manual_maps)
        ],
    }

    if st.button("Analyze manual telemetry"):
        try:
            result = post_predict(payload)
            render_assessment(
                result,
                manual_maps,
                chart_key="manual_assessment_chart",
            )
        except requests.RequestException as exc:
            st.error(f"Backend connection failed: {exc}")


with tab_about:
    st.subheader("AnestheSense v4 architecture")
    st.code(
        """
Telemetry
   ↓
Signal Preprocessor Agent
   ├─ artifact rejection
   ├─ signal quality
   └─ waveform features
   ↓
Predictive Analytics Agent
   ├─ trend
   ├─ acceleration
   ├─ volatility
   ├─ 10/15-min MAP forecast
   └─ hypotension probability
   ↓
Clinical Advisory Agent
   ├─ risk severity
   ├─ mechanism hypothesis
   ├─ contributing factors
   └─ clinician-directed guidance
   ↓
Safety Guardrail
   ├─ severity cannot be downgraded
   ├─ HIGH/CRITICAL alarm cannot be suppressed
   └─ no medication dosing
   ↓
Clinician Dashboard + Audit Trail
        """,
        language="text",
    )
    st.warning(
        "Research/demo prototype only. Outputs are not clinically validated and must "
        "not be used to direct patient care."
    )


st.divider()
st.caption(
    "AnestheSense is a research/demo CDS prototype. It is not clinically validated, "
    "does not provide autonomous treatment, and must not be used to direct patient care."
)
