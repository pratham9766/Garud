"""Post-flight image quality scoring."""

from __future__ import annotations

from dataclasses import dataclass
import math

import cv2
import numpy as np

import config
from storage.mission_manifest import ImageMetadata


@dataclass(frozen=True)
class ImageQuality:
    """Quality metrics and aggregate score for one image."""

    image_name: str
    score: float
    blur_variance: float
    mean_brightness: float
    tilt_deg: float
    angular_rate_dps: float
    flags: tuple[str, ...]

    @property
    def is_usable(self) -> bool:
        return self.score >= 0.5 and not self.flags


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def score_image_quality(
    image: np.ndarray,
    metadata: ImageMetadata,
) -> ImageQuality:
    """Score blur, exposure, tilt, and IMU motion for a captured image."""
    if image.ndim == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image

    blur_variance = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    mean_brightness = float(np.mean(gray))
    tilt_deg = math.hypot(metadata.roll_deg, metadata.pitch_deg)
    angular_rate = math.sqrt(
        metadata.gyro_x_dps**2 + metadata.gyro_y_dps**2 + metadata.gyro_z_dps**2
    )

    blur_score = _clamp01(blur_variance / config.QUALITY_BLUR_MIN_VARIANCE)
    exposure_mid = (
        config.QUALITY_EXPOSURE_LOW + config.QUALITY_EXPOSURE_HIGH
    ) / 2.0
    exposure_span = (
        config.QUALITY_EXPOSURE_HIGH - config.QUALITY_EXPOSURE_LOW
    ) / 2.0
    exposure_score = _clamp01(1.0 - abs(mean_brightness - exposure_mid) / exposure_span)
    tilt_score = _clamp01(1.0 - tilt_deg / config.QUALITY_MAX_TILT_DEG)
    motion_score = _clamp01(1.0 - angular_rate / config.QUALITY_MAX_ANGULAR_RATE_DPS)

    flags: list[str] = []
    if blur_variance < config.QUALITY_BLUR_MIN_VARIANCE:
        flags.append("blur")
    if mean_brightness < config.QUALITY_EXPOSURE_LOW:
        flags.append("underexposed")
    if mean_brightness > config.QUALITY_EXPOSURE_HIGH:
        flags.append("overexposed")
    if tilt_deg > config.QUALITY_MAX_TILT_DEG:
        flags.append("tilt")
    if angular_rate > config.QUALITY_MAX_ANGULAR_RATE_DPS:
        flags.append("motion")

    score = (
        0.35 * blur_score
        + 0.25 * exposure_score
        + 0.20 * tilt_score
        + 0.20 * motion_score
    )
    return ImageQuality(
        image_name=metadata.image_name,
        score=score,
        blur_variance=blur_variance,
        mean_brightness=mean_brightness,
        tilt_deg=tilt_deg,
        angular_rate_dps=angular_rate,
        flags=tuple(flags),
    )

