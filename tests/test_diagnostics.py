"""Focused tests for GARUDA engineering diagnostics."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from tempfile import TemporaryDirectory

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import config
from core.mission_state import MissionState
from core.shared_data import SharedData
from telemetry.telemetry_packet import build_telemetry_packet
from core.payload_diagnostics import validate_storage
from hardware_tests.ground_station_dashboard import write_test_report


def test_worker_metrics_and_recovery() -> None:
    shared = SharedData()
    shared.record_worker_error("GPS", "timeout", expected_hz=5.0)
    shared.record_worker_success("GPS", expected_hz=5.0, reason="fix reacquired")
    metric = shared.get_diagnostics_snapshot()["workers"]["GPS"]
    assert metric["status"] == "HEALTHY"
    assert metric["error_count"] == 1
    assert metric["recovery_count"] == 1
    assert metric["expected_hz"] == 5.0


def test_stale_detection_uses_monotonic_age() -> None:
    original = config.WORKER_STALE_TIMEOUT_SEC
    config.WORKER_STALE_TIMEOUT_SEC = 0.01
    try:
        shared = SharedData()
        shared.record_worker_success("IMU", expected_hz=100.0)
        time.sleep(0.02)
        metric = shared.get_diagnostics_snapshot()["workers"]["IMU"]
        assert metric["status"] == "STALE"
        assert metric["data_age_ms"] >= 10.0
    finally:
        config.WORKER_STALE_TIMEOUT_SEC = original


def test_state_transition_history_is_authoritative() -> None:
    shared = SharedData()
    shared.start_mission_clock()
    shared.transition_state(
        MissionState.DISARMED,
        reason="test_start",
        source="TEST",
    )
    shared.transition_state(
        MissionState.ARMED_PAD,
        reason="operator_arm",
        source="TEST",
        trigger_values={"button": "arm"},
    )
    snap = shared.get_snapshot()
    diagnostics = shared.get_diagnostics_snapshot()
    assert snap.state == MissionState.ARMED_PAD.value
    assert snap.previous_state == MissionState.DISARMED.value
    assert snap.state_transition_reason == "operator_arm"
    assert diagnostics["state_history"][-1]["to"] == MissionState.ARMED_PAD.value
    assert diagnostics["state_history"][-1]["trigger_values"]["button"] == "arm"


def test_event_debounce() -> None:
    shared = SharedData()
    shared.record_event("GPS_FIX_LOST", "GPS", "WARN", "no fix")
    shared.record_event("GPS_FIX_LOST", "GPS", "WARN", "no fix")
    events = shared.get_diagnostics_snapshot()["events"]
    assert len(events) == 1


def test_telemetry_includes_sequence_and_transition_reason() -> None:
    shared = SharedData()
    shared.update(telemetry_sequence=42)
    shared.transition_state(MissionState.DISARMED, reason="test_start", source="TEST")
    packet = json.loads(build_telemetry_packet(shared.get_snapshot()))
    assert packet["seq"] == 42
    assert packet["state"] == MissionState.DISARMED.value
    assert packet["reason"] == "test_start"


def test_fault_flags_are_recorded_as_events() -> None:
    shared = SharedData()
    shared.set_fault("gps_loss", True)
    assert shared.is_fault_active("gps_loss") is True
    diagnostics = shared.get_diagnostics_snapshot()
    assert diagnostics["faults"]["gps_loss"] is True
    assert diagnostics["events"][-1]["event_type"] == "FAULT_INJECTION"


def test_test_session_report_contains_minmax() -> None:
    shared = SharedData()
    shared.start_mission_clock()
    test_id = shared.start_test_session("MOCK", {"sample": True})
    shared.update(baro_altitude=10.0, gps_altitude=12.0, bus_voltage_v=5.1, current_a=0.4)
    shared.record_test_sample()
    shared.update(baro_altitude=20.0, gps_altitude=22.0, bus_voltage_v=4.7, current_a=0.8)
    shared.record_test_sample()
    report = shared.stop_test_session()
    assert report["test_id"] == test_id
    assert report["sample_count"] == 2
    assert report["minmax"]["baro_altitude"]["min"] == 10.0
    assert report["minmax"]["baro_altitude"]["max"] == 20.0
    assert report["minmax"]["bus_voltage_v"]["min"] == 4.7


def test_storage_validation_counts_missing_and_orphan_images() -> None:
    with TemporaryDirectory() as temp:
        original_image_path = config.IMAGE_SAVE_PATH
        config.IMAGE_SAVE_PATH = Path(temp) / "images"
        config.IMAGE_SAVE_PATH.mkdir()
        try:
            (config.IMAGE_SAVE_PATH / "present.jpg").write_bytes(b"fake")
            (config.IMAGE_SAVE_PATH / "orphan.jpg").write_bytes(b"fake")
            log_path = Path(temp) / "log.csv"
            log_path.write_text("image_name\npresent.jpg\nmissing.jpg\n", encoding="utf-8")
            result = validate_storage(log_path)
            assert result["images_referenced"] == 2
            assert result["images_present"] == 1
            assert result["images_missing"] == 1
            assert result["images_orphan"] == 1
        finally:
            config.IMAGE_SAVE_PATH = original_image_path


def test_write_test_report_creates_json_csv_html() -> None:
    with TemporaryDirectory() as temp:
        original_log_path = config.LOG_SAVE_PATH
        config.LOG_SAVE_PATH = Path(temp)
        try:
            paths = write_test_report(
                {
                    "test_id": "unit-report",
                    "mode": "MOCK",
                    "sample_count": 1,
                    "events": [{"mission_time": 0.1, "severity": "INFO", "source": "TEST", "event_type": "UNIT", "message": "ok"}],
                    "workers": {"IMU": {"status": "HEALTHY", "actual_hz": 100.0, "expected_hz": 100.0, "error_count": 0, "reason": "ok"}},
                    "minmax": {},
                }
            )
            assert Path(paths["json"]).exists()
            assert Path(paths["csv"]).exists()
            assert Path(paths["html"]).exists()
        finally:
            config.LOG_SAVE_PATH = original_log_path


if __name__ == "__main__":
    test_worker_metrics_and_recovery()
    test_stale_detection_uses_monotonic_age()
    test_state_transition_history_is_authoritative()
    test_event_debounce()
    test_telemetry_includes_sequence_and_transition_reason()
    test_fault_flags_are_recorded_as_events()
    test_test_session_report_contains_minmax()
    test_storage_validation_counts_missing_and_orphan_images()
    test_write_test_report_creates_json_csv_html()
    print("diagnostics tests passed")
