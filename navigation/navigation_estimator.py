"""Real-time lightweight navigation estimator and worker."""

from __future__ import annotations

import logging
import math
import threading
import time
from typing import Any

import config
from core.shared_data import PayloadSnapshot, SharedData
from navigation.geo_utils import (
    circular_lerp_deg,
    geodetic_to_local,
    is_finite_number,
    local_to_geodetic,
    speed_course_from_velocity,
    valid_lat_lon,
    velocity_from_speed_course,
    wrap_360,
)
from navigation.gps_validator import GPSMeasurement, GPSValidationResult, GPSValidator
from navigation.kalman_filter import ConstantVelocityKalman
from navigation.navigation_state import (
    AltitudeQuality,
    HeadingQuality,
    NavigationMode,
    NavigationState,
    PositionQuality,
    PositionSource,
)

logger = logging.getLogger(__name__)


def _cfg(name: str, default: Any) -> Any:
    return getattr(config, name, default)


def _now_ns() -> int:
    return time.monotonic_ns()


class NavigationEstimator:
    """Fuse GPS horizontal motion, BMP388 altitude, and AHRS heading."""

    def __init__(self) -> None:
        self.validator = GPSValidator(
            min_satellites=int(_cfg("NAV_MIN_SATELLITES", 5)),
            max_hdop=float(_cfg("NAV_MAX_HDOP", 4.0)),
            max_age_ms=float(_cfg("NAV_MAX_GPS_AGE_MS", 1500.0)),
            max_plausible_speed_mps=float(_cfg("NAV_MAX_PLAUSIBLE_SPEED_MPS", 120.0)),
            max_absolute_jump_m=float(_cfg("NAV_MAX_ABSOLUTE_GPS_JUMP_M", 250.0)),
        )
        self.filter = ConstantVelocityKalman(
            process_noise_position=float(_cfg("NAV_PROCESS_NOISE_POSITION", 1.0)),
            process_noise_velocity=float(_cfg("NAV_PROCESS_NOISE_VELOCITY", 4.0)),
        )
        self.origin_latitude = 0.0
        self.origin_longitude = 0.0
        self.baro_reference_altitude_m: float | None = None
        self.last_update_ns: int | None = None
        self.last_good_gps: GPSMeasurement | None = None
        self.last_seen_gps_timestamp_ns: int = 0
        self.consecutive_good_gps = 0
        self.consecutive_bad_gps = 0
        self.dead_reckoning_started_ns: int | None = None
        self.mode = NavigationMode.INITIALIZING
        self.reset_count = 0
        self.last_state = NavigationState()
        self.last_event = ""

    def reset(self, gps: GPSMeasurement | None = None, now_ns: int | None = None) -> NavigationState:
        now = now_ns or _now_ns()
        self.filter = ConstantVelocityKalman(
            process_noise_position=float(_cfg("NAV_PROCESS_NOISE_POSITION", 1.0)),
            process_noise_velocity=float(_cfg("NAV_PROCESS_NOISE_VELOCITY", 4.0)),
        )
        self.origin_latitude = 0.0
        self.origin_longitude = 0.0
        self.last_update_ns = now
        self.last_good_gps = None
        self.last_seen_gps_timestamp_ns = 0
        self.consecutive_good_gps = 0
        self.consecutive_bad_gps = 0
        self.dead_reckoning_started_ns = None
        self.mode = NavigationMode.INITIALIZING
        self.reset_count += 1
        self.last_event = "NAV_RESET"
        if gps and gps.fix_ok and valid_lat_lon(gps.latitude, gps.longitude):
            self._initialize_filter(gps)
        self.last_state = self._make_state(
            now_ns=now,
            gps_valid=False,
            gps_rejected=False,
            gps_reason="RESET",
            gps_age_ms=-1.0,
            position_source=PositionSource.NONE,
            altitude_m=0.0,
            agl_m=0.0,
            altitude_quality=AltitudeQuality.INVALID,
            heading_deg=0.0,
            heading_quality=HeadingQuality.INVALID,
            gps_position_error_m=-1.0,
        )
        return self.last_state

    def update(self, snap: PayloadSnapshot, now_ns: int | None = None) -> NavigationState:
        now = now_ns or _now_ns()
        try:
            return self._update_checked(snap, now)
        except Exception as exc:
            logger.exception("Navigation estimator error: %s", exc)
            self.consecutive_bad_gps += 1
            self.mode = NavigationMode.UNRELIABLE
            self.last_event = "NAV_ESTIMATOR_ERROR"
            state = self._state_from_previous(now, "ESTIMATOR_ERROR")
            self.last_state = state
            return state

    def _update_checked(self, snap: PayloadSnapshot, now_ns: int) -> NavigationState:
        gps = self._gps_from_snapshot(snap)
        gps_result = self._validate_gps_for_update(gps, now_ns)
        dt_s = self._dt(now_ns)
        if dt_s is None:
            self.last_state = self._state_from_previous(now_ns, "NAV_INVALID_DT")
            return self.last_state

        if self.filter.initialized:
            self.filter.predict(dt_s)
            if not self.filter.is_finite():
                self.reset_count += 1
                self.last_event = "NAV_RESET_NUMERICAL"
                self.mode = NavigationMode.INITIALIZING
                self.filter.initialized = False

        altitude_m, agl_m, altitude_quality = self._altitude_from_snapshot(snap, now_ns)
        heading_deg, heading_quality = self._heading_from_snapshot(snap, now_ns, gps)
        gps_position_error_m = -1.0
        position_source = PositionSource.NONE

        if gps_result.valid:
            self.last_seen_gps_timestamp_ns = gps.timestamp_ns
            gps_position_error_m = self._gps_position_error(gps)
            self._accept_gps(gps, gps_position_error_m, dt_s)
            position_source = PositionSource.GPS if self.mode == NavigationMode.GOOD else PositionSource.RECOVERY
        elif gps_result.rejected:
            self._reject_gps(gps_result, now_ns)
            position_source = PositionSource.PREDICTED if self.filter.initialized else PositionSource.NONE
        else:
            position_source = PositionSource.PREDICTED if self.filter.initialized else PositionSource.NONE

        if not self.filter.initialized and gps_result.valid:
            self._initialize_filter(gps)
            position_source = PositionSource.GPS

        position_quality = self._position_quality()
        if altitude_quality != AltitudeQuality.GOOD and position_quality == PositionQuality.GOOD:
            nav_valid = True
        else:
            nav_valid = position_quality in {
                PositionQuality.GOOD,
                PositionQuality.DEGRADED,
                PositionQuality.DEAD_RECKONING,
            }
        if position_quality == PositionQuality.UNRELIABLE:
            nav_valid = False
        safe = self._safe_for_guidance(position_quality, nav_valid)

        state = self._make_state(
            now_ns=now_ns,
            gps_valid=gps_result.valid,
            gps_rejected=gps_result.rejected,
            gps_reason=gps_result.reason,
            gps_age_ms=gps_result.age_ms,
            position_source=position_source,
            altitude_m=altitude_m,
            agl_m=agl_m,
            altitude_quality=altitude_quality,
            heading_deg=heading_deg,
            heading_quality=heading_quality,
            gps_position_error_m=gps_position_error_m,
            navigation_valid=nav_valid,
            safe_for_guidance=safe,
        )
        self.last_state = state
        return state

    def _validate_gps_for_update(self, gps: GPSMeasurement, now_ns: int) -> GPSValidationResult:
        if gps.timestamp_ns and gps.timestamp_ns == self.last_seen_gps_timestamp_ns:
            age_ms = (now_ns - gps.timestamp_ns) / 1_000_000.0
            if age_ms <= float(_cfg("NAV_MAX_GPS_AGE_MS", 1500.0)):
                return GPSValidationResult(False, False, "GPS_WAITING_NEW_SAMPLE", age_ms)
        return self.validator.validate(gps, now_ns=now_ns, last_good=self.last_good_gps)

    def _dt(self, now_ns: int) -> float | None:
        if self.last_update_ns is None:
            self.last_update_ns = now_ns
            return 0.0
        dt_s = (now_ns - self.last_update_ns) / 1_000_000_000.0
        self.last_update_ns = now_ns
        if dt_s < float(_cfg("NAV_MIN_DT_SEC", 0.001)) and self.filter.initialized:
            self.last_event = "NAV_DT_TOO_SMALL"
            return None
        if dt_s > float(_cfg("NAV_MAX_DT_SEC", 0.25)):
            self.last_event = "NAV_DT_TOO_LARGE"
            return min(dt_s, float(_cfg("NAV_MAX_DT_SEC", 0.25)))
        return max(0.0, dt_s)

    def _gps_from_snapshot(self, snap: PayloadSnapshot) -> GPSMeasurement:
        return GPSMeasurement(
            latitude=float(snap.latitude),
            longitude=float(snap.longitude),
            altitude_m=float(snap.gps_altitude),
            fix_ok=bool(snap.gps_ok),
            fix_type=str(getattr(snap, "gps_fix_type", "")),
            satellites=self._optional_int(getattr(snap, "gps_satellites", None)),
            hdop=self._optional_float(getattr(snap, "gps_hdop", None)),
            ground_speed_mps=self._optional_float(getattr(snap, "gps_ground_speed_mps", None)),
            course_deg=self._optional_float(getattr(snap, "gps_course_deg", None)),
            timestamp_ns=int(getattr(snap, "gps_timestamp_ns", 0) or 0),
        )

    def _initialize_filter(self, gps: GPSMeasurement) -> None:
        self.origin_latitude = gps.latitude
        self.origin_longitude = gps.longitude
        vn, ve = self._gps_velocity(gps, None)
        self.filter.initialize(0.0, 0.0, vn, ve)
        self.last_good_gps = gps
        self.mode = NavigationMode.INITIALIZING

    def _accept_gps(self, gps: GPSMeasurement, position_error_m: float, dt_s: float) -> None:
        self.consecutive_good_gps += 1
        self.consecutive_bad_gps = 0
        lost_before = self.mode in {NavigationMode.GPS_LOST, NavigationMode.UNRELIABLE}

        if not self.filter.initialized:
            if self.consecutive_good_gps >= int(_cfg("NAV_GPS_GOOD_COUNT_TO_RECOVER", 3)):
                self._initialize_filter(gps)
                self.mode = NavigationMode.GOOD
            self.last_good_gps = gps
            return

        north, east = geodetic_to_local(gps.latitude, gps.longitude, self.origin_latitude, self.origin_longitude)
        if lost_before or self.mode == NavigationMode.RECOVERING:
            self.mode = NavigationMode.RECOVERING
            north, east = self._bounded_recovery_position(north, east, dt_s)
        elif self.mode in {NavigationMode.INITIALIZING, NavigationMode.DEGRADED}:
            if self.consecutive_good_gps >= int(_cfg("NAV_GPS_GOOD_COUNT_TO_RECOVER", 3)):
                self.mode = NavigationMode.GOOD
            else:
                self.mode = NavigationMode.DEGRADED

        self.filter.update_position(north, east, float(_cfg("NAV_GPS_POSITION_NOISE_M2", 16.0)))
        vn, ve = self._gps_velocity(gps, self.last_good_gps)
        self.filter.update_velocity(vn, ve, float(_cfg("NAV_GPS_VELOCITY_NOISE_M2PS2", 4.0)))

        if self.mode == NavigationMode.RECOVERING:
            recovery_error = math.hypot(north - self.filter.x[0], east - self.filter.x[1])
            if (
                self.consecutive_good_gps >= int(_cfg("NAV_GPS_GOOD_COUNT_TO_RECOVER", 3))
                and recovery_error <= float(_cfg("NAV_GPS_RECOVERY_POSITION_TOLERANCE_M", 8.0))
            ):
                self.mode = NavigationMode.GOOD
                self.dead_reckoning_started_ns = None
                self.last_event = "GPS_RECOVERED"
            else:
                self.last_event = "GPS_RECOVERY_STARTED"
        elif self.mode == NavigationMode.GOOD:
            self.dead_reckoning_started_ns = None

        self.last_good_gps = gps

    def _reject_gps(self, result: GPSValidationResult, now_ns: int) -> None:
        self.consecutive_bad_gps += 1
        self.consecutive_good_gps = 0
        self.last_event = result.reason
        if self.dead_reckoning_started_ns is None and self.filter.initialized:
            self.dead_reckoning_started_ns = now_ns
            self.last_event = "DEAD_RECKONING_STARTED"
        bad_to_lost = int(_cfg("NAV_GPS_REJECT_COUNT_TO_LOST", 4))
        dr_age = self._dead_reckoning_age(now_ns)
        if not self.filter.initialized:
            self.mode = NavigationMode.INITIALIZING
        elif dr_age >= float(_cfg("NAV_DEAD_RECKON_MAX_SEC", 5.0)):
            self.mode = NavigationMode.UNRELIABLE
            self.last_event = "DEAD_RECKONING_TIMEOUT"
        elif self.consecutive_bad_gps >= bad_to_lost:
            self.mode = NavigationMode.GPS_LOST
            self.last_event = "GPS_LOST"
        else:
            self.mode = NavigationMode.DEGRADED

    def _gps_velocity(self, gps: GPSMeasurement, previous: GPSMeasurement | None) -> tuple[float, float]:
        if (
            gps.ground_speed_mps is not None
            and gps.course_deg is not None
            and is_finite_number(gps.ground_speed_mps)
            and is_finite_number(gps.course_deg)
            and gps.ground_speed_mps >= 0.0
        ):
            return velocity_from_speed_course(float(gps.ground_speed_mps), float(gps.course_deg))
        if previous and gps.timestamp_ns > previous.timestamp_ns:
            dt_s = (gps.timestamp_ns - previous.timestamp_ns) / 1_000_000_000.0
            if dt_s > 0.0 and self.origin_latitude:
                n1, e1 = geodetic_to_local(previous.latitude, previous.longitude, self.origin_latitude, self.origin_longitude)
                n2, e2 = geodetic_to_local(gps.latitude, gps.longitude, self.origin_latitude, self.origin_longitude)
                return (n2 - n1) / dt_s, (e2 - e1) / dt_s
        return self.filter.x[2], self.filter.x[3]

    def _bounded_recovery_position(self, north: float, east: float, dt_s: float) -> tuple[float, float]:
        if not bool(_cfg("NAV_GPS_RECOVERY_ENABLED", True)):
            return north, east
        max_step = max(
            float(_cfg("NAV_GPS_RECOVERY_MAX_CORRECTION_RATE_MPS", 8.0)) * max(dt_s, 0.05),
            float(_cfg("NAV_GPS_RECOVERY_MIN_STEP_M", 0.5)),
        )
        dn = north - self.filter.x[0]
        de = east - self.filter.x[1]
        distance = math.hypot(dn, de)
        if distance <= max_step or distance <= 1e-9:
            return north, east
        scale = max_step / distance
        self.last_event = "GPS_RECOVERY_RATE_LIMITED"
        return self.filter.x[0] + dn * scale, self.filter.x[1] + de * scale

    def _altitude_from_snapshot(
        self,
        snap: PayloadSnapshot,
        now_ns: int,
    ) -> tuple[float, float, AltitudeQuality]:
        altitude = float(getattr(snap, "baro_altitude", 0.0))
        baro_ts = int(getattr(snap, "baro_timestamp_ns", 0) or 0)
        if not is_finite_number(altitude) or not bool(getattr(snap, "barometer_ok", False)):
            return float(getattr(snap, "gps_altitude", 0.0)), 0.0, AltitudeQuality.DEGRADED
        if baro_ts and (now_ns - baro_ts) / 1_000_000.0 > float(_cfg("NAV_MAX_BARO_AGE_MS", 1000.0)):
            return altitude, self._agl(altitude), AltitudeQuality.DEGRADED
        if self.baro_reference_altitude_m is None:
            self.baro_reference_altitude_m = altitude
        return altitude, self._agl(altitude), AltitudeQuality.GOOD

    def _agl(self, altitude_m: float) -> float:
        if self.baro_reference_altitude_m is None:
            return 0.0
        return altitude_m - self.baro_reference_altitude_m

    def _heading_from_snapshot(
        self,
        snap: PayloadSnapshot,
        now_ns: int,
        gps: GPSMeasurement,
    ) -> tuple[float, HeadingQuality]:
        ahrs_ts = int(getattr(snap, "ahrs_timestamp_ns", 0) or 0)
        ahrs_age_ms = (now_ns - ahrs_ts) / 1_000_000.0 if ahrs_ts else float("inf")
        if (
            bool(getattr(snap, "ahrs_valid", False))
            and bool(getattr(snap, "ahrs_healthy", False))
            and ahrs_age_ms <= float(_cfg("NAV_MAX_AHRS_AGE_MS", 500.0))
            and is_finite_number(getattr(snap, "ahrs_yaw", 0.0))
        ):
            heading = wrap_360(float(snap.ahrs_yaw))
            if self.last_state.heading_quality != HeadingQuality.INVALID:
                heading = circular_lerp_deg(self.last_state.estimated_heading_deg, heading, 0.35)
            return heading, HeadingQuality.GOOD
        if (
            gps.ground_speed_mps is not None
            and gps.course_deg is not None
            and gps.ground_speed_mps >= float(_cfg("NAV_MIN_SPEED_FOR_GPS_HEADING_MPS", 2.0))
        ):
            return wrap_360(float(gps.course_deg)), HeadingQuality.GPS_COURSE
        return self.last_state.estimated_heading_deg, HeadingQuality.INVALID

    def _gps_position_error(self, gps: GPSMeasurement) -> float:
        if not self.filter.initialized or not self.origin_latitude:
            return -1.0
        north, east = geodetic_to_local(gps.latitude, gps.longitude, self.origin_latitude, self.origin_longitude)
        return math.hypot(north - self.filter.x[0], east - self.filter.x[1])

    def _position_quality(self) -> PositionQuality:
        if not self.filter.initialized:
            return PositionQuality.INVALID
        if self.mode == NavigationMode.GOOD:
            return PositionQuality.GOOD
        if self.mode == NavigationMode.RECOVERING:
            return PositionQuality.DEGRADED
        if self.mode == NavigationMode.DEGRADED:
            return PositionQuality.DEGRADED
        if self.mode == NavigationMode.GPS_LOST:
            return PositionQuality.DEAD_RECKONING
        return PositionQuality.UNRELIABLE

    def _safe_for_guidance(self, quality: PositionQuality, nav_valid: bool) -> bool:
        if not nav_valid:
            return False
        if quality == PositionQuality.GOOD:
            return True
        if quality == PositionQuality.DEGRADED:
            return bool(_cfg("NAV_SAFE_IN_DEGRADED", False))
        if quality == PositionQuality.DEAD_RECKONING:
            return bool(_cfg("NAV_SAFE_IN_SHORT_DEAD_RECKONING", False))
        return False

    def _dead_reckoning_age(self, now_ns: int) -> float:
        if self.dead_reckoning_started_ns is None:
            return 0.0
        return max(0.0, (now_ns - self.dead_reckoning_started_ns) / 1_000_000_000.0)

    def _make_state(
        self,
        *,
        now_ns: int,
        gps_valid: bool,
        gps_rejected: bool,
        gps_reason: str,
        gps_age_ms: float,
        position_source: PositionSource,
        altitude_m: float,
        agl_m: float,
        altitude_quality: AltitudeQuality,
        heading_deg: float,
        heading_quality: HeadingQuality,
        gps_position_error_m: float,
        navigation_valid: bool = False,
        safe_for_guidance: bool = False,
    ) -> NavigationState:
        if self.filter.initialized:
            north, east, vn, ve = self.filter.x
            lat, lon = local_to_geodetic(north, east, self.origin_latitude, self.origin_longitude)
            speed, course = speed_course_from_velocity(vn, ve)
        else:
            north = east = vn = ve = speed = course = 0.0
            lat = lon = 0.0
        dr_age = self._dead_reckoning_age(now_ns)
        return NavigationState(
            timestamp_ns=now_ns,
            origin_latitude=self.origin_latitude,
            origin_longitude=self.origin_longitude,
            estimated_latitude=lat,
            estimated_longitude=lon,
            estimated_north_m=north,
            estimated_east_m=east,
            estimated_altitude_m=altitude_m,
            estimated_agl_m=agl_m,
            estimated_velocity_north_mps=vn,
            estimated_velocity_east_mps=ve,
            estimated_ground_speed_mps=speed,
            estimated_course_deg=course,
            estimated_heading_deg=wrap_360(heading_deg),
            navigation_mode=self.mode,
            position_quality=self._position_quality(),
            heading_quality=heading_quality,
            altitude_quality=altitude_quality,
            position_source=position_source,
            gps_valid=gps_valid,
            gps_rejected=gps_rejected,
            gps_rejection_reason=gps_reason,
            gps_age_ms=gps_age_ms,
            gps_position_error_m=gps_position_error_m,
            dead_reckoning_active=self.mode in {NavigationMode.DEGRADED, NavigationMode.GPS_LOST} and self.filter.initialized,
            dead_reckoning_age_s=dr_age,
            recovery_active=self.mode == NavigationMode.RECOVERING,
            navigation_valid=navigation_valid,
            safe_for_guidance=safe_for_guidance,
            consecutive_good_gps=self.consecutive_good_gps,
            consecutive_bad_gps=self.consecutive_bad_gps,
            estimator_reset_count=self.reset_count,
            last_event=self.last_event,
        )

    def _state_from_previous(self, now_ns: int, reason: str) -> NavigationState:
        return NavigationState(
            **{
                **self.last_state.__dict__,
                "timestamp_ns": now_ns,
                "navigation_mode": NavigationMode.UNRELIABLE,
                "position_quality": PositionQuality.UNRELIABLE,
                "gps_rejected": True,
                "gps_rejection_reason": reason,
                "navigation_valid": False,
                "safe_for_guidance": False,
                "consecutive_good_gps": self.consecutive_good_gps,
                "consecutive_bad_gps": self.consecutive_bad_gps,
                "estimator_reset_count": self.reset_count,
                "last_event": self.last_event,
            }
        )

    @staticmethod
    def _optional_float(value: object) -> float | None:
        if value is None:
            return None
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return number if math.isfinite(number) else None

    @staticmethod
    def _optional_int(value: object) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None


def navigation_worker(shared: SharedData, stop_event: threading.Event) -> None:
    """Navigation estimator worker consuming SharedData snapshots only."""
    estimator = NavigationEstimator()
    period_s = 1.0 / max(1.0, float(_cfg("NAVIGATION_RATE_HZ", 20.0)))
    logger.info("Navigation estimator worker started at %.1f Hz.", 1.0 / period_s)
    last_event = ""
    try:
        while not stop_event.is_set():
            try:
                snap = shared.get_snapshot()
                state = estimator.update(snap)
                shared.publish_navigation(state)
                if state.last_event and state.last_event != last_event:
                    severity = "WARN" if state.navigation_mode != NavigationMode.GOOD else "INFO"
                    shared.record_event(state.last_event, "Navigation", severity, state.gps_rejection_reason)
                    last_event = state.last_event
                shared.record_worker_success(
                    "Navigation",
                    expected_hz=float(_cfg("NAVIGATION_EXPECTED_HZ", _cfg("NAVIGATION_RATE_HZ", 20.0))),
                    reason=f"{state.navigation_mode.value}; {state.position_quality.value}",
                    status="HEALTHY" if state.navigation_valid else "DEGRADED",
                    details={
                        "mode": state.navigation_mode.value,
                        "position_quality": state.position_quality.value,
                        "heading_quality": state.heading_quality.value,
                        "altitude_quality": state.altitude_quality.value,
                        "gps_valid": state.gps_valid,
                        "gps_rejected": state.gps_rejected,
                        "gps_rejection_reason": state.gps_rejection_reason,
                        "dead_reckoning_age_s": state.dead_reckoning_age_s,
                        "safe_for_guidance": state.safe_for_guidance,
                    },
                )
            except Exception as exc:
                logger.error("Navigation worker error: %s", exc)
                shared.record_worker_error("Navigation", exc, expected_hz=float(_cfg("NAVIGATION_EXPECTED_HZ", 20.0)))
            stop_event.wait(period_s)
    finally:
        logger.info("Navigation estimator worker stopped.")
