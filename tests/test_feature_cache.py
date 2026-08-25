"""Feature cache tests."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from storage.mission_manifest import CameraModel, ImageMetadata
from vision.feature_cache import FeatureCache, FeatureCacheConfig
from vision.feature_detection import FeatureDetector


def test_feature_cache_reuses_npz() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        image_path = root / "img.jpg"
        image = np.zeros((160, 160, 3), dtype=np.uint8)
        cv2.circle(image, (80, 80), 40, (255, 255, 255), -1)
        cv2.line(image, (10, 10), (150, 150), (120, 120, 120), 3)
        cv2.imwrite(str(image_path), image)

        metadata = ImageMetadata(
            image_name="img.jpg",
            image_path=image_path,
            timestamp=1.0,
            latitude=18.0,
            longitude=73.0,
            gps_altitude_m=100.0,
            baro_altitude_m=100.0,
            roll_deg=0.0,
            pitch_deg=0.0,
            yaw_deg=0.0,
            gyro_x_dps=0.0,
            gyro_y_dps=0.0,
            gyro_z_dps=0.0,
            camera=CameraModel(width_px=160, height_px=160, focal_length_px=120.0),
        )
        detector = FeatureDetector(max_features=100)
        settings = FeatureCacheConfig(detector.detector_name, max_dim=160, max_features=100)
        cache = FeatureCache(root / "cache")
        first = cache.get_or_extract(metadata, detector, settings)
        second = cache.get_or_extract(metadata, detector, settings)
        assert len(first.keypoints) == len(second.keypoints)
        assert cache.path_for(metadata, settings).exists()


if __name__ == "__main__":
    test_feature_cache_reuses_npz()
    print("Feature cache tests passed.")
