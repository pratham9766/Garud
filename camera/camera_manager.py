"""
Camera manager — periodic image capture in a background thread.
"""

from __future__ import annotations

import logging
import threading
import time

import config
from camera.mock_camera import MockCamera, RealCamera
from core.shared_data import SharedData

logger = logging.getLogger(__name__)


def create_camera():
    """Factory: return mock or real camera based on config."""
    if config.USE_MOCK_HARDWARE:
        return MockCamera()
    return RealCamera()


def camera_worker(shared: SharedData, stop_event: threading.Event) -> None:
    """
    Background thread: capture images at IMAGE_CAPTURE_INTERVAL_SEC.

    Updates shared.image_name and shared.camera_ok on each capture.
    """
    camera = create_camera()
    logger.info("Camera worker started (mock=%s).", config.USE_MOCK_HARDWARE)

    try:
        while not stop_event.is_set():
            try:
                snap = shared.get_snapshot()
                filename = camera.capture(
                    latitude=snap.latitude,
                    longitude=snap.longitude,
                )
                shared.update(
                    image_name=filename,
                    image_timestamp=time.time(),
                    camera_ok=True,
                )
                logger.info("Image captured: %s", filename)
            except Exception as exc:
                logger.error("Camera capture error: %s", exc)
                shared.update(camera_ok=False, status="CAMERA_ERROR")

            stop_event.wait(config.IMAGE_CAPTURE_INTERVAL_SEC)
    finally:
        camera.close()
        logger.info("Camera worker stopped.")
