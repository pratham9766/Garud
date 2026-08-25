"""
bno_calibrate.py
----------------
Guided BNO085 self-calibration.

Commands the BNO085 built-in DCD calibration (accel + gyro + mag), then
polls the magnetometer accuracy (the only per-axis accuracy the
circuitpython library exposes) and saves to flash automatically once it
reaches 3, or on Ctrl+C.

Procedure (from BNO08x / Hillcrest-Labs guidance):
  1. Flat and STILL on the table for ~10 s  -> gyro/accel offsets settle
  2. Slowly rotate through all 6 orientations, holding each ~2 s
  3. Figure-8 / full-air rotations for the magnetometer until cal = 3

Run with:  python3 bno_calibrate.py
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "libraries"))


import time

import bus_manager
from sensors.bno085_sensor import BNO085Sensor

POLL_S = 0.5
TARGET_STATUS = 3


def main():
    i2c = bus_manager.get_i2c()
    imu = BNO085Sensor(i2c)

    print("BNO085 calibration starting...")
    print("  phase 1: leave the sensor FLAT and STILL ~10 s")
    imu.bno.begin_calibration()
    for i in range(20):
        time.sleep(POLL_S)
        print(f"    [{i * POLL_S + POLL_S:5.1f}s] cal={imu.bno.calibration_status}/3")

    print("  phase 2: slowly rotate through all 6 orientations,"
          " holding each ~2 s still")
    print("  phase 3: figure-8 / air rotations for the magnetometer until cal=3\n")

    stable = False
    stable_since = None
    t0 = time.monotonic()
    try:
        while True:
            time.sleep(POLL_S)
            status = imu.bno.calibration_status
            d = imu.read()
            mx, my, mz = d["mag_ut"]
            print(f"  [{time.monotonic() - t0:7.1f}s] cal {status}/3 | "
                  f"mag ({mx:7.1f}, {my:7.1f}, {mz:7.1f}) uT | "
                  f"quat ({d['quaternion'][0]:7.3f}, {d['quaternion'][1]:7.3f}, "
                  f"{d['quaternion'][2]:7.3f}, {d['quaternion'][3]:7.3f})")
            if status >= TARGET_STATUS:
                if stable_since is None:
                    stable_since = time.monotonic()
                    print(f"  >>> cal = {TARGET_STATUS}/3 reached, holding 5 s to confirm...")
                if time.monotonic() - stable_since >= 5.0:
                    stable = True
                    break
            else:
                stable_since = None
    except KeyboardInterrupt:
        print("\nCalibration ended by user.")
    finally:
        print("Saving calibration to DCD...")
        imu.bno.save_calibration_data()
        print("Saved - calibration survives power cycles.")


if __name__ == "__main__":
    main()