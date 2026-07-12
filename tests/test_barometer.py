"""
Test mock barometer readings.

Run from project root:
    python tests/test_barometer.py
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import config
from sensors.barometer import MockBarometer


def test_barometer() -> None:
    print("=" * 50)
    print("TEST: Mock Barometer")
    print("=" * 50)

    baro = MockBarometer()
    readings = [baro.read() for _ in range(10)]

    for i, r in enumerate(readings):
        print(f"  [{i}] altitude={r['altitude']:.1f}m pressure={r['pressure']:.1f} hPa")
        assert r["altitude"] >= 0
        assert r["altitude"] <= config.MOCK_START_ALTITUDE_M + 10

    # Altitude should generally decrease
    assert readings[-1]["altitude"] < readings[0]["altitude"], "Altitude should decrease"

    baro.close()
    print("\nBarometer test passed.")


if __name__ == "__main__":
    test_barometer()
