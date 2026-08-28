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
        "state": snap.state,
        "lat": round(snap.latitude, 6),
        "lon": round(snap.longitude, 6),
        "alt": round(snap.baro_altitude, 1),
        "img": snap.image_name,
        "gps": snap.gps_ok,
        "cam": snap.camera_ok,
        "imu": snap.imu_ok,
        "ahrs": snap.ahrs_healthy,
        "src": snap.ahrs_source,
        "r": round(snap.ahrs_roll if snap.ahrs_valid else snap.roll, 1),
        "p": round(snap.ahrs_pitch if snap.ahrs_valid else snap.pitch, 1),
        "y": round(snap.ahrs_yaw if snap.ahrs_valid else snap.yaw, 1),
        "battery": round(snap.battery, 1),
        "status": snap.status,
    }
    return json.dumps(packet, separators=(",", ":"))


def parse_telemetry_packet(raw: str) -> dict:
    """Parse a telemetry JSON string back into a dict."""
    return json.loads(raw)
