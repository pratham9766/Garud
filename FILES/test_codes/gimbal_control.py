"""
gimbal_control.py
------------------
Standalone camera gimbal controller (orientation hold).

Reads the BNO085 gyro and drives:
  - 28BYJ-48 stepper (ULN2003)  -> ROLL counter-rotation
  - PCA9685 ch0 positional servo -> TILT counter-rotation

See actuators/gimbal.py for the control law; axes/signs live in
config.py. Run on the bench, roll/tilt the rig by hand and check the
camera holds level. If it amplifies motion instead of cancelling it,
flip GIMBAL_ROLL_SIGN / GIMBAL_TILT_SIGN in config.py.

Run with:  python3 gimbal_control.py
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


def main():
    i2c = bus_manager.get_i2c()

    imu = BNO085Sensor(i2c)
    pwm = PCA9685Driver(i2c)
    pwm.enable_outputs()
    stepper = ULN2003Stepper()

    gimbal = GimbalController(imu, pwm, stepper)
    print("Gimbal running (Ctrl+C to stop)...")
    print(f"  tick: {config.GIMBAL_LOOP_HZ} Hz | "
          f"roll sign {config.GIMBAL_ROLL_SIGN} | "
          f"tilt sign {config.GIMBAL_TILT_SIGN}")

    last_report = time.monotonic()
    window_steps = 0
    window_peak = 0.0
    try:
        while True:
            roll, tilt, roll_rate, steps, state, tilt_err = \
                gimbal.update(1.0 / config.GIMBAL_LOOP_HZ)
            window_steps += steps
            window_peak = max(window_peak, abs(roll_rate))
            now = time.monotonic()
            if now - last_report >= 0.5:
                print(f"[{now:8.2f}s] roll rate {roll_rate:+6.1f} deg/s "
                      f"(peak {window_peak:5.1f}) | "
                      f"steps/0.5s {window_steps:+4d} | "
                      f"stage {roll:7.1f} deg | "
                      f"tilt {tilt:6.1f} deg | tilt err {tilt_err:+6.1f} | "
                      f"{state}")
                last_report = now
                window_steps = 0
                window_peak = 0.0
            time.sleep(1.0 / config.GIMBAL_LOOP_HZ)
    except KeyboardInterrupt:
        print("\nStopping gimbal...")
    finally:
        gimbal.release()
        print("Gimbal released.")


if __name__ == "__main__":
    main()