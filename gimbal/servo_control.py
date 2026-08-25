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
    PCA9685 two-servo gimbal on the Garud HAT.

    The existing stabilizer pipeline sends pitch/roll offsets in degrees.
    Those offsets are mapped around the servo center onto the configured
    PCA9685 channels.
    """

    def __init__(self) -> None:
        import digitalio
        from adafruit_servokit import ServoKit

        self._oe = digitalio.DigitalInOut(config.PCA9685_OE_PIN)
        self._oe.direction = digitalio.Direction.OUTPUT
        self._oe.value = False
        self._kit = ServoKit(
            channels=16,
            address=config.SERVO_CONTROLLER_ADDRESS,
        )
        logger.info(
            "PCA9685 gimbal initialized at 0x%02X (pitch ch%d, roll ch%d).",
            config.SERVO_CONTROLLER_ADDRESS,
            config.GIMBAL_TILT_CHANNEL,
            config.GIMBAL_PAN_CHANNEL,
        )

    @staticmethod
    def _servo_angle(offset: float) -> float:
        return max(
            config.GIMBAL_SERVO_MIN,
            min(config.GIMBAL_SERVO_MAX, config.GIMBAL_SERVO_CENTER + offset),
        )

    def set_angles(self, pitch: float, roll: float) -> None:
        pitch = max(config.GIMBAL_PITCH_MIN, min(config.GIMBAL_PITCH_MAX, pitch))
        roll = max(config.GIMBAL_ROLL_MIN, min(config.GIMBAL_ROLL_MAX, roll))
        self._kit.servo[config.GIMBAL_TILT_CHANNEL].angle = self._servo_angle(pitch)
        self._kit.servo[config.GIMBAL_PAN_CHANNEL].angle = self._servo_angle(roll)

    def close(self) -> None:
        self._kit.servo[config.GIMBAL_TILT_CHANNEL].angle = None
        self._kit.servo[config.GIMBAL_PAN_CHANNEL].angle = None
        self._oe.value = True


def create_gimbal() -> BaseGimbal:
    if config.USE_MOCK_HARDWARE:
        return MockGimbal()
    return RealGimbal()
