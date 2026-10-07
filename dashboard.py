import json
import random
import plotly.graph_objects as go
import requests
import streamlit as st

st.set_page_config(page_title="AnestheSense | Clinical Dashboard",page_icon="🏥",layout="wide")
st.title("AnestheSense — Intraoperative CDS")
st.caption("Assistive AI-powered intraoperative hypotension risk prediction")

API_URL=st.sidebar.text_input("Backend URL","http://127.0.0.1:8000")
mode=st.sidebar.radio("Input source",["Manual","Simulation"])
patient_id=st.sidebar.text_input("Patient ID","PATIENT-001")

if mode=="Manual":
    st.sidebar.subheader("5-Minute Telemetry")
    map_vals=[st.sidebar.slider(f"MAP {m} min",40,140,d) for m,d in [(-5,76),(-4,73),(-3,70),(-2,67),(-1,65),(0,63)]]
    svv=st.sidebar.slider("SVV (%)",0,30,8); hr=st.sidebar.slider("HR (bpm)",40,180,62); etco2=st.sidebar.slider("EtCO₂ (mmHg)",20,60,35)
else:
    scenario=st.sidebar.selectbox("Scenario",["Vasodilation","Hypovolemia","Normotensive"])
    scenarios={"Vasodilation":([78,74,70,66,64,61],8,60),"Hypovolemia":([82,79,74,68,63,59],18,105),"Normotensive":([85,84,86,85,83,85],9,72)}
    map_vals,svv,hr=scenarios[scenario]; map_vals=[m+random.choice([-1,0,1]) for m in map_vals]; etco2=35

telemetry=[{"minute":m,"MAP":v,"HR":hr,"SVV":svv,"EtCO2":etco2} for m,v in zip(range(-5,1),map_vals)]

if st.button("Evaluate Patient Telemetry",type="primary"):
    try:
        response=requests.post(f"{API_URL.rstrip('/')}/api/v1/predict",json={"patient_id":patient_id,"telemetry":telemetry},timeout=30)
        response.raise_for_status()
        data=response.json(); assessment=data["clinical_assessment"]; risk=assessment["hypotension_risk_level"]
        c1,c2,c3=st.columns(3)
        c1.metric("Predicted MAP (+15 min)",f"{assessment['predicted_map_15min']:.1f} mmHg")
        c2.metric("Risk Level",risk)
        c3.metric("Confidence",f"{assessment['confidence_score']*100:.0f}%")
        fig=go.Figure()
        fig.add_trace(go.Scatter(x=list(range(-5,1)),y=map_vals,mode="lines+markers",name="Observed MAP"))
        fig.add_trace(go.Scatter(x=[0,15],y=[map_vals[-1],assessment["predicted_map_15min"]],mode="lines+markers",name="15-min projection",line={"dash":"dash"}))
        fig.add_hline(y=65,line_dash="dot",annotation_text="MAP 65 mmHg threshold")
        fig.update_layout(title="MAP Trend and 15-Minute Projection",xaxis_title="Time (minutes)",yaxis_title="MAP (mmHg)",yaxis_range=[30,120])
        st.plotly_chart(fig,use_container_width=True)
        st.subheader("Clinical Decision Support")
        left,right=st.columns(2)
        left.info(f"**Suspected mechanism**\n\n{assessment['suspected_mechanism']}")
        right.warning(f"**Suggested action**\n\n{assessment['suggested_action']}")
        if assessment.get("guardrail_note"): st.caption(assessment["guardrail_note"])
        st.subheader("Audit Export")
        st.download_button("Export assessment JSON",data=json.dumps(data,indent=2),file_name=f"AnestheSense_Audit_{patient_id}.json",mime="application/json")
    except requests.RequestException as exc:
        st.error(f"Backend connection failed: {exc}")
    except (KeyError,ValueError) as exc:
        st.error(f"Invalid backend response: {exc}")
