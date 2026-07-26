"""Shared helper functions for diagnostics and hardware probing."""

from __future__ import annotations

import platform
import shutil
import socket
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path


class HardwareError(RuntimeError):
    """Raised for expected hardware initialization or communication failures."""


@dataclass(frozen=True)
class SystemInfo:
    hostname: str
    os_version: str
    python_version: str
    cpu_temperature_c: float | None
    ram_usage: str
    disk_usage: str
    ip_address: str


def ensure_directory(path: Path) -> Path:
    """Create a directory if needed and return the path."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def timestamp_slug() -> str:
    """Return a filesystem-friendly timestamp."""
    from datetime import datetime

    return datetime.now().strftime("%Y%m%d_%H%M%S")


def scan_i2c_bus() -> list[int]:
    """Scan the primary Raspberry Pi I2C bus using Blinka/busio."""
    try:
        import board
        import busio
    except ImportError as exc:
        raise HardwareError("I2C libraries not installed. Install adafruit-blinka.") from exc

    try:
        i2c = busio.I2C(board.SCL, board.SDA)
        while not i2c.try_lock():
            time.sleep(0.01)
        try:
            return list(i2c.scan())
        finally:
            i2c.unlock()
    except Exception as exc:
        raise HardwareError(f"Unable to scan I2C bus: {exc}") from exc


def read_cpu_temperature() -> float | None:
    """Read CPU temperature from Linux thermal sysfs."""
    temp_file = Path("/sys/class/thermal/thermal_zone0/temp")
    try:
        return int(temp_file.read_text(encoding="utf-8").strip()) / 1000
    except (FileNotFoundError, ValueError, OSError):
        return None


def _read_mem_usage() -> str:
    try:
        values: dict[str, int] = {}
        for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            key, raw_value = line.split(":", 1)
            values[key] = int(raw_value.strip().split()[0])
        total = values["MemTotal"]
        available = values["MemAvailable"]
        used = total - available
        return f"{used / 1024:.0f} MB / {total / 1024:.0f} MB"
    except (FileNotFoundError, KeyError, ValueError, OSError):
        return "Unavailable"


def get_ip_address() -> str:
    """Return the primary outbound IP address without requiring internet traffic."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        return "Unavailable"
    finally:
        sock.close()


def get_system_info() -> SystemInfo:
    """Collect basic system diagnostics."""
    usage = shutil.disk_usage("/")
    return SystemInfo(
        hostname=socket.gethostname(),
        os_version=platform.platform(),
        python_version=platform.python_version(),
        cpu_temperature_c=read_cpu_temperature(),
        ram_usage=_read_mem_usage(),
        disk_usage=f"{usage.used / (1024**3):.1f} GB / {usage.total / (1024**3):.1f} GB",
        ip_address=get_ip_address(),
    )


def command_exists(command: str) -> bool:
    """Return True if a command is available on PATH."""
    return shutil.which(command) is not None


def run_command(command: list[str]) -> tuple[int, str]:
    """Run a short diagnostic command and capture stdout/stderr."""
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    output = (result.stdout + result.stderr).strip()
    return result.returncode, output
