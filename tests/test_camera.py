"""
Test mock camera capture.

Run from project root:
    python tests/test_camera.py
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import config
from camera.mock_camera import MockCamera


def test_camera() -> None:
    print("=" * 50)
    print("TEST: Mock Camera")
    print("=" * 50)

    config.IMAGE_SAVE_PATH.mkdir(parents=True, exist_ok=True)
    cam = MockCamera()

    filename = cam.capture(latitude=18.5204, longitude=73.8567)
    filepath = config.IMAGE_SAVE_PATH / filename

    assert filepath.exists(), f"Image not saved: {filepath}"
    assert filepath.stat().st_size > 0, "Image file is empty"
    print(f"[OK] Image captured: {filepath}")

    cam.close()
    print("\nCamera test passed.")


if __name__ == "__main__":
    test_camera()
