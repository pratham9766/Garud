"""
IMU module — mock and real-hardware placeholder.

Mock generates small roll/pitch/yaw variations.
"""

from __future__ import annotations

import logging
import math
import random
import threading
import time
from abc import ABC, abstractmethod

import config
from core.shared_data import SharedData
from sensor_fusion.ahrs import AHRSManager, raw_from_reading
from sensor_fusion.quaternion import bno_xyzw_to_wxyz, from_euler_deg, to_euler_deg

logger = logging.getLogger(__name__)


class BaseIMU(ABC):
    @abstractmethod
    def read(self) -> dict:
        """Return attitude in degrees and angular velocity in degrees/second."""

    @abstractmethod
    def close(self) -> None:
        pass


class MockIMU(BaseIMU):
    """Simulated IMU with gentle attitude oscillation."""

    def __init__(self) -> None:
        self._t = 0.0
        self._last_roll = 0.0
        self._last_pitch = 0.0
        self._last_yaw = 0.0

    def read(self) -> dict:
        timestamp_ns = time.monotonic_ns()
        self._t += 0.1
        roll = 5.0 * math.sin(self._t) + random.uniform(-0.5, 0.5)
        pitch = 3.0 * math.cos(self._t * 0.7) + random.uniform(-0.5, 0.5)
        yaw = (self._t * 10.0 + random.uniform(-1.0, 1.0)) % 360.0
        gyro_x = (roll - self._last_roll) / 0.1
        gyro_y = (pitch - self._last_pitch) / 0.1
        yaw_delta = ((yaw - self._last_yaw + 180.0) % 360.0) - 180.0
        gyro_z = yaw_delta / 0.1
        self._last_roll = roll
        self._last_pitch = pitch
        self._last_yaw = yaw
        q = from_euler_deg(roll, pitch, yaw)
        return {
            "timestamp_ns": timestamp_ns,
            "roll": roll,
            "pitch": pitch,
            "yaw": yaw,
            "gyro_x": gyro_x,
            "gyro_y": gyro_y,
            "gyro_z": gyro_z,
            "gyro_rads": (math.radians(gyro_x), math.radians(gyro_y), math.radians(gyro_z)),
            "accel_mps2": (0.0, 0.0, 9.80665),
            "mag_ut": (25.0, 0.0, 35.0),
            "quaternion": (q[1], q[2], q[3], q[0]),
            "accuracy_rad": 0.05,
            "calibration_status": 3,
        }

    def close(self) -> None:
        logger.debug("MockIMU closed.")


class RealIMU(BaseIMU):
    """BNO085 IMU on GARUDA HAT I2C1 by default, with SPI bench fallback by config."""

    def __init__(self) -> None:
        if str(config.BNO085_TRANSPORT).upper() == "SPI":
            import bus_manager
            import digitalio
            from adafruit_bno08x import (
                BNO_REPORT_ACCELEROMETER,
                BNO_REPORT_GYROSCOPE,
                BNO_REPORT_LINEAR_ACCELERATION,
                BNO_REPORT_MAGNETOMETER,
            )
            import adafruit_bno08x as bno08x
            from adafruit_bno08x.spi import BNO08X_SPI

            if config.BNO085_CS is None or config.BNO085_INT is None or config.BNO085_RST is None:
                raise ValueError("BNO085 SPI transport requires BNO085_CS/INT/RST pins.")
            rotation_report = getattr(
                bno08x,
                "BNO_REPORT_GAME_ROTATION_VECTOR"
                if config.BNO085_ROTATION_MODE == "GAME_ROTATION_VECTOR"
                else "BNO_REPORT_ROTATION_VECTOR",
            )
            self._cs = digitalio.DigitalInOut(config.BNO085_CS)
            self._int = digitalio.DigitalInOut(config.BNO085_INT)
            self._reset = digitalio.DigitalInOut(config.BNO085_RST)
            self._bno = BNO08X_SPI(bus_manager.get_spi(), self._cs, self._int, self._reset)
            self._sensor = None
            self._bno.enable_feature(BNO_REPORT_ACCELEROMETER)
            self._bno.enable_feature(BNO_REPORT_GYROSCOPE)
            if config.AHRS_USE_MAGNETOMETER:
                self._bno.enable_feature(BNO_REPORT_MAGNETOMETER)
            self._bno.enable_feature(BNO_REPORT_LINEAR_ACCELERATION)
            self._bno.enable_feature(rotation_report)
            bus_detail = f"SPI CS GPIO{config.BNO085_CS_PIN}"
        else:
            import bus_manager
            from sensors.bno085_sensor import BNO085Sensor

            self._sensor = BNO085Sensor(
                bus_manager.get_i2c(),
                address=config.BNO085_I2C_ADDRESS,
            )
            self._bno = self._sensor.bno
            bus_detail = f"I2C address 0x{config.BNO085_I2C_ADDRESS:02X}"
        logger.info("BNO085 initialized on %s (%s).", bus_detail, config.BNO085_ROTATION_MODE)

    def read(self) -> dict:
        if self._sensor is not None:
            data = self._sensor.read()
        else:
            timestamp_ns = time.monotonic_ns()
            accel = tuple(float(v) for v in self._bno.acceleration)
            gyro = tuple(float(v) for v in self._bno.gyro)
            mag = None
            if config.AHRS_USE_MAGNETOMETER:
                try:
                    mag = tuple(float(v) for v in self._bno.magnetic)
                except Exception:
                    mag = None
            lin = tuple(float(v) for v in self._bno.linear_acceleration)
            quat_i, quat_j, quat_k, quat_real = self._bno.quaternion
            data = {
                "timestamp_ns": timestamp_ns,
                "accel_mps2": accel,
                "gyro_rads": gyro,
                "mag_ut": mag,
                "linear_accel_mps2": lin,
                "quaternion": (quat_i, quat_j, quat_k, quat_real),
                "accuracy_rad": getattr(self._bno, "accuracy", None),
                "calibration_status": getattr(self._bno, "calibration_status", None),
            }
        quat_i, quat_j, quat_k, quat_real = data["quaternion"]
        q = bno_xyzw_to_wxyz(quat_i, quat_j, quat_k, quat_real)
        roll, pitch, yaw = to_euler_deg(q) if q else (0.0, 0.0, 0.0)
        gyro_x, gyro_y, gyro_z = data["gyro_rads"]
        return {
            **data,
            "roll": roll,
            "pitch": pitch,
            "yaw": yaw,
            "gyro_x": math.degrees(gyro_x),
            "gyro_y": math.degrees(gyro_y),
            "gyro_z": math.degrees(gyro_z),
        }

    def close(self) -> None:
        pass


def create_imu() -> BaseIMU:
    if config.USE_MOCK_HARDWARE:
        return MockIMU()
    return RealIMU()


def imu_worker(shared: SharedData, stop_event: threading.Event) -> None:
    """Background thread: poll IMU and update shared data."""
    try:
        imu = create_imu()
    except Exception as exc:
        logger.error("IMU init error: %s", exc)
        shared.update(imu_ok=False, status="IMU_INIT_ERROR")
        return
    ahrs = AHRSManager()
    logger.info("IMU worker started (mock=%s).", config.USE_MOCK_HARDWARE)

    try:
        while not stop_event.is_set():
            try:
                reading = imu.read()
                raw = raw_from_reading(reading)
                attitude = ahrs.update(raw)
                raw_q = bno_xyzw_to_wxyz(*raw.bno_quaternion_xyzw) if raw.bno_quaternion_xyzw else None
                raw_accel = raw.accel_mps2 or (0.0, 0.0, 0.0)
                raw_mag = raw.mag_ut or (0.0, 0.0, 0.0)
                if raw_q is None:
                    raw_q = (1.0, 0.0, 0.0, 0.0)
                shared.update(
                    raw_accel_x=raw_accel[0],
                    raw_accel_y=raw_accel[1],
                    raw_accel_z=raw_accel[2],
                    raw_mag_x=raw_mag[0],
                    raw_mag_y=raw_mag[1],
                    raw_mag_z=raw_mag[2],
                    raw_quat_w=raw_q[0],
                    raw_quat_x=raw_q[1],
                    raw_quat_y=raw_q[2],
                    raw_quat_z=raw_q[3],
                    imu_ok=True,
                )
                shared.publish_attitude(attitude)
            except Exception as exc:
                logger.error("IMU read error: %s", exc)
                shared.update(imu_ok=False, status="IMU_ERROR")

            stop_event.wait(1.0 / config.AHRS_RATE_HZ)
    finally:
        imu.close()
        logger.info("IMU worker stopped.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sd = SharedData()
    evt = threading.Event()
    t = threading.Thread(target=imu_worker, args=(sd, evt), daemon=True)
    t.start()
    for _ in range(5):
        time.sleep(0.5)
        print(sd.get_snapshot())
    evt.set()
    t.join()
