"""Low-rate real BNO085/AHRS smoke test."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import config
from sensors.imu import create_imu
from sensor_fusion.ahrs import AHRSManager, AHRSMode, raw_from_reading


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=[m.value.lower() for m in AHRSMode], default=config.AHRS_MODE.lower())
    parser.add_argument("--rate", type=float, default=2.0, help="Print rate in Hz.")
    args = parser.parse_args()

    config.USE_MOCK_HARDWARE = False
    manager = AHRSManager(mode=args.mode.upper(), enabled=args.mode.upper() != "OFF")
    imu = create_imu()
    period = 1.0 / max(0.1, args.rate)
    last_print = time.monotonic()
    count = 0
    started = time.monotonic()

    print("AHRS real test started; press Ctrl+C to stop.")
    try:
        while True:
            reading = imu.read()
            raw = raw_from_reading(reading)
            state = manager.update(raw)
            count += 1
            now = time.monotonic()
            if now - last_print >= period:
                hz = count / max(1e-6, now - started)
                print(
                    f"mode={args.mode.upper()} source={state.source} "
                    f"q=({state.q_w:+.4f},{state.q_x:+.4f},{state.q_y:+.4f},{state.q_z:+.4f}) "
                    f"rpy=({state.roll_deg:+7.2f},{state.pitch_deg:+7.2f},{state.yaw_deg:7.2f}) "
                    f"acc={state.accuracy_rad} health={state.confidence}/{state.healthy} "
                    f"age_ms={state.sample_age_ms:.1f} hz={hz:.1f} "
                    f"rejected={manager.diagnostics.rejected_samples}"
                )
                last_print = now
            time.sleep(1.0 / config.AHRS_RATE_HZ)
    except KeyboardInterrupt:
        print("\nStopping AHRS real test.")
    finally:
        imu.close()


if __name__ == "__main__":
    main()
