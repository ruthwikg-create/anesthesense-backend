from __future__ import annotations

from dataclasses import dataclass
from statistics import mean, pstdev


@dataclass(frozen=True)
class ForecastResult:
    predicted_map_10min: float
    predicted_map_15min: float
    map_slope_per_min: float
    map_acceleration_per_min2: float
    trend_strength: float
    volatility: float
    hypotension_probability: float
    trajectory: str


def _slope(values: list[float], minutes: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    xm, ym = mean(minutes), mean(values)
    den = sum((x - xm) ** 2 for x in minutes)
    return sum((x - xm) * (y - ym) for x, y in zip(minutes, values)) / den if den else 0.0


def _linear_prediction(current: float, slope: float, horizon: float) -> float:
    return max(30.0, min(140.0, current + slope * horizon))


def forecast_map(maps: list[float], minutes: list[float]) -> ForecastResult:
    if not maps:
        raise ValueError("At least one MAP value is required.")

    slope = _slope(maps, minutes)
    midpoint = max(1, len(maps) // 2)
    first_slope = _slope(maps[:midpoint], minutes[:midpoint]) if midpoint >= 2 else slope
    second_slope = _slope(maps[midpoint:], minutes[midpoint:]) if len(maps[midpoint:]) >= 2 else slope
    acceleration = second_slope - first_slope

    current = maps[-1]
    p10 = _linear_prediction(current, slope, 10)
    p15 = _linear_prediction(current, slope + 0.35 * acceleration, 15)

    volatility = pstdev(maps) if len(maps) > 1 else 0.0
    fitted = [mean(maps) + slope * (m - mean(minutes)) for m in minutes]
    ss_tot = sum((v - mean(maps)) ** 2 for v in maps)
    ss_res = sum((v - f) ** 2 for v, f in zip(maps, fitted))
    trend_strength = max(0.0, min(1.0, 1.0 - ss_res / ss_tot)) if ss_tot else 1.0

    # This is a transparent prototype probability, not a calibrated clinical probability.
    probability = (
        0.55 * max(0.0, min(1.0, (65.0 - p15) / 20.0))
        + 0.25 * max(0.0, min(1.0, -slope / 2.0))
        + 0.20 * max(0.0, min(1.0, (65.0 - current) / 15.0))
    )
    probability = round(max(0.0, min(0.99, probability)), 3)

    if p15 < 60:
        trajectory = "CRITICAL_DECLINE"
    elif p15 < 65:
        trajectory = "HIGH_RISK_DECLINE"
    elif slope < -0.25:
        trajectory = "DECLINING"
    elif slope > 0.25:
        trajectory = "RECOVERING"
    else:
        trajectory = "STABLE"

    return ForecastResult(
        predicted_map_10min=round(p10, 1),
        predicted_map_15min=round(p15, 1),
        map_slope_per_min=round(slope, 3),
        map_acceleration_per_min2=round(acceleration, 4),
        trend_strength=round(trend_strength, 3),
        volatility=round(volatility, 3),
        hypotension_probability=probability,
        trajectory=trajectory,
    )
