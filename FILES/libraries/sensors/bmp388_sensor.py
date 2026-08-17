"""
sensors/bmp388_sensor.py
--------------------------
BMP388 barometric pressure / altitude wrapper (SPI0: MISO=GPIO9,
MOSI=GPIO10, SCK=GPIO11, CS=GPIO8).

Requires: adafruit-circuitpython-bmp3xx
"""
import digitalio
from adafruit_bmp3xx import BMP3XX_SPI

import config


class BMP388Sensor:
    """Thin wrapper around BMP3XX_SPI exposing a single read() call."""

    def __init__(self, spi_bus, cs_pin=config.BMP388_CS_PIN,
                 sea_level_pressure_hpa=1013.25):
        cs = digitalio.DigitalInOut(cs_pin)
        self.bmp = BMP3XX_SPI(spi_bus, cs)
        self.bmp.sea_level_pressure = sea_level_pressure_hpa

        # Tuned for a fast-descending / fast-moving CanSat payload
        self.bmp.pressure_oversampling = 8
        self.bmp.temperature_oversampling = 2
        self.bmp.filter_coefficient = 2

    def set_sea_level_pressure(self, hpa):
        """Call this on the pad just before launch for accurate AGL altitude."""
        self.bmp.sea_level_pressure = hpa

    def read(self):
        return {
            "temperature_c": self.bmp.temperature,
            "pressure_hpa": self.bmp.pressure,
            "altitude_m": self.bmp.altitude,
        }
