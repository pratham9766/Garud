"""
Real barometer test (BMP280 / BMP388 style).

Wiring (I2C):
  VCC -> 3.3V (pin 1)
  GND -> GND (pin 6)
  SDA -> GPIO2 (pin 3)
  SCL -> GPIO3 (pin 5)

Run from project root:
  python hardware_tests/test_barometer_real.py
"""

from __future__ import annotations

import sys
import time

from hw_common import banner, ensure_dirs, result, write_log

import config


def main() -> int:
    banner("Hardware Test: Real Barometer (BMP280 family)")
    ensure_dirs()
    log_lines: list[str] = []

    print("I2C bus:     1 (SDA=GPIO2 pin 3, SCL=GPIO3 pin 5)")
    print(f"I2C address: 0x{config.BAROMETER_ADDRESS:02X} (also try 0x77)")
    print("Samples:     20")
    print()

    sensor = None
    backend = ""

    # --- Try adafruit_bmp280 (BMP280) ---
    try:
        import board
        import busio
        import adafruit_bmp280

        i2c = busio.I2C(board.SCL, board.SDA)
        try:
            sensor = adafruit_bmp280.Adafruit_BMP280_I2C(i2c, address=config.BAROMETER_ADDRESS)
            backend = "adafruit_bmp280"
        except ValueError:
            alt = 0x77 if config.BAROMETER_ADDRESS == 0x76 else 0x76
            sensor = adafruit_bmp280.Adafruit_BMP280_I2C(i2c, address=alt)
            backend = f"adafruit_bmp280 (alt 0x{alt:02X})"
    except ImportError:
        result("WARNING", "adafruit_bmp280 not installed.")
        print("Install: pip install adafruit-circuitpython-bmp280 adafruit-blinka")
        log_lines.append("Library missing")
    except Exception as exc:
        result("WARNING", f"adafruit_bmp280 init failed: {exc}")
        log_lines.append(f"init fail: {exc}")

    if sensor is None:
        result("FAIL", "Barometer not found on I2C bus.")
        print("Run: python hardware_tests/test_i2c_scan.py")
        write_log("test_barometer_real.log", log_lines + ["FAIL: sensor not found"])
        return 1

    result("INFO", f"Using backend: {backend}")
    log_lines.append(f"Backend: {backend}")

    # Sea-level pressure for altitude estimate (hPa)
    if hasattr(sensor, "sea_level_pressure"):
        sensor.sea_level_pressure = 1013.25

    temps: list[float] = []
    pressures: list[float] = []
    altitudes: list[float] = []

    try:
        for i in range(20):
            temp = float(sensor.temperature)
            pressure = float(sensor.pressure)
            altitude = float(sensor.altitude) if hasattr(sensor, "altitude") else 0.0

            temps.append(temp)
            pressures.append(pressure)
            altitudes.append(altitude)

            line = (
                f"[{i + 1:02d}] T={temp:.1f}°C  P={pressure:.1f} hPa  Alt={altitude:.1f} m"
            )
            print(line)
            log_lines.append(line)
            time.sleep(0.2)

    except Exception as exc:
        result("FAIL", f"Read error: {exc}")
        write_log("test_barometer_real.log", log_lines + [f"FAIL: {exc}"])
        return 1

    alt_min, alt_max = min(altitudes), max(altitudes)
    alt_avg = sum(altitudes) / len(altitudes)
    p_avg = sum(pressures) / len(pressures)

    print()
    print(f"Altitude  min={alt_min:.1f} m  max={alt_max:.1f} m  avg={alt_avg:.1f} m")
    print(f"Pressure  avg={p_avg:.1f} hPa")
    log_lines.append(f"Summary: alt min/max/avg={alt_min}/{alt_max}/{alt_avg} p_avg={p_avg}")

    if 300 < p_avg < 1100 and -500 < alt_avg < 10000:
        result("PASS", "Pressure and altitude readings look valid.")
        log_lines.append("PASS")
        code = 0
    else:
        result("WARNING", "Readings received but values look unusual — verify sensor.")
        log_lines.append("WARNING: unusual values")
        code = 2

    log_path = write_log("test_barometer_real.log", log_lines)
    print(f"Log saved: {log_path}")
    return code


if __name__ == "__main__":
    sys.exit(main())
