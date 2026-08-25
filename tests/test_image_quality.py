"""Post-flight image quality scoring tests."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from processing.quality_scoring import score_image_quality
from storage.mission_manifest import CameraModel, ImageMetadata


def _metadata() -> ImageMetadata:
    return ImageMetadata(
        image_name="img.jpg",
        image_path=Path("img.jpg"),
        timestamp=1.0,
        latitude=18.0,
        longitude=73.0,
        gps_altitude_m=100.0,
        baro_altitude_m=95.0,
        roll_deg=2.0,
        pitch_deg=2.0,
        yaw_deg=0.0,
        gyro_x_dps=1.0,
        gyro_y_dps=1.0,
        gyro_z_dps=1.0,
        camera=CameraModel(width_px=160, height_px=120, focal_length_px=120.0),
    )


def test_quality_statuses() -> None:
    textured = np.zeros((120, 160, 3), dtype=np.uint8)
    textured[::4, :] = 255
    textured[:, ::4] = 180
    quality = score_image_quality(textured, _metadata())
    assert quality.status in {"GOOD", "MARGINAL"}
    assert quality.total_score > 0.0

    black = np.zeros((120, 160, 3), dtype=np.uint8)
    rejected = score_image_quality(black, _metadata())
    assert rejected.status == "REJECTED"
    assert "underexposed" in rejected.flags


if __name__ == "__main__":
    test_quality_statuses()
    print("Image quality tests passed.")
