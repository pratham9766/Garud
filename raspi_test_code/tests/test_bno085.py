"""BNO085 SPI IMU tests."""

from __future__ import annotations

import time

from config import AppConfig
from hardware.bno085 import BNO085Reading, BNO085Sensor
from utils.helpers import HardwareError
from utils.logger import ToolkitLogger


def _format_reading(reading: BNO085Reading) -> str:
    return (
        f"Acceleration: {reading.acceleration}\n"
        f"Gyroscope:    {reading.gyroscope}\n"
        f"Magnetometer: {reading.magnetometer}\n"
        f"Quaternion:   {reading.quaternion}\n"
        f"Calibration:  {reading.calibration_status}"
    )


def run(logger: ToolkitLogger, config: AppConfig) -> bool:
    """Continuously print BNO085 readings at the configured refresh rate."""
    sensor = BNO085Sensor(config.bno085)
    interval = 1 / config.bno085.refresh_hz
    try:
        logger.info("BNO085 SPI stream running. Press CTRL+C to stop.")
        while True:
            print("\033[2J\033[H", end="")
            print(_format_reading(sensor.read()))
            time.sleep(interval)
    except KeyboardInterrupt:
        logger.info("BNO085 stream stopped")
        return True
    except HardwareError as exc:
        logger.error(str(exc))
        return False
    finally:
        sensor.close()


def quick_check(logger: ToolkitLogger, config: AppConfig) -> bool:
    """Read one BNO085 sample."""
    sensor = BNO085Sensor(config.bno085)
    try:
        reading = sensor.read()
        logger.success(
            f"BNO085 read OK: Quaternion={reading.quaternion}, "
            f"Calibration={reading.calibration_status}"
        )
        return True
    except HardwareError as exc:
        logger.error(str(exc))
        return False
    finally:
        sensor.close()
