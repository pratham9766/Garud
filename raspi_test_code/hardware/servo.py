"""Servo motor control using the pigpio daemon."""

from __future__ import annotations

import time
from dataclasses import dataclass

from config import ServoConfig
from utils.helpers import HardwareError


@dataclass
class ServoController:
    """Control a PWM servo through pigpio."""

    config: ServoConfig

    def __post_init__(self) -> None:
        self._pi = None

    def connect(self) -> None:
        """Connect to the local pigpio daemon."""
        if self._pi is not None:
            return
        try:
            import pigpio
        except ImportError as exc:
            raise HardwareError("pigpio Python package is not installed.") from exc

        self._pi = pigpio.pi()
        if not self._pi.connected:
            self._pi = None
            raise HardwareError("pigpio daemon is not running. Start it with: sudo systemctl start pigpiod")

    def angle_to_pulse(self, angle: float) -> int:
        """Convert an angle in degrees to a servo pulse width in microseconds."""
        if not self.config.min_angle <= angle <= self.config.max_angle:
            raise ValueError(
                f"Angle must be between {self.config.min_angle} and {self.config.max_angle} degrees"
            )
        span = self.config.max_pulse - self.config.min_pulse
        ratio = (angle - self.config.min_angle) / (self.config.max_angle - self.config.min_angle)
        return int(self.config.min_pulse + ratio * span)

    def move_to_angle(self, angle: float) -> None:
        """Move the servo to a requested angle."""
        self.connect()
        pulse = self.angle_to_pulse(angle)
        self._pi.set_servo_pulsewidth(self.config.gpio, pulse)
        time.sleep(self.config.settle_seconds)

    def sweep(self, step: int = 15) -> None:
        """Sweep from min angle to max angle and back."""
        for angle in range(self.config.min_angle, self.config.max_angle + 1, step):
            self.move_to_angle(angle)
        for angle in range(self.config.max_angle, self.config.min_angle - 1, -step):
            self.move_to_angle(angle)

    def stop(self) -> None:
        """Stop PWM output on the configured GPIO."""
        self.connect()
        self._pi.set_servo_pulsewidth(self.config.gpio, 0)

    def close(self) -> None:
        """Release the pigpio connection."""
        if self._pi is not None:
            self.stop()
            self._pi.stop()
            self._pi = None

    def __enter__(self) -> "ServoController":
        self.connect()
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()
