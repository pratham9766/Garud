"""
2-axis gimbal hardware test (pan + tilt servos).

Wiring:
  Pan servo signal  -> GPIO18 (physical pin 12)
  Tilt servo signal -> GPIO19 (physical pin 35)
  Both VCC          -> EXTERNAL 5V supply (common BEC)
  Both GND          -> Common GND with Pi

Run from project root:
  python hardware_tests/test_gimbal_real.py
"""

from __future__ import annotations

import sys
import time

from hw_common import banner, ensure_dirs, is_raspberry_pi, result, write_log

PAN_SERVO_PIN = 18
TILT_SERVO_PIN = 19
CENTER_PAN = 90
CENTER_TILT = 90
STEP_DELAY_SEC = 1.2

# Safe small movements from center (degrees)
MOVEMENTS = [
    ("center", CENTER_PAN, CENTER_TILT),
    ("pan left", CENTER_PAN - 20, CENTER_TILT),
    ("pan right", CENTER_PAN + 20, CENTER_TILT),
    ("tilt up", CENTER_PAN, CENTER_TILT - 15),
    ("tilt down", CENTER_PAN, CENTER_TILT + 15),
    ("center", CENTER_PAN, CENTER_TILT),
]


def create_servo(pin: int):
    """Create an AngularServo on the given GPIO pin."""
    from gpiozero import AngularServo

    try:
        from gpiozero.pins.pigpio import PiGPIOFactory

        return AngularServo(pin, min_angle=0, max_angle=180, pin_factory=PiGPIOFactory())
    except Exception:
        return AngularServo(pin, min_angle=0, max_angle=180)


def main() -> int:
    banner("Hardware Test: 2-Axis Gimbal")
    ensure_dirs()
    log_lines: list[str] = []

    print(f"Pan servo (GPIO{PAN_SERVO_PIN}, pin 12):  left/right")
    print(f"Tilt servo (GPIO{TILT_SERVO_PIN}, pin 35): up/down")
    print(f"Center position: pan={CENTER_PAN}° tilt={CENTER_TILT}°")
    print()
    result(
        "WARNING",
        "Do not power servos from Raspberry Pi 5V. "
        "Use external 5V supply and common GND.",
    )
    log_lines.append("External power warning shown")
    print()

    if not is_raspberry_pi():
        result("WARNING", "Not running on Raspberry Pi — GPIO servos will not work.")
        log_lines.append("WARNING: not on Pi")

    pan = tilt = None
    try:
        pan = create_servo(PAN_SERVO_PIN)
        tilt = create_servo(TILT_SERVO_PIN)
    except ImportError:
        result("FAIL", "gpiozero not installed.")
        print("Install: sudo apt install -y python3-gpiozero pigpio")
        write_log("test_gimbal_real.log", ["FAIL: gpiozero missing"])
        return 1
    except Exception as exc:
        result("FAIL", f"Cannot init gimbal servos: {exc}")
        write_log("test_gimbal_real.log", [f"FAIL: {exc}"])
        return 1

    result("INFO", f"Pan=GPIO{PAN_SERVO_PIN}, Tilt=GPIO{TILT_SERVO_PIN}")
    log_lines.append(f"Pins: pan={PAN_SERVO_PIN} tilt={TILT_SERVO_PIN}")

    try:
        for label, pan_angle, tilt_angle in MOVEMENTS:
            print(f"  -> {label}: pan={pan_angle}° tilt={tilt_angle}°")
            log_lines.append(f"{label}: pan={pan_angle} tilt={tilt_angle}")
            pan.angle = pan_angle
            tilt.angle = tilt_angle
            time.sleep(STEP_DELAY_SEC)

        pan.detach()
        tilt.detach()
        result("PASS", "Gimbal movement sequence completed.")
        log_lines.append("PASS")
        code = 0

    except Exception as exc:
        result("FAIL", f"Gimbal error: {exc}")
        log_lines.append(f"FAIL: {exc}")
        code = 1
    finally:
        for s in (pan, tilt):
            if s is not None:
                try:
                    s.close()
                except Exception:
                    pass

    log_path = write_log("test_gimbal_real.log", log_lines)
    print(f"Log saved: {log_path}")
    return code


if __name__ == "__main__":
    sys.exit(main())
