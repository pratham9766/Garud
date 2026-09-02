"""
Ground Mapping Payload — main entry point.

Starts all enabled subsystems as background threads, runs the mission
state machine, and generates maps on shutdown.

Press Ctrl+C to stop cleanly.
"""

from __future__ import annotations

import logging
import signal
import sys
import time
import argparse
import multiprocessing
from pathlib import Path

# Ensure project root is on sys.path when run as script
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config
from camera.camera_manager import camera_worker
from core.health_monitor import health_monitor_loop
from core.mission_state import MissionState, next_state
from core.shared_data import SharedData
from core.thread_manager import ManagedThread, ThreadManager
from gnc.gnc_worker import FlightComputer
from gimbal.gimbal_stabilizer import gimbal_worker
from logging_system.data_logger import DataLogger, logger_worker
from mapping.kml_generator import generate_kml
from mapping.map_visualizer import generate_flight_map
from sensors.barometer import barometer_worker
from sensors.gps import gps_worker
from sensors.imu import imu_worker
from telemetry.xbee_sender import telemetry_worker

logger = logging.getLogger(__name__)


def setup_logging() -> None:
    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def ensure_directories() -> None:
    """Create data storage folders if they do not exist."""
    for path in (config.IMAGE_SAVE_PATH, config.LOG_SAVE_PATH, config.MAP_SAVE_PATH):
        path.mkdir(parents=True, exist_ok=True)
        logger.debug("Directory ready: %s", path)


def camera_ipc_bridge(shared: SharedData, cam_dict: dict, stop_event) -> None:
    """
    Main thread loop: polls the multiprocessing dict for camera updates
    and pushes them into SharedData.
    """
    logger.info("Camera IPC Bridge started.")
    while not stop_event.is_set():
        if "image_name" in cam_dict and "image_timestamp" in cam_dict:
            # We don't want to constantly update SharedData if it hasn't changed, 
            # so we check the timestamp.
            snap = shared.get_snapshot()
            if snap.image_timestamp != cam_dict["image_timestamp"]:
                shared.update(
                    image_name=cam_dict["image_name"],
                    image_timestamp=cam_dict["image_timestamp"]
                )
        time.sleep(0.1)
    logger.info("Camera IPC Bridge finished.")


def generate_outputs(log_path: Path) -> None:
    """Generate HTML map and KML from the flight log."""
    if not config.ENABLE_MAPPING:
        return
    if not log_path.exists():
        logger.warning("No log file at %s — skipping map generation.", log_path)
        return
    try:
        html_path = generate_flight_map(log_path)
        kml_path = generate_kml(log_path)
        logger.info("Maps generated: %s, %s", html_path, kml_path)
    except Exception as exc:
        logger.error("Map generation failed: %s", exc)


def log_terminal_snapshot(shared: SharedData) -> None:
    """Print a compact live verification line for bench setup."""
    snap = shared.get_snapshot()
    logger.info(
        "VERIFY state=%s t=%.1fs baro=%.2fm imu=%s rpy=(%.2f, %.2f, %.2f) "
        "ahrs=%s/%s ahrs_rpy=(%.2f, %.2f, %.2f) gyro=(%.2f, %.2f, %.2f) "
        "raw_gyro=(%.4f, %.4f, %.4f) accel=(%.2f, %.2f, %.2f) "
        "mag=(%.2f, %.2f, %.2f) pressure=%.2fhPa temp=%.2fC "
        "gimbal=%s deflect_xy=(%.2f, %.2f) cmd_stepper=%.2f cmd_servo=%.2f steps=%d",
        snap.state,
        snap.mission_time,
        snap.baro_altitude,
        "OK" if snap.imu_ok else "BAD",
        snap.roll,
        snap.pitch,
        snap.yaw,
        snap.ahrs_source,
        snap.ahrs_confidence,
        snap.ahrs_roll,
        snap.ahrs_pitch,
        snap.ahrs_yaw,
        snap.gyro_x,
        snap.gyro_y,
        snap.gyro_z,
        snap.raw_gyro_x,
        snap.raw_gyro_y,
        snap.raw_gyro_z,
        snap.raw_accel_x,
        snap.raw_accel_y,
        snap.raw_accel_z,
        snap.raw_mag_x,
        snap.raw_mag_y,
        snap.raw_mag_z,
        snap.raw_baro_pressure_hpa,
        snap.raw_baro_temperature_c,
        "OK" if snap.gimbal_ok else "BAD",
        snap.gimbal_x_deflection_deg,
        snap.gimbal_y_deflection_deg,
        snap.gimbal_stepper_angle_deg,
        snap.gimbal_servo_angle_deg,
        snap.gimbal_stepper_steps,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="GARUDA Ground Mapping Payload & GNC")
    parser.add_argument("--drop-height", type=float, default=0.0, help="Simulate a drop test from this height in meters")
    parser.add_argument("--mock", action="store_true", help="Force mock hardware mode (useful for testing on PC)")
    args = parser.parse_args()

    if args.mock:
        config.USE_MOCK_HARDWARE = True

    setup_logging()
    ensure_directories()

    logger.info("=" * 60)
    logger.info("Ground Mapping Payload — starting")
    logger.info("Real hardware mode: %s", not config.USE_MOCK_HARDWARE)
    logger.info("=" * 60)

    shared = SharedData()
    thread_mgr = ThreadManager()
    data_logger: DataLogger | None = None
    global_stop = False

    manager = multiprocessing.Manager()
    cam_dict = manager.dict()
    cam_process = None
    cam_stop_event = multiprocessing.Event()

    def handle_signal(signum, frame):
        nonlocal global_stop
        logger.info("Shutdown signal received (Ctrl+C).")
        global_stop = True
        cam_stop_event.set()

    signal.signal(signal.SIGINT, handle_signal)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, handle_signal)

    # --- Register worker threads based on config flags ---
    if config.ENABLE_GPS:
        thread_mgr.register(
            ManagedThread("GPS", lambda evt: gps_worker(shared, evt))
        )
    if config.ENABLE_IMU:
        thread_mgr.register(
            ManagedThread("IMU", lambda evt: imu_worker(shared, evt))
        )
    if config.ENABLE_BAROMETER:
        thread_mgr.register(
            ManagedThread("Barometer", lambda evt: barometer_worker(shared, evt))
        )
    if config.ENABLE_CAMERA:
        cam_process = multiprocessing.Process(
            target=camera_worker, args=(cam_dict, cam_stop_event)
        )
        cam_process.start()
        logger.info("Started multiprocessing.Process for Camera")
    if config.ENABLE_GIMBAL:
        thread_mgr.register(
            ManagedThread("Gimbal", lambda evt: gimbal_worker(shared, evt))
        )
    if config.ENABLE_TELEMETRY:
        thread_mgr.register(
            ManagedThread("Telemetry", lambda evt: telemetry_worker(shared, evt))
        )

    fc = FlightComputer(shared, drop_height=args.drop_height)
    thread_mgr.register(
        ManagedThread("GNC", lambda evt: fc.run(evt))
    )

    if config.ENABLE_LOGGING:
        data_logger = DataLogger(shared)
        data_logger.open()
        thread_mgr.register(
            ManagedThread(
                "DataLogger",
                lambda evt: logger_worker(shared, data_logger, evt),
            )
        )

    thread_mgr.register(
        ManagedThread(
            "HealthMonitor",
            lambda evt: health_monitor_loop(shared, evt, interval_sec=10.0),
        )
    )

    # Start all workers
    thread_mgr.start_all()

    class _StopProxy:
        def is_set(self):
            return global_stop

    try:
        if config.PAUSE_STATE_TRANSITIONS:
            shared.update(state=MissionState.IDLE.value, status="SETUP_TEST")
            shared.start_mission_clock()
            logger.info(
                "Mission state transitions paused for setup verification. "
                "Press Ctrl+C to stop."
            )
            
            # Bench verification loop
            while not global_stop:
                log_terminal_snapshot(shared)
                time.sleep(1.0)
        else:
            if config.ENABLE_CAMERA:
                camera_ipc_bridge(shared, cam_dict, _StopProxy())
            else:
                while not global_stop:
                    snap = shared.get_snapshot()
                    if snap.state == MissionState.LANDED.value:
                        logger.info("Mission complete — press Ctrl+C to exit and generate maps.")
                    time.sleep(1.0)

    except KeyboardInterrupt:
        logger.info("Keyboard interrupt.")
    finally:
        logger.info("Stopping all threads and processes...")
        global_stop = True
        cam_stop_event.set()
        
        thread_mgr.stop_all()

        if cam_process:
            cam_process.join(timeout=2.0)
            if cam_process.is_alive():
                logger.warning("Terminating camera process forcefully.")
                cam_process.terminate()

        if data_logger:
            data_logger.close()
            if config.ENABLE_MAPPING:
                generate_outputs(data_logger.path)

        logger.info("Ground Mapping Payload — shutdown complete.")


if __name__ == "__main__":
    main()
