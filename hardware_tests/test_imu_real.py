"""
Real IMU test for the GARUDA HAT BNO085 I2C wiring.

Wiring from Schema_Draft_2.pdf:
  SDA_BNO -> GPIO2 / physical pin 3
  SCL_BNO -> GPIO3 / physical pin 5
  ADDR    -> 0x4A by default

Run from project root:
  python hardware_tests/test_imu_real.py
"""

from __future__ import annotations

import sys
import time

from hw_common import banner, ensure_dirs, is_raspberry_pi, result, write_log

import config


def main() -> int:
    banner("Hardware Test: Real IMU (BNO085 I2C)")
    ensure_dirs()
    log_lines: list[str] = []

    print("I2C bus:      I2C1")
    print(f"SDA:          GPIO{config.I2C_SDA_PIN} pin 3")
    print(f"SCL:          GPIO{config.I2C_SCL_PIN} pin 5")
    print(f"Address:      0x{config.BNO085_I2C_ADDRESS:02X}")
    print()

    if not is_raspberry_pi():
        result("WARNING", "Not running on Raspberry Pi - I2C sensor access will not work.")
        log_lines.append("WARNING: not on Pi")

    try:
        import board
        import busio
        from adafruit_bno08x import BNO_REPORT_ACCELEROMETER, BNO_REPORT_GYROSCOPE
        from adafruit_bno08x.i2c import BNO08X_I2C
    except ImportError as exc:
        result("FAIL", f"Missing library: {exc}")
        print("Install: pip install adafruit-circuitpython-bno08x")
        write_log("test_imu_real.log", [f"FAIL: import {exc}"])
        return 1

    try:
        i2c = busio.I2C(config.I2C_SCL, config.I2C_SDA)
        sensor = BNO08X_I2C(i2c, address=config.BNO085_I2C_ADDRESS)
        sensor.enable_feature(BNO_REPORT_ACCELEROMETER)
        sensor.enable_feature(BNO_REPORT_GYROSCOPE)
    except Exception as exc:
        result("FAIL", f"Cannot initialize BNO085 over I2C: {exc}")
        write_log("test_imu_real.log", [f"FAIL: init {exc}"])
        return 1

    try:
        for i in range(10):
            ax, ay, az = sensor.acceleration
            gx, gy, gz = sensor.gyro
            line = (
                f"sample={i + 1} accel=({ax:.3f},{ay:.3f},{az:.3f})m/s^2 "
                f"gyro=({gx:.3f},{gy:.3f},{gz:.3f})rad/s"
            )
            print(line)
            log_lines.append(line)
            time.sleep(1.0)

        result("PASS", "BNO085 returned acceleration/gyro readings over I2C.")
        log_lines.append("PASS")
        code = 0
    except Exception as exc:
        result("FAIL", f"BNO085 read error: {exc}")
        log_lines.append(f"FAIL: read {exc}")
        code = 1

    log_path = write_log("test_imu_real.log", log_lines)
    print(f"Log saved: {log_path}")
    return code


if __name__ == "__main__":
    sys.exit(main())
