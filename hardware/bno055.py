"""Bosch BNO055 IMU interface."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from config import BNO055Config
from utils.helpers import HardwareError


@dataclass(frozen=True)
class BNO055Reading:
    acceleration: tuple[float, float, float] | None
    gyroscope: tuple[float, float, float] | None
    magnetometer: tuple[float, float, float] | None
    euler: tuple[float, float, float] | None
    quaternion: tuple[float, float, float, float] | None
    calibration_status: tuple[int, int, int, int]
    temperature_c: int | None


@dataclass
class BNO055Sensor:
    """Read orientation and motion data from a BNO055 over I2C."""

    config: BNO055Config

    def __post_init__(self) -> None:
        self._sensor: Any | None = None

    def connect(self) -> None:
        """Initialize the BNO055 sensor."""
        if self._sensor is not None:
            return
        if self.config.interface != "i2c":
            raise HardwareError(
                "BNO055Sensor supports I2C only. The uploaded schematic appears "
                "to show SPI-style BNO nets; use an I2C BNO055 connection or a "
                "BNO08x driver if that is the actual module."
            )
        try:
            import board
            import busio
            import adafruit_bno055
        except ImportError as exc:
            raise HardwareError("BNO055 dependencies are not installed.") from exc

        try:
            i2c = busio.I2C(board.SCL, board.SDA)
            self._sensor = adafruit_bno055.BNO055_I2C(i2c, address=self.config.address)
        except Exception as exc:
            raise HardwareError(
                f"BNO055 not detected at 0x{self.config.address:02X}: {exc}"
            ) from exc

    def read(self) -> BNO055Reading:
        """Return one complete BNO055 sensor sample."""
        self.connect()
        try:
            return BNO055Reading(
                acceleration=self._sensor.acceleration,
                gyroscope=self._sensor.gyro,
                magnetometer=self._sensor.magnetic,
                euler=self._sensor.euler,
                quaternion=self._sensor.quaternion,
                calibration_status=self._sensor.calibration_status,
                temperature_c=self._sensor.temperature,
            )
        except Exception as exc:
            raise HardwareError(f"Failed to read BNO055: {exc}") from exc

    def close(self) -> None:
        """Release references held by the sensor object."""
        self._sensor = None
