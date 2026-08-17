"""
main.py
--------
MRIC CanSat - Garud HAT integration demo.

Ties together:
  - BNO085 IMU        (I2C1)
  - BMP388 barometer   (SPI0)
  - PCA9685 servo/PWM  (I2C1, /OE on GPIO4)
  - ULN2003 stepper    (GPIO25/24/23/18)
  - Buzzer             (GPIO16)

Run with:  python3 main.py
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


def main():
    # --- Shared buses ---
    i2c = bus_manager.get_i2c()
    spi = bus_manager.get_spi()

    # --- Sensors ---
    imu = BNO085Sensor(i2c)
    baro = BMP388Sensor(spi)
    # Set this on the pad right before launch for accurate AGL altitude:
    # baro.set_sea_level_pressure(<local QNH in hPa>)

    # --- Actuators ---
    pwm = None
    try:
        pwm = PCA9685Driver(i2c)
        pwm.enable_outputs()
    except Exception as e:
        print(f"WARNING: PCA9685 servo driver unavailable ({e})")

    stepper_motor = ULN2003Stepper()
    buzzer = Buzzer()
    buzzer.beep(0.1)   # power-on confirmation chirp

    # --- PCA9685 demo: sequential 0->180->0 sweep on channels 0, 1, 2 ---
    if pwm:
        for ch in (0, 1, 2):
            for angle in [0, 90, 180, 90, 0]:
                pwm.set_angle(ch, angle)
                time.sleep(0.3)

    # --- Stepper demo: 200 steps forward, 200 backward ---
    stepper_motor.step(200)
    stepper_motor.step(-200)
    stepper_motor.release()

    try:
        while True:
            imu_data = imu.read()
            baro_data = baro.read()

            print("---- Telemetry ----")
            print(f"Accel (m/s^2):      {imu_data['accel_ms2']}")
            print(f"Gyro (rad/s):       {imu_data['gyro_rads']}")
            print(f"Mag (uT):           {imu_data['mag_ut']}")
            print(f"Altitude (m):       {baro_data['altitude_m']:.2f}")
            print(f"Pressure (hPa):     {baro_data['pressure_hpa']:.2f}")
            print(f"Temperature (C):    {baro_data['temperature_c']:.2f}")

            # --- Example actuator calls (adapt to your mission logic) ---
            # stepper_motor.step(100)              # 100 steps forward
            # if baro_data["altitude_m"] < 5:
            #     buzzer.beep_pattern(count=5)     # recovery beacon on landing

            time.sleep(0.5)

    except KeyboardInterrupt:
        print("\nShutting down safely...")
    finally:
        if pwm:
            pwm.disable_outputs()
        stepper_motor.release()
        buzzer.off()


if __name__ == "__main__":
    main()
