"""
Bench setup verification for GARUDA hardware, excluding GPS and camera.

This script keeps the mission state machine out of the loop and prints live
terminal readings for IMU, AHRS calculations, barometer, and gimbal/servo
commands. It continues after individual device failures so the whole setup can
be checked in one run.

Run from project root:
  python hardware_tests/setup_verify_no_gps_camera.py
"""

from __future__ import annotations

import argparse
import math
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from hw_common import banner, ensure_dirs, is_raspberry_pi, result, write_log

import config
from sensor_fusion.ahrs import AHRSManager, raw_from_reading


@dataclass
class DeviceHandle:
    name: str
    device: object | None
    ok: bool
    note: str


def scan_i2c() -> tuple[str, list[int]]:
    if not shutil.which("i2cdetect"):
        return "i2cdetect not found", []
    try:
        proc = subprocess.run(
            ["i2cdetect", "-y", "1"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except Exception as exc:
        return f"i2cdetect failed: {exc}", []

    output = proc.stdout + proc.stderr
    detected: list[int] = []
    for line in output.splitlines():
        for part in line.split()[1:]:
            if part not in ("--", "UU") and len(part) == 2:
                try:
                    detected.append(int(part, 16))
                except ValueError:
                    pass
    return output.strip(), sorted(set(detected))


def open_imu() -> DeviceHandle:
    try:
        from sensors.imu import create_imu

        return DeviceHandle("IMU/BNO085", create_imu(), True, "opened")
    except Exception as exc:
        return DeviceHandle("IMU/BNO085", None, False, str(exc))


def open_barometer() -> DeviceHandle:
    try:
        from sensors.barometer import create_barometer

        return DeviceHandle("Barometer/BMP388", create_barometer(), True, "opened")
    except Exception as exc:
        return DeviceHandle("Barometer/BMP388", None, False, str(exc))


def open_gimbal() -> DeviceHandle:
    try:
        from gimbal.servo_control import create_gimbal

        return DeviceHandle("Gimbal/PCA9685", create_gimbal(), True, "opened")
    except Exception as exc:
        return DeviceHandle("Gimbal/PCA9685", None, False, str(exc))


def close_device(handle: DeviceHandle) -> None:
    if handle.device is None:
        return
    close = getattr(handle.device, "close", None)
    if close is None:
        return
    try:
        close()
    except Exception:
        pass


def format_bool(value: bool) -> str:
    return "OK" if value else "BAD"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=float, default=30.0)
    parser.add_argument("--rate", type=float, default=2.0, help="Terminal print rate in Hz.")
    parser.add_argument("--mock", action="store_true", help="Use mock devices for a dry run.")
    parser.add_argument(
        "--no-servo-motion",
        action="store_true",
        help="Print calculated gimbal commands without moving servos.",
    )
    args = parser.parse_args()

    banner("GARUDA Setup Verify: sensors + gimbal, no GPS/camera")
    ensure_dirs()
    config.USE_MOCK_HARDWARE = bool(args.mock)
    config.ENABLE_GPS = False
    config.ENABLE_CAMERA = False
    config.PAUSE_STATE_TRANSITIONS = True

    log_lines: list[str] = [
        f"mock={config.USE_MOCK_HARDWARE}",
        "gps=disabled",
        "camera=disabled",
        "state_transitions=paused",
        f"calibration_file={config.SENSOR_CALIBRATION_PATH}",
    ]

    print(f"Mode:             {'MOCK' if config.USE_MOCK_HARDWARE else 'REAL HARDWARE'}")
    print("GPS:              skipped")
    print("Camera:           skipped")
    print("State machine:    paused")
    print(f"Print rate:       {args.rate:.2f} Hz")
    print(f"Duration:         {args.seconds:.1f} s")
    print()

    if not is_raspberry_pi() and not config.USE_MOCK_HARDWARE:
        result("WARNING", "Not running on Raspberry Pi - real GPIO/I2C/SPI access may fail.")

    print("I2C expectations:")
    print(f"  BNO085 IMU/AHRS:          0x{config.BNO085_I2C_ADDRESS:02X}")
    print(f"  PCA9685 servo controller: 0x{config.SERVO_CONTROLLER_ADDRESS:02X}")
    scan_output, detected = scan_i2c()
    if detected:
        detected_text = ", ".join(f"0x{addr:02X}" for addr in detected)
        result("PASS", f"I2C detected: {detected_text}")
    else:
        result("WARNING", "No I2C devices detected by scan.")
    log_lines.append("i2c_scan:")
    log_lines.extend(scan_output.splitlines() or ["no scan output"])
    print()

    imu = open_imu()
    barometer = open_barometer()
    gimbal = open_gimbal()
    for handle in (imu, barometer, gimbal):
        result("PASS" if handle.ok else "FAIL", f"{handle.name}: {handle.note}")
        log_lines.append(f"{handle.name}: {format_bool(handle.ok)} {handle.note}")
    print()

    manager = AHRSManager()
    period = 1.0 / max(0.1, args.rate)
    end_time = time.monotonic() + max(0.0, args.seconds)
    sample = 0
    failure_count = 0

    header = (
        "sample | imu | baro | ahrs | roll pitch yaw | "
        "gyro_dps xyz | accel xyz | mag xyz | baro_m hPa C | gimbal servo stepper"
    )
    print(header)
    print("-" * len(header))

    try:
        while time.monotonic() < end_time:
            sample += 1
            imu_ok = baro_ok = ahrs_ok = False
            roll = pitch = yaw = 0.0
            gyro = (0.0, 0.0, 0.0)
            accel = (0.0, 0.0, 0.0)
            mag = (0.0, 0.0, 0.0)
            altitude = pressure = temperature = float("nan")
            gimbal_servo = gimbal_stepper = 0.0

            if imu.device is not None:
                try:
                    reading = imu.device.read()
                    raw = raw_from_reading(reading)
                    state = manager.update(raw)
                    imu_ok = True
                    ahrs_ok = bool(state.valid)
                    roll, pitch, yaw = state.roll_deg, state.pitch_deg, state.yaw_deg
                    gyro = (state.gyro_x_dps, state.gyro_y_dps, state.gyro_z_dps)
                    accel = raw.accel_mps2 or accel
                    mag = raw.mag_ut or mag
                    gimbal_servo = max(
                        config.GIMBAL_SERVO_MIN,
                        min(
                            config.GIMBAL_SERVO_MAX,
                            config.GIMBAL_SERVO_CENTER + config.GIMBAL_SERVO_SIGN * pitch,
                        ),
                    )
                    gimbal_stepper = max(
                        config.GIMBAL_STEPPER_MIN_DEG,
                        min(
                            config.GIMBAL_STEPPER_MAX_DEG,
                            config.GIMBAL_STEPPER_HOME_DEG + config.GIMBAL_STEPPER_SIGN * roll,
                        ),
                    )
                except Exception as exc:
                    failure_count += 1
                    log_lines.append(f"sample {sample} imu read fail: {exc}")

            if barometer.device is not None:
                try:
                    baro = barometer.device.read()
                    baro_ok = True
                    altitude = float(baro.get("altitude", float("nan")))
                    pressure = float(baro.get("pressure", float("nan")))
                    temperature = float(baro.get("temperature", float("nan")))
                except Exception as exc:
                    failure_count += 1
                    log_lines.append(f"sample {sample} barometer read fail: {exc}")

            if gimbal.device is not None and not args.no_servo_motion:
                try:
                    sweep = math.sin(sample * 0.4)
                    if imu_ok:
                        command = gimbal.device.point_down(roll, pitch, period)
                    else:
                        gimbal.device.set_angles(8.0 * sweep, -8.0 * sweep)
                        command = {
                            "servo_angle_deg": config.GIMBAL_SERVO_CENTER + 8.0 * sweep,
                            "stepper_angle_deg": -8.0 * sweep,
                        }
                    gimbal_servo = command["servo_angle_deg"]
                    gimbal_stepper = command["stepper_angle_deg"]
                except Exception as exc:
                    failure_count += 1
                    log_lines.append(f"sample {sample} gimbal command fail: {exc}")

            line = (
                f"{sample:6d} | {format_bool(imu_ok):3s} | {format_bool(baro_ok):4s} | "
                f"{format_bool(ahrs_ok):4s} | "
                f"{roll:+6.2f} {pitch:+6.2f} {yaw:+6.2f} | "
                f"{gyro[0]:+7.2f} {gyro[1]:+7.2f} {gyro[2]:+7.2f} | "
                f"{accel[0]:+6.2f} {accel[1]:+6.2f} {accel[2]:+6.2f} | "
                f"{mag[0]:+6.2f} {mag[1]:+6.2f} {mag[2]:+6.2f} | "
                f"{altitude:7.2f} {pressure:7.2f} {temperature:6.2f} | "
                f"{gimbal_servo:+6.2f} {gimbal_stepper:+6.2f}"
            )
            print(line)
            log_lines.append(line)
            time.sleep(period)
    except KeyboardInterrupt:
        print("\nStopped by user.")
        log_lines.append("stopped by user")
    finally:
        for handle in (gimbal, barometer, imu):
            close_device(handle)

    log_path = write_log("setup_verify_no_gps_camera.log", log_lines)
    print()
    if imu.ok or barometer.ok or gimbal.ok:
        result("PASS" if failure_count == 0 else "WARNING", f"Setup verification finished; runtime read failures: {failure_count}")
        code = 0 if failure_count == 0 else 2
    else:
        result("FAIL", "No setup devices opened.")
        code = 1
    print(f"Log saved: {log_path}")
    return code


if __name__ == "__main__":
    sys.exit(main())
