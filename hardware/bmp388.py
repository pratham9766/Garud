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
            if self.config.interface == "i2c":
                sensor = self._connect_i2c(board, busio, adafruit_bmp3xx)
            elif self.config.interface == "spi":
                sensor = self._connect_spi(board, busio, adafruit_bmp3xx)
            else:
                raise HardwareError(
                    f"Unsupported BMP388 interface: {self.config.interface}"
                )
            sensor.sea_level_pressure = self.config.sea_level_pressure_hpa
            self._sensor = sensor
        except Exception as exc:
            raise HardwareError(
                f"BMP388 not detected on {self.config.interface.upper()}: {exc}"
            ) from exc

    def _connect_i2c(self, board, busio, adafruit_bmp3xx):
        i2c = busio.I2C(board.SCL, board.SDA)
        return adafruit_bmp3xx.BMP3XX_I2C(i2c, address=self.config.address)

    def _connect_spi(self, board, busio, adafruit_bmp3xx):
        try:
            import digitalio
        except ImportError as exc:
            raise HardwareError("digitalio is required for BMP388 SPI mode.") from exc

        spi = busio.SPI(board.SCK, board.MOSI, board.MISO)
        chip_select_pin = getattr(board, f"D{self.config.cs_gpio}")
        chip_select = digitalio.DigitalInOut(chip_select_pin)
        return adafruit_bmp3xx.BMP3XX_SPI(spi, chip_select)

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
