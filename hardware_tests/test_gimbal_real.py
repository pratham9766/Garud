"""
2-axis gimbal hardware test through the GARUDA HAT stepper + PCA9685 servo.

Wiring:
  Stepper                  -> ULN2003 pins from config.ULN2003_IN*
  Servo                    -> PCA9685 channel config.GIMBAL_SERVO_CHANNEL
  Servo VCC                -> external 5V rail from servo supply
  Servo GND                -> common GND with Pi

Run from project root:
  python hardware_tests/test_gimbal_real.py
"""

from __future__ import annotations

import sys
import time

from hw_common import banner, ensure_dirs, is_raspberry_pi, result, write_log

import config

SERVO_CHANNEL = config.GIMBAL_SERVO_CHANNEL
STEP_DELAY_SEC = 1.2

MOVEMENTS = [
    ("center", 0.0, 0.0),
    ("opp x deflect +12", 12.0, 0.0),
    ("opp x deflect -12", -12.0, 0.0),
    ("opp y deflect +10", 0.0, 10.0),
    ("opp y deflect -10", 0.0, -10.0),
    ("combined", 8.0, -8.0),
    ("center", 0.0, 0.0),
]


def main() -> int:
    banner("Hardware Test: Gimbal Stepper + Servo")
    ensure_dirs()
    log_lines: list[str] = []

    print(f"Servo controller: PCA9685 at I2C address 0x{config.SERVO_CONTROLLER_ADDRESS:02X}")
    print(f"I2C pins:         SDA=GPIO{config.I2C_SDA_PIN} pin 3, SCL=GPIO{config.I2C_SCL_PIN} pin 5")
    print(f"OE pin:           GPIO{config.SERVO_OE_PIN} (physical pin 7)")
    print(f"Servo channel:    {SERVO_CHANNEL} (opposite Y axis)")
    print(
        "Stepper pins:     "
        f"IN1=GPIO{config.ULN2003_IN1_PIN}, IN2=GPIO{config.ULN2003_IN2_PIN}, "
        f"IN3=GPIO{config.ULN2003_IN3_PIN}, IN4=GPIO{config.ULN2003_IN4_PIN} "
        "(opposite X axis)"
    )
    print(f"Center servo:     {config.GIMBAL_SERVO_CENTER} deg")
    print()
    result(
        "WARNING",
        "Use external servo/stepper power sized for motor current and keep Pi, "
        "HAT, and motor grounds common.",
    )
    log_lines.append("External power warning shown")
    print()

    if not is_raspberry_pi():
        result("WARNING", "Not running on Raspberry Pi - GPIO/I2C motor control will not work.")
        log_lines.append("WARNING: not on Pi")

    try:
        from gimbal.servo_control import create_gimbal
    except ImportError as exc:
        result("FAIL", f"Gimbal imports failed: {exc}")
        print("Install: pip install adafruit-circuitpython-servokit")
        write_log("test_gimbal_real.log", [f"FAIL: import {exc}"])
        return 1

    gimbal = None
    try:
        config.USE_MOCK_HARDWARE = False
        gimbal = create_gimbal()
    except Exception as exc:
        result("FAIL", f"Cannot init gimbal: {exc}")
        print("Check I2C wiring, HAT power, ULN2003 pins, and run: python hardware_tests/test_i2c_scan.py")
        write_log("test_gimbal_real.log", [f"FAIL: {exc}"])
        return 1

    result("INFO", f"Stepper axis={config.GIMBAL_STEPPER_AXIS}, servo channel={SERVO_CHANNEL}")
    log_lines.append(f"Stepper axis={config.GIMBAL_STEPPER_AXIS} servo={SERVO_CHANNEL}")

    try:
        for label, x_deflection, y_deflection in MOVEMENTS:
            command = gimbal.point_down(x_deflection, y_deflection, STEP_DELAY_SEC)
            line = (
                f"{label}: x_deflect={x_deflection:+.1f} y_deflect={y_deflection:+.1f} "
                f"stepper={command['stepper_angle_deg']:+.1f} "
                f"servo={command['servo_angle_deg']:+.1f} "
                f"steps={command['stepper_steps']}"
            )
            print(f"  -> {line}")
            log_lines.append(line)
            time.sleep(STEP_DELAY_SEC)

        result("PASS", "Gimbal movement sequence completed.")
        log_lines.append("PASS")
        code = 0

    except Exception as exc:
        result("FAIL", f"Gimbal error: {exc}")
        log_lines.append(f"FAIL: {exc}")
        code = 1
    finally:
        if gimbal is not None:
            gimbal.close()

    log_path = write_log("test_gimbal_real.log", log_lines)
    print(f"Log saved: {log_path}")
    return code


if __name__ == "__main__":
    sys.exit(main())
