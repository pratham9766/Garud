"""Pluggable feature extraction for mapping images."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import cv2
import numpy as np


@dataclass(frozen=True)
class FeatureSet:
    """Detected keypoints and descriptors for one image."""

    detector_name: str
    keypoints: tuple[cv2.KeyPoint, ...]
    descriptors: np.ndarray | None
    image_shape: tuple[int, int] | None = None
    scale: float = 1.0


class FeatureBackend(ABC):
    """Backend abstraction for feature extraction."""

    name: str

    @abstractmethod
    def extract(self, image: np.ndarray) -> FeatureSet:
        """Extract features from an image."""


class FeatureDetector(FeatureBackend):
    """SIFT-first detector with ORB fallback."""

    def __init__(self, preferred: str = "SIFT", max_features: int = 4000) -> None:
        self.preferred = preferred.upper()
        self.max_features = max_features
        self.detector_name, self._detector = self._create_detector()
        self.name = self.detector_name

    def _create_detector(self) -> tuple[str, cv2.Feature2D]:
        if self.preferred == "SIFT" and hasattr(cv2, "SIFT_create"):
            return "SIFT", cv2.SIFT_create(nfeatures=self.max_features)
        return "ORB", cv2.ORB_create(nfeatures=self.max_features)

    def extract(self, image: np.ndarray) -> FeatureSet:
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
            image_shape=gray.shape[:2],
            scale=1.0,
        )

    def detect(self, image: np.ndarray) -> FeatureSet:
        """Backward-compatible alias for extract()."""
        return self.extract(image)


def resize_for_features(
    image: np.ndarray,
    max_dim: int,
) -> tuple[np.ndarray, float]:
    """Resize image for feature extraction while returning coordinate scale."""
    height, width = image.shape[:2]
    largest = max(height, width)
    if largest <= max_dim:
        return image, 1.0
    scale = max_dim / float(largest)
    resized = cv2.resize(
        image,
        (int(round(width * scale)), int(round(height * scale))),
        interpolation=cv2.INTER_AREA,
    )
    return resized, scale
