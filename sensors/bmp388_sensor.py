"""
BMP388 barometer wrapper for the GARUDA HAT.

Runtime wiring is SPI0: MISO=GPIO9, MOSI=GPIO10, SCK=GPIO11, CS=GPIO8.
"""

from __future__ import annotations

import config


class BMP388Sensor:
    """Thin wrapper around the tested BMP3XX SPI setup."""

    def __init__(
        self,
        spi_bus,
        cs_pin=config.BMP388_CS,
        sea_level_pressure_hpa: float = 1013.25,
    ) -> None:
        import digitalio
        from adafruit_bmp3xx import BMP3XX_SPI

        self._cs = digitalio.DigitalInOut(cs_pin)
        self.bmp = BMP3XX_SPI(spi_bus, self._cs)
        self.bmp.sea_level_pressure = sea_level_pressure_hpa
        self.bmp.pressure_oversampling = 8
        self.bmp.temperature_oversampling = 2
        self.bmp.filter_coefficient = 2

    def set_sea_level_pressure(self, hpa: float) -> None:
        self.bmp.sea_level_pressure = hpa

    def read(self) -> dict:
        return {
            "temperature_c": self.bmp.temperature,
            "pressure_hpa": self.bmp.pressure,
            "altitude_m": self.bmp.altitude,
        }
