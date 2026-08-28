"""
Flight-safe AHRS manager and estimators.

The AHRS consumes preserved raw IMU samples and publishes one AttitudeState.
Only q=(w, x, y, z) is used internally; Euler angles are derived outputs for
logging, telemetry, gimbal stabilization, and pose priors.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import logging
import math
import time
from typing import Any

import config
from sensor_fusion.quaternion import (
    Quaternion,
    angular_difference_rad,
    bno_xyzw_to_wxyz,
    from_euler_deg,
    multiply,
    normalize,
    to_euler_deg,
)

logger = logging.getLogger(__name__)
GRAVITY_MPS2 = 9.80665


class AHRSMode(Enum):
    OFF = "OFF"
    BNO085 = "BNO085"
    MADGWICK = "MADGWICK"
    MAHONY = "MAHONY"
    AUTO = "AUTO"


class AHRSQuality(Enum):
    INVALID = "INVALID"
    DEGRADED = "DEGRADED"
    GOOD = "GOOD"


@dataclass(frozen=True)
class RawIMUData:
    """One coherent raw IMU sample. BNO quaternion order is native x,y,z,w."""

    timestamp_ns: int
    accel_mps2: tuple[float, float, float] | None = None
    gyro_rads: tuple[float, float, float] | None = None
    mag_ut: tuple[float, float, float] | None = None
    bno_quaternion_xyzw: tuple[float, float, float, float] | None = None
    bno_accuracy_rad: float | None = None
    calibration_status: Any = None
    roll_deg: float | None = None
    pitch_deg: float | None = None
    yaw_deg: float | None = None


@dataclass(frozen=True)
class AttitudeState:
    """Published AHRS output. Quaternion order is q=(w, x, y, z)."""

    timestamp_ns: int = 0
    q_w: float = 1.0
    q_x: float = 0.0
    q_y: float = 0.0
    q_z: float = 0.0
    roll_deg: float = 0.0
    pitch_deg: float = 0.0
    yaw_deg: float = 0.0
    gyro_x_dps: float = 0.0
    gyro_y_dps: float = 0.0
    gyro_z_dps: float = 0.0
    source: str = AHRSMode.OFF.value
    valid: bool = False
    healthy: bool = False
    confidence: str = AHRSQuality.INVALID.value
    accuracy_rad: float | None = None
    sample_age_ms: float = math.inf
    accel_correction_enabled: bool = False
    mag_correction_enabled: bool = False
    enabled: bool = False

    @property
    def quaternion(self) -> Quaternion:
        return self.q_w, self.q_x, self.q_y, self.q_z


@dataclass
class AHRSDiagnostics:
    received_samples: int = 0
    rejected_samples: int = 0
    stale_samples: int = 0
    estimator_resets: int = 0
    source_changes: int = 0
    invalid_dt: int = 0


def validate_config() -> None:
    mode = AHRSMode(str(config.AHRS_MODE).upper())
    if not bool(config.ENABLE_AHRS) and mode != AHRSMode.OFF:
        return
    if config.AHRS_RATE_HZ <= 0:
        raise ValueError("AHRS_RATE_HZ must be positive.")
    if config.AHRS_MIN_DT_SEC <= 0 or config.AHRS_MAX_DT_SEC <= config.AHRS_MIN_DT_SEC:
        raise ValueError("AHRS dt bounds are invalid.")
    if config.AHRS_MAX_SAMPLE_AGE_MS <= 0:
        raise ValueError("AHRS_MAX_SAMPLE_AGE_MS must be positive.")
    if config.AHRS_FAIL_COUNT_THRESHOLD < 1 or config.AHRS_RECOVERY_COUNT_THRESHOLD < 1:
        raise ValueError("AHRS hysteresis thresholds must be >= 1.")
    if config.AHRS_ACCEL_NORM_MIN_G <= 0 or config.AHRS_ACCEL_NORM_MAX_G <= config.AHRS_ACCEL_NORM_MIN_G:
        raise ValueError("AHRS acceleration rejection bounds are invalid.")


def _finite_vector(v: tuple[float, ...] | None, length: int) -> bool:
    return v is not None and len(v) == length and all(math.isfinite(x) for x in v)


def _accel_ok(accel: tuple[float, float, float] | None) -> bool:
    if not config.AHRS_ACCEL_REJECTION_ENABLED:
        return _finite_vector(accel, 3)
    if not _finite_vector(accel, 3):
        return False
    norm_g = math.sqrt(sum(a * a for a in accel)) / GRAVITY_MPS2
    return config.AHRS_ACCEL_NORM_MIN_G <= norm_g <= config.AHRS_ACCEL_NORM_MAX_G


def _mag_ok(mag: tuple[float, float, float] | None) -> bool:
    if not config.AHRS_USE_MAGNETOMETER:
        return False
    if not config.AHRS_MAG_REJECTION_ENABLED:
        return _finite_vector(mag, 3)
    if not _finite_vector(mag, 3):
        return False
    norm = math.sqrt(sum(m * m for m in mag))
    return config.AHRS_MAG_NORM_MIN_UT <= norm <= config.AHRS_MAG_NORM_MAX_UT


def _state_from_quaternion(
    q: Quaternion,
    raw: RawIMUData,
    source: str,
    valid: bool,
    healthy: bool,
    quality: AHRSQuality,
    accel_active: bool,
    mag_active: bool,
) -> AttitudeState:
    mount_q = normalize(tuple(float(v) for v in config.IMU_TO_BODY_QUATERNION))
    if mount_q is None:
        raise ValueError("IMU_TO_BODY_QUATERNION is invalid")
    q = normalize(multiply(mount_q, q))
    if q is None:
        raise ValueError("body-frame quaternion invalid")
    roll, pitch, yaw = to_euler_deg(q)
    gyro = raw.gyro_rads or (0.0, 0.0, 0.0)
    age_ms = (time.monotonic_ns() - raw.timestamp_ns) / 1_000_000.0
    return AttitudeState(
        timestamp_ns=raw.timestamp_ns,
        q_w=q[0],
        q_x=q[1],
        q_y=q[2],
        q_z=q[3],
        roll_deg=roll,
        pitch_deg=pitch,
        yaw_deg=yaw,
        gyro_x_dps=math.degrees(gyro[0]),
        gyro_y_dps=math.degrees(gyro[1]),
        gyro_z_dps=math.degrees(gyro[2]),
        source=source,
        valid=valid,
        healthy=healthy,
        confidence=quality.value,
        accuracy_rad=raw.bno_accuracy_rad,
        sample_age_ms=max(0.0, age_ms),
        accel_correction_enabled=accel_active,
        mag_correction_enabled=mag_active,
        enabled=True,
    )


class AHRSBase:
    source = "BASE"

    def __init__(self) -> None:
        self.q: Quaternion = (1.0, 0.0, 0.0, 0.0)
        self.prev_timestamp_ns: int | None = None

    def reset(self, q: Quaternion | None = None) -> None:
        self.q = normalize(q or (1.0, 0.0, 0.0, 0.0)) or (1.0, 0.0, 0.0, 0.0)
        self.prev_timestamp_ns = None

    def _dt(self, raw: RawIMUData) -> float | None:
        if self.prev_timestamp_ns is None:
            self.prev_timestamp_ns = raw.timestamp_ns
            return None
        dt = (raw.timestamp_ns - self.prev_timestamp_ns) / 1_000_000_000.0
        self.prev_timestamp_ns = raw.timestamp_ns
        if not math.isfinite(dt) or dt < config.AHRS_MIN_DT_SEC or dt > config.AHRS_MAX_DT_SEC:
            return None
        return dt

    def update(self, raw: RawIMUData) -> AttitudeState:
        raise NotImplementedError


class BNO085AHRS(AHRSBase):
    source = AHRSMode.BNO085.value

    def update(self, raw: RawIMUData) -> AttitudeState:
        if raw.bno_quaternion_xyzw is None:
            raise ValueError("BNO085 quaternion missing")
        q = bno_xyzw_to_wxyz(*raw.bno_quaternion_xyzw)
        if q is None:
            raise ValueError("BNO085 quaternion invalid")
        if angular_difference_rad(self.q, q) > math.radians(config.AHRS_MAX_ANGULAR_JUMP_DEG):
            if self.prev_timestamp_ns is not None:
                raise ValueError("BNO085 quaternion jump rejected")
        self.q = q
        self.prev_timestamp_ns = raw.timestamp_ns
        quality = AHRSQuality.GOOD
        if raw.bno_accuracy_rad is not None and raw.bno_accuracy_rad > config.AHRS_BNO085_DEGRADED_ACCURACY_RAD:
            quality = AHRSQuality.DEGRADED
        return _state_from_quaternion(q, raw, self.source, True, True, quality, False, _mag_ok(raw.mag_ut))


class MadgwickAHRS(AHRSBase):
    source = AHRSMode.MADGWICK.value

    def __init__(self, beta: float | None = None) -> None:
        super().__init__()
        self.beta = float(config.AHRS_MADGWICK_BETA if beta is None else beta)

    def update(self, raw: RawIMUData) -> AttitudeState:
        if not _finite_vector(raw.gyro_rads, 3):
            raise ValueError("gyro missing")
        dt = self._dt(raw)
        accel_active = _accel_ok(raw.accel_mps2)
        mag_active = _mag_ok(raw.mag_ut)
        if dt is None:
            return _state_from_quaternion(self.q, raw, self.source, True, False, AHRSQuality.DEGRADED, accel_active, mag_active)

        gx, gy, gz = raw.gyro_rads
        q1, q2, q3, q4 = self.q
        q_dot = list(multiply(self.q, (0.0, gx, gy, gz)))
        for i in range(4):
            q_dot[i] *= 0.5
        if accel_active:
            ax, ay, az = raw.accel_mps2
            recip_norm = 1.0 / math.sqrt(ax * ax + ay * ay + az * az)
            ax *= recip_norm
            ay *= recip_norm
            az *= recip_norm
            two_q1 = 2.0 * q1
            two_q2 = 2.0 * q2
            two_q3 = 2.0 * q3
            two_q4 = 2.0 * q4
            four_q1 = 4.0 * q1
            four_q2 = 4.0 * q2
            four_q3 = 4.0 * q3
            eight_q2 = 8.0 * q2
            eight_q3 = 8.0 * q3
            q1q1 = q1 * q1
            q2q2 = q2 * q2
            q3q3 = q3 * q3
            q4q4 = q4 * q4
            s1 = four_q1 * q3q3 + two_q3 * ax + four_q1 * q2q2 - two_q2 * ay
            s2 = four_q2 * q4q4 - two_q4 * ax + 4.0 * q1q1 * q2 - two_q1 * ay - four_q2 + eight_q2 * q2q2 + eight_q2 * q3q3 + four_q2 * az
            s3 = 4.0 * q1q1 * q3 + two_q1 * ax + four_q3 * q4q4 - two_q4 * ay - four_q3 + eight_q3 * q2q2 + eight_q3 * q3q3 + four_q3 * az
            s4 = 4.0 * q2q2 * q4 - two_q2 * ax + 4.0 * q3q3 * q4 - two_q3 * ay
            step = normalize((s1, s2, s3, s4))
            if step is not None:
                for i, s in enumerate(step):
                    q_dot[i] -= self.beta * s
        q = normalize(tuple(self.q[i] + q_dot[i] * dt for i in range(4)))
        if q is None:
            raise ValueError("Madgwick update produced invalid quaternion")
        self.q = q
        quality = AHRSQuality.GOOD if accel_active else AHRSQuality.DEGRADED
        return _state_from_quaternion(q, raw, self.source, True, True, quality, accel_active, mag_active)


class MahonyAHRS(AHRSBase):
    source = AHRSMode.MAHONY.value

    def __init__(self, kp: float | None = None, ki: float | None = None) -> None:
        super().__init__()
        self.kp = float(config.AHRS_MAHONY_KP if kp is None else kp)
        self.ki = float(config.AHRS_MAHONY_KI if ki is None else ki)
        self.bias = [0.0, 0.0, 0.0]

    def reset(self, q: Quaternion | None = None) -> None:
        super().reset(q)
        self.bias = [0.0, 0.0, 0.0]

    def update(self, raw: RawIMUData) -> AttitudeState:
        if not _finite_vector(raw.gyro_rads, 3):
            raise ValueError("gyro missing")
        dt = self._dt(raw)
        accel_active = _accel_ok(raw.accel_mps2)
        mag_active = _mag_ok(raw.mag_ut)
        if dt is None:
            return _state_from_quaternion(self.q, raw, self.source, True, False, AHRSQuality.DEGRADED, accel_active, mag_active)

        gx, gy, gz = raw.gyro_rads
        if accel_active:
            roll_acc, pitch_acc = _roll_pitch_from_accel(raw.accel_mps2)
            roll, pitch, _ = to_euler_deg(self.q)
            error = (
                math.radians(roll_acc - roll),
                math.radians(pitch_acc - pitch),
                0.0,
            )
            for i in range(3):
                self.bias[i] += self.ki * error[i] * dt
                self.bias[i] = max(-config.AHRS_MAHONY_BIAS_LIMIT_RADS, min(config.AHRS_MAHONY_BIAS_LIMIT_RADS, self.bias[i]))
            gx += self.kp * error[0] + self.bias[0]
            gy += self.kp * error[1] + self.bias[1]
            gz += self.kp * error[2] + self.bias[2]

        q_dot = multiply(self.q, (0.0, gx, gy, gz))
        q = normalize(tuple(self.q[i] + 0.5 * q_dot[i] * dt for i in range(4)))
        if q is None:
            raise ValueError("Mahony propagation produced invalid quaternion")
        self.q = q
        quality = AHRSQuality.GOOD if accel_active else AHRSQuality.DEGRADED
        return _state_from_quaternion(q, raw, self.source, True, True, quality, accel_active, mag_active)


class AHRSManager:
    """Mode selection, health checks, hysteresis, and runtime toggles."""

    def __init__(self, mode: str | AHRSMode | None = None, enabled: bool | None = None) -> None:
        validate_config()
        self.enabled = bool(config.ENABLE_AHRS if enabled is None else enabled)
        self.mode = _parse_mode(mode or config.AHRS_MODE)
        if not self.enabled:
            self.mode = AHRSMode.OFF
        self.estimators: dict[AHRSMode, AHRSBase] = {
            AHRSMode.BNO085: BNO085AHRS(),
            AHRSMode.MADGWICK: MadgwickAHRS(),
            AHRSMode.MAHONY: MahonyAHRS(),
        }
        self.software_fallback_mode = _parse_mode(config.AHRS_AUTO_SOFTWARE_FALLBACK)
        self.active_mode = self.mode if self.mode != AHRSMode.AUTO else AHRSMode.BNO085
        self.diagnostics = AHRSDiagnostics()
        self.fail_count = 0
        self.recovery_count = 0
        self.last_state = AttitudeState(enabled=self.enabled, source=self.active_mode.value if self.enabled else AHRSMode.OFF.value)

    def enable(self) -> None:
        self.enabled = True
        if self.mode == AHRSMode.OFF:
            self.mode = _parse_mode(config.AHRS_MODE)

    def disable(self) -> AttitudeState:
        self.enabled = False
        self.mode = AHRSMode.OFF
        self.last_state = AttitudeState(timestamp_ns=time.monotonic_ns(), source=AHRSMode.OFF.value, enabled=False)
        return self.last_state

    def set_mode(self, mode: str | AHRSMode) -> None:
        new_mode = _parse_mode(mode)
        self.mode = new_mode
        self.enabled = new_mode != AHRSMode.OFF
        self.active_mode = new_mode if new_mode != AHRSMode.AUTO else AHRSMode.BNO085
        self.fail_count = 0
        self.recovery_count = 0
        q = self.last_state.quaternion
        for estimator in self.estimators.values():
            estimator.reset(q)
        self.diagnostics.estimator_resets += 1

    def update(self, raw: RawIMUData) -> AttitudeState:
        self.diagnostics.received_samples += 1
        if not self.enabled or self.mode == AHRSMode.OFF:
            q = from_euler_deg(raw.roll_deg or 0.0, raw.pitch_deg or 0.0, raw.yaw_deg or 0.0)
            gyro = raw.gyro_rads or (0.0, 0.0, 0.0)
            self.last_state = AttitudeState(
                timestamp_ns=raw.timestamp_ns,
                q_w=q[0],
                q_x=q[1],
                q_y=q[2],
                q_z=q[3],
                roll_deg=raw.roll_deg or 0.0,
                pitch_deg=raw.pitch_deg or 0.0,
                yaw_deg=raw.yaw_deg or 0.0,
                gyro_x_dps=math.degrees(gyro[0]),
                gyro_y_dps=math.degrees(gyro[1]),
                gyro_z_dps=math.degrees(gyro[2]),
                source=AHRSMode.OFF.value,
                valid=False,
                healthy=False,
                confidence=AHRSQuality.INVALID.value,
                sample_age_ms=max(0.0, (time.monotonic_ns() - raw.timestamp_ns) / 1_000_000.0),
                enabled=False,
            )
            return self.last_state
        age_ms = (time.monotonic_ns() - raw.timestamp_ns) / 1_000_000.0
        if age_ms > config.AHRS_MAX_SAMPLE_AGE_MS:
            self.diagnostics.stale_samples += 1
            return self._degraded_last(raw, "stale sample")
        try:
            if self.mode == AHRSMode.AUTO:
                state = self._update_auto(raw)
            else:
                state = self._update_forced(self.mode, raw)
            self.last_state = state
            return state
        except Exception as exc:
            self.diagnostics.rejected_samples += 1
            logger.warning("AHRS update rejected: %s", exc)
            return self._degraded_last(raw, str(exc))

    def _update_forced(self, mode: AHRSMode, raw: RawIMUData) -> AttitudeState:
        state = self.estimators[mode].update(raw)
        self.active_mode = mode
        return state

    def _update_auto(self, raw: RawIMUData) -> AttitudeState:
        preferred = AHRSMode.BNO085 if raw.bno_quaternion_xyzw is not None else self.software_fallback_mode
        try:
            state = self.estimators[preferred].update(raw)
            if preferred != self.active_mode:
                self.recovery_count += 1
                if self.recovery_count >= config.AHRS_RECOVERY_COUNT_THRESHOLD:
                    self._switch_source(preferred, state.quaternion)
            self.fail_count = 0
            return state if preferred == self.active_mode else self._degraded_last(raw, "source recovering")
        except Exception:
            self.fail_count += 1
            if self.fail_count >= config.AHRS_FAIL_COUNT_THRESHOLD:
                fallback = self.software_fallback_mode if preferred == AHRSMode.BNO085 else AHRSMode.BNO085
                if fallback in self.estimators:
                    self._switch_source(fallback, self.last_state.quaternion)
                    return self.estimators[fallback].update(raw)
            return self._degraded_last(raw, "auto source unhealthy")

    def _switch_source(self, mode: AHRSMode, q: Quaternion) -> None:
        if mode != self.active_mode:
            logger.warning("AHRS source transition: %s -> %s", self.active_mode.value, mode.value)
            self.active_mode = mode
            self.estimators[mode].reset(q)
            self.diagnostics.source_changes += 1
            self.recovery_count = 0

    def _degraded_last(self, raw: RawIMUData, reason: str) -> AttitudeState:
        logger.debug("AHRS degraded: %s", reason)
        q = self.last_state.quaternion
        if raw.roll_deg is not None and raw.pitch_deg is not None and raw.yaw_deg is not None:
            q = from_euler_deg(raw.roll_deg, raw.pitch_deg, raw.yaw_deg)
        return _state_from_quaternion(q, raw, self.active_mode.value, True, False, AHRSQuality.DEGRADED, False, False)


def raw_from_reading(reading: dict[str, Any]) -> RawIMUData:
    timestamp_ns = int(reading.get("timestamp_ns") or time.monotonic_ns())
    gyro = reading.get("gyro_rads")
    if gyro is None and all(k in reading for k in ("gyro_x", "gyro_y", "gyro_z")):
        gyro = tuple(math.radians(float(reading[k])) for k in ("gyro_x", "gyro_y", "gyro_z"))
    bno_q = reading.get("quaternion")
    return RawIMUData(
        timestamp_ns=timestamp_ns,
        accel_mps2=reading.get("accel_mps2"),
        gyro_rads=gyro,
        mag_ut=reading.get("mag_ut"),
        bno_quaternion_xyzw=bno_q,
        bno_accuracy_rad=reading.get("accuracy_rad"),
        calibration_status=reading.get("calibration_status"),
        roll_deg=reading.get("roll"),
        pitch_deg=reading.get("pitch"),
        yaw_deg=reading.get("yaw"),
    )


def _parse_mode(mode: str | AHRSMode) -> AHRSMode:
    if isinstance(mode, AHRSMode):
        return mode
    return AHRSMode(str(mode).upper())


def _roll_pitch_from_accel(accel: tuple[float, float, float]) -> tuple[float, float]:
    ax, ay, az = accel
    roll = math.degrees(math.atan2(ay, az))
    pitch = math.degrees(math.atan2(-ax, math.sqrt(ay * ay + az * az)))
    return roll, pitch


def _slerp(a: Quaternion, b: Quaternion, t: float) -> Quaternion | None:
    a = normalize(a)
    b = normalize(b)
    if a is None or b is None:
        return None
    dot = sum(a[i] * b[i] for i in range(4))
    if dot < 0.0:
        b = tuple(-x for x in b)
        dot = -dot
    if dot > 0.9995:
        return normalize(tuple(a[i] + t * (b[i] - a[i]) for i in range(4)))
    theta_0 = math.acos(max(-1.0, min(1.0, dot)))
    sin_theta_0 = math.sin(theta_0)
    theta = theta_0 * t
    s0 = math.cos(theta) - dot * math.sin(theta) / sin_theta_0
    s1 = math.sin(theta) / sin_theta_0
    return normalize(tuple(s0 * a[i] + s1 * b[i] for i in range(4)))
