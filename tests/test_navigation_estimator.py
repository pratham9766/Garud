"""Tests for the lightweight navigation estimator."""

from __future__ import annotations

import math
from pathlib import Path
import sys
import time

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import config
from core.shared_data import PayloadSnapshot, SharedData
from navigation.geo_utils import (
    angle_diff_deg,
    geodetic_to_local,
    local_to_geodetic,
    velocity_from_speed_course,
)
from navigation.gps_validator import GPSMeasurement, GPSValidator
from navigation.navigation_estimator import NavigationEstimator


BASE_NS = 1_000_000_000_000
LAT0 = 18.5204
LON0 = 73.8567


def gps_sample(
    *,
    lat: float = LAT0,
    lon: float = LON0,
    altitude: float = 100.0,
    speed: float = 10.0,
    course: float = 90.0,
    fix: bool = True,
    sats: int = 10,
    hdop: float = 1.0,
    t_ns: int = BASE_NS,
) -> PayloadSnapshot:
    snap = PayloadSnapshot()
    snap.latitude = lat
    snap.longitude = lon
    snap.gps_altitude = altitude
    snap.gps_ground_speed_mps = speed
    snap.gps_course_deg = course
    snap.gps_ok = fix
    snap.gps_fix_type = "3D" if fix else "NO FIX"
    snap.gps_satellites = sats
    snap.gps_hdop = hdop
    snap.gps_timestamp_ns = t_ns
    snap.baro_altitude = altitude - 5.0
    snap.baro_timestamp_ns = t_ns
    snap.barometer_ok = True
    snap.ahrs_yaw = 135.0
    snap.ahrs_valid = True
    snap.ahrs_healthy = True
    snap.ahrs_timestamp_ns = t_ns
    return snap


def update_shared(shared: SharedData, snap: PayloadSnapshot) -> None:
    shared.update(
        latitude=snap.latitude,
        longitude=snap.longitude,
        gps_altitude=snap.gps_altitude,
        gps_ground_speed_mps=snap.gps_ground_speed_mps,
        gps_course_deg=snap.gps_course_deg,
        gps_satellites=snap.gps_satellites,
        gps_hdop=snap.gps_hdop,
        gps_fix_type=snap.gps_fix_type,
        gps_timestamp_ns=snap.gps_timestamp_ns,
        gps_ok=snap.gps_ok,
        baro_altitude=snap.baro_altitude,
        baro_timestamp_ns=snap.baro_timestamp_ns,
        barometer_ok=snap.barometer_ok,
        ahrs_yaw=snap.ahrs_yaw,
        ahrs_valid=snap.ahrs_valid,
        ahrs_healthy=snap.ahrs_healthy,
        ahrs_timestamp_ns=snap.ahrs_timestamp_ns,
    )


def make_validator() -> GPSValidator:
    return GPSValidator(
        min_satellites=config.NAV_MIN_SATELLITES,
        max_hdop=config.NAV_MAX_HDOP,
        max_age_ms=config.NAV_MAX_GPS_AGE_MS,
        max_plausible_speed_mps=config.NAV_MAX_PLAUSIBLE_SPEED_MPS,
        max_absolute_jump_m=config.NAV_MAX_ABSOLUTE_GPS_JUMP_M,
    )


def test_geo_round_trip_and_course_velocity() -> None:
    north, east = geodetic_to_local(LAT0 + 0.001, LON0 + 0.001, LAT0, LON0)
    lat, lon = local_to_geodetic(north, east, LAT0, LON0)
    assert abs(lat - (LAT0 + 0.001)) < 1e-7
    assert abs(lon - (LON0 + 0.001)) < 1e-7
    vn, ve = velocity_from_speed_course(10.0, 90.0)
    assert abs(vn) < 1e-9
    assert abs(ve - 10.0) < 1e-9
    assert abs(angle_diff_deg(1.0, 359.0) - 2.0) < 1e-9


def test_gps_validator_rejects_bad_samples() -> None:
    validator = make_validator()
    good = GPSMeasurement(LAT0, LON0, 100.0, True, "3D", 10, 1.0, 8.0, 90.0, BASE_NS)
    assert validator.validate(good, now_ns=BASE_NS, last_good=None).valid

    assert validator.validate(
        GPSMeasurement(float("nan"), LON0, 100.0, True, "3D", 10, 1.0, 8.0, 90.0, BASE_NS + 1),
        now_ns=BASE_NS + 1,
        last_good=None,
    ).reason == "GPS_INVALID_LAT_LON"
    assert validator.validate(
        GPSMeasurement(LAT0, LON0, 100.0, True, "3D", 2, 1.0, 8.0, 90.0, BASE_NS + 1),
        now_ns=BASE_NS + 1,
        last_good=None,
    ).reason == "GPS_LOW_SATELLITES"
    assert validator.validate(
        GPSMeasurement(LAT0, LON0, 100.0, True, "3D", 10, 99.0, 8.0, 90.0, BASE_NS + 1),
        now_ns=BASE_NS + 1,
        last_good=None,
    ).reason == "GPS_BAD_HDOP"

    jump = GPSMeasurement(LAT0 + 0.003, LON0, 100.0, True, "3D", 10, 1.0, 8.0, 90.0, BASE_NS + 200_000_000)
    assert validator.validate(jump, now_ns=BASE_NS + 200_000_000, last_good=good).reason in {
        "GPS_ABSOLUTE_JUMP",
        "GPS_IMPLIED_SPEED_IMPLAUSIBLE",
    }
    assert validator.validate(
        GPSMeasurement(LAT0, LON0, 100.0, True, "3D", 10, 1.0, 8.0, 90.0, BASE_NS),
        now_ns=BASE_NS,
        last_good=good,
    ).reason == "GPS_DUPLICATE_TIMESTAMP"


def test_navigation_accepts_native_velocity_and_keeps_heading_separate() -> None:
    estimator = NavigationEstimator()
    for i in range(config.NAV_GPS_GOOD_COUNT_TO_RECOVER + 1):
        state = estimator.update(gps_sample(course=60.0, speed=12.0, t_ns=BASE_NS + i * 500_000_000), now_ns=BASE_NS + i * 500_000_000)
    assert state.navigation_mode == "GOOD"
    assert abs(state.estimated_ground_speed_mps - 12.0) < 1.0
    assert abs(state.estimated_course_deg - 60.0) < 8.0
    assert abs(angle_diff_deg(state.estimated_heading_deg, 135.0)) < 10.0
    assert abs(angle_diff_deg(state.estimated_heading_deg, state.estimated_course_deg)) > 30.0


def test_single_bad_gps_degrades_without_lost() -> None:
    estimator = NavigationEstimator()
    for i in range(4):
        estimator.update(gps_sample(t_ns=BASE_NS + i * 500_000_000), now_ns=BASE_NS + i * 500_000_000)
    bad = gps_sample(fix=False, t_ns=BASE_NS + 2_500_000_000)
    state = estimator.update(bad, now_ns=BASE_NS + 2_500_000_000)
    assert state.navigation_mode == "DEGRADED"
    assert state.dead_reckoning_active
    assert state.navigation_valid


def test_repeated_gps_failure_enters_lost_then_unreliable() -> None:
    estimator = NavigationEstimator()
    for i in range(4):
        estimator.update(gps_sample(t_ns=BASE_NS + i * 500_000_000), now_ns=BASE_NS + i * 500_000_000)
    state = None
    t_ns = BASE_NS + 2_500_000_000
    for i in range(config.NAV_GPS_REJECT_COUNT_TO_LOST):
        t_ns += 500_000_000
        state = estimator.update(gps_sample(fix=False, t_ns=t_ns), now_ns=t_ns)
    assert state is not None
    assert state.navigation_mode in {"GPS_LOST", "UNRELIABLE"}

    timeout_ns = t_ns + int((config.NAV_DEAD_RECKON_MAX_SEC + 0.5) * 1_000_000_000)
    state = estimator.update(gps_sample(fix=False, t_ns=timeout_ns), now_ns=timeout_ns)
    assert state.navigation_mode == "UNRELIABLE"
    assert not state.safe_for_guidance


def test_gps_recovery_requires_multiple_good_samples() -> None:
    estimator = NavigationEstimator()
    for i in range(4):
        estimator.update(gps_sample(t_ns=BASE_NS + i * 500_000_000), now_ns=BASE_NS + i * 500_000_000)
    t_ns = BASE_NS + 2_500_000_000
    for _ in range(config.NAV_GPS_REJECT_COUNT_TO_LOST + 1):
        t_ns += 500_000_000
        estimator.update(gps_sample(fix=False, t_ns=t_ns), now_ns=t_ns)

    t_ns += 500_000_000
    one_good = estimator.update(gps_sample(t_ns=t_ns), now_ns=t_ns)
    assert one_good.navigation_mode == "RECOVERING"
    assert one_good.recovery_active

    for _ in range(config.NAV_GPS_GOOD_COUNT_TO_RECOVER + 2):
        t_ns += 500_000_000
        state = estimator.update(gps_sample(t_ns=t_ns), now_ns=t_ns)
    assert state.navigation_mode in {"GOOD", "RECOVERING"}


def test_baro_and_ahrs_failures_are_independent() -> None:
    estimator = NavigationEstimator()
    state = None
    for i in range(4):
        snap = gps_sample(t_ns=BASE_NS + i * 500_000_000)
        snap.barometer_ok = False
        snap.ahrs_healthy = False
        snap.ahrs_valid = False
        state = estimator.update(snap, now_ns=snap.gps_timestamp_ns)
    assert state is not None
    assert state.position_quality == "GOOD"
    assert state.altitude_quality == "DEGRADED"
    assert state.heading_quality == "GPS_COURSE"


def test_shared_navigation_publication_is_atomic() -> None:
    shared = SharedData()
    estimator = NavigationEstimator()
    for i in range(4):
        snap = gps_sample(t_ns=BASE_NS + i * 500_000_000)
        update_shared(shared, snap)
        shared.publish_navigation(estimator.update(shared.get_snapshot(), now_ns=snap.gps_timestamp_ns))
    snap = shared.get_snapshot()
    assert snap.navigation_mode == "GOOD"
    assert snap.estimated_latitude != 0.0
    assert "estimated_latitude" in SharedData.CSV_HEADER


def test_navigation_benchmark_10000_updates() -> None:
    estimator = NavigationEstimator()
    lat = LAT0
    lon = LON0
    durations_ns: list[int] = []
    now = BASE_NS
    for i in range(10_000):
        if i % 10 == 0:
            lon += 0.000005
            gps_t = now
        else:
            gps_t = now - (i % 10) * 50_000_000
        snap = gps_sample(lat=lat, lon=lon, speed=5.0, course=90.0, t_ns=gps_t)
        start = time.perf_counter_ns()
        estimator.update(snap, now_ns=now)
        durations_ns.append(time.perf_counter_ns() - start)
        now += 50_000_000
    durations = sorted(durations_ns)
    mean_ms = sum(durations_ns) / len(durations_ns) / 1_000_000.0
    p95_ms = durations[int(len(durations) * 0.95)] / 1_000_000.0
    p99_ms = durations[int(len(durations) * 0.99)] / 1_000_000.0
    max_ms = durations[-1] / 1_000_000.0
    print(
        {
            "mean_ms": mean_ms,
            "p95_ms": p95_ms,
            "p99_ms": p99_ms,
            "max_ms": max_ms,
        }
    )
    assert mean_ms < 0.2
    assert p99_ms < 1.0


def test_realistic_mission_sequence_with_glitches_and_crosswind() -> None:
    estimator = NavigationEstimator()
    now = BASE_NS
    lat = LAT0
    lon = LON0
    max_jump_m = 0.0

    for i in range(80):
        now += 500_000_000
        if 25 <= i < 32:
            snap = gps_sample(lat=lat, lon=lon, speed=16.0, course=60.0, fix=False, t_ns=now)
        elif i == 38:
            snap = gps_sample(lat=lat + 0.01, lon=lon + 0.01, speed=250.0, course=60.0, t_ns=now)
        else:
            lon += 0.000012
            snap = gps_sample(lat=lat, lon=lon, speed=16.0, course=60.0, t_ns=now)
        snap.ahrs_yaw = 95.0
        snap.baro_altitude = max(0.0, 250.0 - i * 2.5)
        state = estimator.update(snap, now_ns=now)
        if state.estimated_latitude and state.estimated_longitude:
            raw_error = abs(state.estimated_longitude - LON0)
            max_jump_m = max(max_jump_m, raw_error * 111_320.0)
        assert math.isfinite(state.estimated_latitude)
        assert math.isfinite(state.estimated_longitude)
        assert abs(angle_diff_deg(state.estimated_heading_deg, state.estimated_course_deg)) > 10.0 or not state.navigation_valid

    assert max_jump_m < 500.0
    assert state.navigation_mode in {"GOOD", "RECOVERING", "DEGRADED"}


if __name__ == "__main__":
    test_geo_round_trip_and_course_velocity()
    test_gps_validator_rejects_bad_samples()
    test_navigation_accepts_native_velocity_and_keeps_heading_separate()
    test_single_bad_gps_degrades_without_lost()
    test_repeated_gps_failure_enters_lost_then_unreliable()
    test_gps_recovery_requires_multiple_good_samples()
    test_baro_and_ahrs_failures_are_independent()
    test_shared_navigation_publication_is_atomic()
    test_navigation_benchmark_10000_updates()
    test_realistic_mission_sequence_with_glitches_and_crosswind()
    print("[OK] navigation estimator tests")
