"""
Stationary calibration for GARUDA IMU and barometer.

Keep the payload still and level while this runs. GPS and camera are not used.
The output JSON is loaded by the runtime when APPLY_SENSOR_CALIBRATION is True.

Run from project root:
  python hardware_tests/calibrate_sensors.py --seconds 30 --ground-altitude-m 0
"""

from __future__ import annotations

import argparse
import math
import statistics
import sys
import time
from pathlib import Path
from typing import Iterable

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from hw_common import banner, ensure_dirs, result, write_log

import config
from sensors.barometer import create_barometer
from sensors.calibration import save_calibration
from sensors.imu import create_imu


def mean_vector(samples: Iterable[tuple[float, float, float]]) -> tuple[float, float, float]:
    values = list(samples)
    if not values:
        return 0.0, 0.0, 0.0
    return tuple(sum(sample[i] for sample in values) / len(values) for i in range(3))


def min_vector(samples: Iterable[tuple[float, float, float]]) -> tuple[float, float, float]:
    values = list(samples)
    if not values:
        return 0.0, 0.0, 0.0
    return tuple(min(sample[i] for sample in values) for i in range(3))


def max_vector(samples: Iterable[tuple[float, float, float]]) -> tuple[float, float, float]:
    values = list(samples)
    if not values:
        return 0.0, 0.0, 0.0
    return tuple(max(sample[i] for sample in values) for i in range(3))


def norm(v: tuple[float, float, float]) -> float:
    return math.sqrt(sum(part * part for part in v))


def sea_level_pressure(pressure_hpa: float, altitude_m: float) -> float:
    pressure = float(pressure_hpa)
    if not config.BAROMETER_PRESSURE_MIN_HPA <= pressure <= config.BAROMETER_PRESSURE_MAX_HPA:
        raise ValueError(f"Cannot calibrate from invalid pressure: {pressure:.2f} hPa")
    sea_level = pressure / ((1.0 - altitude_m / 44330.0) ** 5.255)
    if not config.BAROMETER_SEA_LEVEL_MIN_HPA <= sea_level <= config.BAROMETER_SEA_LEVEL_MAX_HPA:
        raise ValueError(
            f"Calculated sea-level pressure outside safe range: {sea_level:.2f} hPa"
        )
    return sea_level


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=float, default=config.CALIBRATION_DEFAULT_SECONDS)
    parser.add_argument("--rate", type=float, default=config.CALIBRATION_SAMPLE_RATE_HZ)
    parser.add_argument("--ground-altitude-m", type=float, default=0.0)
    parser.add_argument("--mock", action="store_true")
    args = parser.parse_args()

    banner("GARUDA Sensor Calibration")
    ensure_dirs()
    config.USE_MOCK_HARDWARE = bool(args.mock)
    config.ENABLE_GPS = False
    config.ENABLE_CAMERA = False
    config.APPLY_SENSOR_CALIBRATION = False

    print("Keep payload still and level.")
    print(f"Duration: {args.seconds:.1f}s at {args.rate:.1f}Hz")
    print(f"Ground altitude: {args.ground_altitude_m:.2f}m")
    print()

    imu = None
    barometer = None
    log_lines: list[str] = []
    gyro_samples: list[tuple[float, float, float]] = []
    accel_samples: list[tuple[float, float, float]] = []
    mag_samples: list[tuple[float, float, float]] = []
    pressure_samples: list[float] = []
    temp_samples: list[float] = []
    calibration_statuses: list[int] = []

    try:
        try:
            imu = create_imu()
            result("PASS", "IMU opened.")
        except Exception as exc:
            result("FAIL", f"IMU open failed: {exc}")
            log_lines.append(f"IMU open failed: {exc}")

        try:
            barometer = create_barometer()
            result("PASS", "Barometer opened.")
        except Exception as exc:
            result("FAIL", f"Barometer open failed: {exc}")
            log_lines.append(f"Barometer open failed: {exc}")

        if imu is None and barometer is None:
            write_log("calibrate_sensors.log", log_lines)
            return 1

        period = 1.0 / max(0.1, args.rate)
        end_time = time.monotonic() + max(0.0, args.seconds)
        sample = 0
        while time.monotonic() < end_time:
            sample += 1
            line_parts = [f"sample={sample}"]
            if imu is not None:
                reading = imu.read()
                gyro = tuple(float(v) for v in reading.get("gyro_rads", (0.0, 0.0, 0.0)))
                accel = tuple(float(v) for v in reading.get("accel_mps2", (0.0, 0.0, 0.0)))
                mag = reading.get("mag_ut")
                gyro_samples.append(gyro)
                accel_samples.append(accel)
                if mag is not None:
                    mag_samples.append(tuple(float(v) for v in mag))
                try:
                    calibration_statuses.append(int(reading.get("calibration_status")))
                except (TypeError, ValueError):
                    pass
                line_parts.append(
                    "gyro_dps=({:+.2f},{:+.2f},{:+.2f}) accel=({:+.2f},{:+.2f},{:+.2f})".format(
                        math.degrees(gyro[0]),
                        math.degrees(gyro[1]),
                        math.degrees(gyro[2]),
                        accel[0],
                        accel[1],
                        accel[2],
                    )
                )
            if barometer is not None:
                reading = barometer.read()
                pressure = float(reading.get("pressure", 0.0))
                temp = float(reading.get("temperature", 0.0))
                altitude = float(reading.get("altitude", 0.0))
                pressure_samples.append(pressure)
                temp_samples.append(temp)
                line_parts.append(
                    f"baro={altitude:.2f}m {pressure:.2f}hPa {temp:.2f}C"
                )
            line = " | ".join(line_parts)
            print(line)
            log_lines.append(line)
            time.sleep(period)
    finally:
        if imu is not None:
            imu.close()
        if barometer is not None:
            barometer.close()

    gyro_bias = mean_vector(gyro_samples)
    accel_mean = mean_vector(accel_samples)
    mag_min = min_vector(mag_samples)
    mag_max = max_vector(mag_samples)
    mag_offset = tuple((mag_min[i] + mag_max[i]) * 0.5 for i in range(3))
    pressure_mean = statistics.fmean(pressure_samples) if pressure_samples else 0.0
    temp_mean = statistics.fmean(temp_samples) if temp_samples else 0.0
    try:
        sea_level_hpa = sea_level_pressure(pressure_mean, args.ground_altitude_m) if pressure_mean else 1013.25
    except ValueError as exc:
        result("FAIL", str(exc))
        write_log("calibrate_sensors.log", log_lines + [f"FAIL: {exc}"])
        return 1

    gyro_bias_dps = tuple(math.degrees(v) for v in gyro_bias)
    accel_norm = norm(accel_mean)
    gyro_stationary = max(abs(v) for v in gyro_bias_dps) <= config.CALIBRATION_STATIONARY_GYRO_MAX_DPS
    accel_ok = config.CALIBRATION_ACCEL_NORM_MIN <= accel_norm <= config.CALIBRATION_ACCEL_NORM_MAX

    data = {
        "created_at_unix": time.time(),
        "sample_count": {
            "imu": len(gyro_samples),
            "barometer": len(pressure_samples),
            "magnetometer": len(mag_samples),
        },
        "imu": {
            "gyro_bias_rads": list(gyro_bias),
            "gyro_bias_dps": list(gyro_bias_dps),
            "accel_level_mps2": list(accel_mean),
            "accel_level_norm_mps2": accel_norm,
            "mag_min_ut": list(mag_min),
            "mag_max_ut": list(mag_max),
            "mag_offset_ut": list(mag_offset),
            "last_bno_calibration_status": calibration_statuses[-1] if calibration_statuses else -1,
        },
        "barometer": {
            "ground_altitude_m": args.ground_altitude_m,
            "pressure_mean_hpa": pressure_mean,
            "temperature_mean_c": temp_mean,
            "sea_level_pressure_hpa": sea_level_hpa,
        },
    }
    saved_path = save_calibration(data)
    log_lines.append(f"saved={saved_path}")

    result("PASS" if gyro_stationary else "WARNING", f"Gyro bias dps: {gyro_bias_dps}")
    result("PASS" if accel_ok else "WARNING", f"Accel level norm: {accel_norm:.3f} m/s^2")
    result("PASS", f"Barometer sea-level pressure: {sea_level_hpa:.2f} hPa")
    result("PASS", f"Calibration saved: {saved_path}")
    log_path = write_log("calibrate_sensors.log", log_lines)
    print(f"Log saved: {log_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
