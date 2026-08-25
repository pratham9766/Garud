"""Tests for the pose-assisted post-flight processing foundation."""

from __future__ import annotations

import csv
import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from mapping.image_graph import build_candidate_graph
from processing.pose_assisted_pipeline import run_pose_assisted_stage
from sensor_fusion.pose_prior import build_pose_prior, relative_pose_prior
from storage.mission_manifest import CameraModel, ImageMetadata


def _metadata(
    image_name: str,
    timestamp: float,
    lat: float = 18.5204,
    lon: float = 73.8567,
    yaw: float = 10.0,
) -> ImageMetadata:
    return ImageMetadata(
        image_name=image_name,
        image_path=Path(image_name),
        timestamp=timestamp,
        latitude=lat,
        longitude=lon,
        gps_altitude_m=100.0,
        baro_altitude_m=95.0,
        roll_deg=4.0,
        pitch_deg=-2.0,
        yaw_deg=yaw,
        gyro_x_dps=5.0,
        gyro_y_dps=4.0,
        gyro_z_dps=6.0,
        camera=CameraModel(width_px=640, height_px=480, focal_length_px=500.0),
    )


def test_pose_prior_homography_shape() -> None:
    metadata = _metadata("img_001.jpg", 1.0)
    prior = build_pose_prior(metadata)

    assert prior.rotation_matrix.shape == (3, 3)
    assert prior.normalization_homography.shape == (3, 3)
    assert np.isclose(prior.normalization_homography[2, 2], 1.0)


def test_candidate_graph_is_not_sequential_only() -> None:
    first = _metadata("img_001.jpg", 1.0)
    second = _metadata("img_002.jpg", 4.0, lat=18.52045, lon=73.85675, yaw=14.0)
    third = _metadata("img_003.jpg", 8.0, lat=18.52048, lon=73.85678, yaw=18.0)

    graph = build_candidate_graph((first, second, third), max_distance_m=50.0)

    assert len(graph.nodes) == 3
    assert len(graph.edges) == 3
    assert relative_pose_prior(first, second).shape == (3, 3)


def test_pose_assisted_stage_scores_images_and_builds_graph() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        image_dir = tmp_path / "images"
        image_dir.mkdir()
        csv_path = tmp_path / "mission.csv"

        image = np.full((120, 160, 3), 120, dtype=np.uint8)
        cv2.rectangle(image, (20, 20), (140, 100), (220, 220, 220), -1)
        cv2.line(image, (0, 0), (159, 119), (40, 40, 40), 2)
        cv2.imwrite(str(image_dir / "img_001.jpg"), image)
        cv2.imwrite(str(image_dir / "img_002.jpg"), image)

        with open(csv_path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "timestamp",
                    "latitude",
                    "longitude",
                    "gps_altitude",
                    "baro_altitude",
                    "roll",
                    "pitch",
                    "yaw",
                    "gyro_x",
                    "gyro_y",
                    "gyro_z",
                    "image_name",
                    "image_timestamp",
                ],
            )
            writer.writeheader()
            writer.writerow(
                {
                    "timestamp": 1.0,
                    "latitude": 18.5204,
                    "longitude": 73.8567,
                    "gps_altitude": 100.0,
                    "baro_altitude": 95.0,
                    "roll": 2.0,
                    "pitch": 1.0,
                    "yaw": 10.0,
                    "gyro_x": 3.0,
                    "gyro_y": 2.0,
                    "gyro_z": 4.0,
                    "image_name": "img_001.jpg",
                    "image_timestamp": 1.0,
                }
            )
            writer.writerow(
                {
                    "timestamp": 3.0,
                    "latitude": 18.52045,
                    "longitude": 73.85675,
                    "gps_altitude": 98.0,
                    "baro_altitude": 93.0,
                    "roll": 2.5,
                    "pitch": 1.5,
                    "yaw": 12.0,
                    "gyro_x": 3.0,
                    "gyro_y": 2.0,
                    "gyro_z": 4.0,
                    "image_name": "img_002.jpg",
                    "image_timestamp": 3.0,
                }
            )

        summary = run_pose_assisted_stage(csv_path, image_dir=image_dir)

        assert summary.image_count == 2
        assert summary.usable_image_count == 2
        assert summary.candidate_edge_count == 1
        assert len(summary.pose_priors) == 2


if __name__ == "__main__":
    test_pose_prior_homography_shape()
    test_candidate_graph_is_not_sequential_only()
    test_pose_assisted_stage_scores_images_and_builds_graph()
    print("Pose-assisted processing tests passed.")
