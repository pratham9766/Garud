"""BNO055 IMU tests."""

from __future__ import annotations

import time

from config import AppConfig
from hardware.bno055 import BNO055Reading, BNO055Sensor
from utils.helpers import HardwareError
from utils.logger import ToolkitLogger


def _format_reading(reading: BNO055Reading) -> str:
    return (
        f"Acceleration: {reading.acceleration}\n"
        f"Gyroscope:    {reading.gyroscope}\n"
        f"Magnetometer: {reading.magnetometer}\n"
        f"Euler:        {reading.euler}\n"
        f"Quaternion:   {reading.quaternion}\n"
        f"Calibration:  {reading.calibration_status}\n"
        f"Temperature:  {reading.temperature_c} C"
    )


def run(logger: ToolkitLogger, config: AppConfig) -> bool:
    """Continuously print BNO055 readings at the configured refresh rate."""
    sensor = BNO055Sensor(config.bno055)
    interval = 1 / config.bno055.refresh_hz
    try:
        logger.info("BNO055 stream running. Press CTRL+C to stop.")
        while True:
            print("\033[2J\033[H", end="")
            print(_format_reading(sensor.read()))
            time.sleep(interval)
    except KeyboardInterrupt:
        logger.info("BNO055 stream stopped")
        return True
    except HardwareError as exc:
        logger.error(str(exc))
        return False
    finally:
        sensor.close()


def quick_check(logger: ToolkitLogger, config: AppConfig) -> bool:
    """Read one BNO055 sample."""
    sensor = BNO055Sensor(config.bno055)
    try:
        reading = sensor.read()
        logger.success(f"BNO055 read OK: Euler={reading.euler}, Temp={reading.temperature_c} C")
        return True
    except HardwareError as exc:
        logger.error(str(exc))
        return False
    finally:
        sensor.close()
