"""
bus_manager.py
---------------
Lazily creates and hands out ONE shared I2C bus object and ONE shared SPI
bus object, so BNO085 + PCA9685 (both on I2C1) and BMP388 (on SPI0) never
fight over re-initializing the same physical bus.
"""
import busio

import config

_i2c_bus = None
_spi_bus = None


def get_i2c():
    """Return the shared I2C1 bus (GPIO2=SDA, GPIO3=SCL)."""
    global _i2c_bus
    if _i2c_bus is None:
        _i2c_bus = busio.I2C(config.I2C_SCL, config.I2C_SDA)
    return _i2c_bus


def get_spi():
    """Return the shared SPI0 bus (GPIO9/10/11)."""
    global _spi_bus
    if _spi_bus is None:
        _spi_bus = busio.SPI(config.SPI_SCK, MOSI=config.SPI_MOSI, MISO=config.SPI_MISO)
    return _spi_bus
