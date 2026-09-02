"""Shared hardware and system diagnostics for GARUD GNC.

Ported from TARSR/GARUD raspi_test_code/utils/helpers.py.

Provides:
  HardwareError    -- raised when a sensor fails to init or read
  scan_i2c_bus()   -- list I2C addresses found on the bus
  list_spi_devices() -- list /dev/spidev* nodes
  read_cpu_temperature() -- CPU temp in Celsius
  get_system_info()  -- hostname, OS, Python, RAM, disk, IP
"""

from __future__ import annotations

import platform
import shutil
import socket
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path


# ---------------------------------------------------------------------------
# Exception
# ---------------------------------------------------------------------------

class HardwareError(RuntimeError):
    """Raised for expected hardware initialisation or communication failures.

    Callers (test scripts, flight computer startup) catch this explicitly
    and decide whether to abort, retry, or log and continue.
    """


# ---------------------------------------------------------------------------
# System diagnostics
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SystemInfo:
    hostname:          str
    os_version:        str
    python_version:    str
    cpu_temperature_c: float | None
    ram_usage:         str
    disk_usage:        str
    ip_address:        str


def read_cpu_temperature() -> float | None:
    """Read CPU temperature from Linux thermal sysfs (Raspberry Pi)."""
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
        total     = values["MemTotal"]
        available = values["MemAvailable"]
        used      = total - available
        return f"{used / 1024:.0f} MB / {total / 1024:.0f} MB"
    except (FileNotFoundError, KeyError, ValueError, OSError):
        return "Unavailable"


def get_ip_address() -> str:
    """Return the primary outbound IP address."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        return "Unavailable"
    finally:
        sock.close()


def get_system_info() -> SystemInfo:
    """Collect basic system diagnostics — useful for pre-flight log header."""
    usage = shutil.disk_usage("/")
    return SystemInfo(
        hostname          = socket.gethostname(),
        os_version        = platform.platform(),
        python_version    = platform.python_version(),
        cpu_temperature_c = read_cpu_temperature(),
        ram_usage         = _read_mem_usage(),
        disk_usage        = f"{usage.used / (1024**3):.1f} GB / {usage.total / (1024**3):.1f} GB",
        ip_address        = get_ip_address(),
    )


# ---------------------------------------------------------------------------
# Bus discovery
# ---------------------------------------------------------------------------

def scan_i2c_bus() -> list[int]:
    """Scan the primary I2C bus and return a list of found addresses.

    Expected on GARUD HAT:
      0x40 -- PCA9685 (servo driver)
      0x41 -- INA219  (power monitor)
    """
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


def list_spi_devices() -> list[Path]:
    """Return available Linux SPI device nodes (/dev/spidev*)."""
    return sorted(Path("/dev").glob("spidev*"))


# ---------------------------------------------------------------------------
# Miscellaneous
# ---------------------------------------------------------------------------

def ensure_directory(path: Path) -> Path:
    """Create a directory if it does not exist and return the path."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def timestamp_slug() -> str:
    """Return a filesystem-friendly UTC timestamp string."""
    from datetime import datetime
    return datetime.utcnow().strftime("%Y%m%d_%H%M%S")


def run_shell(command: list[str]) -> tuple[int, str]:
    """Run a short diagnostic shell command and capture stdout + stderr."""
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    output = (result.stdout + result.stderr).strip()
    return result.returncode, output
