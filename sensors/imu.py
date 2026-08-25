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
        return {
            "roll": roll,
            "pitch": pitch,
            "yaw": yaw,
            "gyro_x": gyro_x,
            "gyro_y": gyro_y,
            "gyro_z": gyro_z,
        }

    def close(self) -> None:
        logger.debug("MockIMU closed.")


class RealIMU(BaseIMU):
    """BNO085 IMU on Garud HAT I2C1."""

    def __init__(self) -> None:
        import bus_manager
        from adafruit_bno08x import (
            BNO_REPORT_ACCELEROMETER,
            BNO_REPORT_GYROSCOPE,
            BNO_REPORT_ROTATION_VECTOR,
        )
        from adafruit_bno08x.i2c import BNO08X_I2C

        self._bno = BNO08X_I2C(
            bus_manager.get_i2c(),
            address=config.BNO085_I2C_ADDRESS,
        )
        self._bno.enable_feature(BNO_REPORT_ACCELEROMETER)
        self._bno.enable_feature(BNO_REPORT_GYROSCOPE)
        self._bno.enable_feature(BNO_REPORT_ROTATION_VECTOR)
        logger.info(
            "BNO085 initialized on I2C address 0x%02X.",
            config.BNO085_I2C_ADDRESS,
        )

    @staticmethod
    def _quat_to_euler(i: float, j: float, k: float, real: float) -> tuple[float, float, float]:
        """Convert BNO085 quaternion (i, j, k, real) to roll/pitch/yaw degrees."""
        x, y, z, w = i, j, k, real
        sinr_cosp = 2.0 * (w * x + y * z)
        cosr_cosp = 1.0 - 2.0 * (x * x + y * y)
        roll = math.degrees(math.atan2(sinr_cosp, cosr_cosp))

        sinp = 2.0 * (w * y - z * x)
        if abs(sinp) >= 1.0:
            pitch = math.degrees(math.copysign(math.pi / 2.0, sinp))
        else:
            pitch = math.degrees(math.asin(sinp))

        siny_cosp = 2.0 * (w * z + x * y)
        cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
        yaw = math.degrees(math.atan2(siny_cosp, cosy_cosp)) % 360.0
        return roll, pitch, yaw

    def read(self) -> dict:
        gyro_x, gyro_y, gyro_z = self._bno.gyro
        quat_i, quat_j, quat_k, quat_real = self._bno.quaternion
        roll, pitch, yaw = self._quat_to_euler(quat_i, quat_j, quat_k, quat_real)
        return {
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
    imu = create_imu()
    logger.info("IMU worker started (mock=%s).", config.USE_MOCK_HARDWARE)

    try:
        while not stop_event.is_set():
            try:
                reading = imu.read()
                shared.update(
                    roll=reading["roll"],
                    pitch=reading["pitch"],
                    yaw=reading["yaw"],
                    gyro_x=reading.get("gyro_x", 0.0),
                    gyro_y=reading.get("gyro_y", 0.0),
                    gyro_z=reading.get("gyro_z", 0.0),
                    imu_ok=True,
                )
            except Exception as exc:
                logger.error("IMU read error: %s", exc)
                shared.update(imu_ok=False, status="IMU_ERROR")

            stop_event.wait(0.1)
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
