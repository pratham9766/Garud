"""
gimbal_diag.py
---------------
Bench diagnostic for the two-axis camera gimbal. No control loop, just
raw hardware + axis mapping checks so we can separate wiring problems
from tuning problems.

Tests (in order):
  1. STEPPER  - rotates the stage +200 then -200 steps, you watch the
                shaft. If nothing moves, check the ULN2003 5 V supply.
  2. AXES     - live 4 Hz printout of gyro + accelerometer. Slowly
                SPIN the rig about the optical axis (roll): gz and the
                projected roll_rate should jump.  PITCH it: gy and the
                projected tilt_rate should jump.  Both directions.
  3. SERVO    - sweeps the tilt servo 60 -> 120 -> 60 deg so you can
                confirm PWM channel 0 wiring and direction.

Run with:  python3 gimbal_diag.py
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "libraries"))


import time

import bus_manager
import config
from actuators.gimbal import GimbalController
from actuators.stepper_driver import ULN2003Stepper
from actuators.servo_driver import PCA9685Driver
from sensors.bno085_sensor import BNO085Sensor


def wait_enter(msg):
    print(f"\n>>> {msg}")
    try:
        input("    Press Enter to run this test, or Ctrl+C to quit...")
    except KeyboardInterrupt:
        raise SystemExit("\nDiagnostic stopped.")


def test_stepper(stepper):
    print(f"  Stepper +200 steps ({200 / config.GIMBAL_STEPS_PER_DEG:.0f} deg)")
    stepper.step(200)
    time.sleep(1.0)
    print("  Stepper -200 steps")
    stepper.step(-200)
    stepper.release()


def test_axes(imu, gimbal):
    print("  Spin the rig about the optical axis -> roll_rate should jump.")
    print("  Pitch it -> tilt_rate should jump.  Both directions, ~8 s.")
    t0 = time.monotonic()
    while time.monotonic() - t0 < 8.0:
        gx, gy, gz = imu.read()["gyro_rads"]
        ax, ay, az = imu.read()["accel_ms2"]
        w = (gx, gy, gz)
        roll_rate = gimbal._dot(w, gimbal._roll_axis) * 57.2958
        tilt_rate = gimbal._dot(w, gimbal._rotate(
            gimbal._servo_axis_zero, gimbal.roll_deg)) * 57.2958
        print(f"  gyro gx {gx * 57.2958:+7.1f} gy {gy * 57.2958:+7.1f} "
              f"gz {gz * 57.2958:+7.1f} deg/s | "
              f"roll_rate {roll_rate:+7.1f} tilt_rate {tilt_rate:+7.1f} | "
              f"accel ax {ax:+6.1f} ay {ay:+6.1f} az {az:+6.1f}")
        time.sleep(0.25)
    print("  Axis test done.")


def test_servo(pwm):
    for angle in (60.0, 120.0, 60.0):
        pwm.set_angle(config.GIMBAL_SERVO_CHANNEL, angle)
        print(f"  Servo -> {angle:5.1f} deg")
        time.sleep(1.5)


def main():
    i2c = bus_manager.get_i2c()

    imu = BNO085Sensor(i2c)
    pwm = PCA9685Driver(i2c)
    pwm.enable_outputs()
    stepper = ULN2003Stepper()
    gimbal = GimbalController(imu, pwm, stepper)

    print("gimbal_diag - bench hardware + axis check")
    print(f"  stepper pins: {config.ULN2003_IN1_PIN} {config.ULN2003_IN2_PIN} "
          f"{config.ULN2003_IN3_PIN} {config.ULN2003_IN4_PIN}")
    print(f"  roll axis {config.GIMBAL_ROLL_AXIS} | "
          f"servo axis @0 {config.GIMBAL_SERVO_AXIS_ZERO}")

    wait_enter("Test 1: STEPPER rotation")
    test_stepper(stepper)

    wait_enter("Test 2: IMU axis mapping")
    test_axes(imu, gimbal)

    wait_enter("Test 3: SERVO sweep")
    test_servo(pwm)

    gimbal.release()
    print("\nAll diagnostics complete.")


if __name__ == "__main__":
    main()
