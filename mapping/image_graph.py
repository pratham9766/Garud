"""Graph representation of image relationships for mosaicking."""

from __future__ import annotations

from dataclasses import dataclass, field
import math

import numpy as np

from sensor_fusion.pose_prior import relative_pose_prior
from storage.mission_manifest import ImageMetadata

EARTH_RADIUS_M = 6_371_000.0


@dataclass(frozen=True)
class ImageNode:
    """One captured image in the mapping graph."""

    image_name: str
    metadata: ImageMetadata


@dataclass(frozen=True)
class ImageEdge:
    """Potential or verified relationship between two image nodes."""

    source: str
    target: str
    distance_m: float
    yaw_delta_deg: float
    time_delta_s: float
    prior_homography: np.ndarray
    inlier_count: int = 0
    verified: bool = False


@dataclass
class ImageGraph:
    """Image graph with nodes for images and edges for match relationships."""

    nodes: dict[str, ImageNode] = field(default_factory=dict)
    edges: list[ImageEdge] = field(default_factory=list)

    def add_node(self, metadata: ImageMetadata) -> None:
        self.nodes[metadata.image_name] = ImageNode(
            image_name=metadata.image_name,
            metadata=metadata,
        )

    def add_edge(self, edge: ImageEdge) -> None:
        self.edges.append(edge)


def _distance_m(first: ImageMetadata, second: ImageMetadata) -> float:
    lat1 = math.radians(first.latitude)
    lat2 = math.radians(second.latitude)
    dlat = lat2 - lat1
    dlon = math.radians(second.longitude - first.longitude)
    a = (
        math.sin(dlat / 2.0) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2.0) ** 2
    )
    return 2.0 * EARTH_RADIUS_M * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))


def _angle_delta_deg(first: float, second: float) -> float:
    return abs((second - first + 180.0) % 360.0 - 180.0)


def build_candidate_graph(
    images: list[ImageMetadata] | tuple[ImageMetadata, ...],
    max_distance_m: float = 250.0,
    max_time_delta_s: float = 20.0,
    max_yaw_delta_deg: float = 80.0,
) -> ImageGraph:
    """
    Build a graph of plausible overlapping image pairs.

    GPS, time, and IMU yaw only reject impossible pairs before expensive visual
    matching. They do not prove a visual match.
    """
    graph = ImageGraph()
    for image in images:
        graph.add_node(image)

    image_list = list(images)
    for i, first in enumerate(image_list):
        for second in image_list[i + 1 :]:
            distance = _distance_m(first, second)
            time_delta = abs(second.timestamp - first.timestamp)
            yaw_delta = _angle_delta_deg(first.yaw_deg, second.yaw_deg)
            if distance > max_distance_m:
                continue
            if time_delta > max_time_delta_s:
                continue
            if yaw_delta > max_yaw_delta_deg:
                continue
            graph.add_edge(
                ImageEdge(
                    source=first.image_name,
                    target=second.image_name,
                    distance_m=distance,
                    yaw_delta_deg=yaw_delta,
                    time_delta_s=time_delta,
                    prior_homography=relative_pose_prior(first, second),
                )
            )
    return graph

