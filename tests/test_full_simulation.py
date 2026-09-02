"""
30-second full simulation using all mock hardware subsystems.

Run from project root:
    python tests/test_full_simulation.py
"""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import config
from camera.camera_manager import camera_worker
from core.mission_state import MissionState
from core.shared_data import SharedData
from core.thread_manager import ManagedThread, ThreadManager
from gimbal.gimbal_stabilizer import gimbal_worker
from logging_system.data_logger import DataLogger, logger_worker
from mapping.kml_generator import generate_kml
from mapping.map_visualizer import generate_flight_map
from navigation.navigation_estimator import navigation_worker
from sensors.barometer import barometer_worker
from sensors.gps import gps_worker
from sensors.imu import imu_worker
from telemetry.xbee_sender import telemetry_worker

SIMULATION_SEC = 30.0


def run_full_simulation() -> None:
    print("=" * 50)
    print(f"TEST: Full Simulation ({SIMULATION_SEC:.0f}s)")
    print("=" * 50)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    # Force mock mode for this test
    config.USE_MOCK_HARDWARE = True
    config.IMAGE_SAVE_PATH.mkdir(parents=True, exist_ok=True)
    config.LOG_SAVE_PATH.mkdir(parents=True, exist_ok=True)
    config.MAP_SAVE_PATH.mkdir(parents=True, exist_ok=True)

    shared = SharedData()
    thread_mgr = ThreadManager()
    data_logger = DataLogger(shared, filename="simulation_test_log.csv")
    data_logger.open()

    thread_mgr.register(ManagedThread("GPS", lambda e: gps_worker(shared, e)))
    thread_mgr.register(ManagedThread("IMU", lambda e: imu_worker(shared, e)))
    thread_mgr.register(ManagedThread("Barometer", lambda e: barometer_worker(shared, e)))
    thread_mgr.register(ManagedThread("Camera", lambda e: camera_worker(shared, e)))
    thread_mgr.register(ManagedThread("Gimbal", lambda e: gimbal_worker(shared, e)))
    thread_mgr.register(ManagedThread("Navigation", lambda e: navigation_worker(shared, e)))
    thread_mgr.register(ManagedThread("Telemetry", lambda e: telemetry_worker(shared, e)))
    thread_mgr.register(
        ManagedThread("DataLogger", lambda e: logger_worker(shared, data_logger, e))
    )

    thread_mgr.start_all()

    # Mission state progression
    shared.update(state=MissionState.BOOT.value)
    shared.start_mission_clock()
    print("[INFO] State: BOOT")
    time.sleep(2)

    shared.update(state=MissionState.IDLE.value)
    print("[INFO] State: IDLE")
    time.sleep(3)

    shared.update(state=MissionState.DESCENT.value)
    print("[INFO] State: DESCENT")
    descent_start = time.time()
    while time.time() - descent_start < SIMULATION_SEC - 8:
        time.sleep(1)
        snap = shared.get_snapshot()
        print(
            f"  t={snap.mission_time:.0f}s alt={snap.baro_altitude:.0f}m "
            f"lat={snap.latitude:.5f} img={snap.image_name or '-'}"
        )

    shared.update(state=MissionState.LANDED.value)
    print("[INFO] State: LANDED")
    time.sleep(2)

    print("[INFO] Stopping threads...")
    thread_mgr.stop_all()
    data_logger.close()

    # Generate maps
    html_path = generate_flight_map(data_logger.path)
    kml_path = generate_kml(data_logger.path)
    print(f"[OK] HTML map: {html_path}")
    print(f"[OK] KML file: {kml_path}")
    print(f"[OK] CSV log:  {data_logger.path}")

    snap = shared.get_snapshot()
    assert snap.gps_ok or snap.latitude != 0, "GPS data missing"
    assert snap.navigation_mode in {"GOOD", "DEGRADED", "RECOVERING"}, "Navigation estimator did not initialize"
    assert snap.estimated_latitude != 0.0 and snap.estimated_longitude != 0.0, "Estimated navigation position missing"
    assert data_logger.path.exists(), "CSV log missing"
    assert html_path.exists(), "HTML map missing"
    assert kml_path.exists(), "KML missing"

    print("\nFull simulation test passed.")


if __name__ == "__main__":
    run_full_simulation()
