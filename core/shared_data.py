"""
Thread-safe shared data store for all payload subsystems.

Every sensor thread writes here; logger, telemetry, and mapping read from here.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, fields
from typing import Any

from core.mission_state import MissionState
from sensor_fusion.ahrs import AttitudeState


@dataclass
class PayloadSnapshot:
    """Point-in-time copy of all shared payload fields."""

    timestamp: float = 0.0
    mission_time: float = 0.0
    state: str = MissionState.BOOT.value
    latitude: float = 0.0
    longitude: float = 0.0
    gps_altitude: float = 0.0
    baro_altitude: float = 0.0
    roll: float = 0.0
    pitch: float = 0.0
    yaw: float = 0.0
    gyro_x: float = 0.0
    gyro_y: float = 0.0
    gyro_z: float = 0.0
    raw_gyro_x: float = 0.0
    raw_gyro_y: float = 0.0
    raw_gyro_z: float = 0.0
    raw_accel_x: float = 0.0
    raw_accel_y: float = 0.0
    raw_accel_z: float = 0.0
    raw_mag_x: float = 0.0
    raw_mag_y: float = 0.0
    raw_mag_z: float = 0.0
    raw_quat_w: float = 1.0
    raw_quat_x: float = 0.0
    raw_quat_y: float = 0.0
    raw_quat_z: float = 0.0
    raw_imu_timestamp_ns: int = 0
    raw_imu_accuracy_rad: float = 0.0
    raw_imu_calibration_status: int = -1
    raw_baro_pressure_hpa: float = 0.0
    raw_baro_temperature_c: float = 0.0
    gimbal_x_deflection_deg: float = 0.0
    gimbal_y_deflection_deg: float = 0.0
    gimbal_stepper_angle_deg: float = 0.0
    gimbal_servo_angle_deg: float = 90.0
    gimbal_stepper_steps: int = 0
    gimbal_ok: bool = False
    ahrs_enabled: bool = False
    ahrs_source: str = "OFF"
    ahrs_valid: bool = False
    ahrs_healthy: bool = False
    ahrs_confidence: str = "INVALID"
    quat_w: float = 1.0
    quat_x: float = 0.0
    quat_y: float = 0.0
    quat_z: float = 0.0
    ahrs_roll: float = 0.0
    ahrs_pitch: float = 0.0
    ahrs_yaw: float = 0.0
    attitude_accuracy_rad: float = 0.0
    imu_sample_age_ms: float = 0.0
    accel_correction_active: bool = False
    mag_correction_active: bool = False
    ahrs_timestamp_ns: int = 0
    image_name: str = ""
    image_timestamp: float = 0.0
    battery: float = 100.0
    status: str = "OK"
    camera_ok: bool = False
    gps_ok: bool = False
    imu_ok: bool = False
    barometer_ok: bool = False
    telemetry_ok: bool = False
    
    # GNC fields
    servo_left: float = 90.0
    servo_right: float = 90.0
    servo_drogue: float = 60.0
    heading_cmd: float = 0.0
    roll_cmd: float = 0.0
    pitch_cmd: float = 0.0


class SharedData:
    """Thread-safe container for live mission data."""

    CSV_HEADER = (
        "timestamp,mission_time,state,latitude,longitude,gps_altitude,"
        "baro_altitude,roll,pitch,yaw,gyro_x,gyro_y,gyro_z,image_name,"
        "image_timestamp,battery,status,ahrs_enabled,ahrs_source,ahrs_valid,"
        "ahrs_healthy,ahrs_confidence,quat_w,quat_x,quat_y,quat_z,ahrs_roll,"
        "ahrs_pitch,ahrs_yaw,attitude_accuracy_rad,imu_sample_age_ms,"
        "accel_correction_active,mag_correction_active,ahrs_timestamp_ns,"
        "raw_gyro_x,raw_gyro_y,raw_gyro_z,raw_accel_x,raw_accel_y,raw_accel_z,"
        "raw_mag_x,raw_mag_y,raw_mag_z,raw_quat_w,raw_quat_x,raw_quat_y,"
        "raw_quat_z,raw_imu_timestamp_ns,raw_imu_accuracy_rad,"
        "raw_imu_calibration_status,raw_baro_pressure_hpa,"
        "raw_baro_temperature_c,gimbal_x_deflection_deg,gimbal_y_deflection_deg,"
        "gimbal_stepper_angle_deg,gimbal_servo_angle_deg,gimbal_stepper_steps,"
        "gimbal_ok,"
        "servo_left,servo_right,servo_drogue,heading_cmd,roll_cmd,pitch_cmd"
    )

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._data = PayloadSnapshot()
        self._mission_start: float | None = None

    def start_mission_clock(self) -> None:
        """Reset and start the mission elapsed-time clock."""
        with self._lock:
            self._mission_start = time.time()

    def get_mission_time(self) -> float:
        """Seconds elapsed since mission clock started."""
        with self._lock:
            if self._mission_start is None:
                return 0.0
            return time.time() - self._mission_start

    def update(self, **kwargs: Any) -> None:
        """Update one or more fields atomically."""
        with self._lock:
            for key, value in kwargs.items():
                if hasattr(self._data, key):
                    setattr(self._data, key, value)
                else:
                    raise AttributeError(f"Unknown shared field: {key}")
            self._data.timestamp = time.time()
            if self._mission_start is not None:
                self._data.mission_time = time.time() - self._mission_start

    def publish_attitude(self, attitude: AttitudeState) -> None:
        """Atomically publish final AHRS attitude while preserving legacy fields."""
        accuracy = 0.0 if attitude.accuracy_rad is None else attitude.accuracy_rad
        self.update(
            roll=attitude.roll_deg,
            pitch=attitude.pitch_deg,
            yaw=attitude.yaw_deg,
            gyro_x=attitude.gyro_x_dps,
            gyro_y=attitude.gyro_y_dps,
            gyro_z=attitude.gyro_z_dps,
            ahrs_enabled=attitude.enabled,
            ahrs_source=attitude.source,
            ahrs_valid=attitude.valid,
            ahrs_healthy=attitude.healthy,
            ahrs_confidence=attitude.confidence,
            quat_w=attitude.q_w,
            quat_x=attitude.q_x,
            quat_y=attitude.q_y,
            quat_z=attitude.q_z,
            ahrs_roll=attitude.roll_deg,
            ahrs_pitch=attitude.pitch_deg,
            ahrs_yaw=attitude.yaw_deg,
            attitude_accuracy_rad=accuracy,
            imu_sample_age_ms=attitude.sample_age_ms,
            accel_correction_active=attitude.accel_correction_enabled,
            mag_correction_active=attitude.mag_correction_enabled,
            ahrs_timestamp_ns=attitude.timestamp_ns,
        )

    def get_snapshot(self) -> PayloadSnapshot:
        """Return a copy of the current data (safe to use outside the lock)."""
        with self._lock:
            return PayloadSnapshot(**{
                f.name: getattr(self._data, f.name) for f in fields(self._data)
            })

    def to_csv_row(self) -> str:
        """Format current data as a CSV row matching CSV_HEADER."""
        snap = self.get_snapshot()
        return (
            f"{snap.timestamp:.3f},{snap.mission_time:.3f},{snap.state},"
            f"{snap.latitude:.6f},{snap.longitude:.6f},"
            f"{snap.gps_altitude:.2f},{snap.baro_altitude:.2f},"
            f"{snap.roll:.2f},{snap.pitch:.2f},{snap.yaw:.2f},"
            f"{snap.gyro_x:.3f},{snap.gyro_y:.3f},{snap.gyro_z:.3f},"
            f"{snap.image_name},{snap.image_timestamp:.3f},"
            f"{snap.battery:.1f},{snap.status},"
            f"{int(snap.ahrs_enabled)},{snap.ahrs_source},{int(snap.ahrs_valid)},"
            f"{int(snap.ahrs_healthy)},{snap.ahrs_confidence},"
            f"{snap.quat_w:.8f},{snap.quat_x:.8f},{snap.quat_y:.8f},{snap.quat_z:.8f},"
            f"{snap.ahrs_roll:.2f},{snap.ahrs_pitch:.2f},{snap.ahrs_yaw:.2f},"
            f"{snap.attitude_accuracy_rad:.6f},{snap.imu_sample_age_ms:.2f},"
            f"{int(snap.accel_correction_active)},{int(snap.mag_correction_active)},"
            f"{snap.ahrs_timestamp_ns},"
            f"{snap.raw_gyro_x:.6f},{snap.raw_gyro_y:.6f},{snap.raw_gyro_z:.6f},"
            f"{snap.raw_accel_x:.4f},{snap.raw_accel_y:.4f},{snap.raw_accel_z:.4f},"
            f"{snap.raw_mag_x:.4f},{snap.raw_mag_y:.4f},{snap.raw_mag_z:.4f},"
            f"{snap.raw_quat_w:.8f},{snap.raw_quat_x:.8f},{snap.raw_quat_y:.8f},"
            f"{snap.raw_quat_z:.8f},{snap.raw_imu_timestamp_ns},"
            f"{snap.raw_imu_accuracy_rad:.6f},{snap.raw_imu_calibration_status},"
            f"{snap.raw_baro_pressure_hpa:.4f},{snap.raw_baro_temperature_c:.4f},"
            f"{snap.gimbal_x_deflection_deg:.3f},{snap.gimbal_y_deflection_deg:.3f},"
            f"{snap.gimbal_stepper_angle_deg:.3f},{snap.gimbal_servo_angle_deg:.3f},"
            f"{snap.gimbal_stepper_steps},{int(snap.gimbal_ok)}"
        )
