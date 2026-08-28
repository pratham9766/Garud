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
    image_timestamp: float = 0.0
    mission_state: str = ""
    ahrs_timestamp_ns: int = 0
    ahrs_source: str = ""
    ahrs_valid: bool = False
    ahrs_confidence: str = ""
    quat_w: float = 1.0
    quat_x: float = 0.0
    quat_y: float = 0.0
    quat_z: float = 0.0

    @property
    def gps_altitude(self) -> float:
        return self.gps_altitude_m

    @property
    def baro_altitude(self) -> float:
        return self.baro_altitude_m

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
    """Load synchronized image records from a mission CSV log.

    The onboard logger stores only rows of shared state. This loader keeps one
    metadata record per image and chooses the row closest to the camera capture
    timestamp, avoiding decoded image data entirely.
    """
    image_dir = image_dir or config.IMAGE_SAVE_PATH
    camera = camera or CameraModel()
    df = pd.read_csv(csv_path)
    if "image_name" not in df.columns:
        raise ValueError("Mission CSV does not contain image_name.")

    rows = df[
        df["image_name"].notna() & (df["image_name"].astype(str).str.len() > 0)
    ]
    if "image_timestamp" not in rows.columns:
        rows = rows.copy()
        rows["image_timestamp"] = rows.get("timestamp", 0.0)

    records: list[ImageMetadata] = []
    for image_name, group in rows.groupby(rows["image_name"].astype(str), sort=False):
        group = group.copy()
        group["_sync_target"] = group["image_timestamp"].apply(_number)
        group["_sample_time"] = group["timestamp"].apply(_number)
        target = _number(group.iloc[0].get("image_timestamp"), _number(group.iloc[0].get("timestamp")))
        if target:
            idx = (group["_sample_time"] - target).abs().idxmin()
            row = group.loc[idx]
        else:
            row = group.iloc[0]
        image_name = str(row["image_name"])
        image_timestamp = _number(row.get("image_timestamp"), _number(row.get("timestamp")))
        timestamp = image_timestamp or _number(row.get("timestamp"))
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
                image_timestamp=image_timestamp,
                mission_state=str(row.get("state", "")),
                ahrs_timestamp_ns=int(_number(row.get("ahrs_timestamp_ns"), 0.0)),
                ahrs_source=str(row.get("ahrs_source", "")),
                ahrs_valid=bool(_number(row.get("ahrs_valid"), 0.0)),
                ahrs_confidence=str(row.get("ahrs_confidence", "")),
                quat_w=_number(row.get("quat_w"), 1.0),
                quat_x=_number(row.get("quat_x")),
                quat_y=_number(row.get("quat_y")),
                quat_z=_number(row.get("quat_z")),
            )
        )
    return records
