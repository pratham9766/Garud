"""Feature matching and geometric verification."""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from vision.feature_detection import FeatureSet


@dataclass(frozen=True)
class MatchResult:
    """Pairwise feature-match result after geometric verification."""

    matches: tuple[cv2.DMatch, ...]
    inlier_mask: np.ndarray | None
    homography: np.ndarray | None

    @property
    def inlier_count(self) -> int:
        if self.inlier_mask is None:
            return 0
        return int(np.count_nonzero(self.inlier_mask))


def match_features(
    first: FeatureSet,
    second: FeatureSet,
    ratio: float = 0.75,
) -> tuple[cv2.DMatch, ...]:
    """Match descriptors using FLANN for SIFT and Hamming BF for ORB."""
    if first.descriptors is None or second.descriptors is None:
        return ()
    if len(first.descriptors) < 2 or len(second.descriptors) < 2:
        return ()

    if first.detector_name == "SIFT":
        matcher = cv2.FlannBasedMatcher(
            dict(algorithm=1, trees=5),
            dict(checks=64),
        )
        desc_a = np.asarray(first.descriptors, dtype=np.float32)
        desc_b = np.asarray(second.descriptors, dtype=np.float32)
    else:
        matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
        desc_a = first.descriptors
        desc_b = second.descriptors

    raw_matches = matcher.knnMatch(desc_a, desc_b, k=2)
    good: list[cv2.DMatch] = []
    for candidates in raw_matches:
        if len(candidates) != 2:
            continue
        best, next_best = candidates
        if best.distance < ratio * next_best.distance:
            good.append(best)
    return tuple(good)


def estimate_homography_ransac(
    first: FeatureSet,
    second: FeatureSet,
    matches: tuple[cv2.DMatch, ...],
    reprojection_threshold: float = 4.0,
) -> MatchResult:
    """Estimate a pairwise homography from feature matches with RANSAC."""
    if len(matches) < 4:
        return MatchResult(matches=matches, inlier_mask=None, homography=None)

    points_a = np.float32([first.keypoints[m.queryIdx].pt for m in matches])
    points_b = np.float32([second.keypoints[m.trainIdx].pt for m in matches])
    homography, mask = cv2.findHomography(
        points_a,
        points_b,
        cv2.RANSAC,
        reprojection_threshold,
    )
    return MatchResult(
        matches=matches,
        inlier_mask=mask,
        homography=homography,
    )

