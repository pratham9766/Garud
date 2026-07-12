"""
Camera-footprint and coverage estimation for ground mapping.

The algorithm treats each geotagged image as a nadir-looking camera footprint:
altitude and camera field-of-view define the ground rectangle, yaw rotates that
rectangle, and GPS fixes anchor it on the map. Unique coverage is estimated by
rasterizing those rectangles onto a small metric grid.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable

import pandas as pd

import config

EARTH_RADIUS_M = 6_371_000.0


@dataclass(frozen=True)
class ImageFootprint:
    """Estimated ground footprint for one captured image."""

    image_name: str
    center_lat: float
    center_lon: float
    altitude_m: float
    yaw_deg: float
    width_m: float
    height_m: float
    corners: list[tuple[float, float]]

    @property
    def area_m2(self) -> float:
        return self.width_m * self.height_m


def _valid_number(value: object, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(result):
        return default
    return result


def _meters_to_latlon(
    lat: float,
    lon: float,
    east_m: float,
    north_m: float,
) -> tuple[float, float]:
    dlat = north_m / EARTH_RADIUS_M
    cos_lat = max(math.cos(math.radians(lat)), 1e-9)
    dlon = east_m / (EARTH_RADIUS_M * cos_lat)
    return lat + math.degrees(dlat), lon + math.degrees(dlon)


def _latlon_to_meters(
    lat: float,
    lon: float,
    ref_lat: float,
    ref_lon: float,
) -> tuple[float, float]:
    north_m = math.radians(lat - ref_lat) * EARTH_RADIUS_M
    east_m = (
        math.radians(lon - ref_lon)
        * EARTH_RADIUS_M
        * math.cos(math.radians(ref_lat))
    )
    return east_m, north_m


def _point_in_polygon(
    point: tuple[float, float],
    polygon: list[tuple[float, float]],
) -> bool:
    x, y = point
    inside = False
    j = len(polygon) - 1
    for i, (xi, yi) in enumerate(polygon):
        xj, yj = polygon[j]
        crosses = (yi > y) != (yj > y)
        if crosses:
            x_at_y = (xj - xi) * (y - yi) / (yj - yi) + xi
            if x < x_at_y:
                inside = not inside
        j = i
    return inside


def footprint_dimensions(
    altitude_m: float,
    horizontal_fov_deg: float | None = None,
    vertical_fov_deg: float | None = None,
) -> tuple[float, float]:
    """
    Return estimated ground footprint width and height in meters.

    The model assumes a nadir camera and flat terrain:
        ground_size = 2 * altitude * tan(field_of_view / 2)
    """
    altitude_m = max(altitude_m, config.MAPPING_MIN_FOOTPRINT_ALTITUDE_M)
    horizontal_fov_deg = horizontal_fov_deg or config.CAMERA_HORIZONTAL_FOV_DEG
    vertical_fov_deg = vertical_fov_deg or config.CAMERA_VERTICAL_FOV_DEG

    width_m = 2.0 * altitude_m * math.tan(math.radians(horizontal_fov_deg) / 2.0)
    height_m = 2.0 * altitude_m * math.tan(math.radians(vertical_fov_deg) / 2.0)
    return width_m, height_m


def build_footprint(
    lat: float,
    lon: float,
    altitude_m: float,
    yaw_deg: float,
    image_name: str,
) -> ImageFootprint:
    """Build one rotated image footprint polygon."""
    width_m, height_m = footprint_dimensions(altitude_m)
    half_w = width_m / 2.0
    half_h = height_m / 2.0
    yaw_rad = math.radians(yaw_deg)
    cos_yaw = math.cos(yaw_rad)
    sin_yaw = math.sin(yaw_rad)

    local_corners = [
        (-half_w, half_h),
        (half_w, half_h),
        (half_w, -half_h),
        (-half_w, -half_h),
    ]
    corners: list[tuple[float, float]] = []
    for east, north in local_corners:
        rotated_east = east * cos_yaw + north * sin_yaw
        rotated_north = -east * sin_yaw + north * cos_yaw
        corners.append(_meters_to_latlon(lat, lon, rotated_east, rotated_north))

    return ImageFootprint(
        image_name=str(image_name),
        center_lat=lat,
        center_lon=lon,
        altitude_m=max(altitude_m, config.MAPPING_MIN_FOOTPRINT_ALTITUDE_M),
        yaw_deg=yaw_deg,
        width_m=width_m,
        height_m=height_m,
        corners=corners,
    )


def build_image_footprints(df: pd.DataFrame) -> list[ImageFootprint]:
    """Create footprints for CSV rows that contain valid coordinates and images."""
    required = {"latitude", "longitude", "image_name"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing mapping columns: {', '.join(sorted(missing))}")

    footprints: list[ImageFootprint] = []
    image_rows = df[
        df["image_name"].notna() & (df["image_name"].astype(str).str.len() > 0)
    ]
    for _, row in image_rows.iterrows():
        lat = _valid_number(row.get("latitude"))
        lon = _valid_number(row.get("longitude"))
        if lat == 0.0 or lon == 0.0:
            continue

        altitude_m = _valid_number(row.get("baro_altitude"))
        if altitude_m <= 0.0:
            altitude_m = _valid_number(row.get("gps_altitude"))
        yaw_deg = _valid_number(row.get("yaw"))
        footprints.append(
            build_footprint(lat, lon, altitude_m, yaw_deg, str(row["image_name"]))
        )

    return footprints


def estimate_coverage_area(
    footprints: Iterable[ImageFootprint],
    grid_size_m: float | None = None,
) -> dict:
    """
    Estimate unique mapped area by rasterizing footprint polygons.

    This avoids adding heavyweight geometry dependencies while still handling
    overlap better than a simple sum of rectangle areas.
    """
    footprint_list = list(footprints)
    if not footprint_list:
        return {
            "image_count": 0,
            "raw_area_m2": 0.0,
            "unique_area_m2": 0.0,
            "overlap_area_m2": 0.0,
            "coverage_grid_m": grid_size_m or config.MAPPING_COVERAGE_GRID_M,
        }

    grid_size_m = grid_size_m or config.MAPPING_COVERAGE_GRID_M
    ref_lat = footprint_list[0].center_lat
    ref_lon = footprint_list[0].center_lon
    occupied: set[tuple[int, int]] = set()
    raw_area_m2 = 0.0

    for footprint in footprint_list:
        raw_area_m2 += footprint.area_m2
        polygon_m = [
            _latlon_to_meters(lat, lon, ref_lat, ref_lon)
            for lat, lon in footprint.corners
        ]
        min_x = min(x for x, _ in polygon_m)
        max_x = max(x for x, _ in polygon_m)
        min_y = min(y for _, y in polygon_m)
        max_y = max(y for _, y in polygon_m)

        ix_start = math.floor(min_x / grid_size_m)
        ix_end = math.ceil(max_x / grid_size_m)
        iy_start = math.floor(min_y / grid_size_m)
        iy_end = math.ceil(max_y / grid_size_m)

        for ix in range(ix_start, ix_end):
            for iy in range(iy_start, iy_end):
                center = ((ix + 0.5) * grid_size_m, (iy + 0.5) * grid_size_m)
                if _point_in_polygon(center, polygon_m):
                    occupied.add((ix, iy))

    unique_area_m2 = len(occupied) * grid_size_m * grid_size_m
    return {
        "image_count": len(footprint_list),
        "raw_area_m2": raw_area_m2,
        "unique_area_m2": unique_area_m2,
        "overlap_area_m2": max(0.0, raw_area_m2 - unique_area_m2),
        "coverage_grid_m": grid_size_m,
    }
