"""
Compact JSON telemetry packet builder.
"""

from __future__ import annotations

import json

from core.shared_data import PayloadSnapshot


def build_telemetry_packet(snap: PayloadSnapshot) -> str:
    """
    Build a compact JSON telemetry string from a payload snapshot.

    Fields stay compact for radio use; AHRS adds only attitude and health.
    """
    packet = {
        "seq": snap.telemetry_sequence,
        "state": snap.state,
        "prev": snap.previous_state,
        "reason": snap.state_transition_reason,
        "lat": round(snap.latitude, 6),
        "lon": round(snap.longitude, 6),
        "alt": round(snap.baro_altitude, 1),
        "vel": round(snap.vertical_velocity, 1),
        "max_alt": round(snap.max_altitude, 1),
        "img": snap.image_name,
        "eject": snap.payload_ejected,
        "glider": snap.glider_deployed,
        "act": snap.actuation_enabled,
        "gps": snap.gps_ok,
        "cam": snap.camera_ok,
        "imu": snap.imu_ok,
        "ahrs": snap.ahrs_healthy,
        "src": snap.ahrs_source,
        "r": round(snap.ahrs_roll if snap.ahrs_valid else snap.roll, 1),
        "p": round(snap.ahrs_pitch if snap.ahrs_valid else snap.pitch, 1),
        "y": round(snap.ahrs_yaw if snap.ahrs_valid else snap.yaw, 1),
        "battery": round(snap.battery, 1),
        "vbat": round(snap.bus_voltage_v, 2),
        "amps": round(snap.current_a, 2),
        "tx": snap.telemetry_tx_count,
        "log_rows": snap.logger_rows_written,
        "cam_seq": snap.camera_capture_sequence,
        "cam_fail": snap.camera_failed_captures,
        "status": snap.status,
        "t": round(snap.mission_time, 2),
    }
    return json.dumps(packet, separators=(",", ":"))


def parse_telemetry_packet(raw: str) -> dict:
    """Parse a telemetry JSON string back into a dict."""
    return json.loads(raw)
