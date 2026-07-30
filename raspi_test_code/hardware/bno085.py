"""Bosch/Hillcrest BNO085 IMU interface using SPI."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from config import BNO085Config
from utils.helpers import HardwareError


@dataclass(frozen=True)
class BNO085Reading:
    acceleration: tuple[float, float, float] | None
    gyroscope: tuple[float, float, float] | None
    magnetometer: tuple[float, float, float] | None
    quaternion: tuple[float, float, float, float] | None
    calibration_status: int | None


@dataclass
class BNO085Sensor:
    """Read motion and orientation data from a BNO085 over SPI0."""

    config: BNO085Config

    def __post_init__(self) -> None:
        self._sensor: Any | None = None

    def connect(self) -> None:
        """Initialize the BNO085 SPI sensor."""
        if self._sensor is not None:
            return
        if self.config.interface != "spi":
            raise HardwareError(f"Unsupported BNO085 interface: {self.config.interface}")

        try:
            import board
            import busio
            import digitalio
            from adafruit_bno08x import (
                BNO_REPORT_ACCELEROMETER,
                BNO_REPORT_GYROSCOPE,
                BNO_REPORT_MAGNETOMETER,
                BNO_REPORT_ROTATION_VECTOR,
            )
            from adafruit_bno08x.spi import BNO08X_SPI
        except ImportError as exc:
            raise HardwareError(
                "BNO085 SPI dependencies are not installed. Install "
                "adafruit-circuitpython-bno08x."
            ) from exc

        try:
            spi = busio.SPI(board.SCK, board.MOSI, board.MISO)
            chip_select = digitalio.DigitalInOut(getattr(board, f"D{self.config.cs_gpio}"))
            interrupt = digitalio.DigitalInOut(getattr(board, f"D{self.config.int_gpio}"))
            reset = digitalio.DigitalInOut(getattr(board, f"D{self.config.reset_gpio}"))
            sensor = BNO08X_SPI(spi, chip_select, interrupt, reset)
            sensor.enable_feature(BNO_REPORT_ACCELEROMETER)
            sensor.enable_feature(BNO_REPORT_GYROSCOPE)
            sensor.enable_feature(BNO_REPORT_MAGNETOMETER)
            sensor.enable_feature(BNO_REPORT_ROTATION_VECTOR)
            self._sensor = sensor
        except Exception as exc:
            raise HardwareError(
                "BNO085 not detected on SPI "
                f"(CS GPIO{self.config.cs_gpio}, RST GPIO{self.config.reset_gpio}): {exc}"
            ) from exc

    def read(self) -> BNO085Reading:
        """Return one complete BNO085 sensor sample."""
        self.connect()
        try:
            return BNO085Reading(
                acceleration=self._sensor.acceleration,
                gyroscope=self._sensor.gyro,
                magnetometer=self._sensor.magnetic,
                quaternion=self._sensor.quaternion,
                calibration_status=getattr(self._sensor, "calibration_status", None),
            )
        except Exception as exc:
            raise HardwareError(f"Failed to read BNO085: {exc}") from exc

    def close(self) -> None:
        """Release references held by the sensor object."""
        self._sensor = None
