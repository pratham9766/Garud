"""Tests for the sensor-driven flight state machine."""

from __future__ import annotations

import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import config
from core.flight_state_machine import FlightStateController
from core.mission_state import MissionState
from core.shared_data import SharedData


def _tick(
    controller: FlightStateController,
    shared: SharedData,
    altitude: float,
    accel_z: float = 9.80665,
    repeats: int = 1,
    dt: float = 0.02,
) -> MissionState:
    state = MissionState(shared.get_snapshot().state)
    for _ in range(repeats):
        shared.update(baro_altitude=altitude, raw_accel_z=accel_z)
        state = controller.update()
        time.sleep(dt)
    return state


def test_flight_profile_reaches_guided_descent_after_600m_glider_deploy() -> None:
    original_mock = config.USE_MOCK_HARDWARE
    original_auto_arm = config.AUTO_ARM_IN_MOCK_MODE
    original_settle = config.GLIDER_DEPLOY_SETTLE_SEC
    try:
        config.USE_MOCK_HARDWARE = True
        config.AUTO_ARM_IN_MOCK_MODE = True
        config.GLIDER_DEPLOY_SETTLE_SEC = 0.0

        shared = SharedData()
        controller = FlightStateController(shared)
        controller.start()

        assert shared.get_snapshot().state == MissionState.ARMED_PAD.value

        _tick(controller, shared, altitude=35.0, accel_z=22.0, repeats=3)
        assert shared.get_snapshot().state == MissionState.BOOST.value
        assert shared.get_snapshot().launch_detected

        _tick(controller, shared, altitude=250.0, accel_z=9.80665, repeats=5)
        assert shared.get_snapshot().state == MissionState.COAST.value

        for altitude in (500.0, 800.0, 1000.0):
            _tick(controller, shared, altitude=altitude, repeats=1)
        for altitude in (990.0, 980.0, 970.0, 960.0, 950.0):
            _tick(controller, shared, altitude=altitude, repeats=1)
        assert shared.get_snapshot().state == MissionState.APOGEE.value
        assert shared.get_snapshot().payload_ejected

        _tick(controller, shared, altitude=950.0, repeats=1)
        assert shared.get_snapshot().state == MissionState.DESCENT_DROGUE.value

        for altitude in (595.0, 590.0, 585.0, 580.0, 575.0):
            _tick(controller, shared, altitude=altitude, repeats=1)
        assert shared.get_snapshot().state == MissionState.GLIDER_DEPLOY.value
        assert shared.get_snapshot().glider_deployed

        _tick(controller, shared, altitude=580.0, repeats=1)
        snap = shared.get_snapshot()
        assert snap.state == MissionState.GUIDED_DESCENT.value
        assert snap.actuation_enabled
    finally:
        config.USE_MOCK_HARDWARE = original_mock
        config.AUTO_ARM_IN_MOCK_MODE = original_auto_arm
        config.GLIDER_DEPLOY_SETTLE_SEC = original_settle


if __name__ == "__main__":
    test_flight_profile_reaches_guided_descent_after_600m_glider_deploy()
    print("Flight state-machine test passed.")
