"""
Gimbal stabilizer — uses IMU attitude to command counter-rotation.
"""

from __future__ import annotations

import logging
import threading

import config
from core.shared_data import SharedData
from gimbal.servo_control import create_gimbal

logger = logging.getLogger(__name__)


def gimbal_worker(shared: SharedData, stop_event: threading.Event) -> None:
    """
    Background thread: read IMU from shared data and stabilize gimbal.

    Simple proportional correction: command partial opposite of roll/pitch.
    """
    gimbal = create_gimbal()
    logger.info("Gimbal stabilizer started (mock=%s).", config.USE_MOCK_HARDWARE)

    try:
        while not stop_event.is_set():
            try:
                snap = shared.get_snapshot()
                # Dampen large swings without assuming perfect stabilization.
                target_pitch = -snap.pitch * config.GIMBAL_POSE_DAMPING_GAIN
                target_roll = -snap.roll * config.GIMBAL_POSE_DAMPING_GAIN
                gimbal.set_angles(target_pitch, target_roll)
            except Exception as exc:
                logger.error("Gimbal error: %s", exc)

            stop_event.wait(0.2)
    finally:
        gimbal.close()
        logger.info("Gimbal stabilizer stopped.")
