"""Pluggable feature extraction for mapping images."""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass(frozen=True)
class FeatureSet:
    """Detected keypoints and descriptors for one image."""

    detector_name: str
    keypoints: tuple[cv2.KeyPoint, ...]
    descriptors: np.ndarray | None


class FeatureDetector:
    """SIFT-first detector with ORB fallback."""

    def __init__(self, preferred: str = "SIFT", max_features: int = 4000) -> None:
        self.preferred = preferred.upper()
        self.max_features = max_features
        self.detector_name, self._detector = self._create_detector()

    def _create_detector(self) -> tuple[str, cv2.Feature2D]:
        if self.preferred == "SIFT" and hasattr(cv2, "SIFT_create"):
            return "SIFT", cv2.SIFT_create(nfeatures=self.max_features)
        return "ORB", cv2.ORB_create(nfeatures=self.max_features)

    def detect(self, image: np.ndarray) -> FeatureSet:
        """Detect features in a BGR/RGB/gray image."""
        if image.ndim == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image
        keypoints, descriptors = self._detector.detectAndCompute(gray, None)
        return FeatureSet(
            detector_name=self.detector_name,
            keypoints=tuple(keypoints or ()),
            descriptors=descriptors,
        )

