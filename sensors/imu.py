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
        """Return dict with roll, pitch, yaw (degrees)."""

    @abstractmethod
    def close(self) -> None:
        pass


class MockIMU(BaseIMU):
    """Simulated IMU with gentle attitude oscillation."""

    def __init__(self) -> None:
        self._t = 0.0

    def read(self) -> dict:
        self._t += 0.1
        return {
            "roll": 5.0 * math.sin(self._t) + random.uniform(-0.5, 0.5),
            "pitch": 3.0 * math.cos(self._t * 0.7) + random.uniform(-0.5, 0.5),
            "yaw": (self._t * 10.0 + random.uniform(-1.0, 1.0)) % 360.0,
        }

    def close(self) -> None:
        logger.debug("MockIMU closed.")


class RealIMU(BaseIMU):
    """Placeholder for I2C IMU at config.IMU_ADDRESS."""

    def __init__(self) -> None:
        logger.warning(
            "RealIMU is a stub — connect I2C address 0x%02X when hardware is ready.",
            config.IMU_ADDRESS,
        )

    def read(self) -> dict:
        return {"roll": 0.0, "pitch": 0.0, "yaw": 0.0}

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
