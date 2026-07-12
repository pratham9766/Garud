"""
Test mock IMU readings.

Run from project root:
    python tests/test_imu.py
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from sensors.imu import MockIMU


def test_imu() -> None:
    print("=" * 50)
    print("TEST: Mock IMU")
    print("=" * 50)

    imu = MockIMU()
    readings = [imu.read() for _ in range(5)]

    for i, r in enumerate(readings):
        print(
            f"  [{i}] roll={r['roll']:.2f}° pitch={r['pitch']:.2f}° yaw={r['yaw']:.2f}°"
        )
        assert -90 <= r["roll"] <= 90
        assert -90 <= r["pitch"] <= 90
        assert 0 <= r["yaw"] < 360

    imu.close()
    print("\nIMU test passed.")


if __name__ == "__main__":
    test_imu()
