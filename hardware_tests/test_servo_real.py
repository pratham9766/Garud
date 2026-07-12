"""
Single servo hardware test.

Wiring:
  Servo signal (orange/yellow) -> GPIO18 (physical pin 12)
  Servo VCC (red)              -> EXTERNAL 5V supply (NOT Pi 5V pin)
  Servo GND (brown/black)      -> Common GND with Pi

Run from project root:
  python hardware_tests/test_servo_real.py
"""

from __future__ import annotations

import sys
import time

from hw_common import banner, ensure_dirs, is_raspberry_pi, result, write_log

# Default pitch servo pin from project pin map
SERVO_PIN = 18
SWEEP_ANGLES = [0, 45, 90, 45, 0]
STEP_DELAY_SEC = 1.5


def main() -> int:
    banner("Hardware Test: Single Servo")
    ensure_dirs()
    log_lines: list[str] = []

    print(f"Servo signal pin: GPIO{SERVO_PIN} (physical pin 12)")
    print(f"Sweep sequence:   {SWEEP_ANGLES} degrees")
    print(f"Step delay:       {STEP_DELAY_SEC}s between moves")
    print()
    result(
        "WARNING",
        "Do not power servo from Raspberry Pi 5V for serious testing. "
        "Use external 5V supply and common GND.",
    )
    log_lines.append("External power warning shown")
    print()

    if not is_raspberry_pi():
        result("WARNING", "Not running on Raspberry Pi — servo GPIO will not work.")
        log_lines.append("WARNING: not on Pi")

    servo = None
    backend = ""

    # --- Try gpiozero AngularServo ---
    try:
        from gpiozero import AngularServo
        from gpiozero.pins.pigpio import PiGPIOFactory

        factory = PiGPIOFactory()
        servo = AngularServo(
            SERVO_PIN,
            min_angle=0,
            max_angle=180,
            pin_factory=factory,
        )
        backend = f"gpiozero AngularServo GPIO{SERVO_PIN} (pigpio)"
    except ImportError:
        result("WARNING", "gpiozero/pigpio not available — trying gpiozero default.")
    except Exception as exc:
        result("WARNING", f"pigpio backend failed: {exc} — trying default pin factory.")

    if servo is None:
        try:
            from gpiozero import AngularServo

            servo = AngularServo(SERVO_PIN, min_angle=0, max_angle=180)
            backend = f"gpiozero AngularServo GPIO{SERVO_PIN}"
        except ImportError:
            result("FAIL", "gpiozero not installed.")
            print("Install: sudo apt install -y python3-gpiozero")
            print("For stable PWM: sudo apt install -y pigpio && sudo systemctl enable pigpiod")
            write_log("test_servo_real.log", ["FAIL: gpiozero missing"])
            return 1
        except Exception as exc:
            result("FAIL", f"Cannot init servo on GPIO{SERVO_PIN}: {exc}")
            write_log("test_servo_real.log", [f"FAIL: {exc}"])
            return 1

    result("INFO", f"Using backend: {backend}")
    log_lines.append(f"Backend: {backend}")

    try:
        for angle in SWEEP_ANGLES:
            print(f"  -> Moving to {angle}°")
            log_lines.append(f"Angle: {angle}")
            servo.angle = angle
            time.sleep(STEP_DELAY_SEC)

        # Return to neutral and release
        servo.angle = 0
        time.sleep(0.5)
        servo.detach()

        result("PASS", f"Servo sweep completed on GPIO{SERVO_PIN}.")
        log_lines.append("PASS")
        code = 0

    except Exception as exc:
        result("FAIL", f"Servo movement error: {exc}")
        log_lines.append(f"FAIL: {exc}")
        code = 1
    finally:
        if servo is not None:
            try:
                servo.close()
            except Exception:
                pass

    log_path = write_log("test_servo_real.log", log_lines)
    print(f"Log saved: {log_path}")
    return code


if __name__ == "__main__":
    sys.exit(main())
