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
        shared.record_worker_error("Gimbal", exc, expected_hz=config.GIMBAL_EXPECTED_HZ)
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
                if config.USE_MOCK_HARDWARE and shared.is_fault_active("gimbal_saturation"):
                    attitude_roll = 140.0
                    attitude_pitch = -140.0
                command = gimbal.point_down(attitude_roll, attitude_pitch, dt)
                shared.update(
                    gimbal_x_deflection_deg=command["x_deflection_deg"],
                    gimbal_y_deflection_deg=command["y_deflection_deg"],
                    gimbal_stepper_angle_deg=command["stepper_angle_deg"],
                    gimbal_servo_angle_deg=command["servo_angle_deg"],
                    gimbal_stepper_steps=command["stepper_steps"],
                    gimbal_ok=True,
                )
                saturated = bool(command.get("stepper_saturated") or command.get("servo_saturated"))
                rate_limited = bool(command.get("stepper_rate_limited") or command.get("servo_rate_limited"))
                shared.record_worker_success(
                    "Gimbal",
                    expected_hz=config.GIMBAL_EXPECTED_HZ,
                    reason="Gimbal command updated.",
                    details={
                        "mode": "nadir_stabilize",
                        "feedback": "commanded_only",
                        "payload_roll_deg": attitude_roll,
                        "payload_pitch_deg": attitude_pitch,
                        "stepper_target_deg": command.get("stepper_target_deg"),
                        "servo_target_deg": command.get("servo_target_deg"),
                        "stepper_command_deg": command["stepper_angle_deg"],
                        "servo_command_deg": command["servo_angle_deg"],
                        "servo_physical_angle_deg": command.get("servo_physical_angle_deg"),
                        "stepper_steps": command["stepper_steps"],
                        "saturated": saturated,
                        "rate_limited": rate_limited,
                    },
                )
                if saturated:
                    shared.record_event(
                        "GIMBAL_SATURATION",
                        "Gimbal",
                        "WARN",
                        "Gimbal command reached configured travel limit.",
                        command,
                    )
            except Exception as exc:
                logger.error("Gimbal error: %s", exc)
                shared.update(gimbal_ok=False, status="GIMBAL_ERROR")
                shared.record_worker_error("Gimbal", exc, expected_hz=config.GIMBAL_EXPECTED_HZ)

            stop_event.wait(1.0 / config.GIMBAL_LOOP_HZ)
    finally:
        gimbal.close()
        logger.info("Gimbal stabilizer stopped.")
