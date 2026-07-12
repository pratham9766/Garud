"""
XBee telemetry sender — mock prints to console, real sends via serial.
"""

from __future__ import annotations

import logging
import threading
from abc import ABC, abstractmethod

import config
from core.shared_data import SharedData
from telemetry.telemetry_packet import build_telemetry_packet

logger = logging.getLogger(__name__)


class BaseTelemetry(ABC):
    @abstractmethod
    def send(self, packet: str) -> bool:
        """Send a telemetry packet. Return True on success."""

    @abstractmethod
    def close(self) -> None:
        pass


class MockTelemetry(BaseTelemetry):
    """Prints telemetry packets to console instead of XBee radio."""

    def send(self, packet: str) -> bool:
        print(f"[TELEMETRY] {packet}")
        return True

    def close(self) -> None:
        logger.info("MockTelemetry closed.")


class RealTelemetry(BaseTelemetry):
    """Placeholder for XBee serial transmission."""

    def __init__(self) -> None:
        self._serial = None
        logger.warning(
            "RealTelemetry is a stub — connect %s @ %d when XBee is ready.",
            config.XBEE_PORT,
            config.XBEE_BAUDRATE,
        )

    def send(self, packet: str) -> bool:
        logger.info("RealTelemetry stub would send: %s", packet)
        return False

    def close(self) -> None:
        if self._serial:
            self._serial.close()


def create_telemetry() -> BaseTelemetry:
    if config.USE_MOCK_HARDWARE:
        return MockTelemetry()
    return RealTelemetry()


def telemetry_worker(shared: SharedData, stop_event: threading.Event) -> None:
    """Background thread: send telemetry at TELEMETRY_INTERVAL_SEC."""
    radio = create_telemetry()
    logger.info("Telemetry worker started (mock=%s).", config.USE_MOCK_HARDWARE)

    try:
        while not stop_event.is_set():
            try:
                snap = shared.get_snapshot()
                packet = build_telemetry_packet(snap)
                ok = radio.send(packet)
                shared.update(telemetry_ok=ok)
            except Exception as exc:
                logger.error("Telemetry send error: %s", exc)
                shared.update(telemetry_ok=False, status="TELEM_ERROR")

            stop_event.wait(config.TELEMETRY_INTERVAL_SEC)
    finally:
        radio.close()
        logger.info("Telemetry worker stopped.")
