from __future__ import annotations
import math
import random
from schema import PatientTelemetry, SimulationRequest, TelemetryFrame

def build_simulation(request: SimulationRequest) -> PatientTelemetry:
    rng = random.Random(42)
    frames=[]
    for i in range(request.frames):
        t=i*request.interval_seconds/60.0
        if request.scenario=="Vasodilation":
            vals=(82-1.0*t,8,62,34,98)
        elif request.scenario=="Hypovolemia":
            vals=(86-1.35*t,18,75+3*t,31,97)
        elif request.scenario=="HypoxiaStress":
            vals=(84-1.1*t,15,78+2*t,27,max(70,96-.35*t))
        else:
            vals=(84+1.2*math.sin(t),9,70,36,99)
        m,s,h,e,o=vals
        frames.append(TelemetryFrame(
            minute=round(t,3),MAP=round(m+rng.uniform(-.8,.8),1),
            HR=round(h+rng.uniform(-1.5,1.5),1),SVV=round(s+rng.uniform(-.6,.6),1),
            EtCO2=round(e+rng.uniform(-.7,.7),1),SpO2=round(o+rng.uniform(-.3,.3),1),
            arterial_waveform=[m-2,m+3,m+1,m-1],ecg_waveform=[0,1,-.2,.1,0]))
    return PatientTelemetry(patient_id=request.patient_id,sampling_interval_seconds=request.interval_seconds,telemetry=frames)
