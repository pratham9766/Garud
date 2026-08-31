"""
Gimbal stabilizer — uses IMU attitude to command counter-rotation.
"""

from __future__ import annotations

import logging
import threading
import time

import config
from core.shared_data import SharedData
from gimbal.servo_control import create_gimbal

logger = logging.getLogger(__name__)


def gimbal_worker(shared: SharedData, stop_event: threading.Event) -> None:
    """
    Background thread: read IMU from shared data and stabilize gimbal.

    Simple proportional correction: command partial opposite of roll/pitch.
    """
    try:
        gimbal = create_gimbal()
    except Exception as exc:
        logger.error("Gimbal init error: %s", exc)
        shared.update(status="GIMBAL_INIT_ERROR")
        return
    logger.info("Gimbal stabilizer started (mock=%s).", config.USE_MOCK_HARDWARE)
    last_update = time.monotonic()

    try:
        while not stop_event.is_set():
            try:
                now = time.monotonic()
                dt = now - last_update
                last_update = now
                snap = shared.get_snapshot()
                attitude_roll = snap.ahrs_roll if snap.ahrs_healthy else snap.roll
                attitude_pitch = snap.ahrs_pitch if snap.ahrs_healthy else snap.pitch
                command = gimbal.point_down(attitude_roll, attitude_pitch, dt)
                shared.update(
                    gimbal_x_deflection_deg=command["x_deflection_deg"],
                    gimbal_y_deflection_deg=command["y_deflection_deg"],
                    gimbal_stepper_angle_deg=command["stepper_angle_deg"],
                    gimbal_servo_angle_deg=command["servo_angle_deg"],
                    gimbal_stepper_steps=command["stepper_steps"],
                    gimbal_ok=True,
                )
            except Exception as exc:
                logger.error("Gimbal error: %s", exc)
                shared.update(gimbal_ok=False, status="GIMBAL_ERROR")

            stop_event.wait(1.0 / config.GIMBAL_LOOP_HZ)
    finally:
        gimbal.close()
        logger.info("Gimbal stabilizer stopped.")
