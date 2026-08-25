"""
Mission metadata records used by the offline photogrammetry pipeline.

The onboard system should only capture and persist data. Processing modules
consume these records after recovery and must not depend on hardware drivers.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pandas as pd

import config


@dataclass(frozen=True)
class CameraModel:
    """Pinhole camera model plus lens distortion coefficients."""

    width_px: int = config.CAMERA_SENSOR_WIDTH_PX
    height_px: int = config.CAMERA_SENSOR_HEIGHT_PX
    focal_length_px: float = config.CAMERA_FOCAL_LENGTH_PX
    center_x_px: float = config.CAMERA_CENTER_X_PX
    center_y_px: float = config.CAMERA_CENTER_Y_PX
    distortion_coeffs: tuple[float, ...] = tuple(config.CAMERA_DISTORTION_COEFFS)

    @property
    def intrinsic_matrix(self) -> list[list[float]]:
        return [
            [self.focal_length_px, 0.0, self.center_x_px],
            [0.0, self.focal_length_px, self.center_y_px],
            [0.0, 0.0, 1.0],
        ]


@dataclass(frozen=True)
class ImageMetadata:
    """Synchronized sensor metadata for one captured image."""

    image_name: str
    image_path: Path
    timestamp: float
    latitude: float
    longitude: float
    gps_altitude_m: float
    baro_altitude_m: float
    roll_deg: float
    pitch_deg: float
    yaw_deg: float
    gyro_x_dps: float
    gyro_y_dps: float
    gyro_z_dps: float
    camera: CameraModel

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["image_path"] = str(self.image_path)
        return data


def _number(value: object, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def load_image_metadata(
    csv_path: Path,
    image_dir: Path | None = None,
    camera: CameraModel | None = None,
) -> list[ImageMetadata]:
    """Load synchronized image records from a mission CSV log."""
    image_dir = image_dir or config.IMAGE_SAVE_PATH
    camera = camera or CameraModel()
    df = pd.read_csv(csv_path)
    if "image_name" not in df.columns:
        raise ValueError("Mission CSV does not contain image_name.")

    rows = df[
        df["image_name"].notna() & (df["image_name"].astype(str).str.len() > 0)
    ]
    records: list[ImageMetadata] = []
    for _, row in rows.iterrows():
        image_name = str(row["image_name"])
        timestamp = _number(row.get("image_timestamp"), _number(row.get("timestamp")))
        records.append(
            ImageMetadata(
                image_name=image_name,
                image_path=image_dir / image_name,
                timestamp=timestamp,
                latitude=_number(row.get("latitude")),
                longitude=_number(row.get("longitude")),
                gps_altitude_m=_number(row.get("gps_altitude")),
                baro_altitude_m=_number(row.get("baro_altitude")),
                roll_deg=_number(row.get("roll")),
                pitch_deg=_number(row.get("pitch")),
                yaw_deg=_number(row.get("yaw")),
                gyro_x_dps=_number(row.get("gyro_x")),
                gyro_y_dps=_number(row.get("gyro_y")),
                gyro_z_dps=_number(row.get("gyro_z")),
                camera=camera,
            )
        )
    return records

