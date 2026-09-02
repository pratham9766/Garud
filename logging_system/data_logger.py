"""
Continuous CSV data logger.

Header:
timestamp,mission_time,state,latitude,longitude,gps_altitude,baro_altitude,
roll,pitch,yaw,image_name,battery,status
"""

from __future__ import annotations

import logging
import shutil
import threading
import time
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
        self.rows_written = 0
        self.write_errors = 0
        self.last_write_timestamp = 0.0

    def open(self) -> None:
        """Open log file and write CSV header."""
        requested_path = self.log_path
        for attempt in range(3):
            try:
                self._file = open(self.log_path, "w", encoding="utf-8")
                self._file.write(SharedData.CSV_HEADER + "\n")
                self._file.flush()
                break
            except PermissionError:
                if self._file is not None:
                    try:
                        self._file.close()
                    except OSError:
                        pass
                    self._file = None
                if attempt == 2:
                    raise
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                suffix = "" if attempt == 0 else f"_{attempt + 1}"
                fallback_name = (
                    f"{requested_path.stem}_{timestamp}{suffix}{requested_path.suffix}"
                )
                fallback_path = requested_path.with_name(fallback_name)
                logger.warning(
                    "Log file %s is locked or not writable; using %s instead.",
                    self.log_path,
                    fallback_path,
                )
                self.log_path = fallback_path
        if self._file is None:
            raise RuntimeError("Logger did not open a file.")
        logger.info("Data logger opened: %s", self.log_path)

    def write_row(self) -> None:
        """Append one CSV row from current shared data."""
        if self._file is None:
            raise RuntimeError("Logger not open — call open() first.")
        row = self.shared.to_csv_row()
        with self._lock:
            self._file.write(row + "\n")
            self._file.flush()
            self.rows_written += 1
            self.last_write_timestamp = time.time()
        self.shared.update(
            logger_rows_written=self.rows_written,
            logger_last_write_timestamp=self.last_write_timestamp,
        )

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
                if config.USE_MOCK_HARDWARE and shared.is_fault_active("logger_write_failure"):
                    raise OSError("Mock logger write failure injected.")
                data_logger.write_row()
                file_size = data_logger.path.stat().st_size if data_logger.path.exists() else 0
                disk = shutil.disk_usage(data_logger.path.parent)
                shared.record_worker_success(
                    "DataLogger",
                    expected_hz=config.LOGGER_EXPECTED_HZ,
                    reason="CSV row written and flushed.",
                    details={
                        "active_log_file": str(data_logger.path),
                        "rows_written": data_logger.rows_written,
                        "file_size_bytes": file_size,
                        "disk_free_bytes": disk.free,
                    },
                )
            except Exception as exc:
                data_logger.write_errors += 1
                shared.update(logger_errors=data_logger.write_errors)
                logger.error("CSV write error: %s", exc)
                shared.record_worker_error("DataLogger", exc, expected_hz=config.LOGGER_EXPECTED_HZ)

            stop_event.wait(config.SENSOR_LOG_INTERVAL_SEC)
    finally:
        logger.info("Logger worker stopped.")
