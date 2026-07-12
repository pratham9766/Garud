"""
Generate synthetic flight CSV data for offline map testing.

No hardware required — produces a realistic descent profile near Pune.
"""

from __future__ import annotations

import math
import random
from datetime import datetime
from pathlib import Path

import config
from core.mission_state import MissionState
from core.shared_data import SharedData


def generate_fake_flight_csv(
    output_path: Path | None = None,
    duration_sec: float = 60.0,
    interval_sec: float = 1.0,
    num_images: int = 10,
) -> Path:
    """
    Write a synthetic flight CSV log for map/KML testing.

    Simulates descent from ~700 m with GPS drift around Pune and
    periodic image capture events.

    Args:
        output_path: Destination CSV path.
        duration_sec: Total simulated mission duration.
        interval_sec: Seconds between log rows.
        num_images: Number of image capture events to include.

    Returns:
        Path to the generated CSV file.
    """
    output_path = output_path or (config.LOG_SAVE_PATH / "fake_flight_log.csv")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    lat = config.MOCK_GPS_LAT
    lon = config.MOCK_GPS_LON
    altitude = config.MOCK_START_ALTITUDE_M
    descent_rate = altitude / max(duration_sec, 1.0)

    states = [MissionState.BOOT.value]
    # Rough state timeline
    boot_end = 2.0
    idle_end = 5.0
    landed_start = duration_sec - 2.0

    image_interval = duration_sec / max(num_images, 1)
    next_image_at = image_interval

    rows: list[str] = [SharedData.CSV_HEADER]
    t = 0.0
    step = 0

    while t <= duration_sec:
        if t < boot_end:
            state = MissionState.BOOT.value
        elif t < idle_end:
            state = MissionState.IDLE.value
        elif t < landed_start:
            state = MissionState.DESCENT.value
        else:
            state = MissionState.LANDED.value

        angle = step * 0.1
        lat += 0.00002 * math.sin(angle) + random.uniform(-0.000003, 0.000003)
        lon += 0.00002 * math.cos(angle) + random.uniform(-0.000003, 0.000003)
        altitude = max(0.0, altitude - descent_rate * interval_sec)

        roll = 5.0 * math.sin(t * 0.3) + random.uniform(-0.5, 0.5)
        pitch = 3.0 * math.cos(t * 0.2) + random.uniform(-0.5, 0.5)
        yaw = (t * 8.0) % 360.0

        image_name = ""
        if t >= next_image_at and state == MissionState.DESCENT.value:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            image_name = f"fake_img_{ts}_{step}.jpg"
            next_image_at += image_interval

        battery = max(0.0, 100.0 - (t / duration_sec) * 15.0)
        timestamp = datetime.now().timestamp() + t

        row = (
            f"{timestamp:.3f},{t:.3f},{state},"
            f"{lat:.6f},{lon:.6f},"
            f"{altitude:.2f},{altitude:.2f},"
            f"{roll:.2f},{pitch:.2f},{yaw:.2f},"
            f"{image_name},{battery:.1f},OK"
        )
        rows.append(row)
        t += interval_sec
        step += 1

    output_path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return output_path


if __name__ == "__main__":
    path = generate_fake_flight_csv()
    print(f"Fake flight CSV written: {path}")
