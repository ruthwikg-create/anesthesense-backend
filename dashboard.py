import json
import random
import plotly.graph_objects as go
import requests
import streamlit as st

st.set_page_config(page_title="AnestheSense | OT Monitor",page_icon="🏥",layout="wide")
st.title("AnestheSense")
st.caption("Intraoperative hemodynamic early-warning clinical decision support")

API_URL=st.sidebar.text_input("Backend URL","http://127.0.0.1:8000")
patient_id=st.sidebar.text_input("Patient ID","PATIENT-001")
scenario=st.sidebar.selectbox("Simulation scenario",["Vasodilation","Hypovolemia","Normotensive","Hypoxia + Hemodynamic Stress"])

scenarios={
"Vasodilation":([78,74,70,66,64,61],8,60,35,98),
"Hypovolemia":([82,79,74,68,63,59],18,105,32,96),
"Normotensive":([85,84,86,85,83,85],9,72,36,99),
"Hypoxia + Hemodynamic Stress":([84,80,75,69,64,58],16,110,27,88),
}
maps,svv,hr,etco2,spo2=scenarios[scenario]
maps=[m+random.choice([-1,0,1]) for m in maps]

with st.sidebar.expander("Telemetry controls"):
    svv=st.slider("SVV (%)",0,30,svv)
    hr=st.slider("HR (bpm)",40,180,hr)
    etco2=st.slider("EtCO₂ (mmHg)",15,60,etco2)
    spo2=st.slider("SpO₂ (%)",70,100,spo2)

telemetry=[{"minute":m,"MAP":v,"HR":hr,"SVV":svv,"EtCO2":etco2,"SpO2":spo2} for m,v in zip(range(-5,1),maps)]

if st.button("Run AnestheSense",type="primary"):
    try:
        response=requests.post(f"{API_URL.rstrip('/')}/api/v1/predict",json={"patient_id":patient_id,"sampling_interval_seconds":60,"telemetry":telemetry},timeout=30)
        response.raise_for_status()
        data=response.json(); a=data["clinical_assessment"]; f=data["features"]
        c1,c2,c3,c4=st.columns(4)
        c1.metric("Hemodynamic Risk",f"{a['hemodynamic_risk_score']:.0f}/100")
        c2.metric("Predicted MAP",f"{a['predicted_map_15min']:.1f} mmHg")
        c3.metric("Risk",a["hypotension_risk_level"])
        c4.metric("Confidence",f"{a['confidence_score']*100:.0f}%")

        if data["alert_triggered"]: st.error(f"⚠️ Impending instability: {a['primary_risk']}")
        else: st.success("No high-risk alert from the current prototype engine.")

        fig=go.Figure()
        fig.add_trace(go.Scatter(x=list(range(-5,1)),y=maps,mode="lines+markers",name="Observed MAP"))
        fig.add_trace(go.Scatter(x=[0,15],y=[maps[-1],a["predicted_map_15min"]],mode="lines+markers",name="15-min forecast",line={"dash":"dash"}))
        fig.add_hline(y=65,line_dash="dot",annotation_text="MAP 65")
        fig.update_layout(title="Dynamic MAP trajectory",xaxis_title="Minutes",yaxis_title="MAP (mmHg)",yaxis_range=[30,120])
        st.plotly_chart(fig,use_container_width=True)

        st.subheader("Physiological interpretation")
        x,y=st.columns(2)
        x.info(f"**Likely mechanism**\n\n{a['suspected_mechanism']}")
        y.warning(f"**Clinician-directed next step**\n\n{a['suggested_action']}")
        st.caption(f"Signal quality: {a['data_quality']} · MAP slope: {f['map_slope_per_min']:.2f} mmHg/min · MAP <65 fraction: {f['map_below_65_fraction']:.0%}")

        st.subheader("Multi-agent pipeline")
        for step in data["pipeline"]: st.write("✓",step)

        st.download_button("Export audit JSON",json.dumps(data,indent=2),f"AnestheSense_Audit_{patient_id}.json","application/json")
    except requests.RequestException as exc: st.error(f"Backend connection failed: {exc}")
    except (KeyError,ValueError) as exc: st.error(f"Invalid backend response: {exc}")
