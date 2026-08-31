"""
Periodic health checks for payload subsystems.
"""

from __future__ import annotations

import logging
import threading
import time

import config
from core.shared_data import SharedData

logger = logging.getLogger(__name__)


def health_monitor_loop(
    shared: SharedData,
    stop_event: threading.Event,
    interval_sec: float = 5.0,
) -> None:
    """
    Background loop that logs subsystem health from shared data flags.

    Args:
        shared: Thread-safe shared data store.
        stop_event: Set to request shutdown.
        interval_sec: Seconds between health log messages.
    """
    logger.info("Health monitor started.")
    while not stop_event.is_set():
        snap = shared.get_snapshot()
        issues = []
        if config.ENABLE_GPS and not snap.gps_ok:
            issues.append("GPS")
        if config.ENABLE_IMU and not snap.imu_ok:
            issues.append("IMU")
        if config.ENABLE_BAROMETER and not snap.barometer_ok:
            issues.append("Barometer")
        if config.ENABLE_CAMERA and not snap.camera_ok:
            issues.append("Camera")
        if config.ENABLE_TELEMETRY and not snap.telemetry_ok:
            issues.append("Telemetry")

        if issues:
            logger.warning(
                "Health check [%s] — degraded: %s",
                snap.state,
                ", ".join(issues),
            )
        else:
            logger.info(
                "Health check [%s] — all subsystems OK (battery %.1f%%)",
                snap.state,
                snap.battery,
            )

        stop_event.wait(interval_sec)

    logger.info("Health monitor stopped.")
