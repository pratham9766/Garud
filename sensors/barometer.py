"""
Barometer module — mock and real-hardware placeholder.

Mock simulates descent from ~700 m to ground level.
"""

from __future__ import annotations

import logging
import random
import threading
import time
from abc import ABC, abstractmethod

import config
from core.mission_state import MissionState
from core.shared_data import SharedData

logger = logging.getLogger(__name__)


class BaseBarometer(ABC):
    @abstractmethod
    def read(self) -> dict:
        """Return dict with altitude (metres) and pressure (hPa, optional)."""

    @abstractmethod
    def close(self) -> None:
        pass


class MockBarometer(BaseBarometer):
    """Simulated barometric altitude decreasing during descent."""

    def __init__(self) -> None:
        self._altitude = config.MOCK_START_ALTITUDE_M
        self._descent_rate = config.MOCK_START_ALTITUDE_M / max(
            config.SIMULATION_DURATION_SEC, 1.0
        )

    def read(self) -> dict:
        # Decrease altitude each read; add small noise
        self._altitude = max(
            0.0,
            self._altitude - self._descent_rate * 0.5 + random.uniform(-0.3, 0.3),
        )
        pressure = 1013.25 * (1.0 - self._altitude / 44330.0) ** 5.255
        return {"altitude": self._altitude, "pressure": pressure}

    def close(self) -> None:
        logger.debug("MockBarometer closed.")


class RealBarometer(BaseBarometer):
    """BMP388 barometer on Garud HAT SPI0 CE0."""

    def __init__(self) -> None:
        import bus_manager
        import digitalio
        from adafruit_bmp3xx import BMP3XX_SPI

        cs = digitalio.DigitalInOut(config.BMP388_CS)
        self._bmp = BMP3XX_SPI(bus_manager.get_spi(), cs)
        self._bmp.sea_level_pressure = 1013.25
        self._bmp.pressure_oversampling = 8
        self._bmp.temperature_oversampling = 2
        self._bmp.filter_coefficient = 2
        logger.info("BMP388 initialized on SPI0 CE0/GPIO%d.", config.BMP388_CS_PIN)

    def read(self) -> dict:
        return {
            "altitude": self._bmp.altitude,
            "pressure": self._bmp.pressure,
            "temperature": self._bmp.temperature,
        }

    def close(self) -> None:
        pass


def create_barometer() -> BaseBarometer:
    if config.USE_MOCK_HARDWARE:
        return MockBarometer()
    return RealBarometer()


def barometer_worker(shared: SharedData, stop_event: threading.Event) -> None:
    """Background thread: poll barometer and update shared data."""
    baro = create_barometer()
    logger.info("Barometer worker started (mock=%s).", config.USE_MOCK_HARDWARE)

    try:
        while not stop_event.is_set():
            try:
                reading = baro.read()
                shared.update(
                    baro_altitude=reading["altitude"],
                    barometer_ok=True,
                )
            except Exception as exc:
                logger.error("Barometer read error: %s", exc)
                shared.update(barometer_ok=False, status="BARO_ERROR")

            stop_event.wait(0.5)
    finally:
        baro.close()
        logger.info("Barometer worker stopped.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sd = SharedData()
    evt = threading.Event()
    t = threading.Thread(target=barometer_worker, args=(sd, evt), daemon=True)
    t.start()
    for _ in range(10):
        time.sleep(0.5)
        snap = sd.get_snapshot()
        print(f"baro_alt={snap.baro_altitude:.1f} m")
    evt.set()
    t.join()
