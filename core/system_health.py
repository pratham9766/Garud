"""Lightweight Raspberry Pi/system health collection for verification dashboards."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import threading
import time
from pathlib import Path

import config
from core.shared_data import SharedData


def _cpu_temperature_c() -> float | None:
    thermal = Path("/sys/class/thermal/thermal_zone0/temp")
    try:
        if thermal.exists():
            return float(thermal.read_text(encoding="utf-8").strip()) / 1000.0
    except Exception:
        return None
    return None


def _throttle_status() -> str:
    try:
        proc = subprocess.run(
            ["vcgencmd", "get_throttled"],
            capture_output=True,
            text=True,
            timeout=2.0,
            check=False,
        )
    except Exception:
        return "UNAVAILABLE"
    return (proc.stdout or proc.stderr).strip() or "UNAVAILABLE"


def _memory() -> tuple[int | None, int | None]:
    try:
        import psutil  # type: ignore
    except Exception:
        return None, None
    mem = psutil.virtual_memory()
    return int(mem.used), int(mem.total)


def _cpu_percent() -> float | None:
    try:
        import psutil  # type: ignore
    except Exception:
        return None
    return float(psutil.cpu_percent(interval=None))


def _uptime_s() -> float | None:
    try:
        import psutil  # type: ignore
    except Exception:
        return None
    return float(time.time() - psutil.boot_time())


def system_health_worker(shared: SharedData, stop_event: threading.Event) -> None:
    """Publish low-rate CPU, memory, disk, and Raspberry Pi throttle diagnostics."""
    expected_hz = 0.5
    while not stop_event.is_set():
        try:
            disk = shutil.disk_usage(config.PROJECT_ROOT)
            load = os.getloadavg() if hasattr(os, "getloadavg") else None
            mem_used, mem_total = _memory()
            cpu_temp = _cpu_temperature_c()
            cpu_percent = _cpu_percent()
            if config.USE_MOCK_HARDWARE and shared.is_fault_active("high_cpu_temperature"):
                cpu_temp = config.CPU_TEMP_WARN_C + 8.0
                cpu_percent = 96.0
            details = {
                "platform": platform.platform(),
                "cpu_percent": cpu_percent,
                "cpu_temperature_c": cpu_temp,
                "ram_used_bytes": mem_used,
                "ram_total_bytes": mem_total,
                "disk_free_bytes": int(disk.free),
                "disk_total_bytes": int(disk.total),
                "uptime_s": _uptime_s(),
                "load_average": load,
                "throttle_status": _throttle_status(),
            }
            reason = "System metrics sampled."
            if cpu_temp is not None and cpu_temp >= config.CPU_TEMP_WARN_C:
                reason = f"CPU temperature {cpu_temp:.1f}C above warning threshold."
                shared.record_event("SYSTEM_TEMP_HIGH", "System", "WARN", reason, details)
            if disk.free < config.DISK_FREE_WARN_BYTES:
                reason = "Disk free space below warning threshold."
                shared.record_event("DISK_SPACE_LOW", "System", "WARN", reason, details)
            shared.record_worker_success(
                "System",
                expected_hz=expected_hz,
                reason=reason,
                details=details,
            )
        except Exception as exc:
            shared.record_worker_error("System", exc, expected_hz=expected_hz)
        stop_event.wait(2.0)
