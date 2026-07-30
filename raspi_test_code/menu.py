"""Interactive command-line menu for the hardware test toolkit."""

from __future__ import annotations

from config import AppConfig
from tests import test_all, test_bmp388, test_bno085, test_camera, test_servo
from utils.colors import Color
from utils.helpers import get_system_info, list_spi_devices
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
    print("3 Test BNO085")
    print("4 Test BMP388")
    print("5 Check SPI Devices")
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


def check_spi(logger: ToolkitLogger) -> None:
    """Print available Linux SPI device nodes."""
    devices = list_spi_devices()
    if devices:
        logger.success("SPI devices found: " + ", ".join(str(item) for item in devices))
    else:
        logger.warning("No SPI devices found. Enable SPI with raspi-config and reboot.")


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
            test_bno085.run(logger, config)
        elif choice == "4":
            test_bmp388.run(logger, config)
        elif choice == "5":
            check_spi(logger)
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
