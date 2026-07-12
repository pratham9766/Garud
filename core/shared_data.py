"""
Thread-safe shared data store for all payload subsystems.

Every sensor thread writes here; logger, telemetry, and mapping read from here.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, fields
from typing import Any

from core.mission_state import MissionState


@dataclass
class PayloadSnapshot:
    """Point-in-time copy of all shared payload fields."""

    timestamp: float = 0.0
    mission_time: float = 0.0
    state: str = MissionState.BOOT.value
    latitude: float = 0.0
    longitude: float = 0.0
    gps_altitude: float = 0.0
    baro_altitude: float = 0.0
    roll: float = 0.0
    pitch: float = 0.0
    yaw: float = 0.0
    image_name: str = ""
    battery: float = 100.0
    status: str = "OK"
    camera_ok: bool = False
    gps_ok: bool = False
    imu_ok: bool = False
    barometer_ok: bool = False
    telemetry_ok: bool = False


class SharedData:
    """Thread-safe container for live mission data."""

    CSV_HEADER = (
        "timestamp,mission_time,state,latitude,longitude,gps_altitude,"
        "baro_altitude,roll,pitch,yaw,image_name,battery,status"
    )

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._data = PayloadSnapshot()
        self._mission_start: float | None = None

    def start_mission_clock(self) -> None:
        """Reset and start the mission elapsed-time clock."""
        with self._lock:
            self._mission_start = time.time()

    def get_mission_time(self) -> float:
        """Seconds elapsed since mission clock started."""
        with self._lock:
            if self._mission_start is None:
                return 0.0
            return time.time() - self._mission_start

    def update(self, **kwargs: Any) -> None:
        """Update one or more fields atomically."""
        with self._lock:
            for key, value in kwargs.items():
                if hasattr(self._data, key):
                    setattr(self._data, key, value)
                else:
                    raise AttributeError(f"Unknown shared field: {key}")
            self._data.timestamp = time.time()
            if self._mission_start is not None:
                self._data.mission_time = time.time() - self._mission_start

    def get_snapshot(self) -> PayloadSnapshot:
        """Return a copy of the current data (safe to use outside the lock)."""
        with self._lock:
            return PayloadSnapshot(**{
                f.name: getattr(self._data, f.name) for f in fields(self._data)
            })

    def to_csv_row(self) -> str:
        """Format current data as a CSV row matching CSV_HEADER."""
        snap = self.get_snapshot()
        return (
            f"{snap.timestamp:.3f},{snap.mission_time:.3f},{snap.state},"
            f"{snap.latitude:.6f},{snap.longitude:.6f},"
            f"{snap.gps_altitude:.2f},{snap.baro_altitude:.2f},"
            f"{snap.roll:.2f},{snap.pitch:.2f},{snap.yaw:.2f},"
            f"{snap.image_name},{snap.battery:.1f},{snap.status}"
        )
