"""Geometric verification tests."""

from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from vision.feature_detection import FeatureSet
from vision.geometric_verification import verify_geometry


def test_homography_fallback_accepts_shifted_grid() -> None:
    keypoints_a = []
    keypoints_b = []
    matches = []
    idx = 0
    for y in range(20, 120, 20):
        for x in range(20, 120, 20):
            keypoints_a.append(cv2.KeyPoint(float(x), float(y), 5))
            keypoints_b.append(cv2.KeyPoint(float(x + 8), float(y + 4), 5))
            matches.append(cv2.DMatch(idx, idx, 0.1))
            idx += 1
    first = FeatureSet("SIFT", tuple(keypoints_a), np.ones((idx, 128), dtype=np.float32))
    second = FeatureSet("SIFT", tuple(keypoints_b), np.ones((idx, 128), dtype=np.float32))
    result = verify_geometry(first, second, tuple(matches), camera=None, raw_match_count=len(matches))
    assert result.accepted
    assert result.model_type in {"FUNDAMENTAL", "HOMOGRAPHY"}


if __name__ == "__main__":
    test_homography_fallback_accepts_shifted_grid()
    print("Geometric verification tests passed.")
