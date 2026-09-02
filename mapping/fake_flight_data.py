"""
Generate synthetic flight CSV data for offline map testing.

No hardware required — produces a realistic descent profile near Pune.
"""

from __future__ import annotations

import math
import random
import time
import csv
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

    Simulates ascent to apogee, ejection, glider deployment at 600 m AGL, and
    periodic descent image capture events.

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
    apogee_m = config.TARGET_APOGEE_AGL_M
    boot_end = 2.0
    armed_end = 5.0
    boost_end = 9.0
    apogee_time = max(12.0, duration_sec * 0.35)
    glider_time = max(apogee_time + 1.0, duration_sec * 0.60)
    landed_start = duration_sec - 2.0

    image_interval = duration_sec / max(num_images, 1)
    next_image_at = image_interval

    rows: list[dict[str, object]] = []
    t = 0.0
    step = 0
    max_altitude = 0.0
    last_altitude = 0.0
    base_timestamp = time.time()

    while t <= duration_sec:
        if t < boot_end:
            state = MissionState.DISARMED.value
        elif t < armed_end:
            state = MissionState.ARMED_PAD.value
        elif t < boost_end:
            state = MissionState.BOOST.value
        elif t < apogee_time:
            state = MissionState.COAST.value
        elif t < apogee_time + 1.0:
            state = MissionState.APOGEE.value
        elif t < glider_time:
            state = MissionState.DESCENT_DROGUE.value
        elif t < glider_time + 1.0:
            state = MissionState.GLIDER_DEPLOY.value
        elif t < landed_start:
            state = MissionState.GUIDED_DESCENT.value
        else:
            state = MissionState.LANDED.value

        angle = step * 0.1
        lat += 0.00002 * math.sin(angle) + random.uniform(-0.000003, 0.000003)
        lon += 0.00002 * math.cos(angle) + random.uniform(-0.000003, 0.000003)
        if t < armed_end:
            altitude = 0.0
        elif t < apogee_time:
            climb_fraction = (t - armed_end) / max(apogee_time - armed_end, 1.0)
            altitude = apogee_m * math.sin(climb_fraction * math.pi / 2.0)
        elif t < landed_start:
            descent_fraction = (t - apogee_time) / max(landed_start - apogee_time, 1.0)
            altitude = max(0.0, apogee_m * (1.0 - descent_fraction))
        else:
            altitude = 0.0
        vertical_velocity = (altitude - last_altitude) / max(interval_sec, 1e-3)
        last_altitude = altitude
        max_altitude = max(max_altitude, altitude)

        roll = 5.0 * math.sin(t * 0.3) + random.uniform(-0.5, 0.5)
        pitch = 3.0 * math.cos(t * 0.2) + random.uniform(-0.5, 0.5)
        yaw = (t * 8.0) % 360.0
        gyro_x = 1.5 * math.cos(t * 0.3)
        gyro_y = -0.6 * math.sin(t * 0.2)
        gyro_z = 8.0
        accel_z = 9.80665
        if state == MissionState.BOOST.value:
            accel_z = 22.0
        elif state == MissionState.COAST.value:
            accel_z = 8.5

        image_name = ""
        image_timestamp = 0.0
        capture_states = {
            MissionState.APOGEE.value,
            MissionState.DESCENT_DROGUE.value,
            MissionState.GLIDER_DEPLOY.value,
            MissionState.GUIDED_DESCENT.value,
        }
        timestamp = base_timestamp + t
        if t >= next_image_at and state in capture_states:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            image_name = f"fake_img_{ts}_{step}.jpg"
            image_timestamp = timestamp
            next_image_at += image_interval

        battery = max(0.0, 100.0 - (t / duration_sec) * 15.0)
        rows.append(
            {
                "timestamp": f"{timestamp:.3f}",
                "mission_time": f"{t:.3f}",
                "state": state,
                "latitude": f"{lat:.6f}",
                "longitude": f"{lon:.6f}",
                "gps_altitude": f"{altitude:.2f}",
                "baro_altitude": f"{altitude:.2f}",
                "vertical_velocity": f"{vertical_velocity:.2f}",
                "max_altitude": f"{max_altitude:.2f}",
                "roll": f"{roll:.2f}",
                "pitch": f"{pitch:.2f}",
                "yaw": f"{yaw:.2f}",
                "gyro_x": f"{gyro_x:.3f}",
                "gyro_y": f"{gyro_y:.3f}",
                "gyro_z": f"{gyro_z:.3f}",
                "image_name": image_name,
                "image_timestamp": f"{image_timestamp:.3f}",
                "battery": f"{battery:.1f}",
                "status": "OK",
                "raw_accel_z": f"{accel_z:.4f}",
                "launch_detected": int(t >= armed_end),
                "apogee_detected": int(t >= apogee_time),
                "payload_ejected": int(t >= apogee_time),
                "glider_deployed": int(t >= glider_time),
                "actuation_enabled": int(state == MissionState.GUIDED_DESCENT.value),
            }
        )
        t += interval_sec
        step += 1

    headers = SharedData.CSV_HEADER.split(",")
    try:
        handle = open(output_path, "w", newline="", encoding="utf-8")
    except PermissionError:
        fallback_name = f"{output_path.stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{output_path.suffix}"
        output_path = output_path.with_name(fallback_name)
        handle = open(output_path, "w", newline="", encoding="utf-8")

    with handle:
        writer = csv.DictWriter(handle, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({header: row.get(header, 0) for header in headers})
    return output_path


if __name__ == "__main__":
    path = generate_fake_flight_csv()
    print(f"Fake flight CSV written: {path}")
