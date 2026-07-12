"""
Real GPS test — read NMEA sentences over serial.

Wiring (USB adapter phase):
  GPS module -> USB-UART adapter -> Pi USB port
  Config port: GPS_PORT (default /dev/ttyUSB0)

Wiring (direct UART phase):
  GPS TX -> Pi RX (GPIO15, pin 10)
  GPS RX -> Pi TX (GPIO14, pin 8)
  Common GND

Run from project root:
  python hardware_tests/test_gps_real.py
"""

from __future__ import annotations

import sys
import time

from hw_common import banner, ensure_dirs, result, write_log

import config


def main() -> int:
    banner("Hardware Test: Real GPS (NMEA serial)")
    ensure_dirs()
    log_lines: list[str] = []

    print(f"Serial port:  {config.GPS_PORT}")
    print(f"Baud rate:    {config.GPS_BAUDRATE}")
    print("Duration:     60 seconds")
    print("Wiring:       GPS via USB-UART or Pi UART (GPIO14 TX / GPIO15 RX)")
    print()

    try:
        import serial
        import pynmea2
    except ImportError as exc:
        result("FAIL", f"Missing library: {exc}")
        print("Install: pip install pyserial pynmea2")
        write_log("test_gps_real.log", [f"FAIL: import {exc}"])
        return 1

    try:
        ser = serial.Serial(config.GPS_PORT, config.GPS_BAUDRATE, timeout=1)
    except Exception as exc:
        result("FAIL", f"Cannot open {config.GPS_PORT}: {exc}")
        print("Check USB cable, port name (ls /dev/ttyUSB*), and permissions.")
        write_log("test_gps_real.log", [f"FAIL: open port {exc}"])
        return 1

    result("INFO", f"Port {config.GPS_PORT} opened successfully.")
    log_lines.append(f"Opened {config.GPS_PORT}")

    raw_lines = 0
    valid_fix = False
    best_lat = best_lon = best_alt = None
    satellites = fix_quality = None
    deadline = time.time() + 60

    try:
        while time.time() < deadline:
            try:
                line = ser.readline().decode("ascii", errors="ignore").strip()
            except Exception as exc:
                result("WARNING", f"Read error: {exc}")
                continue

            if not line or not line.startswith("$"):
                continue

            raw_lines += 1
            print(f"RAW: {line}")
            log_lines.append(f"RAW: {line}")

            try:
                msg = pynmea2.parse(line)
            except pynmea2.ParseError:
                continue

            if hasattr(msg, "latitude") and msg.latitude != 0:
                best_lat = msg.latitude
                best_lon = msg.longitude
                valid_fix = True
                if hasattr(msg, "altitude"):
                    best_alt = msg.altitude
                if hasattr(msg, "num_sats"):
                    satellites = msg.num_sats
                if hasattr(msg, "gps_qual"):
                    fix_quality = msg.gps_qual

                print(
                    f"  PARSED: lat={best_lat:.6f} lon={best_lon:.6f} "
                    f"alt={best_alt} sats={satellites} fix_q={fix_quality}"
                )
                log_lines.append(
                    f"PARSED: lat={best_lat} lon={best_lon} alt={best_alt} "
                    f"sats={satellites} fix_q={fix_quality}"
                )

    finally:
        ser.close()

    if valid_fix:
        result("PASS", f"Valid fix received — lat={best_lat:.6f}, lon={best_lon:.6f}")
        log_lines.append("PASS: valid fix")
        code = 0
    elif raw_lines > 0:
        result("WARNING", f"Raw NMEA received ({raw_lines} lines) but no valid lat/lon fix yet.")
        result("INFO", "Move antenna outdoors with clear sky view and retry.")
        log_lines.append("WARNING: no fix")
        code = 2
    else:
        result("FAIL", "No serial data received in 60 seconds.")
        log_lines.append("FAIL: no data")
        code = 1

    log_path = write_log("test_gps_real.log", log_lines)
    print(f"Log saved: {log_path}")
    return code


if __name__ == "__main__":
    sys.exit(main())
