"""Footprint prediction tests."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from mapping.footprint import approximate_overlap_ratio, predict_footprint
from storage.mission_manifest import CameraModel, ImageMetadata


def _metadata(name: str, lat: float, lon: float) -> ImageMetadata:
    return ImageMetadata(
        image_name=name,
        image_path=Path(name),
        timestamp=1.0,
        latitude=lat,
        longitude=lon,
        gps_altitude_m=100.0,
        baro_altitude_m=100.0,
        roll_deg=0.0,
        pitch_deg=0.0,
        yaw_deg=0.0,
        gyro_x_dps=0.0,
        gyro_y_dps=0.0,
        gyro_z_dps=0.0,
        camera=CameraModel(width_px=640, height_px=480, focal_length_px=500.0),
    )


def test_overlap_changes_with_distance() -> None:
    first = _metadata("a.jpg", 18.5204, 73.8567)
    near = _metadata("b.jpg", 18.52042, 73.85672)
    far = _metadata("c.jpg", 18.5304, 73.8667)
    fp_a = predict_footprint(first, first.latitude, first.longitude)
    fp_b = predict_footprint(near, first.latitude, first.longitude)
    fp_c = predict_footprint(far, first.latitude, first.longitude)
    assert approximate_overlap_ratio(fp_a, fp_b) > 0.0
    assert approximate_overlap_ratio(fp_a, fp_c) == 0.0


if __name__ == "__main__":
    test_overlap_changes_with_distance()
    print("Footprint overlap tests passed.")
