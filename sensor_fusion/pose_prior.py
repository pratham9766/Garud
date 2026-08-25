"""
IMU-derived pose priors for image normalization and match initialization.

These transforms are priors only. Visual matching and RANSAC must refine or
reject them before images are warped into the final mosaic.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np

from storage.mission_manifest import CameraModel, ImageMetadata


@dataclass(frozen=True)
class PosePrior:
    """Camera attitude and corresponding image-plane prior transform."""

    image_name: str
    roll_deg: float
    pitch_deg: float
    yaw_deg: float
    rotation_matrix: np.ndarray
    normalization_homography: np.ndarray


def _rotation_x(angle_rad: float) -> np.ndarray:
    c = math.cos(angle_rad)
    s = math.sin(angle_rad)
    return np.array([[1.0, 0.0, 0.0], [0.0, c, -s], [0.0, s, c]])


def _rotation_y(angle_rad: float) -> np.ndarray:
    c = math.cos(angle_rad)
    s = math.sin(angle_rad)
    return np.array([[c, 0.0, s], [0.0, 1.0, 0.0], [-s, 0.0, c]])


def _rotation_z(angle_rad: float) -> np.ndarray:
    c = math.cos(angle_rad)
    s = math.sin(angle_rad)
    return np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])


def attitude_rotation_matrix(
    roll_deg: float,
    pitch_deg: float,
    yaw_deg: float,
) -> np.ndarray:
    """
    Return camera attitude rotation from roll, pitch, yaw in degrees.

    The convention is yaw around Z, pitch around Y, roll around X. Exact signs
    must be validated against the mounted IMU/camera frame during calibration.
    """
    roll = math.radians(roll_deg)
    pitch = math.radians(pitch_deg)
    yaw = math.radians(yaw_deg)
    return _rotation_z(yaw) @ _rotation_y(pitch) @ _rotation_x(roll)


def camera_intrinsic_matrix(camera: CameraModel) -> np.ndarray:
    """Return camera intrinsics as a 3x3 NumPy matrix."""
    return np.array(camera.intrinsic_matrix, dtype=np.float64)


def normalization_homography(
    roll_deg: float,
    pitch_deg: float,
    yaw_deg: float,
    camera: CameraModel,
    include_yaw: bool = True,
) -> np.ndarray:
    """
    Estimate an image-plane homography that removes IMU attitude.

    For V1 this is used to normalize working images or initialize pairwise
    matching. It should not overwrite raw image geometry.
    """
    yaw = yaw_deg if include_yaw else 0.0
    rotation = attitude_rotation_matrix(roll_deg, pitch_deg, yaw)
    k = camera_intrinsic_matrix(camera)
    k_inv = np.linalg.inv(k)
    h = k @ rotation.T @ k_inv
    return h / h[2, 2]


def build_pose_prior(
    metadata: ImageMetadata,
    include_yaw: bool = True,
) -> PosePrior:
    """Build the IMU-derived pose prior for one image record."""
    rotation = attitude_rotation_matrix(
        metadata.roll_deg,
        metadata.pitch_deg,
        metadata.yaw_deg if include_yaw else 0.0,
    )
    homography = normalization_homography(
        metadata.roll_deg,
        metadata.pitch_deg,
        metadata.yaw_deg,
        metadata.camera,
        include_yaw=include_yaw,
    )
    return PosePrior(
        image_name=metadata.image_name,
        roll_deg=metadata.roll_deg,
        pitch_deg=metadata.pitch_deg,
        yaw_deg=metadata.yaw_deg,
        rotation_matrix=rotation,
        normalization_homography=homography,
    )


def relative_pose_prior(
    first: ImageMetadata,
    second: ImageMetadata,
    include_yaw: bool = True,
) -> np.ndarray:
    """Return a relative image homography prior from first image to second."""
    yaw_a = first.yaw_deg if include_yaw else 0.0
    yaw_b = second.yaw_deg if include_yaw else 0.0
    r_a = attitude_rotation_matrix(first.roll_deg, first.pitch_deg, yaw_a)
    r_b = attitude_rotation_matrix(second.roll_deg, second.pitch_deg, yaw_b)
    relative_rotation = r_b @ r_a.T
    k = camera_intrinsic_matrix(first.camera)
    h = k @ relative_rotation @ np.linalg.inv(k)
    return h / h[2, 2]

