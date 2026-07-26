"""BMP388 pressure sensor tests."""

from __future__ import annotations

import time

from config import AppConfig
from hardware.bmp388 import BMP388Reading, BMP388Sensor
from utils.helpers import HardwareError
from utils.logger import ToolkitLogger


def _format_reading(reading: BMP388Reading) -> str:
    return (
        f"Temperature: {reading.temperature_c:.2f} C\n"
        f"Pressure:    {reading.pressure_hpa:.2f} hPa\n"
        f"Altitude:    {reading.altitude_m:.2f} m"
    )


def run(logger: ToolkitLogger, config: AppConfig) -> bool:
    """Continuously print BMP388 readings at the configured refresh rate."""
    sensor = BMP388Sensor(config.bmp388)
    interval = 1 / config.bmp388.refresh_hz
    try:
        logger.info("BMP388 stream running. Press CTRL+C to stop.")
        while True:
            print("\033[2J\033[H", end="")
            print(_format_reading(sensor.read()))
            time.sleep(interval)
    except KeyboardInterrupt:
        logger.info("BMP388 stream stopped")
        return True
    except HardwareError as exc:
        logger.error(str(exc))
        return False
    finally:
        sensor.close()


def quick_check(logger: ToolkitLogger, config: AppConfig) -> bool:
    """Read one BMP388 sample."""
    sensor = BMP388Sensor(config.bmp388)
    try:
        reading = sensor.read()
        logger.success(
            f"BMP388 read OK: {reading.temperature_c:.2f} C, {reading.pressure_hpa:.2f} hPa"
        )
        return True
    except HardwareError as exc:
        logger.error(str(exc))
        return False
    finally:
        sensor.close()
