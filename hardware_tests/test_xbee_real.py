"""
Real XBee serial telemetry test.

Wiring:
  XBee USB adapter -> Pi USB port (development)
  Config port: XBEE_PORT (default /dev/ttyUSB1)
  Baud:        XBEE_BAUDRATE (default 9600)
  GND common with Pi

Sends a small JSON packet every 1 second for 10 seconds.

Run from project root:
  python hardware_tests/test_xbee_real.py
"""

from __future__ import annotations

import json
import sys
import time

from hw_common import banner, ensure_dirs, result, write_log

import config


def main() -> int:
    banner("Hardware Test: XBee Telemetry (serial)")
    ensure_dirs()
    log_lines: list[str] = []

    print(f"Serial port: {config.XBEE_PORT}")
    print(f"Baud rate:   {config.XBEE_BAUDRATE}")
    print("Duration:    10 packets, 1 second apart")
    print("Wiring:      XBee via USB-UART adapter (or UART later)")
    print()

    try:
        import serial
    except ImportError:
        result("FAIL", "pyserial not installed. pip install pyserial")
        write_log("test_xbee_real.log", ["FAIL: pyserial missing"])
        return 1

    try:
        ser = serial.Serial(config.XBEE_PORT, config.XBEE_BAUDRATE, timeout=2)
    except Exception as exc:
        result("FAIL", f"Cannot open port {config.XBEE_PORT}: {exc}")
        print("Check: ls /dev/ttyUSB*  and user dialout group.")
        write_log("test_xbee_real.log", [f"FAIL: {exc}"])
        return 1

    result("PASS", f"Serial port {config.XBEE_PORT} opened.")
    log_lines.append(f"Opened {config.XBEE_PORT}")

    sent = 0
    try:
        for i in range(10):
            packet = {
                "state": "TEST",
                "lat": config.MOCK_GPS_LAT,
                "lon": config.MOCK_GPS_LON,
                "alt": 100.0,
                "battery": 99.0 - i,
                "status": "XBEE_HW_TEST",
            }
            payload = json.dumps(packet, separators=(",", ":")) + "\n"
            ser.write(payload.encode("utf-8"))
            ser.flush()
            sent += 1
            print(f"  [{i + 1}/10] SENT: {payload.strip()}")
            log_lines.append(f"SENT: {payload.strip()}")
            time.sleep(1.0)

        result("PASS", f"Successfully wrote {sent} packets to {config.XBEE_PORT}.")
        log_lines.append("PASS")
        code = 0

    except Exception as exc:
        result("FAIL", f"Write error: {exc}")
        log_lines.append(f"FAIL: {exc}")
        code = 1
    finally:
        ser.close()

    log_path = write_log("test_xbee_real.log", log_lines)
    print(f"Log saved: {log_path}")
    return code


if __name__ == "__main__":
    sys.exit(main())
