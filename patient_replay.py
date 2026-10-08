from __future__ import annotations

import csv
import io
import math
import re
from dataclasses import dataclass
from datetime import datetime
from statistics import median
from typing import Iterable

from schema import PatientTelemetry, TelemetryFrame


ALIASES = {
    "timestamp": {"timestamp", "time", "datetime", "date_time", "date time", "recorded_at", "recorded time", "date", "datetime local", "date/time"},
    "minute": {"minute", "minutes", "elapsed_min", "elapsed_minutes", "relative_time", "elapsed time", "time_min", "time minutes"},
    "MAP": {"map", "mean arterial pressure", "mean arterial pressure map", "arterial pressure mean", "nibp mean", "abp mean", "map mmhg", "map mm hg", "mean arterial pressure mmhg", "mean map"},
    "HR": {"hr", "heart rate", "heart_rate", "pulse", "pulse rate", "hr bpm", "heart rate bpm", "pulse bpm"},
    "SVV": {"svv", "stroke volume variation", "stroke_volume_variation", "svv percent", "svv %", "stroke volume variation percent"},
    "EtCO2": {"etco2", "etco2 mmhg", "etco2 (mmhg)", "end tidal co2", "end tidal co2 mmhg", "end_tidal_co2", "et co2"},
    "SpO2": {"spo2", "spo2 percent", "spo2 (%)", "oxygen saturation", "o2 sat", "spo2 %", "spo2 percentage", "oxygen saturation percent"},
    "CVP": {"cvp", "central venous pressure", "cvp mmhg", "central venous pressure mmhg"},
}


@dataclass(frozen=True)
class ReplayReport:
    patient_id: str
    rows_read: int
    rows_used: int
    rows_skipped: int
    sampling_interval_seconds: float
    mapped_columns: dict[str, str]
    missing_optional_signals: list[str]


def _normalise(value: str) -> str:
    text = str(value).strip().lower().replace("\ufeff", "")
    text = re.sub(r"[%()\[\]{}:/\\]+", " ", text)
    text = text.replace("_", " ").replace("-", " ")
    return " ".join(text.split())


def _decode_csv_bytes(csv_bytes: bytes) -> str:
    if not csv_bytes:
        raise ValueError("The selected CSV file is empty.")
    for encoding in ("utf-8-sig", "utf-8", "utf-16", "utf-16-le", "utf-16-be", "cp1252"):
        try:
            return csv_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("Could not read this CSV encoding. Save/export the file as UTF-8 CSV and try again.")


def parse_csv_bytes(csv_bytes: bytes, patient_id: str = "REPLAY-001", default_interval_seconds: float = 30.0) -> tuple[PatientTelemetry, ReplayReport]:
    return parse_csv_text(_decode_csv_bytes(csv_bytes), patient_id=patient_id, default_interval_seconds=default_interval_seconds)


def _column_map(fieldnames: Iterable[str]) -> dict[str, str]:
    normalised = {_normalise(name): name for name in fieldnames if name}
    mapped: dict[str, str] = {}
    for target, aliases in ALIASES.items():
        for alias in aliases:
            key = _normalise(alias)
            if key in normalised:
                mapped[target] = normalised[key]
                break
    return mapped


def _number(value: str | None) -> float | None:
    if value is None or not str(value).strip():
        return None
    try:
        number = float(str(value).strip().replace(",", ""))
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def _timestamp_seconds(value: str | None) -> float | None:
    if value is None or not str(value).strip():
        return None
    numeric = _number(value)
    if numeric is not None:
        return numeric
    text = str(value).strip()
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text).timestamp()
    except ValueError:
        pass
    match = re.fullmatch(r"(\d{1,2}):(\d{2})(?::(\d{2})(?:\.(\d+))?)?", text)
    if match:
        hours = int(match.group(1))
        minutes = int(match.group(2))
        seconds = int(match.group(3) or 0)
        fraction = float(f"0.{match.group(4)}") if match.group(4) else 0.0
        return hours * 3600 + minutes * 60 + seconds + fraction
    return None


def _safe_patient_id(patient_id: str) -> str:
    value = str(patient_id or "REPLAY-001").strip()
    return value[:128] or "REPLAY-001"


def parse_csv_text(csv_text: str, patient_id: str = "REPLAY-001", default_interval_seconds: float = 30.0) -> tuple[PatientTelemetry, ReplayReport]:
    if not csv_text or not csv_text.strip():
        raise ValueError("The selected CSV file is empty.")
    if not math.isfinite(default_interval_seconds) or default_interval_seconds <= 0:
        default_interval_seconds = 30.0
    default_interval_seconds = min(60.0, default_interval_seconds)

    sample = csv_text[:16384]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel

    reader = csv.DictReader(io.StringIO(csv_text), dialect=dialect)
    if not reader.fieldnames:
        raise ValueError("CSV must contain a header row.")

    mapped = _column_map(reader.fieldnames)
    if "MAP" not in mapped:
        raise ValueError("CSV must contain a MAP column (for example MAP, Mean Arterial Pressure, or ABP Mean).")
    if "HR" not in mapped:
        raise ValueError("CSV must contain an HR column (for example HR, Heart Rate, or Pulse).")

    rows = list(reader)
    parsed: list[tuple[float | None, float | None, dict[str, float | None]]] = []
    skipped = 0
    previous_timestamp: float | None = None
    previous_minute: float | None = None

    for row in rows:
        timestamp = _timestamp_seconds(row.get(mapped["timestamp"])) if "timestamp" in mapped else None
        minute = _number(row.get(mapped["minute"])) if "minute" in mapped else None
        values = {target: _number(row.get(column)) for target, column in mapped.items() if target not in {"timestamp", "minute"}}

        if values.get("MAP") is None or values.get("HR") is None:
            skipped += 1
            continue

        time_value = minute if minute is not None else timestamp
        if minute is not None:
            if previous_minute is not None and minute <= previous_minute:
                skipped += 1
                continue
            previous_minute = minute
        elif timestamp is not None:
            if previous_timestamp is not None and timestamp <= previous_timestamp:
                skipped += 1
                continue
            previous_timestamp = timestamp

        parsed.append((time_value, timestamp, values))

    if len(parsed) < 2:
        raise ValueError("At least two usable rows with MAP and HR are required. Check the required columns and numeric values.")

    if len(parsed) > 1200:
        step = (len(parsed) - 1) / 1199
        selected = [parsed[round(i * step)] for i in range(1200)]
        skipped += len(parsed) - len(selected)
        parsed = selected

    use_explicit_minute = "minute" in mapped and any(item[0] is not None for item in parsed)
    use_timestamp = not use_explicit_minute and "timestamp" in mapped and any(item[0] is not None for item in parsed)

    frames: list[TelemetryFrame] = []
    base = parsed[0][0] if (use_explicit_minute or use_timestamp) else None
    last_minute = -default_interval_seconds / 60.0

    for index, (time_value, timestamp, values) in enumerate(parsed):
        if (use_explicit_minute or use_timestamp) and time_value is not None and base is not None:
            minute_value = (time_value - base) / 60.0 if use_timestamp else time_value
        else:
            minute_value = index * default_interval_seconds / 60.0

        if minute_value <= last_minute:
            minute_value = last_minute + default_interval_seconds / 60.0
        last_minute = minute_value

        frame_timestamp = timestamp if use_timestamp and timestamp is not None else None
        frames.append(TelemetryFrame(
            timestamp=float(frame_timestamp) if frame_timestamp is not None else None,
            minute=round(float(minute_value), 4),
            MAP=values["MAP"],
            HR=values["HR"],
            SVV=values.get("SVV"),
            EtCO2=values.get("EtCO2"),
            SpO2=values.get("SpO2"),
            CVP=values.get("CVP"),
        ))

    intervals = [(frames[i].minute - frames[i - 1].minute) * 60 for i in range(1, len(frames)) if frames[i].minute > frames[i - 1].minute]
    interval = median(intervals) if intervals else default_interval_seconds
    interval = max(0.1, min(60.0, float(interval)))

    missing = [name for name in ("SVV", "EtCO2", "SpO2", "CVP") if name not in mapped]
    report = ReplayReport(
        patient_id=_safe_patient_id(patient_id),
        rows_read=len(rows),
        rows_used=len(frames),
        rows_skipped=skipped,
        sampling_interval_seconds=round(interval, 2),
        mapped_columns=mapped,
        missing_optional_signals=missing,
    )
    return PatientTelemetry(
        patient_id=_safe_patient_id(patient_id),
        sampling_interval_seconds=interval,
        telemetry=frames,
    ), report
