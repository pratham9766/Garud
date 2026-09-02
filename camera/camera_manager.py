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


def camera_worker(cam_dict: dict, stop_event) -> None:
    """
    Background process: capture images at IMAGE_CAPTURE_INTERVAL_SEC.
    """
    try:
        camera = create_camera()
    except Exception as exc:
        logger.error("Camera init error: %s", exc)
        shared.update(camera_ok=False, status="CAMERA_INIT_ERROR")
        return
    logger.info("Camera worker started (mock=%s).", config.USE_MOCK_HARDWARE)

    try:
        while not stop_event.is_set():
            try:
                lat = cam_dict.get("latitude", 0.0)
                lon = cam_dict.get("longitude", 0.0)
                
                filename = camera.capture(latitude=lat, longitude=lon)
                
                cam_dict["image_name"] = filename
                cam_dict["image_timestamp"] = time.time()
                cam_dict["camera_ok"] = True
                
                logger.info("Image captured: %s", filename)
            except Exception as exc:
                logger.error("Camera capture error: %s", exc)
                cam_dict["camera_ok"] = False
                cam_dict["status"] = "CAMERA_ERROR"

            stop_event.wait(config.IMAGE_CAPTURE_INTERVAL_SEC)
    finally:
        camera.close()
        logger.info("Camera worker stopped.")
