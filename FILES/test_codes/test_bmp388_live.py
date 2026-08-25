"""
test_bmp388_live.py
-------------------
Live BMP388 barometer streaming test: prints timestamped readings at ~10 Hz,
refreshing the terminal in place. Ctrl+C to stop.

Run with:  python3 test_bmp388_live.py
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "libraries"))


import time

import bus_manager
from sensors.bmp388_sensor import BMP388Sensor

FPS = 10.0


def main():
    spi = bus_manager.get_spi()
    baro = BMP388Sensor(spi)

    t0 = time.monotonic()
    print("BMP388 live stream started... Ctrl+C to quit.")
    time.sleep(0.5)

    try:
        while True:
            d = baro.read()
            print("\033[2J\033[H", end="")
            print(f"[{time.monotonic() - t0:8.3f}s] BMP388 live      (@ ~{FPS:.0f} Hz)")
            print(f"  temperature (C):  {d['temperature_c']:.3f}")
            print(f"  pressure (hPa):   {d['pressure_hpa']:.3f}")
            print(f"  altitude (m):     {d['altitude_m']:.3f}")
            time.sleep(1.0 / FPS)
    except KeyboardInterrupt:
        print("\nStopped. Test complete.")


if __name__ == "__main__":
    main()