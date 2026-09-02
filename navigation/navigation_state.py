"""Explicit navigation state and quality enums."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class NavigationMode(str, Enum):
    INITIALIZING = "INITIALIZING"
    GOOD = "GOOD"
    DEGRADED = "DEGRADED"
    GPS_LOST = "GPS_LOST"
    RECOVERING = "RECOVERING"
    UNRELIABLE = "UNRELIABLE"


class PositionQuality(str, Enum):
    INVALID = "INVALID"
    GOOD = "GOOD"
    DEGRADED = "DEGRADED"
    DEAD_RECKONING = "DEAD_RECKONING"
    UNRELIABLE = "UNRELIABLE"


class HeadingQuality(str, Enum):
    INVALID = "INVALID"
    GOOD = "GOOD"
    GPS_COURSE = "GPS_COURSE"
    DEGRADED = "DEGRADED"


class AltitudeQuality(str, Enum):
    INVALID = "INVALID"
    GOOD = "GOOD"
    DEGRADED = "DEGRADED"


class PositionSource(str, Enum):
    NONE = "NONE"
    GPS = "GPS"
    PREDICTED = "PREDICTED"
    RECOVERY = "RECOVERY"


@dataclass(frozen=True)
class NavigationState:
    timestamp_ns: int = 0
    origin_latitude: float = 0.0
    origin_longitude: float = 0.0
    estimated_latitude: float = 0.0
    estimated_longitude: float = 0.0
    estimated_north_m: float = 0.0
    estimated_east_m: float = 0.0
    estimated_altitude_m: float = 0.0
    estimated_agl_m: float = 0.0
    estimated_velocity_north_mps: float = 0.0
    estimated_velocity_east_mps: float = 0.0
    estimated_ground_speed_mps: float = 0.0
    estimated_course_deg: float = 0.0
    estimated_heading_deg: float = 0.0
    navigation_mode: NavigationMode = NavigationMode.INITIALIZING
    position_quality: PositionQuality = PositionQuality.INVALID
    heading_quality: HeadingQuality = HeadingQuality.INVALID
    altitude_quality: AltitudeQuality = AltitudeQuality.INVALID
    position_source: PositionSource = PositionSource.NONE
    gps_valid: bool = False
    gps_rejected: bool = False
    gps_rejection_reason: str = "NO_SAMPLE"
    gps_age_ms: float = -1.0
    gps_position_error_m: float = -1.0
    dead_reckoning_active: bool = False
    dead_reckoning_age_s: float = 0.0
    recovery_active: bool = False
    navigation_valid: bool = False
    safe_for_guidance: bool = False
    consecutive_good_gps: int = 0
    consecutive_bad_gps: int = 0
    estimator_reset_count: int = 0
    last_event: str = ""

    def as_shared_updates(self) -> dict[str, object]:
        """Flatten for SharedData without exposing enum objects."""
        return {
            "nav_timestamp_ns": self.timestamp_ns,
            "nav_origin_latitude": self.origin_latitude,
            "nav_origin_longitude": self.origin_longitude,
            "estimated_latitude": self.estimated_latitude,
            "estimated_longitude": self.estimated_longitude,
            "estimated_north_m": self.estimated_north_m,
            "estimated_east_m": self.estimated_east_m,
            "estimated_altitude_m": self.estimated_altitude_m,
            "estimated_agl_m": self.estimated_agl_m,
            "estimated_velocity_north_mps": self.estimated_velocity_north_mps,
            "estimated_velocity_east_mps": self.estimated_velocity_east_mps,
            "estimated_ground_speed_mps": self.estimated_ground_speed_mps,
            "estimated_course_deg": self.estimated_course_deg,
            "estimated_heading_deg": self.estimated_heading_deg,
            "navigation_mode": self.navigation_mode.value,
            "position_quality": self.position_quality.value,
            "heading_quality": self.heading_quality.value,
            "altitude_quality": self.altitude_quality.value,
            "position_source": self.position_source.value,
            "nav_gps_valid": self.gps_valid,
            "nav_gps_rejected": self.gps_rejected,
            "nav_gps_rejection_reason": self.gps_rejection_reason,
            "nav_gps_age_ms": self.gps_age_ms,
            "nav_gps_position_error_m": self.gps_position_error_m,
            "dead_reckoning_active": self.dead_reckoning_active,
            "dead_reckoning_age_s": self.dead_reckoning_age_s,
            "recovery_active": self.recovery_active,
            "navigation_valid": self.navigation_valid,
            "safe_for_guidance": self.safe_for_guidance,
            "nav_consecutive_good_gps": self.consecutive_good_gps,
            "nav_consecutive_bad_gps": self.consecutive_bad_gps,
            "estimator_reset_count": self.estimator_reset_count,
            "nav_last_event": self.last_event,
        }
