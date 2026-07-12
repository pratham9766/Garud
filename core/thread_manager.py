"""
Manages background worker threads for payload subsystems.
"""

from __future__ import annotations

import logging
import threading
from typing import Callable

logger = logging.getLogger(__name__)


class ManagedThread:
    """Wraps a daemon thread with a stop event."""

    def __init__(self, name: str, target: Callable[[threading.Event], None]) -> None:
        self.name = name
        self._target = target
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Start the worker thread."""
        if self._thread and self._thread.is_alive():
            logger.warning("Thread '%s' is already running.", self.name)
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._target,
            args=(self._stop_event,),
            name=self.name,
            daemon=True,
        )
        self._thread.start()
        logger.info("Started thread: %s", self.name)

    def stop(self, timeout: float = 5.0) -> None:
        """Signal the thread to stop and wait for it to finish."""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)
            if self._thread.is_alive():
                logger.warning("Thread '%s' did not stop within %.1fs.", self.name, timeout)
            else:
                logger.info("Stopped thread: %s", self.name)

    @property
    def is_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()


class ThreadManager:
    """Registry of all managed payload threads."""

    def __init__(self) -> None:
        self._threads: list[ManagedThread] = []

    def register(self, managed: ManagedThread) -> ManagedThread:
        self._threads.append(managed)
        return managed

    def start_all(self) -> None:
        for t in self._threads:
            t.start()

    def stop_all(self, timeout: float = 5.0) -> None:
        for t in reversed(self._threads):
            t.stop(timeout=timeout)
