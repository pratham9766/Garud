"""Optional INA219 power-monitor worker for GARUDA verification."""

from __future__ import annotations

import random
import threading
import time

import config
from core.shared_data import SharedData


class MockPowerMonitor:
    def read(self) -> dict:
        voltage = 5.08 + random.uniform(-0.03, 0.03)
        current = 0.55 + random.uniform(-0.08, 0.08)
        return {"bus_voltage_v": voltage, "current_a": current, "power_w": voltage * current}

    def close(self) -> None:
        pass


class RealPowerMonitor:
    """INA219 adapter, used only when the library and hardware are available."""

    def __init__(self) -> None:
        if config.INA219_I2C_ADDRESS is None:
            raise RuntimeError("INA219_I2C_ADDRESS is not configured.")
        import board
        import busio
        from adafruit_ina219 import INA219

        i2c = busio.I2C(board.SCL, board.SDA)
        self._sensor = INA219(i2c, addr=config.INA219_I2C_ADDRESS)

    def read(self) -> dict:
        return {
            "bus_voltage_v": float(self._sensor.bus_voltage),
            "current_a": float(self._sensor.current) / 1000.0,
            "power_w": float(self._sensor.power) / 1000.0,
        }

    def close(self) -> None:
        pass


def create_power_monitor():
    if config.USE_MOCK_HARDWARE:
        return MockPowerMonitor()
    return RealPowerMonitor()


def power_worker(shared: SharedData, stop_event: threading.Event) -> None:
    try:
        monitor = create_power_monitor()
    except Exception as exc:
        shared.record_worker_error("Power", f"UNAVAILABLE: {exc}", expected_hz=config.POWER_EXPECTED_HZ, status="DISABLED")
        return

    min_voltage = 0.0
    max_current = 0.0
    undervoltage_events = 0
    try:
        while not stop_event.is_set():
            try:
                reading = monitor.read()
                if shared.is_fault_active("low_voltage") and config.USE_MOCK_HARDWARE:
                    reading["bus_voltage_v"] = config.POWER_UNDERVOLTAGE_WARN_V - 0.25
                    reading["power_w"] = reading["bus_voltage_v"] * reading["current_a"]
                voltage = float(reading["bus_voltage_v"])
                current = float(reading["current_a"])
                power = float(reading["power_w"])
                min_voltage = voltage if min_voltage <= 0.0 else min(min_voltage, voltage)
                max_current = max(max_current, current)
                status = "HEALTHY"
                reason = "Power sample fresh."
                if voltage < config.POWER_UNDERVOLTAGE_WARN_V:
                    undervoltage_events += 1
                    status = "DEGRADED"
                    reason = f"Voltage {voltage:.2f}V below threshold."
                    shared.record_event("POWER_UNDERVOLTAGE", "Power", "WARN", reason, reading)
                if current > config.POWER_OVERCURRENT_WARN_A:
                    status = "DEGRADED"
                    reason = f"Current {current:.2f}A above threshold."
                    shared.record_event("POWER_OVERCURRENT", "Power", "WARN", reason, reading)
                shared.update(
                    bus_voltage_v=voltage,
                    current_a=current,
                    power_w=power,
                    min_voltage_v=min_voltage,
                    max_current_a=max_current,
                    undervoltage_events=undervoltage_events,
                )
                shared.record_worker_success(
                    "Power",
                    expected_hz=config.POWER_EXPECTED_HZ,
                    reason=reason,
                    status=status,
                    details={
                        "bus_voltage_v": voltage,
                        "current_a": current,
                        "power_w": power,
                        "min_voltage_v": min_voltage,
                        "max_current_a": max_current,
                        "undervoltage_events": undervoltage_events,
                    },
                )
            except Exception as exc:
                shared.record_worker_error("Power", exc, expected_hz=config.POWER_EXPECTED_HZ)
            stop_event.wait(1.0 / max(config.POWER_EXPECTED_HZ, 0.1))
    finally:
        monitor.close()
