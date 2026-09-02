"""
Camera manager — periodic image capture in a background thread.
"""

from __future__ import annotations

import logging
from pathlib import Path
import threading
import time

import config
from camera.mock_camera import MockCamera, RealCamera
from core.mission_state import MissionState
from core.shared_data import SharedData

logger = logging.getLogger(__name__)

CAPTURE_STATES = {
    MissionState.APOGEE.value,
    MissionState.DESCENT.value,
    MissionState.DESCENT_DROGUE.value,
    MissionState.GLIDER_DEPLOY.value,
    MissionState.GUIDED_DESCENT.value,
}


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
    try:
        camera = create_camera()
    except Exception as exc:
        logger.error("Camera init error: %s", exc)
        shared.update(camera_ok=False, status="CAMERA_INIT_ERROR")
        shared.record_worker_error("Camera", exc, expected_hz=config.CAMERA_EXPECTED_HZ)
        return
    logger.info("Camera worker started (mock=%s).", config.USE_MOCK_HARDWARE)
    capture_sequence = 0
    successful_captures = 0
    failed_captures = 0

    try:
        while not stop_event.is_set():
            try:
                snap = shared.get_snapshot()
                if snap.state not in CAPTURE_STATES:
                    shared.record_worker_success(
                        "Camera",
                        expected_hz=config.CAMERA_EXPECTED_HZ,
                        reason=f"Waiting for capture state; current state {snap.state}.",
                        details={
                            "capture_enabled_in_state": False,
                            "configured_interval_sec": config.IMAGE_CAPTURE_INTERVAL_SEC,
                            "successful_captures": successful_captures,
                            "failed_captures": failed_captures,
                        },
                    )
                    stop_event.wait(config.IMAGE_CAPTURE_INTERVAL_SEC)
                    continue
                if config.USE_MOCK_HARDWARE and shared.is_fault_active("camera_timeout"):
                    raise TimeoutError("Mock camera timeout injected.")
                if config.USE_MOCK_HARDWARE and shared.is_fault_active("camera_dropped_frame"):
                    capture_sequence += 1
                    shared.update(
                        camera_capture_sequence=capture_sequence,
                        camera_total_captures=capture_sequence + failed_captures,
                        camera_dropped_captures=snap.camera_dropped_captures + 1,
                    )
                    shared.record_event("CAMERA_CAPTURE_FAILED", "Camera", "WARN", "Mock dropped frame injected.")
                    stop_event.wait(config.IMAGE_CAPTURE_INTERVAL_SEC)
                    continue
                start = time.monotonic()
                filename = camera.capture(
                    latitude=snap.latitude,
                    longitude=snap.longitude,
                )
                capture_time = time.time()
                write_latency_ms = (time.monotonic() - start) * 1000.0
                image_path = config.IMAGE_SAVE_PATH / Path(filename).name
                file_size = image_path.stat().st_size if image_path.exists() else 0
                capture_sequence += 1
                successful_captures += 1
                diagnostics = shared.get_diagnostics_snapshot()
                workers = diagnostics.get("workers", {})

                def age_delta_ms(worker_name: str) -> float:
                    worker = workers.get(worker_name, {})
                    last_wall = float(worker.get("last_update_wall") or 0.0)
                    if last_wall <= 0.0:
                        return -1.0
                    return abs(capture_time - last_wall) * 1000.0

                sync_imu = age_delta_ms("IMU")
                sync_gps = age_delta_ms("GPS")
                sync_baro = age_delta_ms("Barometer")
                shared.update(
                    image_name=filename,
                    image_timestamp=capture_time,
                    camera_capture_sequence=capture_sequence,
                    camera_total_captures=capture_sequence + failed_captures,
                    camera_successful_captures=successful_captures,
                    camera_failed_captures=failed_captures,
                    camera_last_file_size_bytes=file_size,
                    camera_last_write_latency_ms=write_latency_ms,
                    image_sync_imu_delta_ms=sync_imu,
                    image_sync_gps_delta_ms=sync_gps,
                    image_sync_baro_delta_ms=sync_baro,
                    camera_ok=True,
                )
                shared.record_worker_success(
                    "Camera",
                    expected_hz=config.CAMERA_EXPECTED_HZ,
                    reason="Image capture completed.",
                    details={
                        "capture_enabled_in_state": True,
                        "capture_sequence": capture_sequence,
                        "successful_captures": successful_captures,
                        "failed_captures": failed_captures,
                        "configured_interval_sec": config.IMAGE_CAPTURE_INTERVAL_SEC,
                        "last_file_size_bytes": file_size,
                        "write_latency_ms": write_latency_ms,
                        "resolution": f"{config.CAMERA_FRAME_WIDTH}x{config.CAMERA_FRAME_HEIGHT}",
                        "sync_imu_delta_ms": sync_imu,
                        "sync_gps_delta_ms": sync_gps,
                        "sync_baro_delta_ms": sync_baro,
                    },
                )
                if max(sync_imu, sync_gps, sync_baro) > config.IMAGE_SYNC_WARN_MS:
                    shared.record_event(
                        "IMAGE_SYNC_WARNING",
                        "Camera",
                        "WARN",
                        "Image captured with stale sensor synchronization.",
                        {"imu_ms": sync_imu, "gps_ms": sync_gps, "baro_ms": sync_baro},
                    )
                logger.info("Image captured: %s", filename)
            except Exception as exc:
                failed_captures += 1
                logger.error("Camera capture error: %s", exc)
                shared.update(
                    camera_ok=False,
                    status="CAMERA_ERROR",
                    camera_failed_captures=failed_captures,
                    camera_total_captures=capture_sequence + failed_captures,
                )
                shared.record_worker_error("Camera", exc, expected_hz=config.CAMERA_EXPECTED_HZ)
                shared.record_event("CAMERA_CAPTURE_FAILED", "Camera", "ERROR", str(exc))

            stop_event.wait(config.IMAGE_CAPTURE_INTERVAL_SEC)
    finally:
        camera.close()
        logger.info("Camera worker stopped.")
