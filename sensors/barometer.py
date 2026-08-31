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
from sensors.calibration import barometer_sea_level_pressure, load_calibration

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
    """BMP388 barometer on Garud HAT SPI0 CS GPIO8."""

    def __init__(self) -> None:
        import bus_manager
        from sensors.bmp388_sensor import BMP388Sensor

        self._sensor = BMP388Sensor(bus_manager.get_spi())
        sea_level_pressure = barometer_sea_level_pressure(load_calibration())
        if sea_level_pressure is not None:
            self._sensor.set_sea_level_pressure(sea_level_pressure)
        logger.info("BMP388 initialized on SPI0 CS/GPIO%d.", config.BMP388_CS_PIN)

    def read(self) -> dict:
        reading = self._sensor.read()
        return {
            "altitude": reading["altitude_m"],
            "pressure": reading["pressure_hpa"],
            "temperature": reading["temperature_c"],
        }

    def close(self) -> None:
        pass


def create_barometer() -> BaseBarometer:
    if config.USE_MOCK_HARDWARE:
        return MockBarometer()
    return RealBarometer()


def barometer_worker(shared: SharedData, stop_event: threading.Event) -> None:
    """Background thread: poll barometer and update shared data."""
    try:
        baro = create_barometer()
    except Exception as exc:
        logger.error("Barometer init error: %s", exc)
        shared.update(barometer_ok=False, status="BARO_INIT_ERROR")
        return
    logger.info("Barometer worker started (mock=%s).", config.USE_MOCK_HARDWARE)

    try:
        while not stop_event.is_set():
            try:
                reading = baro.read()
                shared.update(
                    baro_altitude=reading["altitude"],
                    raw_baro_pressure_hpa=reading.get("pressure", 0.0),
                    raw_baro_temperature_c=reading.get("temperature", 0.0),
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
