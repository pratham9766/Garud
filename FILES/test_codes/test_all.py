"""
test_all.py
-----------
Full integration test: timestamped sensor telemetry + PCA9685 servo
(channel 0) + ULN2003 stepper rotation.

Run with:  python3 test_all.py
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "libraries"))


import time

import bus_manager
from sensors.bno085_sensor import BNO085Sensor
from sensors.bmp388_sensor import BMP388Sensor
from actuators.servo_driver import PCA9685Driver
from actuators.stepper_driver import ULN2003Stepper
from actuators.buzzer import Buzzer


def log_telemetry(tag, imu, baro):
    ts = time.monotonic()
    imu_data = imu.read()
    baro_data = baro.read()
    print(f"\n[{ts:8.2f}s] {tag}")
    print(f"  accel (m/s2):   {tuple(round(v, 3) for v in imu_data['accel_ms2'])}")
    print(f"  gyro (rad/s):   {tuple(round(v, 3) for v in imu_data['gyro_rads'])}")
    print(f"  mag (uT):       {tuple(round(v, 2) for v in imu_data['mag_ut'])}")
    print(f"  lin_accel:      {tuple(round(v, 3) for v in imu_data['linear_accel_ms2'])}")
    print(f"  quaternion:     {tuple(round(v, 4) for v in imu_data['quaternion'])}")
    print(f"  alt (m):        {baro_data['altitude_m']:.2f}")
    print(f"  press (hPa):    {baro_data['pressure_hpa']:.2f}")
    print(f"  temp (C):       {baro_data['temperature_c']:.2f}")
    return ts


def main():
    i2c = bus_manager.get_i2c()
    spi = bus_manager.get_spi()

    imu = BNO085Sensor(i2c)
    baro = BMP388Sensor(spi)

    pwm = PCA9685Driver(i2c)
    pwm.enable_outputs()

    stepper = ULN2003Stepper()
    buzzer = Buzzer()
    buzzer.beep(0.1)

    t0 = time.monotonic()
    print(f"Test started at t={t0:.2f}s")

    log_telemetry("baseline", imu, baro)

    # --- Servo sweep: sequential 0->180->0 on channels 0, 1, 2 ---
    for ch in (0, 1, 2):
        print(f"\n>> Servo ch{ch} sweep: 0 -> 180 -> 0")
        for angle in [0, 45, 90, 135, 180, 90, 0]:
            pwm.set_angle(ch, angle)
            print(f"[{time.monotonic():8.2f}s] servo ch{ch} = {angle} deg")
            time.sleep(0.4)
        log_telemetry(f"after servo ch{ch} sweep", imu, baro)

    # --- Stepper forward / backward via ULN2003 ---
    print("\n>> Stepper +200 steps (forward)")
    stepper.step(200)
    log_telemetry("after stepper forward", imu, baro)

    print("\n>> Stepper -200 steps (backward)")
    stepper.step(-200)
    log_telemetry("after stepper backward", imu, baro)

    buzzer.beep_pattern(count=2)
    print(f"\nALL TESTS PASSED in {time.monotonic() - t0:.1f}s")

    stepper.release()
    pwm.disable_outputs()
    pwm.deinit()


if __name__ == "__main__":
    main()
