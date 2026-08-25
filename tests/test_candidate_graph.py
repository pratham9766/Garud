"""Sensor-assisted candidate graph tests."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from mapping.image_graph import build_candidate_graph
from storage.mission_manifest import CameraModel, ImageMetadata


def _metadata(name: str, ts: float, lat: float, lon: float, yaw: float = 0.0) -> ImageMetadata:
    return ImageMetadata(
        image_name=name,
        image_path=Path(name),
        timestamp=ts,
        latitude=lat,
        longitude=lon,
        gps_altitude_m=100.0,
        baro_altitude_m=95.0,
        roll_deg=1.0,
        pitch_deg=1.0,
        yaw_deg=yaw,
        gyro_x_dps=0.0,
        gyro_y_dps=0.0,
        gyro_z_dps=0.0,
        camera=CameraModel(width_px=640, height_px=480, focal_length_px=500.0),
    )


def test_graph_supports_non_consecutive_edges() -> None:
    images = (
        _metadata("a.jpg", 1.0, 18.52040, 73.85670),
        _metadata("b.jpg", 2.0, 18.52043, 73.85673),
        _metadata("c.jpg", 3.0, 18.52046, 73.85676),
    )
    graph = build_candidate_graph(images, max_distance_m=100.0)
    pairs = {tuple(sorted((edge.source, edge.target))) for edge in graph.edges}
    assert ("a.jpg", "c.jpg") in pairs
    assert len(graph.edges) <= 3 * 8


if __name__ == "__main__":
    test_graph_supports_non_consecutive_edges()
    print("Candidate graph tests passed.")
