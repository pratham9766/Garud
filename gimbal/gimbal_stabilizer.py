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
    last_pitch = 0.0
    last_roll = 0.0

    try:
        while not stop_event.is_set():
            try:
                snap = shared.get_snapshot()
                attitude_roll = snap.ahrs_roll if snap.ahrs_healthy else snap.roll
                attitude_pitch = snap.ahrs_pitch if snap.ahrs_healthy else snap.pitch
                # Dampen large swings without assuming perfect stabilization.
                target_pitch = -attitude_pitch * config.GIMBAL_POSE_DAMPING_GAIN
                target_roll = -attitude_roll * config.GIMBAL_POSE_DAMPING_GAIN
                max_step = config.GIMBAL_MAX_COMMAND_STEP_DEG
                target_pitch = max(last_pitch - max_step, min(last_pitch + max_step, target_pitch))
                target_roll = max(last_roll - max_step, min(last_roll + max_step, target_roll))
                gimbal.set_angles(target_pitch, target_roll)
                last_pitch = target_pitch
                last_roll = target_roll
            except Exception as exc:
                logger.error("Gimbal error: %s", exc)

            stop_event.wait(0.2)
    finally:
        gimbal.close()
        logger.info("Gimbal stabilizer stopped.")
