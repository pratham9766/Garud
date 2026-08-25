"""Robust geometric verification for candidate image pairs."""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

import config
from storage.mission_manifest import CameraModel
from vision.feature_detection import FeatureSet


@dataclass(frozen=True)
class GeometryResult:
    """Verified pair geometry and statistics."""

    model_type: str
    matrix: np.ndarray | None
    inlier_mask: np.ndarray | None
    raw_match_count: int
    filtered_match_count: int
    inlier_count: int
    inlier_ratio: float
    accepted: bool


def _matched_points(
    first: FeatureSet,
    second: FeatureSet,
    matches: tuple[cv2.DMatch, ...],
) -> tuple[np.ndarray, np.ndarray]:
    points_a = np.float32([first.keypoints[m.queryIdx].pt for m in matches])
    points_b = np.float32([second.keypoints[m.trainIdx].pt for m in matches])
    return points_a, points_b


def _method(preferred: int) -> int:
    return getattr(cv2, "USAC_MAGSAC", preferred)


def verify_geometry(
    first: FeatureSet,
    second: FeatureSet,
    matches: tuple[cv2.DMatch, ...],
    camera: CameraModel | None = None,
    raw_match_count: int | None = None,
) -> GeometryResult:
    """
    Evaluate Essential, Fundamental, and Homography models.

    Homography is retained for local planar diagnostics, but accepted pair
    geometry prefers Essential/Fundamental support when enough inliers exist.
    """
    raw_count = raw_match_count if raw_match_count is not None else len(matches)
    if len(matches) < config.MAPPING_MIN_FILTERED_MATCHES:
        return GeometryResult(
            model_type="NONE",
            matrix=None,
            inlier_mask=None,
            raw_match_count=raw_count,
            filtered_match_count=len(matches),
            inlier_count=0,
            inlier_ratio=0.0,
            accepted=False,
        )

    points_a, points_b = _matched_points(first, second, matches)
    candidates: list[GeometryResult] = []

    if camera is not None and len(matches) >= 5:
        k = np.asarray(camera.intrinsic_matrix, dtype=np.float64)
        essential, mask = cv2.findEssentialMat(
            points_a,
            points_b,
            k,
            method=cv2.RANSAC,
            prob=0.999,
            threshold=1.5,
        )
        if essential is not None and mask is not None:
            inliers = int(np.count_nonzero(mask))
            candidates.append(
                GeometryResult(
                    model_type="ESSENTIAL",
                    matrix=essential,
                    inlier_mask=mask,
                    raw_match_count=raw_count,
                    filtered_match_count=len(matches),
                    inlier_count=inliers,
                    inlier_ratio=inliers / max(1, len(matches)),
                    accepted=False,
                )
            )

    fundamental, f_mask = cv2.findFundamentalMat(
        points_a,
        points_b,
        method=_method(cv2.FM_RANSAC),
        ransacReprojThreshold=2.0,
        confidence=0.999,
    )
    if fundamental is not None and f_mask is not None:
        inliers = int(np.count_nonzero(f_mask))
        candidates.append(
            GeometryResult(
                model_type="FUNDAMENTAL",
                matrix=fundamental,
                inlier_mask=f_mask,
                raw_match_count=raw_count,
                filtered_match_count=len(matches),
                inlier_count=inliers,
                inlier_ratio=inliers / max(1, len(matches)),
                accepted=False,
            )
        )

    homography, h_mask = cv2.findHomography(points_a, points_b, cv2.RANSAC, 4.0)
    if homography is not None and h_mask is not None:
        inliers = int(np.count_nonzero(h_mask))
        candidates.append(
            GeometryResult(
                model_type="HOMOGRAPHY",
                matrix=homography,
                inlier_mask=h_mask,
                raw_match_count=raw_count,
                filtered_match_count=len(matches),
                inlier_count=inliers,
                inlier_ratio=inliers / max(1, len(matches)),
                accepted=False,
            )
        )

    if not candidates:
        return GeometryResult(
            model_type="NONE",
            matrix=None,
            inlier_mask=None,
            raw_match_count=raw_count,
            filtered_match_count=len(matches),
            inlier_count=0,
            inlier_ratio=0.0,
            accepted=False,
        )

    priority = {"ESSENTIAL": 0, "FUNDAMENTAL": 1, "HOMOGRAPHY": 2}
    candidates.sort(key=lambda item: (-item.inlier_count, priority.get(item.model_type, 9)))
    best = candidates[0]
    accepted = (
        best.inlier_count >= config.MAPPING_MIN_GEOMETRIC_INLIERS
        and best.inlier_ratio >= config.MAPPING_MIN_INLIER_RATIO
    )
    return GeometryResult(
        model_type=best.model_type,
        matrix=best.matrix,
        inlier_mask=best.inlier_mask,
        raw_match_count=best.raw_match_count,
        filtered_match_count=best.filtered_match_count,
        inlier_count=best.inlier_count,
        inlier_ratio=best.inlier_ratio,
        accepted=accepted,
    )
