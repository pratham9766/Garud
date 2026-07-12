"""
Test telemetry packet building and mock transmission.

Run from project root:
    python tests/test_telemetry.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.shared_data import PayloadSnapshot
from telemetry.telemetry_packet import build_telemetry_packet, parse_telemetry_packet
from telemetry.xbee_sender import MockTelemetry


def test_telemetry() -> None:
    print("=" * 50)
    print("TEST: Telemetry")
    print("=" * 50)

    snap = PayloadSnapshot(
        state="DESCENT",
        latitude=18.5204,
        longitude=73.8567,
        baro_altitude=350.0,
        image_name="test_img.jpg",
        gps_ok=True,
        camera_ok=True,
        imu_ok=True,
        battery=92.5,
        status="OK",
    )

    packet = build_telemetry_packet(snap)
    print(f"  Packet: {packet}")

    data = parse_telemetry_packet(packet)
    assert data["state"] == "DESCENT"
    assert data["lat"] == 18.5204
    assert data["lon"] == 73.8567
    assert data["img"] == "test_img.jpg"
    assert data["gps"] is True
    print("[OK] Packet build/parse")

    radio = MockTelemetry()
    assert radio.send(packet) is True
    radio.close()
    print("[OK] Mock telemetry send")

    print("\nTelemetry test passed.")


if __name__ == "__main__":
    test_telemetry()
