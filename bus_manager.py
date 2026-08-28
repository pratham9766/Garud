"""
Shared hardware bus access for the GARUDA HAT.

BNO085, PCA9685, and INA219 share I2C1. BMP388 and the SC16IS750 GPS UART
bridge share SPI0 with separate chip-select pins.
"""

from __future__ import annotations

import config

_i2c_bus = None
_spi_bus = None


def get_i2c():
    """Return the shared I2C1 bus (GPIO2=SDA, GPIO3=SCL)."""
    global _i2c_bus
    if _i2c_bus is None:
        import busio

        _i2c_bus = busio.I2C(config.I2C_SCL, config.I2C_SDA)
    return _i2c_bus


def get_spi():
    """Return the shared SPI0 bus (GPIO9/10/11)."""
    global _spi_bus
    if _spi_bus is None:
        import busio

        _spi_bus = busio.SPI(
            config.SPI_SCK,
            MOSI=config.SPI_MOSI,
            MISO=config.SPI_MISO,
        )
    return _spi_bus
