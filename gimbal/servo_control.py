"""
Servo gimbal control — mock and real-hardware placeholder.

Mock mode prints angle commands instead of driving GPIO PWM.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

import config

logger = logging.getLogger(__name__)


class BaseGimbal(ABC):
    @abstractmethod
    def set_angles(self, pitch: float, roll: float) -> None:
        """Set gimbal pitch and roll in degrees."""

    @abstractmethod
    def close(self) -> None:
        pass


class MockGimbal(BaseGimbal):
    """Prints servo commands to console instead of moving hardware."""

    def __init__(self) -> None:
        self._pitch = 0.0
        self._roll = 0.0
        logger.info("MockGimbal initialized.")

    def set_angles(self, pitch: float, roll: float) -> None:
        pitch = max(config.GIMBAL_PITCH_MIN, min(config.GIMBAL_PITCH_MAX, pitch))
        roll = max(config.GIMBAL_ROLL_MIN, min(config.GIMBAL_ROLL_MAX, roll))
        self._pitch = pitch
        self._roll = roll
        logger.info("MockGimbal -> pitch=%.1f° roll=%.1f°", pitch, roll)

    def close(self) -> None:
        logger.info("MockGimbal closed.")


class RealGimbal(BaseGimbal):
    """
    Placeholder for GPIO PWM servo control.

    Connect pitch servo to one GPIO, roll servo to another.
    Use external 5V supply with common ground.
    """

    def __init__(self) -> None:
        logger.warning("RealGimbal is a stub — implement RPi.GPIO or pigpio PWM.")

    def set_angles(self, pitch: float, roll: float) -> None:
        logger.info("RealGimbal stub: pitch=%.1f roll=%.1f", pitch, roll)

    def close(self) -> None:
        pass


def create_gimbal() -> BaseGimbal:
    if config.USE_MOCK_HARDWARE:
        return MockGimbal()
    return RealGimbal()
