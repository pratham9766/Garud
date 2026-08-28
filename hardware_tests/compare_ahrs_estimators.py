"""Bench-only AHRS estimator comparison logger.

This tool never publishes to flight control. It reads one IMU stream and logs
BNO085, Madgwick, and Mahony disagreement for offline selection/tuning.
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import config
from sensors.imu import create_imu
from sensor_fusion.ahrs import AHRSManager, AHRSMode, raw_from_reading
from sensor_fusion.quaternion import angular_difference_rad


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=float, default=30.0)
    parser.add_argument("--output", type=Path, default=config.LOG_SAVE_PATH / "ahrs_comparison.csv")
    args = parser.parse_args()

    config.USE_MOCK_HARDWARE = False
    imu = create_imu()
    managers = {
        AHRSMode.BNO085: AHRSManager(mode=AHRSMode.BNO085, enabled=True),
        AHRSMode.MADGWICK: AHRSManager(mode=AHRSMode.MADGWICK, enabled=True),
        AHRSMode.MAHONY: AHRSManager(mode=AHRSMode.MAHONY, enabled=True),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    end_time = time.monotonic() + args.seconds

    with open(args.output, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "timestamp_ns",
            "bno_valid",
            "madgwick_valid",
            "mahony_valid",
            "bno_madgwick_error_deg",
            "bno_mahony_error_deg",
            "madgwick_mahony_error_deg",
            "bno_yaw",
            "madgwick_yaw",
            "mahony_yaw",
        ])
        try:
            while time.monotonic() < end_time:
                raw = raw_from_reading(imu.read())
                states = {}
                for mode, manager in managers.items():
                    states[mode] = manager.update(raw)
                writer.writerow([
                    raw.timestamp_ns,
                    int(states[AHRSMode.BNO085].valid),
                    int(states[AHRSMode.MADGWICK].valid),
                    int(states[AHRSMode.MAHONY].valid),
                    math.degrees(angular_difference_rad(states[AHRSMode.BNO085].quaternion, states[AHRSMode.MADGWICK].quaternion)),
                    math.degrees(angular_difference_rad(states[AHRSMode.BNO085].quaternion, states[AHRSMode.MAHONY].quaternion)),
                    math.degrees(angular_difference_rad(states[AHRSMode.MADGWICK].quaternion, states[AHRSMode.MAHONY].quaternion)),
                    states[AHRSMode.BNO085].yaw_deg,
                    states[AHRSMode.MADGWICK].yaw_deg,
                    states[AHRSMode.MAHONY].yaw_deg,
                ])
                time.sleep(1.0 / config.AHRS_RATE_HZ)
        finally:
            imu.close()
    print(f"AHRS comparison log written: {args.output}")


if __name__ == "__main__":
    main()
