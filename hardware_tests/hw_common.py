"""
Shared helpers for hardware test scripts.

Each test imports this module for paths, logging, and PASS/FAIL output.
"""

from __future__ import annotations

import platform
import sys
from datetime import datetime
from pathlib import Path

# Project root = parent of hardware_tests/
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config  # noqa: E402

HW_LOG_DIR = config.LOG_SAVE_PATH / "hardware_tests"
HW_IMAGE_DIR = config.IMAGE_SAVE_PATH / "hardware_tests"


def ensure_dirs() -> None:
    """Create hardware test log and image folders."""
    HW_LOG_DIR.mkdir(parents=True, exist_ok=True)
    HW_IMAGE_DIR.mkdir(parents=True, exist_ok=True)


def is_raspberry_pi() -> bool:
    """Return True if running on a Raspberry Pi (Linux arm/arm64)."""
    try:
        with open("/proc/cpuinfo", "r", encoding="utf-8") as f:
            return "Raspberry Pi" in f.read()
    except (OSError, FileNotFoundError):
        machine = platform.machine().lower()
        return sys.platform.startswith("linux") and machine in ("armv7l", "aarch64", "arm64")


def banner(title: str) -> None:
    print("=" * 60)
    print(title)
    print("=" * 60)


def result(status: str, message: str) -> None:
    """Print a coloured-style status line (PASS / FAIL / WARNING)."""
    print(f"[{status}] {message}")


def write_log(filename: str, lines: list[str]) -> Path:
    """Append timestamped lines to a hardware test log file."""
    ensure_dirs()
    path = HW_LOG_DIR / filename
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"\n--- {timestamp} ---\n")
        for line in lines:
            f.write(line + "\n")
    return path
