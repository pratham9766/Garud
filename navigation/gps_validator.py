"""GPS sample validation for the lightweight navigation estimator."""

from __future__ import annotations

from dataclasses import dataclass
import math

from navigation.geo_utils import distance_m, is_finite_number, valid_lat_lon


@dataclass(frozen=True)
class GPSMeasurement:
    latitude: float
    longitude: float
    altitude_m: float
    fix_ok: bool
    fix_type: str
    satellites: int | None
    hdop: float | None
    ground_speed_mps: float | None
    course_deg: float | None
    timestamp_ns: int


@dataclass(frozen=True)
class GPSValidationResult:
    valid: bool
    rejected: bool
    reason: str
    age_ms: float
    implied_speed_mps: float | None = None
    distance_from_last_m: float | None = None
    timestamp_regressed: bool = False
    duplicate_timestamp: bool = False


class GPSValidator:
    def __init__(
        self,
        *,
        min_satellites: int,
        max_hdop: float,
        max_age_ms: float,
        max_plausible_speed_mps: float,
        max_absolute_jump_m: float,
    ) -> None:
        self.min_satellites = int(min_satellites)
        self.max_hdop = float(max_hdop)
        self.max_age_ms = float(max_age_ms)
        self.max_plausible_speed_mps = float(max_plausible_speed_mps)
        self.max_absolute_jump_m = float(max_absolute_jump_m)

    def validate(
        self,
        measurement: GPSMeasurement,
        *,
        now_ns: int,
        last_good: GPSMeasurement | None,
    ) -> GPSValidationResult:
        age_ms = (now_ns - int(measurement.timestamp_ns)) / 1_000_000.0 if measurement.timestamp_ns else -1.0
        if not measurement.timestamp_ns:
            return GPSValidationResult(False, True, "GPS_NO_TIMESTAMP", age_ms)
        if age_ms < -1.0:
            return GPSValidationResult(False, True, "GPS_TIMESTAMP_IN_FUTURE", age_ms)
        if age_ms > self.max_age_ms:
            return GPSValidationResult(False, True, "GPS_STALE", age_ms)
        if not measurement.fix_ok:
            return GPSValidationResult(False, True, "GPS_NO_FIX", age_ms)
        if not valid_lat_lon(measurement.latitude, measurement.longitude):
            return GPSValidationResult(False, True, "GPS_INVALID_LAT_LON", age_ms)
        if not is_finite_number(measurement.altitude_m):
            return GPSValidationResult(False, True, "GPS_INVALID_ALTITUDE", age_ms)
        if measurement.satellites is not None and int(measurement.satellites) < self.min_satellites:
            return GPSValidationResult(False, True, "GPS_LOW_SATELLITES", age_ms)
        if measurement.hdop is not None:
            if not is_finite_number(measurement.hdop) or float(measurement.hdop) <= 0.0:
                return GPSValidationResult(False, True, "GPS_INVALID_HDOP", age_ms)
            if float(measurement.hdop) > self.max_hdop:
                return GPSValidationResult(False, True, "GPS_BAD_HDOP", age_ms)
        if measurement.ground_speed_mps is not None:
            if not is_finite_number(measurement.ground_speed_mps) or float(measurement.ground_speed_mps) < 0.0:
                return GPSValidationResult(False, True, "GPS_INVALID_SPEED", age_ms)
            if float(measurement.ground_speed_mps) > self.max_plausible_speed_mps:
                return GPSValidationResult(False, True, "GPS_REPORTED_SPEED_IMPLAUSIBLE", age_ms)
        if measurement.course_deg is not None and not is_finite_number(measurement.course_deg):
            return GPSValidationResult(False, True, "GPS_INVALID_COURSE", age_ms)

        if last_good is not None:
            if measurement.timestamp_ns < last_good.timestamp_ns:
                return GPSValidationResult(False, True, "GPS_TIMESTAMP_REGRESSED", age_ms, timestamp_regressed=True)
            if measurement.timestamp_ns == last_good.timestamp_ns:
                return GPSValidationResult(False, True, "GPS_DUPLICATE_TIMESTAMP", age_ms, duplicate_timestamp=True)
            dt_s = (measurement.timestamp_ns - last_good.timestamp_ns) / 1_000_000_000.0
            if not math.isfinite(dt_s) or dt_s <= 0.0:
                return GPSValidationResult(False, True, "GPS_INVALID_DT", age_ms)
            distance = distance_m(
                last_good.latitude,
                last_good.longitude,
                measurement.latitude,
                measurement.longitude,
            )
            implied_speed = distance / dt_s
            if distance > self.max_absolute_jump_m:
                return GPSValidationResult(False, True, "GPS_ABSOLUTE_JUMP", age_ms, implied_speed, distance)
            if implied_speed > self.max_plausible_speed_mps:
                return GPSValidationResult(False, True, "GPS_IMPLIED_SPEED_IMPLAUSIBLE", age_ms, implied_speed, distance)
            return GPSValidationResult(True, False, "GPS_VALID", age_ms, implied_speed, distance)

        return GPSValidationResult(True, False, "GPS_VALID", age_ms)
