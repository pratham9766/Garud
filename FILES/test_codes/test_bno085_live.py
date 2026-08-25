"""
test_bno085_live.py
-------------------
Live BNO085 IMU streaming test: prints timestamped readings at ~10 Hz,
refreshing the terminal in place. Ctrl+C to stop.

Run with:  python3 test_bno085_live.py
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "libraries"))


import math
import time

import bus_manager
from sensors.bno085_sensor import BNO085Sensor

FPS = 10.0


def quat_to_euler(qi, qj, qk, qr):
    """Roll/pitch/yaw (deg) from quaternion (i, j, k, real)."""
    roll = math.atan2(2.0 * (qr * qi + qj * qk), 1.0 - 2.0 * (qi * qi + qj * qj))
    pitch = math.asin(max(-1.0, min(1.0, 2.0 * (qr * qj - qk * qi))))
    yaw = math.atan2(2.0 * (qr * qk + qi * qj), 1.0 - 2.0 * (qj * qj + qk * qk))
    return tuple(math.degrees(v) for v in (roll, pitch, yaw))


def main():
    i2c = bus_manager.get_i2c()
    imu = BNO085Sensor(i2c)

    t0 = time.monotonic()
    print("BNO085 live stream started... move the sensor, press Ctrl+C to quit.")
    time.sleep(0.5)

    try:
        while True:
            d = imu.read()
            roll, pitch, yaw = quat_to_euler(*d["quaternion"])
            print("\033[2J\033[H", end="")
            print(f"[{time.monotonic() - t0:8.3f}s] BNO085 live     (@ ~{FPS:.0f} Hz)")
            print(f"  accel (m/s²):  {tuple(round(v, 3) for v in d['accel_ms2'])}")
            print(f"  gyro (rad/s):  {tuple(round(v, 3) for v in d['gyro_rads'])}")
            print(f"  mag (µT):      {tuple(round(v, 2) for v in d['mag_ut'])}")
            print(f"  lin accel:     {tuple(round(v, 3) for v in d['linear_accel_ms2'])}")
            print(f"  quaternion:    {tuple(round(v, 4) for v in d['quaternion'])}")
            print(f"  euler (deg):   roll={roll:7.2f} pitch={pitch:7.2f} yaw={yaw:7.2f}")
            time.sleep(1.0 / FPS)
    except KeyboardInterrupt:
        print("\nStopped. Test complete.")


if __name__ == "__main__":
    main()