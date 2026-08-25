"""
sensors/bno085_sensor.py
-------------------------
BNO085 9-DOF IMU wrapper (I2C1: SDA=GPIO2, SCL=GPIO3).

Requires: adafruit-circuitpython-bno08x
"""
from adafruit_bno08x import (
    BNO_REPORT_ACCELEROMETER,
    BNO_REPORT_GYROSCOPE,
    BNO_REPORT_MAGNETOMETER,
    BNO_REPORT_ROTATION_VECTOR,
    BNO_REPORT_LINEAR_ACCELERATION,
)
from adafruit_bno08x.i2c import BNO08X_I2C

import config


class BNO085Sensor:
    """Thin wrapper around BNO08X_I2C exposing a single read() call."""

    def __init__(self, i2c_bus, address=config.BNO085_I2C_ADDRESS):
        self.bno = BNO08X_I2C(i2c_bus, address=address)
        self._enable_reports()

    def _enable_reports(self):
        self.bno.enable_feature(BNO_REPORT_ACCELEROMETER)
        self.bno.enable_feature(BNO_REPORT_GYROSCOPE)
        self.bno.enable_feature(BNO_REPORT_MAGNETOMETER)
        self.bno.enable_feature(BNO_REPORT_ROTATION_VECTOR)
        self.bno.enable_feature(BNO_REPORT_LINEAR_ACCELERATION)

    def read(self):
        """Return the latest IMU data as a flat dict."""
        accel_x, accel_y, accel_z = self.bno.acceleration
        gyro_x, gyro_y, gyro_z = self.bno.gyro
        mag_x, mag_y, mag_z = self.bno.magnetic
        lin_x, lin_y, lin_z = self.bno.linear_acceleration
        quat_i, quat_j, quat_k, quat_real = self.bno.quaternion

        return {
            "accel_ms2": (accel_x, accel_y, accel_z),
            "gyro_rads": (gyro_x, gyro_y, gyro_z),
            "mag_ut": (mag_x, mag_y, mag_z),
            "linear_accel_ms2": (lin_x, lin_y, lin_z),
            "quaternion": (quat_i, quat_j, quat_k, quat_real),
        }
