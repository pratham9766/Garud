"""Colored console and optional file logger."""

from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path

from utils.colors import Color


SUCCESS_LEVEL = 25
logging.addLevelName(SUCCESS_LEVEL, "SUCCESS")


class _ColoredFormatter(logging.Formatter):
    COLORS = {
        "INFO": Color.INFO,
        "WARNING": Color.WARNING,
        "ERROR": Color.ERROR,
        "SUCCESS": Color.SUCCESS,
    }

    def format(self, record: logging.LogRecord) -> str:
        message = super().format(record)
        color = self.COLORS.get(record.levelname, "")
        return f"{color}{message}{Color.RESET}" if color else message


class ToolkitLogger:
    """Thin wrapper around logging.Logger with a SUCCESS level."""

    def __init__(
        self,
        name: str = "raspi_hardware_test",
        save_logs: bool = True,
        log_dir: Path | None = None,
        level: str = "INFO",
    ) -> None:
        self._logger = logging.getLogger(name)
        self._logger.handlers.clear()
        self._logger.setLevel(getattr(logging, level.upper(), logging.INFO))
        self._logger.propagate = False

        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(
            _ColoredFormatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S")
        )
        self._logger.addHandler(console_handler)

        if save_logs:
            directory = log_dir or Path("logs")
            directory.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(
                directory / f"{datetime.now():%Y%m%d}.log", encoding="utf-8"
            )
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


def build_logger(save_logs: bool, log_dir: Path, level: str) -> ToolkitLogger:
    """Build the application logger from configuration values."""
    return ToolkitLogger(save_logs=save_logs, log_dir=log_dir, level=level)
