"""Sensor-assisted camera footprint prediction and overlap estimates."""

from __future__ import annotations

from dataclasses import dataclass
import math

import config
from storage.mission_manifest import ImageMetadata

EARTH_RADIUS_M = 6_371_000.0


@dataclass(frozen=True)
class Footprint:
    """Approximate image footprint in a local metric frame."""

    image_name: str
    center_east_m: float
    center_north_m: float
    width_m: float
    height_m: float
    yaw_deg: float
    corners_m: tuple[tuple[float, float], ...]

    @property
    def area_m2(self) -> float:
        return self.width_m * self.height_m


def latlon_to_local_m(
    lat: float,
    lon: float,
    ref_lat: float,
    ref_lon: float,
) -> tuple[float, float]:
    """Convert latitude/longitude to local east/north meters."""
    north_m = math.radians(lat - ref_lat) * EARTH_RADIUS_M
    east_m = (
        math.radians(lon - ref_lon)
        * EARTH_RADIUS_M
        * math.cos(math.radians(ref_lat))
    )
    return east_m, north_m


def footprint_size_m(metadata: ImageMetadata) -> tuple[float, float]:
    """Estimate ground footprint size, loosely expanding for roll/pitch."""
    altitude_m = max(
        metadata.baro_altitude_m or metadata.gps_altitude_m,
        config.MAPPING_MIN_FOOTPRINT_ALTITUDE_M,
    )
    width_m = 2.0 * altitude_m * math.tan(
        math.radians(config.CAMERA_HORIZONTAL_FOV_DEG) / 2.0
    )
    height_m = 2.0 * altitude_m * math.tan(
        math.radians(config.CAMERA_VERTICAL_FOV_DEG) / 2.0
    )

    tilt_rad = math.radians(min(70.0, math.hypot(metadata.roll_deg, metadata.pitch_deg)))
    expansion = 1.0 / max(0.35, math.cos(tilt_rad))
    return width_m * expansion, height_m * expansion


def predict_footprint(
    metadata: ImageMetadata,
    ref_lat: float,
    ref_lon: float,
) -> Footprint:
    """Predict one approximate rotated footprint in local metric coordinates."""
    center_east, center_north = latlon_to_local_m(
        metadata.latitude,
        metadata.longitude,
        ref_lat,
        ref_lon,
    )
    width_m, height_m = footprint_size_m(metadata)
    half_w = width_m / 2.0
    half_h = height_m / 2.0
    yaw = math.radians(metadata.yaw_deg)
    cos_yaw = math.cos(yaw)
    sin_yaw = math.sin(yaw)

    local = ((-half_w, half_h), (half_w, half_h), (half_w, -half_h), (-half_w, -half_h))
    corners: list[tuple[float, float]] = []
    for east, north in local:
        rotated_east = east * cos_yaw + north * sin_yaw
        rotated_north = -east * sin_yaw + north * cos_yaw
        corners.append((center_east + rotated_east, center_north + rotated_north))

    return Footprint(
        image_name=metadata.image_name,
        center_east_m=center_east,
        center_north_m=center_north,
        width_m=width_m,
        height_m=height_m,
        yaw_deg=metadata.yaw_deg,
        corners_m=tuple(corners),
    )


def _bounds(poly: tuple[tuple[float, float], ...]) -> tuple[float, float, float, float]:
    xs = [x for x, _ in poly]
    ys = [y for _, y in poly]
    return min(xs), min(ys), max(xs), max(ys)


def approximate_overlap_ratio(first: Footprint, second: Footprint) -> float:
    """
    Estimate footprint overlap using axis-aligned bounds.

    This is intentionally approximate. It cheaply rejects impossible pairs;
    visual geometry later verifies any accepted edge.
    """
    a_min_x, a_min_y, a_max_x, a_max_y = _bounds(first.corners_m)
    b_min_x, b_min_y, b_max_x, b_max_y = _bounds(second.corners_m)
    inter_w = max(0.0, min(a_max_x, b_max_x) - max(a_min_x, b_min_x))
    inter_h = max(0.0, min(a_max_y, b_max_y) - max(a_min_y, b_min_y))
    inter_area = inter_w * inter_h
    if inter_area <= 0.0:
        return 0.0
    smaller = max(1.0, min(first.area_m2, second.area_m2))
    return max(0.0, min(1.0, inter_area / smaller))
