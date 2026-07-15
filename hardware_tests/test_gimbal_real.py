"""
2-axis gimbal hardware test through the GARUDA HAT PCA9685 servo controller.

Wiring:
  PCA9685 servo controller -> I2C SDA/SCL on the GARUDA HAT
  OE                       -> GPIO4 (physical pin 7)
  Pan servo                -> PCA9685 channel from config.GIMBAL_PAN_CHANNEL
  Tilt servo               -> PCA9685 channel from config.GIMBAL_TILT_CHANNEL
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

PAN_SERVO_CHANNEL = config.GIMBAL_PAN_CHANNEL
TILT_SERVO_CHANNEL = config.GIMBAL_TILT_CHANNEL
CENTER_PAN = 90
CENTER_TILT = 90
STEP_DELAY_SEC = 1.2

MOVEMENTS = [
    ("center", CENTER_PAN, CENTER_TILT),
    ("pan left", CENTER_PAN - 20, CENTER_TILT),
    ("pan right", CENTER_PAN + 20, CENTER_TILT),
    ("tilt up", CENTER_PAN, CENTER_TILT - 15),
    ("tilt down", CENTER_PAN, CENTER_TILT + 15),
    ("center", CENTER_PAN, CENTER_TILT),
]


def main() -> int:
    banner("Hardware Test: 2-Axis Gimbal (PCA9685)")
    ensure_dirs()
    log_lines: list[str] = []

    print(f"Servo controller: PCA9685 at I2C address 0x{config.SERVO_CONTROLLER_ADDRESS:02X}")
    print(f"I2C pins:         SDA=GPIO{config.I2C_SDA_PIN} pin 3, SCL=GPIO{config.I2C_SCL_PIN} pin 5")
    print(f"OE pin:           GPIO{config.SERVO_OE_PIN} (physical pin 7)")
    print(f"Pan channel:      {PAN_SERVO_CHANNEL}")
    print(f"Tilt channel:     {TILT_SERVO_CHANNEL}")
    print(f"Center position:  pan={CENTER_PAN} deg tilt={CENTER_TILT} deg")
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
        write_log("test_gimbal_real.log", ["FAIL: adafruit_servokit missing"])
        return 1

    kit = None
    try:
        kit = ServoKit(channels=16, address=config.SERVO_CONTROLLER_ADDRESS)
        pan = kit.servo[PAN_SERVO_CHANNEL]
        tilt = kit.servo[TILT_SERVO_CHANNEL]
        pan.set_pulse_width_range(500, 2500)
        tilt.set_pulse_width_range(500, 2500)
    except Exception as exc:
        result("FAIL", f"Cannot init PCA9685 gimbal servos: {exc}")
        print("Check I2C wiring, HAT power, and run: python hardware_tests/test_i2c_scan.py")
        write_log("test_gimbal_real.log", [f"FAIL: {exc}"])
        return 1

    result("INFO", f"Pan=channel {PAN_SERVO_CHANNEL}, Tilt=channel {TILT_SERVO_CHANNEL}")
    log_lines.append(f"Channels: pan={PAN_SERVO_CHANNEL} tilt={TILT_SERVO_CHANNEL}")

    try:
        for label, pan_angle, tilt_angle in MOVEMENTS:
            print(f"  -> {label}: pan={pan_angle} deg tilt={tilt_angle} deg")
            log_lines.append(f"{label}: pan={pan_angle} tilt={tilt_angle}")
            pan.angle = pan_angle
            tilt.angle = tilt_angle
            time.sleep(STEP_DELAY_SEC)

        pan.angle = None
        tilt.angle = None
        result("PASS", "Gimbal movement sequence completed.")
        log_lines.append("PASS")
        code = 0

    except Exception as exc:
        result("FAIL", f"Gimbal error: {exc}")
        log_lines.append(f"FAIL: {exc}")
        code = 1
    finally:
        if kit is not None:
            kit.servo[PAN_SERVO_CHANNEL].angle = None
            kit.servo[TILT_SERVO_CHANNEL].angle = None

    log_path = write_log("test_gimbal_real.log", log_lines)
    print(f"Log saved: {log_path}")
    return code


if __name__ == "__main__":
    sys.exit(main())
