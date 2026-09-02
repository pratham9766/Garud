"""Colored console and file logger for GARUD GNC.

Ported from TARSR/GARUD raspi_test_code/utils/logger.py with additions:
  - SUCCESS level (green) for PASS/OK events
  - Daily rotating log files (YYYYMMDD.log) in logs/
  - Used by both flight_computer.py and hardware test scripts
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path

from gnc.utils.colors import Color


SUCCESS_LEVEL = 25
logging.addLevelName(SUCCESS_LEVEL, "SUCCESS")


class _ColoredFormatter(logging.Formatter):
    COLORS = {
        "INFO":    Color.INFO,
        "WARNING": Color.WARNING,
        "ERROR":   Color.ERROR,
        "SUCCESS": Color.SUCCESS,
    }

    def format(self, record: logging.LogRecord) -> str:
        message = super().format(record)
        color = self.COLORS.get(record.levelname, "")
        return f"{color}{message}{Color.RESET}" if color else message


class GARUDLogger:
    """
    Thin wrapper around logging.Logger with a SUCCESS level.

    Usage:
        log = GARUDLogger(name="FlightComputer", save_logs=True)
        log.info("System armed")
        log.success("BNO085 calibrated")
        log.warning("GPS stale -- using last fix")
        log.error("RL inference timeout -- PID fallback engaged")
    """

    def __init__(
        self,
        name: str = "garud",
        save_logs: bool = True,
        log_dir: Path | None = None,
        level: str = "INFO",
    ) -> None:
        self._logger = logging.getLogger(name)
        self._logger.handlers.clear()
        self._logger.setLevel(getattr(logging, level.upper(), logging.INFO))
        self._logger.propagate = False

        # Console handler — colored output
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(
            _ColoredFormatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S")
        )
        self._logger.addHandler(console_handler)

        # File handler — daily rotating log file
        if save_logs:
            directory = log_dir or Path("logs")
            directory.mkdir(parents=True, exist_ok=True)
            log_filename = directory / f"{datetime.now():%Y%m%d_%H%M%S}_{name}.log"
            file_handler = logging.FileHandler(log_filename, encoding="utf-8")
            file_handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s [%(levelname)s] %(message)s",
                    "%Y-%m-%d %H:%M:%S",
                )
            )
            self._logger.addHandler(file_handler)

    def info(self, message: str) -> None:
        self._logger.info(message)

    def warning(self, message: str) -> None:
        self._logger.warning(message)

    def error(self, message: str) -> None:
        self._logger.error(message)

    def success(self, message: str) -> None:
        self._logger.log(SUCCESS_LEVEL, message)

    def exception(self, message: str) -> None:
        self._logger.exception(message)


def build_logger(
    name: str = "garud",
    save_logs: bool = True,
    log_dir: Path | None = None,
    level: str = "INFO",
) -> GARUDLogger:
    """Build the application logger."""
    return GARUDLogger(name=name, save_logs=save_logs, log_dir=log_dir, level=level)
