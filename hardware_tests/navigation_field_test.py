"""Field validation helper for the GARUDA navigation estimator.

Run on Raspberry Pi with real sensors:
  python hardware_tests/navigation_field_test.py --seconds 60

This script records raw GPS and estimated navigation scatter/drift evidence. It
does not command servos or modify guidance behavior.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
import statistics
import sys
import time

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import config
from core.shared_data import SharedData
from navigation.geo_utils import distance_m
from navigation.navigation_estimator import NavigationEstimator
from sensors.barometer import create_barometer
from sensors.gps import create_gps
from sensors.imu import create_imu
from sensor_fusion.ahrs import AHRSManager, raw_from_reading


def _read_or_none(device):
    try:
        return device.read()
    except Exception:
        return None


def _update_from_sensors(shared: SharedData, gps, barometer, imu, ahrs: AHRSManager) -> None:
    gps_reading = _read_or_none(gps)
    if gps_reading:
        shared.update(
            latitude=gps_reading.get("latitude", 0.0),
            longitude=gps_reading.get("longitude", 0.0),
            gps_altitude=gps_reading.get("altitude", 0.0),
            gps_ground_speed_mps=float(gps_reading.get("ground_speed_mps") or 0.0),
            gps_course_deg=float(gps_reading.get("course_deg") or 0.0),
            gps_satellites=int(gps_reading.get("satellites") or 0),
            gps_hdop=float(gps_reading.get("hdop") or 0.0),
            gps_fix_type=str(gps_reading.get("fix_type", "NO FIX")),
            gps_timestamp_ns=int(gps_reading.get("timestamp_ns") or time.monotonic_ns()),
            gps_ok=bool(gps_reading.get("fix_ok")),
        )

    baro_reading = _read_or_none(barometer)
    if baro_reading:
        shared.update(
            baro_altitude=baro_reading.get("altitude", 0.0),
            raw_baro_pressure_hpa=baro_reading.get("pressure", 0.0),
            raw_baro_temperature_c=baro_reading.get("temperature", 0.0),
            baro_timestamp_ns=int(baro_reading.get("timestamp_ns") or time.monotonic_ns()),
            barometer_ok=True,
        )

    imu_reading = _read_or_none(imu)
    if imu_reading:
        attitude = ahrs.update(raw_from_reading(imu_reading))
        shared.publish_attitude(attitude)
        shared.update(imu_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=float, default=60.0)
    parser.add_argument("--rate", type=float, default=config.NAVIGATION_RATE_HZ)
    parser.add_argument("--simulate-gps-loss-after", type=float, default=0.0)
    parser.add_argument("--simulate-gps-loss-seconds", type=float, default=0.0)
    parser.add_argument("--output", type=Path, default=config.LOG_SAVE_PATH / "hardware_tests" / "navigation_field_test.csv")
    args = parser.parse_args()

    config.USE_MOCK_HARDWARE = False
    shared = SharedData()
    estimator = NavigationEstimator()
    ahrs = AHRSManager()
    gps = create_gps()
    barometer = create_barometer()
    imu = create_imu()
    period = 1.0 / max(1.0, args.rate)
    deadline = time.monotonic() + args.seconds
    started = time.monotonic()
    args.output.parent.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, object]] = []
    try:
        while time.monotonic() < deadline:
            elapsed = time.monotonic() - started
            _update_from_sensors(shared, gps, barometer, imu, ahrs)
            if (
                args.simulate_gps_loss_after > 0.0
                and args.simulate_gps_loss_after <= elapsed < args.simulate_gps_loss_after + args.simulate_gps_loss_seconds
            ):
                shared.update(gps_ok=False, gps_timestamp_ns=time.monotonic_ns())
            state = estimator.update(shared.get_snapshot())
            shared.publish_navigation(state)
            snap = shared.get_snapshot()
            error_m = -1.0
            if snap.gps_ok and snap.navigation_valid:
                error_m = distance_m(snap.latitude, snap.longitude, snap.estimated_latitude, snap.estimated_longitude)
            row = {
                "elapsed_s": elapsed,
                "gps_latitude": snap.latitude,
                "gps_longitude": snap.longitude,
                "gps_speed_mps": snap.gps_ground_speed_mps,
                "gps_course_deg": snap.gps_course_deg,
                "gps_satellites": snap.gps_satellites,
                "gps_hdop": snap.gps_hdop,
                "estimated_latitude": snap.estimated_latitude,
                "estimated_longitude": snap.estimated_longitude,
                "estimated_ground_speed_mps": snap.estimated_ground_speed_mps,
                "estimated_course_deg": snap.estimated_course_deg,
                "estimated_heading_deg": snap.estimated_heading_deg,
                "navigation_mode": snap.navigation_mode,
                "position_quality": snap.position_quality,
                "gps_rejected": snap.nav_gps_rejected,
                "gps_rejection_reason": snap.nav_gps_rejection_reason,
                "dead_reckoning_age_s": snap.dead_reckoning_age_s,
                "safe_for_guidance": snap.safe_for_guidance,
                "gps_estimated_error_m": error_m,
            }
            rows.append(row)
            print(
                f"t={elapsed:6.1f}s raw=({snap.latitude:+.6f},{snap.longitude:+.6f}) "
                f"est=({snap.estimated_latitude:+.6f},{snap.estimated_longitude:+.6f}) "
                f"mode={snap.navigation_mode} gps={snap.nav_gps_valid} "
                f"err={error_m:.1f}m safe={snap.safe_for_guidance}"
            )
            time.sleep(period)
    finally:
        for device in (imu, barometer, gps):
            try:
                device.close()
            except Exception:
                pass

    if rows:
        with args.output.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        errors = [float(row["gps_estimated_error_m"]) for row in rows if float(row["gps_estimated_error_m"]) >= 0.0]
        if errors:
            print(
                "GPS-estimated error: "
                f"mean={statistics.fmean(errors):.2f}m "
                f"max={max(errors):.2f}m samples={len(errors)}"
            )
        print(f"Saved: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
