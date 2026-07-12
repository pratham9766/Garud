"""
Test camera footprint and coverage estimation.

Run from project root:
    python tests/test_coverage.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from mapping.coverage import build_image_footprints, estimate_coverage_area


def test_coverage_estimation() -> None:
    """Build footprints from geotagged image rows and estimate mapped area."""
    df = pd.DataFrame(
        [
            {
                "latitude": 18.5204,
                "longitude": 73.8567,
                "baro_altitude": 100.0,
                "gps_altitude": 100.0,
                "yaw": 0.0,
                "image_name": "img_001.jpg",
            },
            {
                "latitude": 18.5205,
                "longitude": 73.8568,
                "baro_altitude": 90.0,
                "gps_altitude": 90.0,
                "yaw": 25.0,
                "image_name": "img_002.jpg",
            },
        ]
    )

    footprints = build_image_footprints(df)
    coverage = estimate_coverage_area(footprints)

    assert len(footprints) == 2
    assert all(len(footprint.corners) == 4 for footprint in footprints)
    assert coverage["image_count"] == 2
    assert coverage["raw_area_m2"] > 0
    assert coverage["unique_area_m2"] > 0
    assert coverage["unique_area_m2"] <= coverage["raw_area_m2"]


if __name__ == "__main__":
    test_coverage_estimation()
    print("Coverage algorithm test passed.")
