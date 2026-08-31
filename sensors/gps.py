"""
GPS module — mock and real-hardware placeholder.

When USE_MOCK_HARDWARE is True, generates simulated coordinates near Pune.
Replace MockGPS with a real NMEA reader when hardware arrives.
"""

from __future__ import annotations

import logging
import math
import random
import threading
import time
from abc import ABC, abstractmethod

import config
from core.mission_state import MissionState
from core.shared_data import SharedData

logger = logging.getLogger(__name__)


class BaseGPS(ABC):
    """Abstract GPS interface."""

    @abstractmethod
    def read(self) -> dict:
        """Return dict with latitude, longitude, altitude, fix_ok."""

    @abstractmethod
    def close(self) -> None:
        """Release hardware resources."""


class MockGPS(BaseGPS):
    """Simulated GPS drifting around Pune reference coordinates."""

    def __init__(self) -> None:
        self._lat = config.MOCK_GPS_LAT
        self._lon = config.MOCK_GPS_LON
        self._alt = config.MOCK_START_ALTITUDE_M
        self._step = 0

    def read(self) -> dict:
        self._step += 1
        # Gentle drift simulating movement during descent
        angle = self._step * 0.05
        self._lat += 0.00001 * math.sin(angle) + random.uniform(-0.000005, 0.000005)
        self._lon += 0.00001 * math.cos(angle) + random.uniform(-0.000005, 0.000005)
        self._alt = max(0.0, self._alt - random.uniform(0.0, 0.5))
        return {
            "latitude": self._lat,
            "longitude": self._lon,
            "altitude": self._alt,
            "fix_ok": True,
        }

    def close(self) -> None:
        logger.debug("MockGPS closed.")


class RealGPS(BaseGPS):
    """NEO-M8N GPS through the Garud HAT SC16IS750 SPI UART bridge."""

    def __init__(self) -> None:
        import bus_manager
        from sensors.gps_m8n import GPSM8N

        self._gps = GPSM8N(bus_manager.get_spi())
        self._last = {
            "latitude": 0.0,
            "longitude": 0.0,
            "altitude": 0.0,
            "fix_ok": False,
        }
        logger.info(
            "GPS M8N initialized through SC16IS750 on SPI0 CE1/GPIO%d @ %d.",
            config.GPS_SC16IS750_CS_PIN,
            config.GPS_BAUDRATE,
        )

    def read(self) -> dict:
        fix = self._gps.read_fix(timeout_s=1.0)
        if not fix:
            return {**self._last, "fix_ok": False}

        if fix.get("lat") is not None:
            self._last["latitude"] = fix["lat"]
        if fix.get("lon") is not None:
            self._last["longitude"] = fix["lon"]
        if fix.get("altitude_m") is not None:
            self._last["altitude"] = fix["altitude_m"]
        self._last["fix_ok"] = bool(fix.get("fixed"))
        return dict(self._last)

    def close(self) -> None:
        pass


def create_gps() -> BaseGPS:
    """Factory: return mock or real GPS based on config."""
    if config.USE_MOCK_HARDWARE:
        return MockGPS()
    return RealGPS()


def gps_worker(shared: SharedData, stop_event: threading.Event) -> None:
    """
    Background thread: poll GPS and update shared data.

    Args:
        shared: Shared data store.
        stop_event: Shutdown signal.
    """
    try:
        gps = create_gps()
    except Exception as exc:
        logger.error("GPS init error: %s", exc)
        shared.update(gps_ok=False, status="GPS_INIT_ERROR")
        return
    logger.info("GPS worker started (mock=%s).", config.USE_MOCK_HARDWARE)

    try:
        while not stop_event.is_set():
            try:
                reading = gps.read()
                shared.update(
                    latitude=reading["latitude"],
                    longitude=reading["longitude"],
                    gps_altitude=reading["altitude"],
                    gps_ok=reading["fix_ok"],
                )
            except Exception as exc:
                logger.error("GPS read error: %s", exc)
                shared.update(gps_ok=False, status="GPS_ERROR")

            stop_event.wait(0.5)
    finally:
        gps.close()
        logger.info("GPS worker stopped.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sd = SharedData()
    evt = threading.Event()
    t = threading.Thread(target=gps_worker, args=(sd, evt), daemon=True)
    t.start()
    for _ in range(5):
        time.sleep(1)
        print(sd.get_snapshot())
    evt.set()
    t.join()
