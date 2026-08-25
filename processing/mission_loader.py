"""Load and validate stored mission data for offline mapping."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from storage.mission_manifest import ImageMetadata, load_image_metadata


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


def load_mission_data(csv_path: Path, image_dir: Path | None = None) -> MissionData:
    """Load mission data from the CSV log and associated image directory."""
    records = tuple(load_image_metadata(csv_path, image_dir=image_dir))
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

