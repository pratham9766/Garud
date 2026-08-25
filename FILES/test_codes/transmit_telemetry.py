"""
transmit_telemetry.py
----------------------
One-way XBee telemetry test: reads BNO085 IMU + BMP388 barometer and
transmits a minimal JSON frame per interval over the XBee (UART).

Ground side: coordinator XBee on the laptop, visible in XCTU
serial console as one JSON line per 0.5 s.

Run with:  python3 transmit_telemetry.py
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "libraries"))


import json
import time

import bus_manager
import config
from sensors.bno085_sensor import BNO085Sensor
from sensors.bmp388_sensor import BMP388Sensor
from xbee_link import XBeeLink


def build_frame(imu_data, baro_data):
    gx, gy, gz = imu_data["gyro_rads"]
    mx, my, mz = imu_data["mag_ut"]
    lx, ly, lz = imu_data["linear_accel_ms2"]
    qi, qj, qk, qr = imu_data["quaternion"]
    return {
        "t": round(time.monotonic(), 3),
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()),
        "ax": round(imu_data["accel_ms2"][0], 3),
        "ay": round(imu_data["accel_ms2"][1], 3),
        "az": round(imu_data["accel_ms2"][2], 3),
        "gx": round(gx, 4),
        "gy": round(gy, 4),
        "gz": round(gz, 4),
        "mx": round(mx, 2),
        "my": round(my, 2),
        "mz": round(mz, 2),
        "qx": round(qi, 4),
        "qy": round(qj, 4),
        "qz": round(qk, 4),
        "qw": round(qr, 4),
        "lx": round(lx, 3),
        "ly": round(ly, 3),
        "lz": round(lz, 3),
        "alt": round(baro_data["altitude_m"], 2),
        "press": round(baro_data["pressure_hpa"], 2),
        "temp": round(baro_data["temperature_c"], 2),
    }


def main():
    i2c = bus_manager.get_i2c()
    spi = bus_manager.get_spi()

    imu = BNO085Sensor(i2c)
    baro = BMP388Sensor(spi)

    xbee = XBeeLink()
    xbee.open()
    print(f"XBee link open: {xbee.port} @ {xbee.baudrate} baud")
    print("Transmitting telemetry frames (Ctrl+C to stop)...")

    try:
        while True:
            try:
                imu_data = imu.read()
                baro_data = baro.read()
            except Exception as e:
                print(f"WARNING: sensor read failed, skipping frame ({e})")
                time.sleep(config.XBEE_TX_INTERVAL)
                continue

            frame = build_frame(imu_data, baro_data)
            line = json.dumps(frame)

            try:
                xbee.send_line(line)
            except Exception as e:
                print(f"ERROR: XBee transmit failed ({e})")
                break

            print(line)
            time.sleep(config.XBEE_TX_INTERVAL)

    except KeyboardInterrupt:
        print("\nStopped by user.")
    finally:
        xbee.close()
        print("XBee link closed.")


if __name__ == "__main__":
    main()
