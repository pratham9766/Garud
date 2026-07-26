"""Bosch BMP388 pressure sensor interface."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from config import BMP388Config
from utils.helpers import HardwareError


@dataclass(frozen=True)
class BMP388Reading:
    temperature_c: float
    pressure_hpa: float
    altitude_m: float


@dataclass
class BMP388Sensor:
    """Read temperature, pressure, and altitude from a BMP388 over I2C."""

    config: BMP388Config

    def __post_init__(self) -> None:
        self._sensor: Any | None = None

    def connect(self) -> None:
        """Initialize the BMP388 sensor."""
        if self._sensor is not None:
            return
        try:
            import board
            import busio
            import adafruit_bmp3xx
        except ImportError as exc:
            raise HardwareError("BMP388 dependencies are not installed.") from exc

        try:
            i2c = busio.I2C(board.SCL, board.SDA)
            sensor = adafruit_bmp3xx.BMP3XX_I2C(i2c, address=self.config.address)
            sensor.sea_level_pressure = self.config.sea_level_pressure_hpa
            self._sensor = sensor
        except Exception as exc:
            raise HardwareError(
                f"BMP388 not detected at 0x{self.config.address:02X}: {exc}"
            ) from exc

    def read(self) -> BMP388Reading:
        """Return one BMP388 pressure sensor sample."""
        self.connect()
        try:
            return BMP388Reading(
                temperature_c=float(self._sensor.temperature),
                pressure_hpa=float(self._sensor.pressure),
                altitude_m=float(self._sensor.altitude),
            )
        except Exception as exc:
            raise HardwareError(f"Failed to read BMP388: {exc}") from exc

    def close(self) -> None:
        """Release references held by the sensor object."""
        self._sensor = None
