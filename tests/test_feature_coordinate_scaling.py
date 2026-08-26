from __future__ import annotations

import cv2

from processing.sfm_backend import keypoints_to_original_array
from vision.feature_detection import FeatureSet


def test_keypoints_are_scaled_back_to_original_image_coordinates() -> None:
    features = FeatureSet(
        detector_name="SIFT",
        keypoints=(
            cv2.KeyPoint(x=500.0, y=400.0, size=12.0, angle=35.0),
            cv2.KeyPoint(x=125.0, y=75.0, size=8.0, angle=10.0),
        ),
        descriptors=None,
        image_shape=(1500, 2000),
        scale=0.5,
    )

    keypoints = keypoints_to_original_array(features)

    assert keypoints.shape == (2, 4)
    assert keypoints[0, 0] == 1000.0
    assert keypoints[0, 1] == 800.0
    assert keypoints[0, 2] == 24.0
    assert keypoints[0, 3] == 35.0
    assert keypoints[1, 0] == 250.0
    assert keypoints[1, 1] == 150.0
