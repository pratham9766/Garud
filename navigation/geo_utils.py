"""Small-region geodetic/local-frame helpers for GARUDA navigation."""

from __future__ import annotations

import math

EARTH_RADIUS_M = 6_371_000.0


def is_finite_number(value: object) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(float(value))


def wrap_360(degrees: float) -> float:
    return float(degrees) % 360.0


def angle_diff_deg(a_deg: float, b_deg: float) -> float:
    return ((a_deg - b_deg + 180.0) % 360.0) - 180.0


def circular_lerp_deg(previous_deg: float, new_deg: float, alpha: float) -> float:
    alpha = max(0.0, min(1.0, alpha))
    return wrap_360(previous_deg + alpha * angle_diff_deg(new_deg, previous_deg))


def valid_lat_lon(latitude: object, longitude: object) -> bool:
    if not is_finite_number(latitude) or not is_finite_number(longitude):
        return False
    lat = float(latitude)
    lon = float(longitude)
    return -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0


def geodetic_to_local(
    latitude: float,
    longitude: float,
    origin_latitude: float,
    origin_longitude: float,
) -> tuple[float, float]:
    """Convert lat/lon to local north/east meters with an equirectangular frame."""
    lat = math.radians(latitude)
    lon = math.radians(longitude)
    lat0 = math.radians(origin_latitude)
    lon0 = math.radians(origin_longitude)
    mean_lat = 0.5 * (lat + lat0)
    north = (lat - lat0) * EARTH_RADIUS_M
    east = (lon - lon0) * EARTH_RADIUS_M * math.cos(mean_lat)
    return north, east


def local_to_geodetic(
    north_m: float,
    east_m: float,
    origin_latitude: float,
    origin_longitude: float,
) -> tuple[float, float]:
    """Convert local north/east meters back to latitude/longitude."""
    lat0 = math.radians(origin_latitude)
    lon0 = math.radians(origin_longitude)
    lat = lat0 + north_m / EARTH_RADIUS_M
    mean_lat = 0.5 * (lat + lat0)
    cos_lat = max(1e-9, abs(math.cos(mean_lat)))
    lon = lon0 + east_m / (EARTH_RADIUS_M * cos_lat)
    return math.degrees(lat), math.degrees(lon)


def distance_m(
    lat_a: float,
    lon_a: float,
    lat_b: float,
    lon_b: float,
) -> float:
    north, east = geodetic_to_local(lat_b, lon_b, lat_a, lon_a)
    return math.hypot(north, east)


def velocity_from_speed_course(speed_mps: float, course_deg: float) -> tuple[float, float]:
    """Return VN/VE from GPS speed/course, with 0 deg = north and 90 deg = east."""
    course_rad = math.radians(wrap_360(course_deg))
    return speed_mps * math.cos(course_rad), speed_mps * math.sin(course_rad)


def speed_course_from_velocity(vn_mps: float, ve_mps: float) -> tuple[float, float]:
    speed = math.hypot(vn_mps, ve_mps)
    if speed <= 1e-9:
        return 0.0, 0.0
    return speed, wrap_360(math.degrees(math.atan2(ve_mps, vn_mps)))
