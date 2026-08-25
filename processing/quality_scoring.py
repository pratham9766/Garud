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
    sharpness_score: float
    exposure_score: float
    motion_score: float
    pose_score: float
    total_score: float
    usable: bool
    rejection_reason: str
    status: str
    blur_variance: float
    mean_brightness: float
    clipped_shadow_fraction: float
    clipped_highlight_fraction: float
    tilt_deg: float
    angular_rate_dps: float
    flags: tuple[str, ...]

    @property
    def score(self) -> float:
        """Backward-compatible aggregate score alias."""
        return self.total_score

    @property
    def is_usable(self) -> bool:
        return self.usable


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def score_image_quality(
    image: np.ndarray,
    metadata: ImageMetadata,
) -> ImageQuality:
    """Score blur, exposure, tilt, and IMU motion for a captured image."""
    if image is None or image.size == 0:
        return ImageQuality(
            image_name=metadata.image_name,
            sharpness_score=0.0,
            exposure_score=0.0,
            motion_score=0.0,
            pose_score=0.0,
            total_score=0.0,
            usable=False,
            rejection_reason="unreadable",
            status="REJECTED",
            blur_variance=0.0,
            mean_brightness=0.0,
            clipped_shadow_fraction=1.0,
            clipped_highlight_fraction=1.0,
            tilt_deg=0.0,
            angular_rate_dps=0.0,
            flags=("unreadable",),
        )

    if image.ndim == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image

    blur_variance = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    mean_brightness = float(np.mean(gray))
    clipped_shadow = float(np.mean(gray <= 3))
    clipped_highlight = float(np.mean(gray >= 252))
    tilt_deg = math.hypot(metadata.roll_deg, metadata.pitch_deg)
    angular_rate = math.sqrt(
        metadata.gyro_x_dps**2 + metadata.gyro_y_dps**2 + metadata.gyro_z_dps**2
    )

    sharpness_score = _clamp01(blur_variance / config.QUALITY_BLUR_MIN_VARIANCE)
    exposure_mid = (
        config.QUALITY_EXPOSURE_LOW + config.QUALITY_EXPOSURE_HIGH
    ) / 2.0
    exposure_span = (
        config.QUALITY_EXPOSURE_HIGH - config.QUALITY_EXPOSURE_LOW
    ) / 2.0
    brightness_score = _clamp01(
        1.0 - abs(mean_brightness - exposure_mid) / exposure_span
    )
    clipping_penalty = max(clipped_shadow, clipped_highlight)
    exposure_score = _clamp01(0.75 * brightness_score + 0.25 * (1.0 - clipping_penalty))
    pose_score = _clamp01(1.0 - tilt_deg / config.QUALITY_MAX_TILT_DEG)
    motion_score = _clamp01(1.0 - angular_rate / config.QUALITY_MAX_ANGULAR_RATE_DPS)

    flags: list[str] = []
    if blur_variance < config.QUALITY_BLUR_MIN_VARIANCE:
        flags.append("blur")
    if mean_brightness < config.QUALITY_EXPOSURE_LOW:
        flags.append("underexposed")
    if mean_brightness > config.QUALITY_EXPOSURE_HIGH:
        flags.append("overexposed")
    if clipped_shadow > config.QUALITY_CLIPPED_SHADOW_FRACTION:
        flags.append("clipped_shadows")
    if clipped_highlight > config.QUALITY_CLIPPED_HIGHLIGHT_FRACTION:
        flags.append("clipped_highlights")
    if tilt_deg > config.QUALITY_MAX_TILT_DEG:
        flags.append("tilt")
    if angular_rate > config.QUALITY_MAX_ANGULAR_RATE_DPS:
        flags.append("motion")

    total_score = (
        0.35 * sharpness_score
        + 0.25 * exposure_score
        + 0.20 * pose_score
        + 0.20 * motion_score
    )
    if total_score >= config.QUALITY_GOOD_MIN_SCORE and not flags:
        status = "GOOD"
        usable = True
        rejection_reason = ""
    elif total_score >= config.QUALITY_MARGINAL_MIN_SCORE:
        status = "MARGINAL"
        usable = True
        rejection_reason = ",".join(flags)
    else:
        status = "REJECTED"
        usable = False
        rejection_reason = ",".join(flags) or "low_score"

    return ImageQuality(
        image_name=metadata.image_name,
        sharpness_score=sharpness_score,
        exposure_score=exposure_score,
        motion_score=motion_score,
        pose_score=pose_score,
        total_score=total_score,
        usable=usable,
        rejection_reason=rejection_reason,
        status=status,
        blur_variance=blur_variance,
        mean_brightness=mean_brightness,
        clipped_shadow_fraction=clipped_shadow,
        clipped_highlight_fraction=clipped_highlight,
        tilt_deg=tilt_deg,
        angular_rate_dps=angular_rate,
        flags=tuple(flags),
    )
