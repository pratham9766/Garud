"""Run all hardware validation checks."""

from __future__ import annotations

from config import AppConfig
from tests import test_bmp388, test_bno085, test_camera, test_servo
from utils.helpers import list_spi_devices
from utils.logger import ToolkitLogger


def run(logger: ToolkitLogger, config: AppConfig) -> bool:
    """Run the full validation sequence and print a summary."""
    results: dict[str, bool] = {}

    spi_devices = list_spi_devices()
    if spi_devices:
        logger.success("SPI devices: " + ", ".join(str(item) for item in spi_devices))
        results["SPI"] = True
    else:
        logger.error("No SPI devices found. Enable SPI with raspi-config and reboot.")
        results["SPI"] = False

    results["Camera"] = test_camera.quick_check(logger, config)
    results["Servo"] = test_servo.quick_check(logger, config)
    results["BNO085"] = test_bno085.quick_check(logger, config)
    results["BMP388"] = test_bmp388.quick_check(logger, config)

    print("\nSummary")
    for name, passed in results.items():
        print(f"{name:.<14} {'PASS' if passed else 'FAIL'}")
    overall = all(results.values())
    print(f"{'Overall':.<14} {'SUCCESS' if overall else 'FAIL'}")
    return overall
