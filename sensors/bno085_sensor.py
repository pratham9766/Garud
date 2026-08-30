"""
BNO085 9-DOF IMU wrapper for the GARUDA HAT.

Runtime wiring is I2C1: SDA=GPIO2, SCL=GPIO3, default address 0x4A. The BNO085
native quaternion order is (x, y, z, w); AHRS code converts it explicitly.
"""

from __future__ import annotations

import time

import config


class BNO085Sensor:
    """Thin wrapper around the tested BNO08X I2C setup."""

    def __init__(self, i2c_bus, address: int = config.BNO085_I2C_ADDRESS) -> None:
        from adafruit_bno08x import (
            BNO_REPORT_ACCELEROMETER,
            BNO_REPORT_GYROSCOPE,
            BNO_REPORT_LINEAR_ACCELERATION,
            BNO_REPORT_MAGNETOMETER,
        )
        import adafruit_bno08x as bno08x
        from adafruit_bno08x.i2c import BNO08X_I2C

        self.bno = BNO08X_I2C(i2c_bus, address=address)
        rotation_report_name = (
            "BNO_REPORT_GAME_ROTATION_VECTOR"
            if config.BNO085_ROTATION_MODE == "GAME_ROTATION_VECTOR"
            else "BNO_REPORT_ROTATION_VECTOR"
        )
        rotation_report = getattr(bno08x, rotation_report_name)

        self.bno.enable_feature(BNO_REPORT_ACCELEROMETER)
        self.bno.enable_feature(BNO_REPORT_GYROSCOPE)
        if config.AHRS_USE_MAGNETOMETER:
            self.bno.enable_feature(BNO_REPORT_MAGNETOMETER)
        self.bno.enable_feature(BNO_REPORT_LINEAR_ACCELERATION)
        self.bno.enable_feature(rotation_report)

    def read(self) -> dict:
        timestamp_ns = time.monotonic_ns()
        accel_x, accel_y, accel_z = self.bno.acceleration
        gyro_x, gyro_y, gyro_z = self.bno.gyro
        lin_x, lin_y, lin_z = self.bno.linear_acceleration
        quat_i, quat_j, quat_k, quat_real = self.bno.quaternion

        mag = None
        if config.AHRS_USE_MAGNETOMETER:
            try:
                mag = tuple(float(v) for v in self.bno.magnetic)
            except Exception:
                mag = None

        return {
            "timestamp_ns": timestamp_ns,
            "accel_mps2": (float(accel_x), float(accel_y), float(accel_z)),
            "gyro_rads": (float(gyro_x), float(gyro_y), float(gyro_z)),
            "mag_ut": mag,
            "linear_accel_mps2": (float(lin_x), float(lin_y), float(lin_z)),
            "quaternion": (
                float(quat_i),
                float(quat_j),
                float(quat_k),
                float(quat_real),
            ),
            "accuracy_rad": getattr(self.bno, "accuracy", None),
            "calibration_status": getattr(self.bno, "calibration_status", None),
        }
