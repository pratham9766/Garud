"""
Compact JSON telemetry packet builder.
"""

from __future__ import annotations

import json

from core.shared_data import PayloadSnapshot


def build_telemetry_packet(snap: PayloadSnapshot) -> str:
    """
    Build a compact JSON telemetry string from a payload snapshot.

    Fields: state, lat, lon, alt, img, gps, cam, imu, battery, status
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
        "battery": round(snap.battery, 1),
        "status": snap.status,
    }
    return json.dumps(packet, separators=(",", ":"))


def parse_telemetry_packet(raw: str) -> dict:
    """Parse a telemetry JSON string back into a dict."""
    return json.loads(raw)
