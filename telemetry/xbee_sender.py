"""
XBee telemetry sender — mock prints to console, real sends via serial.
"""

from __future__ import annotations

import logging
import threading
import time
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
    """XBee serial telemetry over Pi primary UART GPIO14/GPIO15."""

    def __init__(self) -> None:
        import serial

        self._serial = serial.Serial(
            config.XBEE_SERIAL_PORT,
            baudrate=config.XBEE_BAUDRATE,
            timeout=1.0,
            write_timeout=1.0,
        )
        logger.info(
            "XBee telemetry opened on %s @ %d.",
            config.XBEE_SERIAL_PORT,
            config.XBEE_BAUDRATE,
        )

    def send(self, packet: str) -> bool:
        if not self._serial or not self._serial.is_open:
            return False
        self._serial.write(packet.encode("utf-8") + b"\n")
        return True

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
                sequence = snap.telemetry_sequence + 1
                shared.update(telemetry_sequence=sequence)
                snap = shared.get_snapshot()
                packet = build_telemetry_packet(snap)
                ok = False if config.USE_MOCK_HARDWARE and shared.is_fault_active("telemetry_drop") else radio.send(packet)
                if config.USE_MOCK_HARDWARE and shared.is_fault_active("telemetry_drop"):
                    shared.record_event("TELEMETRY_LOSS", "Telemetry", "WARN", "Mock telemetry packet drop injected.", {"sequence": sequence})
                shared.update(
                    telemetry_ok=ok,
                    telemetry_tx_count=snap.telemetry_tx_count + (1 if ok else 0),
                    telemetry_last_tx_timestamp=time.time() if ok else snap.telemetry_last_tx_timestamp,
                )
                if ok:
                    shared.record_worker_success(
                        "Telemetry",
                        expected_hz=config.TELEMETRY_EXPECTED_HZ,
                        reason="Telemetry packet transmitted.",
                        details={
                            "sequence": sequence,
                            "tx_count": snap.telemetry_tx_count + 1,
                            "packet_bytes": len(packet.encode("utf-8")),
                            "rssi": None,
                            "snr": None,
                        },
                    )
                else:
                    shared.record_worker_error("Telemetry", "Radio send returned False.", expected_hz=config.TELEMETRY_EXPECTED_HZ)
            except Exception as exc:
                logger.error("Telemetry send error: %s", exc)
                shared.update(telemetry_ok=False, status="TELEM_ERROR")
                shared.record_worker_error("Telemetry", exc, expected_hz=config.TELEMETRY_EXPECTED_HZ)

            stop_event.wait(config.TELEMETRY_INTERVAL_SEC)
    finally:
        radio.close()
        logger.info("Telemetry worker stopped.")
