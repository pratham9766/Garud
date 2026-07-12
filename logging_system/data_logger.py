"""
Continuous CSV data logger.

Header:
timestamp,mission_time,state,latitude,longitude,gps_altitude,baro_altitude,
roll,pitch,yaw,image_name,battery,status
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime
from pathlib import Path

import config
from core.shared_data import SharedData

logger = logging.getLogger(__name__)


class DataLogger:
    """Append-only CSV logger for payload telemetry."""

    def __init__(
        self,
        shared: SharedData,
        log_dir: Path | None = None,
        filename: str | None = None,
    ) -> None:
        self.shared = shared
        self.log_dir = log_dir or config.LOG_SAVE_PATH
        self.log_dir.mkdir(parents=True, exist_ok=True)

        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"flight_log_{timestamp}.csv"
        self.log_path = self.log_dir / filename
        self._file = None
        self._lock = threading.Lock()

    def open(self) -> None:
        """Open log file and write CSV header."""
        self._file = open(self.log_path, "w", encoding="utf-8")
        self._file.write(SharedData.CSV_HEADER + "\n")
        self._file.flush()
        logger.info("Data logger opened: %s", self.log_path)

    def write_row(self) -> None:
        """Append one CSV row from current shared data."""
        if self._file is None:
            raise RuntimeError("Logger not open — call open() first.")
        row = self.shared.to_csv_row()
        with self._lock:
            self._file.write(row + "\n")
            self._file.flush()

    def close(self) -> None:
        """Close the log file."""
        if self._file:
            self._file.close()
            self._file = None
            logger.info("Data logger closed: %s", self.log_path)

    @property
    def path(self) -> Path:
        return self.log_path


def logger_worker(
    shared: SharedData,
    data_logger: DataLogger,
    stop_event: threading.Event,
) -> None:
    """Background thread: write CSV rows at SENSOR_LOG_INTERVAL_SEC."""
    logger.info("Logger worker started — interval %.1fs.", config.SENSOR_LOG_INTERVAL_SEC)

    try:
        while not stop_event.is_set():
            try:
                data_logger.write_row()
            except Exception as exc:
                logger.error("CSV write error: %s", exc)

            stop_event.wait(config.SENSOR_LOG_INTERVAL_SEC)
    finally:
        logger.info("Logger worker stopped.")
