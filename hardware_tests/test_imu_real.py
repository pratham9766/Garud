"""
Real IMU test for the GARUDA HAT BNO085 SPI wiring.

Wiring from Schema_Draft_2.pdf:
  SCK_BNO  -> GPIO11 / physical pin 23
  MOSI_BNO -> GPIO10 / physical pin 19
  MISO_BNO -> GPIO9  / physical pin 21
  CS_BNO   -> GPIO5  / physical pin 29
  RST_BNO  -> GPIO6  / physical pin 31
  INT_BNO  -> GPIO27 / physical pin 13

Run from project root:
  python hardware_tests/test_imu_real.py
"""

from __future__ import annotations

import sys
import time

from hw_common import banner, ensure_dirs, is_raspberry_pi, result, write_log

import config


def main() -> int:
    banner("Hardware Test: Real IMU (BNO085 SPI)")
    ensure_dirs()
    log_lines: list[str] = []

    print("SPI bus:      SPI0")
    print(f"SCLK:         GPIO{config.SPI_SCLK_PIN} pin 23")
    print(f"MOSI:         GPIO{config.SPI_MOSI_PIN} pin 19")
    print(f"MISO:         GPIO{config.SPI_MISO_PIN} pin 21")
    print(f"CS_BNO:       GPIO{config.BNO085_CS_PIN} pin 29")
    print(f"RST_BNO:      GPIO{config.BNO085_RST_PIN} pin 31")
    print(f"INT_BNO:      GPIO{config.BNO085_INT_PIN} pin 13")
    print()

    if not is_raspberry_pi():
        result("WARNING", "Not running on Raspberry Pi - SPI sensor access will not work.")
        log_lines.append("WARNING: not on Pi")

    try:
        import board
        import busio
        import digitalio
        from adafruit_bno08x import BNO_REPORT_ACCELEROMETER, BNO_REPORT_GYROSCOPE
        from adafruit_bno08x.spi import BNO08X_SPI
    except ImportError as exc:
        result("FAIL", f"Missing library: {exc}")
        print("Install: pip install adafruit-circuitpython-bno08x")
        write_log("test_imu_real.log", [f"FAIL: import {exc}"])
        return 1

    try:
        spi = busio.SPI(board.SCK, MOSI=board.MOSI, MISO=board.MISO)
        cs = digitalio.DigitalInOut(board.D5)
        reset = digitalio.DigitalInOut(board.D6)
        interrupt = digitalio.DigitalInOut(board.D27)
        sensor = BNO08X_SPI(spi, cs, interrupt, reset)
        sensor.enable_feature(BNO_REPORT_ACCELEROMETER)
        sensor.enable_feature(BNO_REPORT_GYROSCOPE)
    except Exception as exc:
        result("FAIL", f"Cannot initialize BNO085 over SPI: {exc}")
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

        result("PASS", "BNO085 returned acceleration/gyro readings over SPI.")
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
