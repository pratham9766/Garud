"""Small post-flight mapping pipeline test."""

from __future__ import annotations

import csv
import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from processing.mapping_pipeline import run_mapping_pipeline


def test_small_pipeline_writes_report() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        images = root / "images"
        images.mkdir()
        csv_path = root / "mission.csv"
        for idx, name in enumerate(("img_001.jpg", "img_002.jpg")):
            image = np.zeros((180, 220, 3), dtype=np.uint8)
            cv2.rectangle(image, (30 + idx * 4, 30), (170 + idx * 4, 140), (210, 210, 210), -1)
            cv2.circle(image, (90 + idx * 4, 80), 25, (30, 30, 30), 2)
            cv2.imwrite(str(images / name), image)

        with open(csv_path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "timestamp",
                    "state",
                    "latitude",
                    "longitude",
                    "gps_altitude",
                    "baro_altitude",
                    "roll",
                    "pitch",
                    "yaw",
                    "gyro_x",
                    "gyro_y",
                    "gyro_z",
                    "image_name",
                    "image_timestamp",
                ],
            )
            writer.writeheader()
            for idx, name in enumerate(("img_001.jpg", "img_002.jpg")):
                writer.writerow(
                    {
                        "timestamp": float(idx + 1),
                        "state": "DESCENT",
                        "latitude": 18.5204 + idx * 0.00002,
                        "longitude": 73.8567 + idx * 0.00002,
                        "gps_altitude": 100.0,
                        "baro_altitude": 95.0,
                        "roll": 1.0,
                        "pitch": 1.0,
                        "yaw": 2.0,
                        "gyro_x": 1.0,
                        "gyro_y": 1.0,
                        "gyro_z": 1.0,
                        "image_name": name,
                        "image_timestamp": float(idx + 1),
                    }
                )
        result = run_mapping_pipeline(
            csv_path,
            image_dir=images,
            output_base=root / "postflight",
            profile_name="fast",
            skip_dense=True,
            skip_orthomosaic=True,
        )
        assert result.report.total_images == 2
        assert result.report.candidate_edges >= 1
        assert (result.output_dir / "quality" / "reconstruction_report.json").exists()


if __name__ == "__main__":
    test_small_pipeline_writes_report()
    print("Small mapping pipeline test passed.")
