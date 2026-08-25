"""Load and validate stored mission data for offline mapping."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

import config
from sensor_fusion.timestamp_sync import sync_image_rows
from storage.mission_manifest import CameraModel, ImageMetadata


@dataclass(frozen=True)
class MissionData:
    """Recovered mission data used by the processing pipeline."""

    csv_path: Path
    images: tuple[ImageMetadata, ...]


REQUIRED_COLUMNS = {
    "timestamp",
    "latitude",
    "longitude",
    "baro_altitude",
    "roll",
    "pitch",
    "yaw",
    "image_name",
}


def _number(value: object, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def load_mission_data(csv_path: Path, image_dir: Path | None = None) -> MissionData:
    """Load mission data from the CSV log and associated image directory."""
    image_dir = image_dir or config.IMAGE_SAVE_PATH
    df = pd.read_csv(csv_path)
    camera = CameraModel()
    records: list[ImageMetadata] = []
    for image_name, row, sync in sync_image_rows(
        df,
        interpolate=config.MAPPING_INTERPOLATE_SENSOR_TIMELINE,
    ):
        records.append(
            ImageMetadata(
                image_name=image_name,
                image_path=image_dir / image_name,
                timestamp=sync.sample_timestamp,
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
                image_timestamp=sync.image_timestamp,
                mission_state=str(row.get("state", "")),
            )
        )
    return MissionData(csv_path=Path(csv_path), images=records)


def validate_mission_data(mission: MissionData) -> list[str]:
    """Return validation issues found in mission image metadata."""
    issues: list[str] = []
    if not mission.images:
        issues.append("No image metadata records found.")

    missing_files = [str(record.image_path) for record in mission.images if not record.image_path.exists()]
    if missing_files:
        issues.append(f"Missing image files: {len(missing_files)}")

    missing_gps = [
        record.image_name
        for record in mission.images
        if record.latitude == 0.0 or record.longitude == 0.0
    ]
    if missing_gps:
        issues.append(f"Images without GPS fix: {len(missing_gps)}")

    missing_attitude = [
        record.image_name
        for record in mission.images
        if record.roll_deg == 0.0 and record.pitch_deg == 0.0 and record.yaw_deg == 0.0
    ]
    if missing_attitude:
        issues.append(f"Images without nonzero attitude: {len(missing_attitude)}")

    return issues
