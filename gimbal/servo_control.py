"""
Servo gimbal control — mock and real-hardware placeholder.

Mock mode prints angle commands instead of driving GPIO PWM.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

import config
from gimbal.stepper_control import ULN2003Stepper

logger = logging.getLogger(__name__)


class BaseGimbal(ABC):
    @abstractmethod
    def set_angles(self, pitch: float, roll: float) -> None:
        """Set gimbal pitch and roll in degrees."""

    @abstractmethod
    def point_down(self, attitude_roll: float, attitude_pitch: float, dt: float) -> dict:
        """Correct attitude deflection and return command details."""

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

    def point_down(self, attitude_roll: float, attitude_pitch: float, dt: float) -> dict:
        x_deflection = attitude_roll
        y_deflection = attitude_pitch
        self.set_angles(
            config.GIMBAL_SERVO_SIGN * y_deflection,
            config.GIMBAL_STEPPER_SIGN * x_deflection,
        )
        return {
            "x_deflection_deg": x_deflection,
            "y_deflection_deg": y_deflection,
            "stepper_angle_deg": self._roll,
            "servo_angle_deg": config.GIMBAL_SERVO_CENTER + self._pitch,
            "stepper_steps": 0,
        }

    def close(self) -> None:
        logger.info("MockGimbal closed.")


class RealGimbal(BaseGimbal):
    """
    Stepper plus PCA9685-servo gimbal on the Garud HAT.

    The stepper corrects the opposite X-axis deflection. The positional servo
    on PCA9685 channel 0 corrects the opposite Y-axis deflection.
    """

    def __init__(self) -> None:
        import digitalio
        from adafruit_servokit import ServoKit

        self._oe = digitalio.DigitalInOut(config.PCA9685_OE_PIN)
        self._oe.direction = digitalio.Direction.OUTPUT
        self._oe.value = False
        self._stepper = ULN2003Stepper()
        self._kit = ServoKit(
            channels=16,
            address=config.SERVO_CONTROLLER_ADDRESS,
        )
        self._stepper_angle_deg = config.GIMBAL_STEPPER_HOME_DEG
        self._servo_angle_deg = config.GIMBAL_SERVO_CENTER
        self._kit.servo[config.GIMBAL_SERVO_CHANNEL].set_pulse_width_range(500, 2500)
        self._kit.servo[config.GIMBAL_SERVO_CHANNEL].angle = self._servo_angle_deg
        logger.info(
            "Gimbal initialized: stepper=%s, servo axis=%s channel=%d at PCA9685 0x%02X.",
            config.GIMBAL_STEPPER_AXIS,
            config.GIMBAL_SERVO_AXIS,
            config.GIMBAL_SERVO_CHANNEL,
            config.SERVO_CONTROLLER_ADDRESS,
        )

    @staticmethod
    def _servo_angle(offset: float) -> float:
        return max(
            config.GIMBAL_SERVO_MIN,
            min(config.GIMBAL_SERVO_MAX, config.GIMBAL_SERVO_CENTER + offset),
        )

    @staticmethod
    def _clamp(value: float, lower: float, upper: float) -> float:
        return max(lower, min(upper, value))

    @staticmethod
    def _deadband(value: float) -> float:
        if abs(value) < config.GIMBAL_DEFLECTION_DEADBAND_DEG:
            return 0.0
        return value

    def _move_stepper_to(self, target_deg: float) -> int:
        unclamped_target = target_deg
        target_deg = self._clamp(
            target_deg,
            config.GIMBAL_STEPPER_MIN_DEG,
            config.GIMBAL_STEPPER_MAX_DEG,
        )
        delta_deg = target_deg - self._stepper_angle_deg
        steps = round(delta_deg * config.GIMBAL_STEPS_PER_DEG)
        steps = max(
            -config.GIMBAL_MAX_STEPS_PER_TICK,
            min(config.GIMBAL_MAX_STEPS_PER_TICK, steps),
        )
        if steps:
            self._stepper.step(steps)
            self._stepper_angle_deg += steps / config.GIMBAL_STEPS_PER_DEG
        return steps

    def set_angles(self, pitch: float, roll: float) -> None:
        pitch = self._clamp(pitch, config.GIMBAL_PITCH_MIN, config.GIMBAL_PITCH_MAX)
        roll = self._clamp(roll, config.GIMBAL_ROLL_MIN, config.GIMBAL_ROLL_MAX)
        self._servo_angle_deg = self._servo_angle(pitch)
        self._kit.servo[config.GIMBAL_SERVO_CHANNEL].angle = self._servo_angle_deg
        self._move_stepper_to(roll)

    def point_down(self, attitude_roll: float, attitude_pitch: float, dt: float) -> dict:
        x_deflection = self._deadband(attitude_roll)
        y_deflection = self._deadband(attitude_pitch)

        max_servo_step = config.GIMBAL_SERVO_RATE_LIMIT_DPS * max(dt, 0.0)
        max_stepper_step = config.GIMBAL_STEPPER_RATE_LIMIT_DPS * max(dt, 0.0)
        raw_stepper_target = config.GIMBAL_STEPPER_HOME_DEG + config.GIMBAL_STEPPER_SIGN * x_deflection
        raw_servo_target = config.GIMBAL_SERVO_CENTER + config.GIMBAL_SERVO_SIGN * y_deflection
        desired_stepper = self._clamp(
            raw_stepper_target,
            self._stepper_angle_deg - max_stepper_step,
            self._stepper_angle_deg + max_stepper_step,
        )
        desired_servo = self._clamp(
            raw_servo_target,
            self._servo_angle_deg - max_servo_step,
            self._servo_angle_deg + max_servo_step,
        )

        stepper_steps = self._move_stepper_to(desired_stepper)
        self._servo_angle_deg = self._clamp(
            desired_servo,
            config.GIMBAL_SERVO_MIN,
            config.GIMBAL_SERVO_MAX,
        )
        self._kit.servo[config.GIMBAL_SERVO_CHANNEL].angle = self._servo_angle_deg
        return {
            "x_deflection_deg": x_deflection,
            "y_deflection_deg": y_deflection,
            "stepper_target_deg": raw_stepper_target,
            "servo_target_deg": raw_servo_target,
            "stepper_angle_deg": self._stepper_angle_deg,
            "servo_angle_deg": self._servo_angle_deg,
            "stepper_steps": stepper_steps,
            "stepper_rate_limited": abs(desired_stepper - raw_stepper_target) > 1e-6,
            "servo_rate_limited": abs(desired_servo - raw_servo_target) > 1e-6,
            "stepper_saturated": raw_stepper_target < config.GIMBAL_STEPPER_MIN_DEG or raw_stepper_target > config.GIMBAL_STEPPER_MAX_DEG,
            "servo_saturated": raw_servo_target < config.GIMBAL_SERVO_MIN or raw_servo_target > config.GIMBAL_SERVO_MAX,
        }

    def close(self) -> None:
        self._kit.servo[config.GIMBAL_SERVO_CHANNEL].angle = None
        self._stepper.release()
        self._oe.value = True


def create_gimbal() -> BaseGimbal:
    if config.USE_MOCK_HARDWARE:
        return MockGimbal()
    return RealGimbal()
