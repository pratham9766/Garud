"""
Single servo hardware test.

Wiring:
  PCA9685 servo controller -> I2C SDA/SCL on the GARUDA HAT
  OE                       -> GPIO4 (physical pin 7)
  Servo VCC (red)          -> external 5V rail from servo supply
  Servo GND (brown/black)  -> common GND with Pi

Run from project root:
  python hardware_tests/test_servo_real.py
"""

from __future__ import annotations

import sys
import time

from hw_common import banner, ensure_dirs, is_raspberry_pi, result, write_log

import config

SERVO_CHANNEL = config.GIMBAL_PAN_CHANNEL
SWEEP_ANGLES = [0, 45, 90, 45, 0]
STEP_DELAY_SEC = 1.5


def main() -> int:
    banner("Hardware Test: Single Servo (PCA9685)")
    ensure_dirs()
    log_lines: list[str] = []

    print(f"Servo controller: PCA9685 at I2C address 0x{config.SERVO_CONTROLLER_ADDRESS:02X}")
    print(f"I2C pins:         SDA=GPIO{config.I2C_SDA_PIN} pin 3, SCL=GPIO{config.I2C_SCL_PIN} pin 5")
    print(f"OE pin:           GPIO{config.SERVO_OE_PIN} (physical pin 7)")
    print(f"Servo channel:    {SERVO_CHANNEL}")
    print(f"Sweep sequence:   {SWEEP_ANGLES} degrees")
    print(f"Step delay:       {STEP_DELAY_SEC}s between moves")
    print()
    result(
        "WARNING",
        "Do not power servos from Raspberry Pi 5V. Use the HAT servo power rail "
        "and keep Pi, HAT, and servo grounds common.",
    )
    log_lines.append("External power warning shown")
    print()

    if not is_raspberry_pi():
        result("WARNING", "Not running on Raspberry Pi - I2C servo control will not work.")
        log_lines.append("WARNING: not on Pi")

    try:
        from adafruit_servokit import ServoKit
    except ImportError:
        result("FAIL", "adafruit-circuitpython-servokit not installed.")
        print("Install: pip install adafruit-circuitpython-servokit")
        write_log("test_servo_real.log", ["FAIL: adafruit_servokit missing"])
        return 1

    kit = None
    try:
        kit = ServoKit(channels=16, address=config.SERVO_CONTROLLER_ADDRESS)
        servo = kit.servo[SERVO_CHANNEL]
        servo.set_pulse_width_range(500, 2500)
    except Exception as exc:
        result("FAIL", f"Cannot init PCA9685 servo channel {SERVO_CHANNEL}: {exc}")
        print("Check I2C wiring, HAT power, and run: python hardware_tests/test_i2c_scan.py")
        write_log("test_servo_real.log", [f"FAIL: {exc}"])
        return 1

    result("INFO", f"Using PCA9685 channel {SERVO_CHANNEL}.")
    log_lines.append(f"PCA9685 channel: {SERVO_CHANNEL}")

    try:
        for angle in SWEEP_ANGLES:
            print(f"  -> Moving to {angle} degrees")
            log_lines.append(f"Angle: {angle}")
            servo.angle = angle
            time.sleep(STEP_DELAY_SEC)

        servo.angle = 0
        time.sleep(0.5)
        servo.angle = None

        result("PASS", f"Servo sweep completed on PCA9685 channel {SERVO_CHANNEL}.")
        log_lines.append("PASS")
        code = 0

    except Exception as exc:
        result("FAIL", f"Servo movement error: {exc}")
        log_lines.append(f"FAIL: {exc}")
        code = 1
    finally:
        if kit is not None:
            kit.servo[SERVO_CHANNEL].angle = None

    log_path = write_log("test_servo_real.log", log_lines)
    print(f"Log saved: {log_path}")
    return code


if __name__ == "__main__":
    sys.exit(main())
