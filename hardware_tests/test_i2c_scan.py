"""
I2C bus scan for Raspberry Pi.

Wiring (I2C bus 1):
  SDA -> GPIO2 (physical pin 3)
  SCL -> GPIO3 (physical pin 5)
  3.3V and GND to sensor boards

Run from project root:
  python hardware_tests/test_i2c_scan.py
"""

from __future__ import annotations

import shutil
import subprocess
import sys

from hw_common import banner, ensure_dirs, is_raspberry_pi, result, write_log

import config


def main() -> int:
    banner("Hardware Test: I2C Scan (bus 1)")
    ensure_dirs()
    log_lines: list[str] = []

    print("Bus: I2C-1  (SDA=GPIO2 pin 3, SCL=GPIO3 pin 5)")
    print("Expected addresses:")
    print("  Barometer (BMP280/BMP388): 0x76 or 0x77")
    print(f"  Barometer (config):          0x{config.BAROMETER_ADDRESS:02X}")
    print("  IMU (MPU6050):               0x68 or 0x69")
    print(f"  IMU (config):                0x{config.IMU_ADDRESS:02X}")
    print()

    if not is_raspberry_pi():
        result("WARNING", "Not running on Raspberry Pi — i2cdetect may be unavailable.")
        log_lines.append("WARNING: Not on Raspberry Pi")

    if not shutil.which("i2cdetect"):
        result("FAIL", "i2cdetect not found. Install: sudo apt install -y i2c-tools")
        result("INFO", "Also enable I2C: sudo raspi-config -> Interface Options -> I2C")
        log_lines.append("FAIL: i2cdetect missing")
        write_log("test_i2c_scan.log", log_lines)
        return 1

    try:
        proc = subprocess.run(
            ["i2cdetect", "-y", "1"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        output = proc.stdout + proc.stderr
        print(output)
        log_lines.append(output)

        if proc.returncode != 0:
            result("FAIL", f"i2cdetect exited with code {proc.returncode}")
            write_log("test_i2c_scan.log", log_lines)
            return 1

        # Parse hex addresses from output (two-digit hex in table)
        detected = []
        for line in output.splitlines():
            parts = line.split()[1:]  # skip row label
            for part in parts:
                if part not in ("--", "UU") and len(part) == 2:
                    try:
                        detected.append(int(part, 16))
                    except ValueError:
                        pass

        if detected:
            result("PASS", f"I2C devices detected at: {', '.join(f'0x{a:02X}' for a in sorted(detected))}")
            log_lines.append(f"PASS: detected {detected}")
        else:
            result("WARNING", "No I2C devices found. Check wiring and I2C enable in raspi-config.")
            log_lines.append("WARNING: no devices")

        log_path = write_log("test_i2c_scan.log", log_lines)
        print(f"Log saved: {log_path}")
        return 0 if detected else 2

    except FileNotFoundError:
        result("FAIL", "i2cdetect command not found.")
        write_log("test_i2c_scan.log", ["FAIL: i2cdetect not found"])
        return 1
    except subprocess.TimeoutExpired:
        result("FAIL", "i2cdetect timed out.")
        write_log("test_i2c_scan.log", ["FAIL: timeout"])
        return 1
    except Exception as exc:
        result("FAIL", f"Unexpected error: {exc}")
        write_log("test_i2c_scan.log", [f"FAIL: {exc}"])
        return 1


if __name__ == "__main__":
    sys.exit(main())
