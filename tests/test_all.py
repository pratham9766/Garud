"""Run all hardware validation checks."""

from __future__ import annotations

from config import AppConfig
from tests import test_bmp388, test_bno055, test_camera, test_servo
from utils.helpers import HardwareError, scan_i2c_bus
from utils.logger import ToolkitLogger


def run(logger: ToolkitLogger, config: AppConfig) -> bool:
    """Run the full validation sequence and print a summary."""
    results: dict[str, bool] = {}

    try:
        devices = scan_i2c_bus()
        logger.success("I2C devices: " + ", ".join(f"0x{item:02X}" for item in devices))
        results["I2C"] = True
    except HardwareError as exc:
        logger.error(str(exc))
        results["I2C"] = False

    results["Camera"] = test_camera.quick_check(logger, config)
    results["Servo"] = test_servo.quick_check(logger, config)
    results["BNO055"] = test_bno055.quick_check(logger, config)
    results["BMP388"] = test_bmp388.quick_check(logger, config)

    print("\nSummary")
    for name, passed in results.items():
        print(f"{name:.<14} {'PASS' if passed else 'FAIL'}")
    overall = all(results.values())
    print(f"{'Overall':.<14} {'SUCCESS' if overall else 'FAIL'}")
    return overall
