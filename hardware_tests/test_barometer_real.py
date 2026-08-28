"""
Real barometer test for the GARUDA HAT BMP388 SPI wiring.

Wiring from Schema_Draft_2.pdf:
  SCK_BMP  -> GPIO11 / physical pin 23
  MOSI_BMP -> GPIO10 / physical pin 19
  MISO_BMP -> GPIO9  / physical pin 21
  CS_BMP   -> GPIO8  / physical pin 24
  INT_BMP  -> GPIO17 / physical pin 11

Run from project root:
  python hardware_tests/test_barometer_real.py
"""

from __future__ import annotations

import sys
import time

from hw_common import banner, ensure_dirs, is_raspberry_pi, result, write_log

import config


def main() -> int:
    banner("Hardware Test: Real Barometer (BMP388 SPI)")
    ensure_dirs()
    log_lines: list[str] = []

    print("SPI bus:      SPI0")
    print(f"SCLK:         GPIO{config.SPI_SCLK_PIN} pin 23")
    print(f"MOSI:         GPIO{config.SPI_MOSI_PIN} pin 19")
    print(f"MISO:         GPIO{config.SPI_MISO_PIN} pin 21")
    print(f"CS_BMP:       GPIO{config.BMP388_CS_PIN} pin 24")
    print(f"INT_BMP:      GPIO{config.BMP388_INT_PIN} pin 11")
    print()

    if not is_raspberry_pi():
        result("WARNING", "Not running on Raspberry Pi - SPI sensor access will not work.")
        log_lines.append("WARNING: not on Pi")

    try:
        import board
        import busio
        import digitalio
        from adafruit_bmp3xx import BMP3XX_SPI
    except ImportError as exc:
        result("FAIL", f"Missing library: {exc}")
        print("Install: pip install adafruit-circuitpython-bmp3xx")
        write_log("test_barometer_real.log", [f"FAIL: import {exc}"])
        return 1

    try:
        spi = busio.SPI(board.SCK, MOSI=board.MOSI, MISO=board.MISO)
        cs = digitalio.DigitalInOut(config.BMP388_CS)
        sensor = BMP3XX_SPI(spi, cs)
        sensor.sea_level_pressure = 1013.25
    except Exception as exc:
        result("FAIL", f"Cannot initialize BMP388 over SPI: {exc}")
        write_log("test_barometer_real.log", [f"FAIL: init {exc}"])
        return 1

    try:
        for i in range(10):
            temperature = sensor.temperature
            pressure = sensor.pressure
            altitude = sensor.altitude
            line = (
                f"sample={i + 1} temp={temperature:.2f}C "
                f"pressure={pressure:.2f}hPa altitude={altitude:.2f}m"
            )
            print(line)
            log_lines.append(line)
            time.sleep(1.0)

        result("PASS", "BMP388 returned pressure/temperature readings over SPI.")
        log_lines.append("PASS")
        code = 0
    except Exception as exc:
        result("FAIL", f"BMP388 read error: {exc}")
        log_lines.append(f"FAIL: read {exc}")
        code = 1

    log_path = write_log("test_barometer_real.log", log_lines)
    print(f"Log saved: {log_path}")
    return code


if __name__ == "__main__":
    sys.exit(main())
