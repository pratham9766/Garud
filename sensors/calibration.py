"""Load and apply saved bench calibration offsets."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import config

Calibration = dict[str, Any]


def load_calibration(path: Path | None = None) -> Calibration:
    """Return calibration data, or an empty dict when no file is present."""
    calibration_path = path or config.SENSOR_CALIBRATION_PATH
    if not config.APPLY_SENSOR_CALIBRATION or not calibration_path.exists():
        return {}
    try:
        with open(calibration_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def save_calibration(data: Calibration, path: Path | None = None) -> Path:
    """Write calibration JSON and return the saved path."""
    calibration_path = path or config.SENSOR_CALIBRATION_PATH
    calibration_path.parent.mkdir(parents=True, exist_ok=True)
    with open(calibration_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)
        f.write("\n")
    return calibration_path


def _vector(data: Calibration, key: str) -> tuple[float, float, float] | None:
    values = data.get(key)
    if not isinstance(values, (list, tuple)) or len(values) != 3:
        return None
    try:
        return tuple(float(v) for v in values)
    except (TypeError, ValueError):
        return None


def apply_imu_calibration(reading: dict[str, Any], calibration: Calibration) -> dict[str, Any]:
    """Apply saved gyro and magnetometer offsets to one IMU reading."""
    imu_cal = calibration.get("imu", {})
    if not isinstance(imu_cal, dict):
        return reading

    adjusted = dict(reading)
    gyro_bias = _vector(imu_cal, "gyro_bias_rads")
    gyro = adjusted.get("gyro_rads")
    if gyro_bias is not None and gyro is not None:
        adjusted["gyro_rads"] = tuple(float(v) - gyro_bias[i] for i, v in enumerate(gyro))
        adjusted["gyro_x"] = math.degrees(adjusted["gyro_rads"][0])
        adjusted["gyro_y"] = math.degrees(adjusted["gyro_rads"][1])
        adjusted["gyro_z"] = math.degrees(adjusted["gyro_rads"][2])

    mag_offset = _vector(imu_cal, "mag_offset_ut")
    mag = adjusted.get("mag_ut")
    if mag_offset is not None and mag is not None:
        adjusted["mag_ut"] = tuple(float(v) - mag_offset[i] for i, v in enumerate(mag))

    return adjusted


def barometer_sea_level_pressure(calibration: Calibration) -> float | None:
    """Return saved sea-level pressure in hPa if available."""
    baro_cal = calibration.get("barometer", {})
    if not isinstance(baro_cal, dict):
        return None
    try:
        pressure = float(baro_cal["sea_level_pressure_hpa"])
    except (KeyError, TypeError, ValueError):
        return None
    if not config.BAROMETER_SEA_LEVEL_MIN_HPA <= pressure <= config.BAROMETER_SEA_LEVEL_MAX_HPA:
        return None
    return pressure
