"""AHRS unit, disturbance, fallback, and performance checks."""

from __future__ import annotations

import math
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import config
from sensor_fusion.ahrs import AHRSManager, AHRSMode, RawIMUData
from sensor_fusion.quaternion import angular_difference_rad, from_euler_deg, multiply, normalize, to_euler_deg


def _raw(
    timestamp_ns: int,
    q=None,
    gyro=(0.0, 0.0, 0.0),
    accel=(0.0, 0.0, 9.80665),
    mag=(25.0, 0.0, 35.0),
) -> RawIMUData:
    try:
        euler = to_euler_deg(q) if q else (0.0, 0.0, 0.0)
    except ValueError:
        euler = (0.0, 0.0, 0.0)
    return RawIMUData(
        timestamp_ns=timestamp_ns,
        accel_mps2=accel,
        gyro_rads=gyro,
        mag_ut=mag,
        bno_quaternion_xyzw=(q[1], q[2], q[3], q[0]) if q else None,
        bno_accuracy_rad=0.05,
        calibration_status=3,
        roll_deg=euler[0],
        pitch_deg=euler[1],
        yaw_deg=euler[2],
    )


def test_quaternion() -> None:
    q = from_euler_deg(90.0, 0.0, 0.0)
    assert normalize((0.0, 0.0, 0.0, 0.0)) is None
    assert normalize((math.nan, 0.0, 0.0, 0.0)) is None
    assert angular_difference_rad(q, q) < 1e-9
    assert abs(to_euler_deg(q)[0] - 90.0) < 1e-6
    assert normalize(multiply((1.0, 0.0, 0.0, 0.0), q)) == q


def test_bno085_and_off_modes() -> None:
    t = time.monotonic_ns()
    q = from_euler_deg(4.0, -2.0, 30.0)
    manager = AHRSManager(mode=AHRSMode.BNO085, enabled=True)
    state = manager.update(_raw(t, q=q))
    assert state.valid and state.healthy
    assert state.source == "BNO085"
    assert abs(state.yaw_deg - 30.0) < 0.01

    off = AHRSManager(mode=AHRSMode.OFF, enabled=False)
    off_state = off.update(_raw(t, q=q))
    assert not off_state.enabled
    assert not off_state.valid
    assert off_state.source == "OFF"
    assert abs(off_state.roll_deg - 4.0) < 0.01


def test_software_filters_and_disturbances() -> None:
    start = time.monotonic_ns()
    for mode in (AHRSMode.MADGWICK, AHRSMode.MAHONY):
        manager = AHRSManager(mode=mode, enabled=True)
        manager.update(_raw(start))
        state = None
        for i in range(1, 101):
            state = manager.update(_raw(start + i * 10_000_000))
        assert state is not None and state.valid
        assert state.confidence == "GOOD"

        disturbed = manager.update(_raw(start + 102 * 10_000_000, accel=(0.0, 0.0, 19.6133)))
        assert disturbed.confidence == "DEGRADED"
        assert not disturbed.accel_correction_enabled


def test_yaw_motion_and_auto_fallback() -> None:
    start = time.monotonic_ns()
    manager = AHRSManager(mode=AHRSMode.MADGWICK, enabled=True)
    manager.update(_raw(start))
    for i in range(1, 101):
        manager.update(_raw(start + i * 10_000_000, gyro=(0.0, 0.0, math.radians(90.0))))
    roll, pitch, yaw = to_euler_deg(manager.last_state.quaternion)
    assert abs(roll) < 0.1
    assert abs(pitch) < 0.1
    assert 80.0 <= yaw <= 100.0

    config.AHRS_FAIL_COUNT_THRESHOLD = 2
    auto = AHRSManager(mode=AHRSMode.AUTO, enabled=True)
    q = from_euler_deg(0.0, 0.0, 10.0)
    assert auto.update(_raw(start, q=q)).source == "BNO085"
    auto.update(_raw(start + 10_000_000, q=(0.0, 0.0, 0.0, 0.0)))
    state = auto.update(_raw(start + 20_000_000, q=(0.0, 0.0, 0.0, 0.0)))
    assert state.source in {"MADGWICK", "BNO085"}


def benchmark_ahrs_updates(samples: int = 1000) -> dict[str, float]:
    start = time.monotonic_ns()
    manager = AHRSManager(mode=AHRSMode.MAHONY, enabled=True)
    durations = []
    for i in range(samples):
        raw = _raw(start + i * 10_000_000, gyro=(0.01, -0.02, 0.03))
        t0 = time.perf_counter_ns()
        manager.update(raw)
        durations.append((time.perf_counter_ns() - t0) / 1000.0)
    durations.sort()
    return {
        "mean_us": sum(durations) / len(durations),
        "p95_us": durations[int(0.95 * len(durations))],
        "p99_us": durations[int(0.99 * len(durations))],
        "max_us": max(durations),
    }


if __name__ == "__main__":
    test_quaternion()
    test_bno085_and_off_modes()
    test_software_filters_and_disturbances()
    test_yaw_motion_and_auto_fallback()
    print("AHRS tests passed.")
    print(benchmark_ahrs_updates())
