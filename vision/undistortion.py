"""Lens undistortion helpers built around stored camera calibration."""

from __future__ import annotations

import cv2
import numpy as np

from storage.mission_manifest import CameraModel


def undistort_image(image: np.ndarray, camera: CameraModel) -> np.ndarray:
    """Return an undistorted copy of an image using the camera model."""
    k = np.array(camera.intrinsic_matrix, dtype=np.float64)
    distortion = np.array(camera.distortion_coeffs, dtype=np.float64)
    if distortion.size == 0 or np.allclose(distortion, 0.0):
        return image.copy()
    return cv2.undistort(image, k, distortion)

