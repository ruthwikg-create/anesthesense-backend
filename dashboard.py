import streamlit as st
import requests
import plotly.graph_objects as go
import json
import time
import random

st.set_page_config(
    page_title="AnestheSense | Clinical Dashboard",
    page_icon="🏥",
    layout="wide"
)

st.title("🏥 AnestheSense — Intraoperative CDS")
st.caption("AI-Powered Intraoperative Hypotension Prediction & Guidance System")

API_URL = "http://127.0.0.1:8000/api/v1/predict"

# Sidebar Mode Switcher
st.sidebar.header("Mode Selection")
mode = st.sidebar.radio("Choose Input Source", ["Manual Sliders", "Live Telemetry Simulator"])

patient_id = st.sidebar.text_input("Patient ID", "PATIENT-001")

if mode == "Manual Sliders":
    st.sidebar.subheader("5-Minute Window Telemetry")
    map_vals = [
        st.sidebar.slider("Min -5 MAP", 40, 140, 76),
        st.sidebar.slider("Min -4 MAP", 40, 140, 73),
        st.sidebar.slider("Min -3 MAP", 40, 140, 70),
        st.sidebar.slider("Min -2 MAP", 40, 140, 67),
        st.sidebar.slider("Min -1 MAP", 40, 140, 65),
        st.sidebar.slider("Min 0 MAP", 40, 140, 63)
    ]
    svv_val = st.sidebar.slider("Current SVV (%)", 0, 30, 8)
    hr_val = st.sidebar.slider("Current HR (bpm)", 40, 160, 62)
    
    telemetry_data = [
        {"minute": idx - 5, "MAP": val, "HR": hr_val, "SVV": svv_val, "EtCO2": 35}
        for idx, val in enumerate(map_vals)
    ]

else: # Live Simulator
    st.sidebar.subheader("Simulation Scenario")
    scenario = st.sidebar.selectbox("Scenario Preset", [
        "Vasodilatory Shock (Deep Anesthesia)",
        "Hypovolemic Shock (Blood Loss)",
        "Normotensive Baseline"
    ])
    
    if scenario == "Vasodilatory Shock (Deep Anesthesia)":
        map_vals = [78, 74, 70, 66, 64, 61]
        svv_val, hr_val = 8, 60
    elif scenario == "Hypovolemic Shock (Blood Loss)":
        map_vals = [82, 79, 74, 68, 63, 59]
        svv_val, hr_val = 18, 105
    else: # Normotensive
        map_vals = [85, 84, 86, 85, 83, 85]
        svv_val, hr_val = 9, 72

    # Add realistic live jitter
    map_vals = [m + random.choice([-1, 0, 1]) for m in map_vals]
    telemetry_data = [
        {"minute": idx - 5, "MAP": val, "HR": hr_val, "SVV": svv_val, "EtCO2": 35}
        for idx, val in enumerate(map_vals)
    ]
    st.sidebar.info("Click 'Run Assessment' to process simulated telemetry frame.")

payload = {
    "patient_id": patient_id,
    "telemetry": telemetry_data
}

# Execution Button
if st.button("Evaluate Patient Telemetry", type="primary"):
    with st.spinner("Executing Agent Inference Loop..."):
        try:
            response = requests.post(API_URL, json=payload, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                assessment = data["clinical_assessment"]
                
                # Top Metrics Section
                col1, col2, col3 = st.columns(3)
                risk = assessment["hypotension_risk_level"]
                
                col1.metric(
                    label="Predicted MAP (+15 min)",
                    value=f"{assessment['predicted_map_15min']} mmHg",
                    delta=f"{assessment['predicted_map_15min'] - map_vals[-1]:.1f} mmHg"
                )
                col2.metric(label="Risk Level", value=risk)
                col3.metric(label="Model Confidence", value=f"{int(assessment['confidence_score'] * 100)}%")
                
                st.markdown("---")
                
                # Plotly Trend Chart
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=list(range(-5, 1)), y=map_vals,
                    mode='lines+markers', name='Observed MAP',
                    line=dict(color='#1f77b4', width=3)
                ))
                fig.add_trace(go.Scatter(
                    x=[0, 15], y=[map_vals[-1], assessment["predicted_map_15min"]],
                    mode='lines+markers', name='Projected Forecast',
                    line=dict(color='red' if risk in ["CRITICAL", "HIGH"] else '#2ca02c', width=3, dash='dash')
                ))
                fig.add_hline(y=65, line_dash="dot", line_color="orange", annotation_text="Hypotension Threshold (65 mmHg)")
                fig.update_layout(
                    title="Mean Arterial Pressure (MAP) Trend & 15-Min Forecast",
                    xaxis_title="Time (Minutes)",
                    yaxis_title="MAP (mmHg)",
                    yaxis_range=[30, 120]
                )
                st.plotly_chart(fig, use_container_width=True)
                
                # CDS Advice Section
                st.subheader("Clinical Decision Support Recommendations")
                
                c_col1, c_col2 = st.columns(2)
                with c_col1:
                    st.info(f"**Suspected Mechanism:**\n\n{assessment['suspected_mechanism']}")
                with c_col2:
                    st.warning(f"**Suggested Clinical Intervention:**\n\n{assessment['suggested_action']}")
                
                # EHR Audit Exporter
                st.markdown("---")
                st.subheader("EHR Audit Trail")
                audit_log = json.dumps(data, indent=2)
                st.download_button(
                    label="📄 Export EHR Audit Log (JSON)",
                    data=audit_log,
                    file_name=f"AnestheSense_Audit_{patient_id}.json",
                    mime="application/json"
                )
            else:
                st.error(f"Backend Returned Error {response.status_code}: {response.text}")
                
        except requests.exceptions.RequestException as err:
            st.error(f"Connection Error: Could not reach FastAPI at {API_URL}. Details: {err}")