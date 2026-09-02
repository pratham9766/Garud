"""Live terminal dashboard for manual GARUDA real sensor/AHRS verification."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import config
from core.shared_data import SharedData
from navigation.navigation_estimator import NavigationEstimator
from sensors.barometer import create_barometer
from sensors.gps import create_gps
from sensors.imu import create_imu
from sensor_fusion.ahrs import AHRSManager, AHRSMode, raw_from_reading
from telemetry.telemetry_packet import build_telemetry_packet


def _fmt_vec(values: tuple[float, ...] | None, precision: int = 3) -> str:
    if values is None:
        return "n/a"
    return "(" + ", ".join(f"{v:+.{precision}f}" for v in values) + ")"


def _safe_read(name: str, reader) -> tuple[dict[str, Any] | None, str]:
    try:
        return reader.read(), "OK"
    except Exception as exc:
        return None, f"ERR {type(exc).__name__}: {exc}"


def _print_dashboard(
    *,
    elapsed: float,
    mode: str,
    gps_status: str,
    baro_status: str,
    imu_status: str,
    gps: dict[str, Any] | None,
    baro: dict[str, Any] | None,
    imu: dict[str, Any] | None,
    shared: SharedData,
    manager: AHRSManager,
) -> None:
    snap = shared.get_snapshot()
    print("\033[2J\033[H", end="")
    print("GARUDA Live Sensor/AHRS Dashboard")
    print("=" * 72)
    print(f"mode={mode:<9} hardware=real  runtime={elapsed:7.1f}s  status={snap.status}")
    print(f"config: BNO085={config.BNO085_TRANSPORT}/0x{config.BNO085_I2C_ADDRESS:02X}  "
          f"BMP388_CS=GPIO{config.BMP388_CS_PIN}  AHRS_RATE={config.AHRS_RATE_HZ}Hz")
    print()

    print("GPS")
    print(f"  health: {gps_status}")
    if gps:
        print(
            f"  fix={gps.get('fix_ok')} lat={gps.get('latitude', 0.0):+.6f} "
            f"lon={gps.get('longitude', 0.0):+.6f} alt={gps.get('altitude', 0.0):.2f}m "
            f"speed={gps.get('ground_speed_mps')}m/s course={gps.get('course_deg')}deg "
            f"sats={gps.get('satellites')} hdop={gps.get('hdop')}"
        )
    print()

    print("Barometer")
    print(f"  health: {baro_status}")
    if baro:
        print(
            f"  altitude={baro.get('altitude', 0.0):.2f}m "
            f"pressure={baro.get('pressure', 0.0):.2f}hPa "
            f"temp={baro.get('temperature', 0.0):.2f}C"
        )
    print()

    print("Raw IMU / BNO085")
    print(f"  health: {imu_status}")
    if imu:
        print(f"  accel m/s2:       {_fmt_vec(imu.get('accel_mps2'))}")
        print(f"  linear accel m/s2:{_fmt_vec(imu.get('linear_accel_mps2'))}")
        print(f"  gyro rad/s:       {_fmt_vec(imu.get('gyro_rads'))}")
        print(f"  gyro deg/s:       ({imu.get('gyro_x', 0.0):+.2f}, {imu.get('gyro_y', 0.0):+.2f}, {imu.get('gyro_z', 0.0):+.2f})")
        print(f"  mag uT:           {_fmt_vec(imu.get('mag_ut'))}")
        print(f"  native quat xyzw: {_fmt_vec(imu.get('quaternion'), 5)}")
        print(
            f"  calc r/p/y deg:   ({imu.get('roll', 0.0):+.2f}, "
            f"{imu.get('pitch', 0.0):+.2f}, {imu.get('yaw', 0.0):.2f})"
        )
        print(f"  accuracy_rad={imu.get('accuracy_rad')} calibration={imu.get('calibration_status')}")
    print()

    print("AHRS")
    print(
        f"  source={snap.ahrs_source} valid={snap.ahrs_valid} healthy={snap.ahrs_healthy} "
        f"confidence={snap.ahrs_confidence}"
    )
    print(
        f"  quat wxyz: ({snap.quat_w:+.5f}, {snap.quat_x:+.5f}, "
        f"{snap.quat_y:+.5f}, {snap.quat_z:+.5f})"
    )
    print(
        f"  roll={snap.ahrs_roll:+.2f} deg  pitch={snap.ahrs_pitch:+.2f} deg  "
        f"yaw={snap.ahrs_yaw:.2f} deg"
    )
    print(
        f"  sample_age={snap.imu_sample_age_ms:.1f}ms  "
        f"accel_corr={snap.accel_correction_active}  mag_corr={snap.mag_correction_active}"
    )
    print(
        "  diag: "
        f"rx={manager.diagnostics.received_samples} rejected={manager.diagnostics.rejected_samples} "
        f"stale={manager.diagnostics.stale_samples} source_changes={manager.diagnostics.source_changes}"
    )
    print()

    print("Telemetry Preview")
    print(f"  {build_telemetry_packet(snap)}")
    print()

    print("Estimated Navigation")
    print(
        f"  mode={snap.navigation_mode} valid={snap.navigation_valid} safe_for_guidance={snap.safe_for_guidance} "
        f"source={snap.position_source}"
    )
    print(
        f"  est lat/lon=({snap.estimated_latitude:+.7f}, {snap.estimated_longitude:+.7f}) "
        f"N/E=({snap.estimated_north_m:+.2f}, {snap.estimated_east_m:+.2f})m"
    )
    print(
        f"  VN/VE=({snap.estimated_velocity_north_mps:+.2f}, {snap.estimated_velocity_east_mps:+.2f})m/s "
        f"gs={snap.estimated_ground_speed_mps:.2f}m/s course={snap.estimated_course_deg:.1f}deg "
        f"heading={snap.estimated_heading_deg:.1f}deg"
    )
    print(
        f"  alt={snap.estimated_altitude_m:.2f}m agl~={snap.estimated_agl_m:.2f}m "
        f"quality pos/head/alt={snap.position_quality}/{snap.heading_quality}/{snap.altitude_quality}"
    )
    print(
        f"  gps_valid={snap.nav_gps_valid} rejected={snap.nav_gps_rejected} "
        f"reason={snap.nav_gps_rejection_reason} gps_age={snap.nav_gps_age_ms:.1f}ms "
        f"gps_error={snap.nav_gps_position_error_m:.2f}m"
    )
    print(
        f"  dead_reckoning={snap.dead_reckoning_active} age={snap.dead_reckoning_age_s:.2f}s "
        f"recovery={snap.recovery_active}"
    )
    print()
    print("Ctrl+C to stop. This dashboard reads sensors only; it does not move servos.")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=[m.value.lower() for m in AHRSMode], default=config.AHRS_MODE.lower())
    parser.add_argument("--rate", type=float, default=2.0, help="Terminal refresh rate in Hz.")
    parser.add_argument("--duration", type=float, default=0.0, help="Optional run duration in seconds; 0 runs until Ctrl+C.")
    args = parser.parse_args()

    config.USE_MOCK_HARDWARE = False
    mode = args.mode.upper()
    manager = AHRSManager(mode=mode, enabled=mode != "OFF")
    nav = NavigationEstimator()
    shared = SharedData()

    gps = create_gps()
    baro = create_barometer()
    imu = create_imu()
    period = 1.0 / max(0.2, args.rate)
    started = time.monotonic()
    end_time = None if args.duration <= 0 else started + args.duration

    try:
        while True:
            if end_time is not None and time.monotonic() >= end_time:
                return 0
            gps_reading, gps_status = _safe_read("gps", gps)
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

            baro_reading, baro_status = _safe_read("barometer", baro)
            if baro_reading:
                shared.update(
                    baro_altitude=baro_reading.get("altitude", 0.0),
                    raw_baro_pressure_hpa=baro_reading.get("pressure", 0.0),
                    raw_baro_temperature_c=baro_reading.get("temperature", 0.0),
                    baro_timestamp_ns=int(baro_reading.get("timestamp_ns") or time.monotonic_ns()),
                    barometer_ok=True,
                )

            imu_reading, imu_status = _safe_read("imu", imu)
            if imu_reading:
                raw = raw_from_reading(imu_reading)
                attitude = manager.update(raw)
                shared.publish_attitude(attitude)
                shared.update(imu_ok=True)

            shared.publish_navigation(nav.update(shared.get_snapshot()))

            _print_dashboard(
                elapsed=time.monotonic() - started,
                mode=mode,
                gps_status=gps_status,
                baro_status=baro_status,
                imu_status=imu_status,
                gps=gps_reading,
                baro=baro_reading,
                imu=imu_reading,
                shared=shared,
                manager=manager,
            )
            time.sleep(period)
    except KeyboardInterrupt:
        print("\nStopping live dashboard.")
        return 0
    finally:
        for device in (imu, baro, gps):
            try:
                device.close()
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
