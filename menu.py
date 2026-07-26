"""Interactive command-line menu for the hardware test toolkit."""

from __future__ import annotations

from config import AppConfig
from tests import test_all, test_bmp388, test_bno055, test_camera, test_servo
from utils.colors import Color
from utils.helpers import HardwareError, get_system_info, scan_i2c_bus
from utils.logger import ToolkitLogger


def _print_header() -> None:
    print(f"{Color.BOLD}{Color.MENU}")
    print("===========================")
    print(" Raspberry Pi Test Utility")
    print("===========================")
    print(Color.RESET, end="")


def _print_menu() -> None:
    print("1 Test Camera")
    print("2 Test Servo")
    print("3 Test BNO055")
    print("4 Test BMP388")
    print("5 Scan I2C Bus")
    print("6 Test Everything")
    print("7 Show System Info")
    print("0 Exit")


def show_system_info() -> None:
    """Print host diagnostics."""
    info = get_system_info()
    cpu_temp = (
        f"{info.cpu_temperature_c:.1f} C"
        if info.cpu_temperature_c is not None
        else "Unavailable"
    )
    print("\nSystem Info")
    print(f"Hostname:        {info.hostname}")
    print(f"OS Version:      {info.os_version}")
    print(f"Python Version:  {info.python_version}")
    print(f"CPU Temperature: {cpu_temp}")
    print(f"RAM Usage:       {info.ram_usage}")
    print(f"Disk Usage:      {info.disk_usage}")
    print(f"IP Address:      {info.ip_address}")


def scan_i2c(logger: ToolkitLogger) -> None:
    """Print detected I2C device addresses."""
    try:
        devices = scan_i2c_bus()
    except HardwareError as exc:
        logger.error(str(exc))
        return
    if devices:
        logger.success("I2C devices found: " + ", ".join(f"0x{item:02X}" for item in devices))
    else:
        logger.warning("No I2C devices found")


def run_menu(config: AppConfig, logger: ToolkitLogger) -> None:
    """Run the main interactive menu loop."""
    while True:
        _print_header()
        _print_menu()
        choice = input("Select: ").strip()

        if choice == "1":
            test_camera.run(logger, config)
        elif choice == "2":
            test_servo.run(logger, config)
        elif choice == "3":
            test_bno055.run(logger, config)
        elif choice == "4":
            test_bmp388.run(logger, config)
        elif choice == "5":
            scan_i2c(logger)
        elif choice == "6":
            test_all.run(logger, config)
        elif choice == "7":
            show_system_info()
        elif choice == "0":
            logger.info("Exiting Raspberry Pi Test Utility")
            break
        else:
            logger.warning("Invalid menu option")

        print()
