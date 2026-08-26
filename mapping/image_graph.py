"""Sensor-assisted image graph for post-flight reconstruction."""

from __future__ import annotations

from dataclasses import dataclass, field
import math

import numpy as np

import config
from mapping.footprint import Footprint, approximate_overlap_ratio, predict_footprint
from sensor_fusion.pose_prior import relative_pose_prior
from storage.mission_manifest import ImageMetadata

EARTH_RADIUS_M = 6_371_000.0


@dataclass(frozen=True)
class ImageNode:
    """One captured image in the mapping graph."""

    image_name: str
    metadata: ImageMetadata
    footprint: Footprint | None = None
    quality_status: str = "UNKNOWN"
    quality_score: float = 1.0


@dataclass(frozen=True)
class ImageEdge:
    """Potential or verified relationship between two image nodes."""

    source: str
    target: str
    distance_m: float
    yaw_delta_deg: float
    time_delta_s: float
    altitude_ratio: float
    roll_pitch_delta_deg: float
    predicted_overlap: float
    score: float
    reason: str
    prior_homography: np.ndarray
    inlier_count: int = 0
    verified: bool = False


@dataclass
class ImageGraph:
    """Image graph with nodes for images and edges for match relationships."""

    nodes: dict[str, ImageNode] = field(default_factory=dict)
    edges: list[ImageEdge] = field(default_factory=list)

    def add_node(
        self,
        metadata: ImageMetadata,
        footprint: Footprint | None = None,
        quality_status: str = "UNKNOWN",
        quality_score: float = 1.0,
    ) -> None:
        self.nodes[metadata.image_name] = ImageNode(
            image_name=metadata.image_name,
            metadata=metadata,
            footprint=footprint,
            quality_status=quality_status,
            quality_score=quality_score,
        )

    def add_edge(self, edge: ImageEdge) -> None:
        self.edges.append(edge)


def distance_m(first: ImageMetadata, second: ImageMetadata) -> float:
    """Great-circle distance between two image GPS positions."""
    lat1 = math.radians(first.latitude)
    lat2 = math.radians(second.latitude)
    dlat = lat2 - lat1
    dlon = math.radians(second.longitude - first.longitude)
    a = (
        math.sin(dlat / 2.0) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2.0) ** 2
    )
    return 2.0 * EARTH_RADIUS_M * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))


def angle_delta_deg(first: float, second: float) -> float:
    """Smallest absolute angle difference in degrees."""
    return abs((second - first + 180.0) % 360.0 - 180.0)


def _altitude_ratio(first: ImageMetadata, second: ImageMetadata) -> float:
    a = max(
        first.baro_altitude_m or first.gps_altitude_m,
        config.MAPPING_MIN_FOOTPRINT_ALTITUDE_M,
    )
    b = max(
        second.baro_altitude_m or second.gps_altitude_m,
        config.MAPPING_MIN_FOOTPRINT_ALTITUDE_M,
    )
    return max(a, b) / max(1e-6, min(a, b))


def _roll_pitch_delta(first: ImageMetadata, second: ImageMetadata) -> float:
    return math.hypot(
        first.roll_deg - second.roll_deg,
        first.pitch_deg - second.pitch_deg,
    )


def _edge_score(
    distance: float,
    time_delta: float,
    yaw_delta: float,
    altitude_ratio: float,
    roll_pitch_delta: float,
    overlap: float,
    quality_a: float,
    quality_b: float,
    reason: str,
) -> float:
    distance_score = max(0.0, 1.0 - distance / max(config.MAPPING_MAX_GPS_DISTANCE_M, 1.0))
    time_score = max(0.0, 1.0 - time_delta / max(config.MAPPING_MAX_TIME_SEPARATION_SEC, 1.0))
    yaw_score = max(0.0, 1.0 - yaw_delta / max(config.MAPPING_MAX_YAW_DIFF_DEG, 1.0))
    altitude_score = max(
        0.0,
        1.0 - (altitude_ratio - 1.0) / max(config.MAPPING_MAX_ALTITUDE_RATIO - 1.0, 1.0),
    )
    pose_score = max(0.0, 1.0 - roll_pitch_delta / max(config.MAPPING_MAX_ROLL_PITCH_DIFF_DEG, 1.0))
    quality_score = min(quality_a, quality_b)
    temporal_bonus = 0.08 if reason == "temporal" else 0.0
    return (
        0.24 * overlap
        + 0.18 * distance_score
        + 0.15 * time_score
        + 0.13 * yaw_score
        + 0.10 * altitude_score
        + 0.10 * pose_score
        + 0.10 * quality_score
        + temporal_bonus
    )


def _spatial_cell(metadata: ImageMetadata, ref_lat: float, ref_lon: float) -> tuple[int, int]:
    from mapping.footprint import latlon_to_local_m

    east, north = latlon_to_local_m(metadata.latitude, metadata.longitude, ref_lat, ref_lon)
    grid = max(config.MAPPING_SPATIAL_GRID_M, 1.0)
    return math.floor(east / grid), math.floor(north / grid)


def _neighbor_cells(cell: tuple[int, int]) -> list[tuple[int, int]]:
    x, y = cell
    return [(x + dx, y + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)]


def build_candidate_graph(
    images: list[ImageMetadata] | tuple[ImageMetadata, ...],
    max_distance_m: float | None = None,
    max_time_delta_s: float | None = None,
    max_yaw_delta_deg: float | None = None,
    qualities: dict[str, object] | None = None,
    max_neighbors_per_image: int | None = None,
) -> ImageGraph:
    """
    Build a graph of plausible overlapping image pairs without all-to-all matching.

    GPS, barometer, IMU, timestamp, predicted footprint overlap, and image
    quality only select candidates. Visual geometry still verifies the edges.
    """
    max_distance_m = max_distance_m or config.MAPPING_MAX_GPS_DISTANCE_M
    max_time_delta_s = max_time_delta_s or config.MAPPING_MAX_TIME_SEPARATION_SEC
    max_yaw_delta_deg = max_yaw_delta_deg or config.MAPPING_MAX_YAW_DIFF_DEG
    max_neighbors_per_image = max_neighbors_per_image or config.MAPPING_MAX_NEIGHBORS_PER_IMAGE

    image_list = sorted(list(images), key=lambda item: item.timestamp)
    graph = ImageGraph()
    if not image_list:
        return graph

    has_gps = any(
        abs(image.latitude) > 1e-9 and abs(image.longitude) > 1e-9
        for image in image_list
    )
    ref_lat = next((img.latitude for img in image_list if img.latitude), image_list[0].latitude)
    ref_lon = next((img.longitude for img in image_list if img.longitude), image_list[0].longitude)
    footprints = {
        image.image_name: predict_footprint(image, ref_lat, ref_lon)
        for image in image_list
    }
    quality_scores: dict[str, float] = {}
    quality_status: dict[str, str] = {}
    for image in image_list:
        quality = qualities.get(image.image_name) if qualities else None
        quality_scores[image.image_name] = float(getattr(quality, "total_score", 1.0))
        quality_status[image.image_name] = str(getattr(quality, "status", "UNKNOWN"))
        graph.add_node(
            image,
            footprint=footprints[image.image_name],
            quality_status=quality_status[image.image_name],
            quality_score=quality_scores[image.image_name],
        )

    spatial: dict[tuple[int, int], list[int]] = {}
    if has_gps:
        for idx, image in enumerate(image_list):
            spatial.setdefault(_spatial_cell(image, ref_lat, ref_lon), []).append(idx)

    candidates_by_image: dict[int, list[ImageEdge]] = {
        idx: [] for idx in range(len(image_list))
    }
    seen: set[tuple[int, int]] = set()

    def consider(i: int, j: int, reason: str) -> None:
        if i == j:
            return
        a, b = sorted((i, j))
        if (a, b) in seen:
            return
        first = image_list[a]
        second = image_list[b]
        distance = distance_m(first, second)
        time_delta = abs(second.timestamp - first.timestamp)
        yaw_delta = angle_delta_deg(first.yaw_deg, second.yaw_deg)
        altitude_ratio = _altitude_ratio(first, second)
        roll_pitch_delta = _roll_pitch_delta(first, second)
        overlap = approximate_overlap_ratio(
            footprints[first.image_name],
            footprints[second.image_name],
        )

        temporal_fallback = reason == "temporal" and time_delta <= max_time_delta_s
        plausible = (
            distance <= max_distance_m
            and time_delta <= max_time_delta_s
            and yaw_delta <= max_yaw_delta_deg
            and altitude_ratio <= config.MAPPING_MAX_ALTITUDE_RATIO
            and roll_pitch_delta <= config.MAPPING_MAX_ROLL_PITCH_DIFF_DEG
            and overlap >= config.MAPPING_MIN_PREDICTED_OVERLAP
        )
        if not plausible and not temporal_fallback:
            return

        seen.add((a, b))
        score = _edge_score(
            distance,
            time_delta,
            yaw_delta,
            altitude_ratio,
            roll_pitch_delta,
            overlap,
            quality_scores[first.image_name],
            quality_scores[second.image_name],
            reason,
        )
        edge = ImageEdge(
            source=first.image_name,
            target=second.image_name,
            distance_m=distance,
            yaw_delta_deg=yaw_delta,
            time_delta_s=time_delta,
            altitude_ratio=altitude_ratio,
            roll_pitch_delta_deg=roll_pitch_delta,
            predicted_overlap=overlap,
            score=score,
            reason=reason,
            prior_homography=relative_pose_prior(first, second),
        )
        candidates_by_image[a].append(edge)
        candidates_by_image[b].append(edge)

    for idx, image in enumerate(image_list):
        if has_gps:
            cell = _spatial_cell(image, ref_lat, ref_lon)
            for neighbor_cell in _neighbor_cells(cell):
                for other_idx in spatial.get(neighbor_cell, []):
                    if other_idx > idx:
                        consider(idx, other_idx, "spatial")
        temporal_window = config.MAPPING_TEMPORAL_NEIGHBORS if has_gps else max(
            config.MAPPING_TEMPORAL_NEIGHBORS,
            max_neighbors_per_image,
        )
        for offset in range(1, temporal_window + 1):
            if idx + offset < len(image_list):
                consider(idx, idx + offset, "temporal")

    selected: dict[tuple[str, str], ImageEdge] = {}
    for edges in candidates_by_image.values():
        for edge in sorted(
            edges,
            key=lambda item: item.score,
            reverse=True,
        )[:max_neighbors_per_image]:
            key = tuple(sorted((edge.source, edge.target)))
            if key not in selected or edge.score > selected[key].score:
                selected[key] = edge

    for edge in sorted(selected.values(), key=lambda item: item.score, reverse=True):
        graph.add_edge(edge)
    return graph
