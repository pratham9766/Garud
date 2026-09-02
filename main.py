"""
Ground Mapping Payload — main entry point.

Starts all enabled subsystems as background threads, runs the mission
state machine, and generates maps on shutdown.

Press Ctrl+C to stop cleanly.
"""

from __future__ import annotations

import argparse
import logging
import signal
import sys
import threading
import time
from pathlib import Path

# Ensure project root is on sys.path when run as script
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config
from camera.camera_manager import camera_worker
from core.flight_state_machine import FlightStateController
from core.health_monitor import health_monitor_loop
from core.mission_state import MissionState, next_state
from core.shared_data import SharedData
from core.thread_manager import ManagedThread, ThreadManager
from gimbal.gimbal_stabilizer import gimbal_worker
from logging_system.data_logger import DataLogger, logger_worker
from navigation.navigation_estimator import navigation_worker
from sensors.barometer import barometer_worker
from sensors.gps import gps_worker
from sensors.imu import imu_worker
from telemetry.xbee_sender import telemetry_worker
from gnc.gnc_worker import FlightComputer

logger = logging.getLogger(__name__)


class TestModeControl:
    """Operator-controlled state-machine switchboard for ground testing."""

    def __init__(self, auto_transitions: bool = False) -> None:
        self._lock = threading.Lock()
        self.auto_transitions = auto_transitions
        self.quit_requested = False

    def set_auto(self, enabled: bool) -> None:
        with self._lock:
            self.auto_transitions = enabled

    def request_quit(self) -> None:
        with self._lock:
            self.quit_requested = True

    def snapshot(self) -> tuple[bool, bool]:
        with self._lock:
            return self.auto_transitions, self.quit_requested


def setup_logging() -> None:
    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="GARUDA ground mapping payload runtime.")
    parser.add_argument(
        "--test-mode",
        action="store_true",
        help="Run live workers with operator-controlled states for ground testing.",
    )
    parser.add_argument(
        "--auto-transitions",
        action="store_true",
        help="Start test mode with sensor-driven state transitions enabled.",
    )
    parser.add_argument("--mock", action="store_true", help="Use mock hardware.")
    parser.add_argument("--real-hardware", action="store_true", help="Force real hardware mode.")
    parser.add_argument(
        "--drop-height",
        type=float,
        default=0.0,
        metavar="METERS",
        help="Height above ground (meters) at which the software is started. "
             "Use when booting on a rooftop or elevated position so the barometer "
             "baseline is corrected to true ground level. Example: --drop-height 36",
    )

    for name in ("gps", "imu", "barometer", "camera", "gimbal", "telemetry", "logging", "mapping", "navigation_estimator", "glider_servos"):
        flag = name.replace("_", "-")
        parser.add_argument(f"--enable-{flag}", action="store_true", help=f"Enable {name}.")
        parser.add_argument(f"--disable-{flag}", action="store_true", help=f"Disable {name}.")
    return parser


def apply_runtime_overrides(args: argparse.Namespace) -> None:
    if args.mock and args.real_hardware:
        raise SystemExit("--mock and --real-hardware cannot be used together.")
    if args.mock:
        config.USE_MOCK_HARDWARE = True
    if args.real_hardware:
        config.USE_MOCK_HARDWARE = False
    if args.test_mode:
        config.PAUSE_STATE_TRANSITIONS = not args.auto_transitions

    for name in ("gps", "imu", "barometer", "camera", "gimbal", "telemetry", "logging", "mapping", "navigation_estimator", "glider_servos"):
        enable = getattr(args, f"enable_{name}")
        disable = getattr(args, f"disable_{name}")
        if enable and disable:
            flag = name.replace("_", "-")
            raise SystemExit(f"--enable-{flag} and --disable-{flag} cannot be used together.")
        if enable or disable:
            setattr(config, f"ENABLE_{name.upper()}", enable)


def ensure_directories() -> None:
    """Create data storage folders if they do not exist."""
    for path in (config.IMAGE_SAVE_PATH, config.LOG_SAVE_PATH, config.MAP_SAVE_PATH):
        path.mkdir(parents=True, exist_ok=True)
        logger.debug("Directory ready: %s", path)


def run_mission_state_machine(shared: SharedData, stop_event) -> None:
    """
    Advance mission states from live sensors.

    DISARMED -> ARMED_PAD -> BOOST -> COAST -> APOGEE -> DESCENT_DROGUE ->
    GLIDER_DEPLOY at 600 m AGL -> GUIDED_DESCENT -> LANDED.
    """
    logger.info("Mission state machine started.")
    controller = FlightStateController(shared)
    controller.start()
    while not stop_event.is_set():
        state = controller.update()
        if state == MissionState.LANDED:
            break
        time.sleep(0.1)

    logger.info("Mission state machine finished.")


def _test_state_updates(state: MissionState) -> dict:
    """Return side-effect flags that make manual states visible in logs."""
    updates = {"status": f"TEST_{state.value}"}
    if state == MissionState.ARMED_PAD:
        updates["status"] = "TEST_ARMED"
    elif state == MissionState.BOOST:
        updates["launch_detected"] = True
    elif state == MissionState.APOGEE:
        updates["apogee_detected"] = True
        updates["payload_ejected"] = True
    elif state == MissionState.GLIDER_DEPLOY:
        updates["glider_deployed"] = True
    elif state == MissionState.GUIDED_DESCENT:
        updates["glider_deployed"] = True
        updates["actuation_enabled"] = True
    elif state == MissionState.LANDED:
        updates["actuation_enabled"] = False
    elif state in {MissionState.DISARMED, MissionState.IDLE, MissionState.ABORT, MissionState.ERROR}:
        updates["actuation_enabled"] = False
    return updates


def _set_test_state(shared: SharedData, state: MissionState) -> None:
    shared.transition_state(
        state,
        reason="manual_test_override",
        source="TEST_CONSOLE",
        **_test_state_updates(state),
    )
    logger.info("Test mode forced state: %s", state.value)


def _print_test_mode_help() -> None:
    states = ", ".join(state.value for state in MissionState)
    print()
    print("GARUDA TEST MODE COMMANDS")
    print("  help              show commands")
    print("  auto on|off       enable/disable sensor-driven transitions")
    print("  state <name>      force a state for ground testing")
    print("  next              force the next nominal state")
    print("  arm / disarm      convenience state commands")
    print("  abort / landed    convenience state commands")
    print("  snap              print one live sensor/gimbal/logging snapshot")
    print("  quit              stop runtime cleanly")
    print(f"  states: {states}")
    print()


def _test_command_loop(shared: SharedData, control: TestModeControl) -> None:
    _print_test_mode_help()
    while True:
        try:
            raw = input("garuda-test> ").strip()
        except EOFError:
            return
        except KeyboardInterrupt:
            control.request_quit()
            return

        if not raw:
            continue
        parts = raw.split()
        command = parts[0].lower()

        try:
            if command in {"help", "h", "?"}:
                _print_test_mode_help()
            elif command == "auto" and len(parts) == 2 and parts[1].lower() in {"on", "off"}:
                enabled = parts[1].lower() == "on"
                control.set_auto(enabled)
                logger.info("Test mode automatic transitions: %s", "ON" if enabled else "OFF")
            elif command == "state" and len(parts) == 2:
                _set_test_state(shared, MissionState(parts[1].upper()))
            elif command == "next":
                current = MissionState(shared.get_snapshot().state)
                target = next_state(current)
                if target is None:
                    logger.warning("No nominal next state after %s.", current.value)
                else:
                    _set_test_state(shared, target)
            elif command == "arm":
                _set_test_state(shared, MissionState.ARMED_PAD)
            elif command == "disarm":
                _set_test_state(shared, MissionState.DISARMED)
            elif command == "abort":
                _set_test_state(shared, MissionState.ABORT)
            elif command == "landed":
                _set_test_state(shared, MissionState.LANDED)
            elif command == "snap":
                log_terminal_snapshot(shared)
            elif command in {"quit", "exit", "q"}:
                control.request_quit()
                return
            else:
                logger.warning("Unknown test command: %s", raw)
        except ValueError:
            logger.warning("Unknown state. Type 'help' to list valid states.")


def run_test_mode(shared: SharedData, stop_event, auto_transitions: bool = False) -> None:
    """Run payload workers with operator-controlled state transitions."""
    logger.info("Ground test mode started.")
    shared.start_mission_clock()
    _set_test_state(shared, MissionState.DISARMED)

    control = TestModeControl(auto_transitions=auto_transitions)
    command_thread = threading.Thread(
        target=_test_command_loop,
        args=(shared, control),
        name="TestModeConsole",
        daemon=True,
    )
    command_thread.start()
    controller = FlightStateController(shared)
    last_snapshot = 0.0

    while not stop_event.is_set():
        auto_enabled, quit_requested = control.snapshot()
        if quit_requested:
            break
        if auto_enabled:
            controller.update()

        now = time.monotonic()
        if now - last_snapshot >= 1.0:
            log_terminal_snapshot(shared)
            last_snapshot = now
        time.sleep(0.1)

    logger.info("Ground test mode finished.")


def generate_outputs(log_path: Path) -> None:
    """Generate HTML map and KML from the flight log."""
    if not config.ENABLE_MAPPING:
        return
    if not log_path.exists():
        logger.warning("No log file at %s — skipping map generation.", log_path)
        return
    try:
        from mapping.kml_generator import generate_kml
        from mapping.map_visualizer import generate_flight_map

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
    args = build_parser().parse_args()
    apply_runtime_overrides(args)
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

    def handle_signal(signum, frame):
        nonlocal global_stop
        logger.info("Shutdown signal received (Ctrl+C).")
        global_stop = True

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
        thread_mgr.register(
            ManagedThread("Camera", lambda evt: camera_worker(shared, evt))
        )
    if config.ENABLE_GIMBAL:
        thread_mgr.register(
            ManagedThread("Gimbal", lambda evt: gimbal_worker(shared, evt))
        )
    if config.ENABLE_NAVIGATION_ESTIMATOR:
        thread_mgr.register(
            ManagedThread("Navigation", lambda evt: navigation_worker(shared, evt))
        )
    if config.ENABLE_TELEMETRY:
        thread_mgr.register(
            ManagedThread("Telemetry", lambda evt: telemetry_worker(shared, evt))
        )

    # GNC flight computer (always active — manages servos and descent steering)
    _drop_height = args.drop_height
    fc = FlightComputer(shared, drop_height=_drop_height)
    thread_mgr.register(
        ManagedThread("GNC", lambda evt: fc.run(evt))
    )
    if _drop_height > 0.0:
        logger.info("[GNC] Drop-height correction active: %.1f m offset applied to ground altitude", _drop_height)

    # Glider hardware servos
    if getattr(config, "ENABLE_GLIDER_SERVOS", True):
        from gnc.glider_servo_worker import glider_servo_worker
        thread_mgr.register(
            ManagedThread("GliderServos", lambda evt: glider_servo_worker(shared, evt))
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

    # Run mission state machine in main thread
    class _StopProxy:
        def is_set(self):
            return global_stop

    try:
        if args.test_mode:
            run_test_mode(shared, _StopProxy(), auto_transitions=args.auto_transitions)
            global_stop = True
        elif config.PAUSE_STATE_TRANSITIONS:
            shared.update(state=MissionState.IDLE.value, status="SETUP_TEST")
            shared.start_mission_clock()
            logger.info(
                "Mission state transitions paused for setup verification. "
                "Press Ctrl+C to stop."
            )
        else:
            run_mission_state_machine(shared, _StopProxy())

        # If not interrupted, keep running until LANDED or user stops
        while not global_stop:
            snap = shared.get_snapshot()
            if config.PAUSE_STATE_TRANSITIONS:
                log_terminal_snapshot(shared)
            elif snap.state == MissionState.LANDED.value:
                logger.info("Mission complete — press Ctrl+C to exit and generate maps.")
            time.sleep(1.0)

    except KeyboardInterrupt:
        logger.info("Keyboard interrupt.")
    finally:
        logger.info("Stopping all threads...")
        thread_mgr.stop_all()

        if data_logger:
            data_logger.close()
            if config.ENABLE_MAPPING:
                generate_outputs(data_logger.path)

        logger.info("Ground Mapping Payload — shutdown complete.")


if __name__ == "__main__":
    main()
