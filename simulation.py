from __future__ import annotations

import math
import random

from schema import PatientTelemetry, SimulationRequest, TelemetryFrame


def _waveforms(map_value: float, heart_rate: float) -> tuple[list[float], list[float]]:
    arterial = [
        round(map_value - 3.0, 2),
        round(map_value + 5.0, 2),
        round(map_value + 1.5, 2),
        round(map_value - 1.0, 2),
    ]
    ecg = [0.0, round(1.0 + heart_rate / 200.0, 3), -0.2, 0.1, 0.0]
    return arterial, ecg


def build_simulation(request: SimulationRequest) -> PatientTelemetry:
    rng = random.Random(42)
    frames = []

    for i in range(request.frames):
        t = i * request.interval_seconds / 60.0

        if request.scenario == "Vasodilation":
            map_value = 84 - 1.05 * t
            svv, hr, etco2, spo2 = 9, 68 + 2.5 * t, 35, 99
        elif request.scenario == "Hypovolemia":
            map_value = 86 - 1.35 * t
            svv, hr, etco2, spo2 = 18 + 0.25 * t, 76 + 3.0 * t, 31, 98
        elif request.scenario == "Hemorrhage":
            map_value = 88 - 1.65 * t
            svv, hr, etco2, spo2 = 17 + 0.45 * t, 78 + 4.0 * t, 32 - 0.25 * t, 98
        elif request.scenario == "MixedShock":
            map_value = 86 - 1.45 * t
            svv, hr, etco2, spo2 = 18 + 0.35 * t, 82 + 3.5 * t, 31 - 0.35 * t, 94 - 0.25 * t
        elif request.scenario == "HypoxiaStress":
            map_value = 84 - 1.1 * t
            svv, hr, etco2, spo2 = 15 + 0.15 * t, 78 + 2.0 * t, 27, max(70, 96 - 0.35 * t)
        else:
            map_value = 84 + 1.2 * math.sin(t)
            svv, hr, etco2, spo2 = 9, 70, 36, 99

        arterial, ecg = _waveforms(map_value, hr)
        frames.append(
            TelemetryFrame(
                minute=round(t, 3),
                MAP=round(map_value + rng.uniform(-0.8, 0.8), 1),
                HR=round(hr + rng.uniform(-1.5, 1.5), 1),
                SVV=round(svv + rng.uniform(-0.6, 0.6), 1),
                EtCO2=round(etco2 + rng.uniform(-0.7, 0.7), 1),
                SpO2=round(spo2 + rng.uniform(-0.3, 0.3), 1),
                CVP=round(max(1.0, 7.0 - 0.15 * t), 1),
                arterial_waveform=arterial,
                ecg_waveform=ecg,
            )
        )

    return PatientTelemetry(
        patient_id=request.patient_id,
        sampling_interval_seconds=request.interval_seconds,
        telemetry=frames,
    )
