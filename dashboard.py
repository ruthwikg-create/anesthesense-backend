import json
import time

import plotly.graph_objects as go
import requests
import streamlit as st


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


def render_assessment(data, observed_maps):
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
        st.plotly_chart(fig, use_container_width=True)

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
    )


tab_live, tab_manual, tab_about = st.tabs(["Live simulation", "Manual telemetry", "System"])

with tab_live:
    st.subheader("Intraoperative Simulation Laboratory")
    st.write(
        "Generate a deterministic synthetic case, then replay it through the same "
        "prediction endpoint used for live telemetry."
    )

    if st.button("Run 15-minute simulation", type="primary"):
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
            telemetry = sim.json()["telemetry"]

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
                result = post_predict(payload)
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
                    fig.add_hline(y=65, line_dash="dot")
                    fig.update_layout(
                        title=f"Live replay — {patient_id} — {scenario}",
                        xaxis_title="Simulation time (min)",
                        yaxis_title="MAP (mmHg)",
                        yaxis_range=[30, 110],
                        height=420,
                    )
                    chart.plotly_chart(fig, use_container_width=True)

                with metrics.container():
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Risk", a["hypotension_risk_level"])
                    c2.metric("Score", f"{a['hemodynamic_risk_score']:.0f}/100")
                    c3.metric("Forecast MAP", f"{a['predicted_map_15min']:.1f}")
                    c4.metric("Probability", f"{result['features']['hypotension_probability']:.0%}")

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
                render_assessment(last_result, maps)

        except requests.RequestException as exc:
            st.error(f"Backend connection failed: {exc}")

with tab_manual:
    st.subheader("Manual telemetry stress test")
    maps = st.slider("Current MAP", 40, 110, 70)
    map_slope = st.slider("Synthetic MAP trend (mmHg/min)", -3.0, 2.0, -0.5, 0.1)
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
            render_assessment(result, manual_maps)
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
