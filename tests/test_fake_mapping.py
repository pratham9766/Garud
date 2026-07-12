"""
Test fake flight data generation, HTML map, and KML export.

Run from project root:
    python tests/test_fake_mapping.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import config
from mapping.fake_flight_data import generate_fake_flight_csv
from mapping.kml_generator import generate_kml
from mapping.map_visualizer import generate_flight_map
from mapping.coverage import build_image_footprints, estimate_coverage_area


def test_fake_mapping() -> None:
    """Generate fake CSV and produce HTML + KML maps."""
    print("=" * 50)
    print("TEST: Fake Mapping (no hardware)")
    print("=" * 50)

    config.MAP_SAVE_PATH.mkdir(parents=True, exist_ok=True)
    config.LOG_SAVE_PATH.mkdir(parents=True, exist_ok=True)

    csv_path = generate_fake_flight_csv(
        output_path=config.LOG_SAVE_PATH / "fake_flight_log.csv",
        duration_sec=60.0,
        interval_sec=1.0,
        num_images=12,
    )
    print(f"[OK] Fake flight CSV: {csv_path}")

    footprints = build_image_footprints(pd.read_csv(csv_path))
    coverage = estimate_coverage_area(footprints)
    print(f"[OK] Footprints: {len(footprints)}")
    print(f"[OK] Unique coverage estimate: {coverage['unique_area_m2']:.0f} m^2")
    assert footprints, "No image footprints were generated"
    assert coverage["unique_area_m2"] > 0, "Coverage estimate should be positive"

    html_path = generate_flight_map(csv_path)
    print(f"[OK] HTML map: {html_path}")
    assert html_path.exists(), "HTML map was not created"

    kml_path = generate_kml(csv_path)
    print(f"[OK] KML file: {kml_path}")
    assert kml_path.exists(), "KML file was not created"

    print("\nAll fake mapping tests passed.")


if __name__ == "__main__":
    test_fake_mapping()
