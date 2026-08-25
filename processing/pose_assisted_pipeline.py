"""High-level pose-assisted post-flight processing scaffold."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2

from mapping.image_graph import ImageGraph, build_candidate_graph
from processing.mission_loader import MissionData, load_mission_data, validate_mission_data
from processing.quality_scoring import ImageQuality, score_image_quality
from sensor_fusion.pose_prior import PosePrior, build_pose_prior
from storage.mission_manifest import ImageMetadata
from vision.undistortion import undistort_image


@dataclass(frozen=True)
class ProcessingSummary:
    """Summary of the first pose-assisted processing stage."""

    image_count: int
    usable_image_count: int
    candidate_edge_count: int
    validation_issues: tuple[str, ...]
    qualities: tuple[ImageQuality, ...]
    pose_priors: tuple[PosePrior, ...]
    graph: ImageGraph


def _load_image(metadata: ImageMetadata):
    image = cv2.imread(str(metadata.image_path), cv2.IMREAD_COLOR)
    if image is None:
        raise FileNotFoundError(f"Unable to read image: {metadata.image_path}")
    return image


def run_pose_assisted_stage(
    csv_path: Path,
    image_dir: Path | None = None,
) -> ProcessingSummary:
    """
    Run the V1 preprocessing stage over recovered mission data.

    This does not yet emit a final orthomosaic. It validates stored data,
    scores image quality, creates IMU pose priors, and builds the image graph
    that downstream SIFT/FLANN/RANSAC stages will refine.
    """
    mission: MissionData = load_mission_data(csv_path, image_dir=image_dir)
    validation_issues = tuple(validate_mission_data(mission))

    qualities: list[ImageQuality] = []
    pose_priors: list[PosePrior] = []
    usable_images: list[ImageMetadata] = []

    for metadata in mission.images:
        if not metadata.image_path.exists():
            continue
        image = _load_image(metadata)
        undistorted = undistort_image(image, metadata.camera)
        quality = score_image_quality(undistorted, metadata)
        qualities.append(quality)
        pose_priors.append(build_pose_prior(metadata))
        if quality.is_usable:
            usable_images.append(metadata)

    quality_by_name = {quality.image_name: quality for quality in qualities}
    graph = build_candidate_graph(tuple(usable_images), qualities=quality_by_name)
    return ProcessingSummary(
        image_count=len(mission.images),
        usable_image_count=len(usable_images),
        candidate_edge_count=len(graph.edges),
        validation_issues=validation_issues,
        qualities=tuple(qualities),
        pose_priors=tuple(pose_priors),
        graph=graph,
    )
