"""
Real Raspberry Pi camera test using picamera2.

Wiring:
  HQ / Arducam camera -> CSI ribbon cable -> CAMERA port on Pi
  Enable camera: sudo raspi-config -> Interface Options -> Camera

Run from project root:
  python hardware_tests/test_camera_real.py
"""

from __future__ import annotations

import sys
import time
from datetime import datetime

from hw_common import HW_IMAGE_DIR, banner, ensure_dirs, is_raspberry_pi, result, write_log


def main() -> int:
    banner("Hardware Test: Real Camera (picamera2)")
    ensure_dirs()
    log_lines: list[str] = []

    print("Connection: CSI ribbon cable to CAMERA port")
    print(f"Save path:  {HW_IMAGE_DIR}")
    print("Captures:   3 images, 2 seconds apart")
    print()

    if not is_raspberry_pi():
        result("WARNING", "Not running on Raspberry Pi — camera test will likely fail.")
        log_lines.append("WARNING: not on Pi")

    try:
        from picamera2 import Picamera2
    except ImportError:
        result("FAIL", "picamera2 not installed.")
        print("Install: sudo apt install -y python3-picamera2")
        write_log("test_camera_real.log", ["FAIL: picamera2 missing"])
        return 1

    captured: list[str] = []

    try:
        picam = Picamera2()
        config = picam.create_still_configuration(main={"size": (1920, 1080)})
        picam.configure(config)
        picam.start()
        time.sleep(2)  # let auto-exposure settle

        for i in range(3):
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = HW_IMAGE_DIR / f"hw_camera_{ts}_{i + 1}.jpg"
            picam.capture_file(str(path))
            captured.append(str(path))
            print(f"  Captured: {path}")
            log_lines.append(f"Captured: {path}")
            if i < 2:
                time.sleep(2)

        picam.stop()
        picam.close()

    except Exception as exc:
        result("FAIL", f"Camera error: {exc}")
        log_lines.append(f"FAIL: {exc}")
        write_log("test_camera_real.log", log_lines)
        return 1

    missing = [p for p in captured if not __import__("pathlib").Path(p).exists()]
    if len(captured) == 3 and not missing:
        result("PASS", f"3 images saved to {HW_IMAGE_DIR}")
        log_lines.append("PASS: 3 images")
        code = 0
    else:
        result("FAIL", f"Expected 3 images, got {len(captured)} (missing: {missing})")
        log_lines.append("FAIL: incomplete capture")
        code = 1

    log_path = write_log("test_camera_real.log", log_lines)
    print(f"Log saved: {log_path}")
    return code


if __name__ == "__main__":
    sys.exit(main())
