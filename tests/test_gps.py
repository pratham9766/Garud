"""
Test mock GPS readings.

Run from project root:
    python tests/test_gps.py
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import config
from sensors.gps import MockGPS


def test_gps() -> None:
    print("=" * 50)
    print("TEST: Mock GPS")
    print("=" * 50)

    gps = MockGPS()
    readings = [gps.read() for _ in range(5)]

    for i, r in enumerate(readings):
        print(
            f"  [{i}] lat={r['latitude']:.6f} lon={r['longitude']:.6f} "
            f"alt={r['altitude']:.1f}m fix={r['fix_ok']}"
        )
        assert r["fix_ok"]
        assert abs(r["latitude"] - config.MOCK_GPS_LAT) < 0.01
        assert abs(r["longitude"] - config.MOCK_GPS_LON) < 0.01

    gps.close()
    print("\nGPS test passed.")


if __name__ == "__main__":
    test_gps()
