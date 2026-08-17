"""
motor_emi_test.py
-----------------
Motor EMI test: runs the stepper + servos continuously while streaming
BNO085 (IMU/magnetometer) + BMP388 (baro) readings live on the terminal.

The magnetometer is the EMI-sensitive sensor - watch |m| and its spread
for spikes/offset while the motors are energized.

Motor pattern: first 5 s motors OFF (baseline |m|), then stepper rotates
continuously and servos sweep 0->180->0 on channels 0,1,2 until Ctrl+C.

Data: every sample appended to /tmp/opencode/emi_log.csv
      (t, mx, my, mz, mag_mag, motors_on, press, temp)

Run with:  python3 motor_emi_test.py
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "libraries"))


import csv
import math
import statistics
import threading
import time

import bus_manager
import config
from actuators.buzzer import Buzzer
from actuators.servo_driver import PCA9685Driver
from actuators.stepper_driver import ULN2003Stepper
from sensors.bmp388_sensor import BMP388Sensor
from sensors.bno085_sensor import BNO085Sensor

BASELINE_S = 5.0          # motors-off window used for the reference |m|
SPIKE_DELTA_UT = 2.0      # |d|m|| above this prints the EMI spike marker
DISPLAY_HZ = 10.0
LOG_HZ = 2.0
SERVO_CHANNELS = (0, 1, 2)
STEP_BATCH = 400          # stepper thread steps per batch before re-checking stop
CSV_PATH = "/tmp/opencode/emi_log.csv"

motors_on = threading.Event()
stop_flag = threading.Event()


def _mag_norm(mx, my, mz):
    return math.sqrt(mx * mx + my * my + mz * mz)


def stepper_thread(stepper):
    """Rotate continuously at full speed until stopped."""
    while not stop_flag.is_set():
        stepper.step(STEP_BATCH)


def servo_thread(pwm):
    """Sweep channels 0..2 continuously until stopped."""
    while not stop_flag.is_set():
        for ch in SERVO_CHANNELS:
            for angle in (0, 45, 90, 135, 180, 135, 90, 45, 0):
                if stop_flag.is_set():
                    return
                pwm.set_angle(ch, angle)
                time.sleep(0.12)


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

    logf = open(CSV_PATH, "w", newline="")
    writer = csv.writer(logf)
    writer.writerow(["t", "mx", "my", "mz", "mag_mag", "motors_on",
                     "press", "temp"])

    t0 = time.monotonic()
    baseline_mags = []
    min_m = max_m = 0.0
    mags_since_motors = []

    print("\033[2J\033[H", end="")
    print("Motor EMI test starting...")
    print(f"  phase 1: {BASELINE_S:.0f} s with motors OFF (capturing |m| baseline)")
    print(f"  phase 2: motors ON continuously until Ctrl+C")
    print(f"  log: {CSV_PATH}\n")

    # ---------------- phase 1: baseline (motors off) ----------------
    last_log = 0.0
    while time.monotonic() - t0 < BASELINE_S:
        d = imu.read()
        mx, my, mz = d["mag_ut"]
        m = _mag_norm(mx, my, mz)
        baseline_mags.append(m)
        b = baro.read()
        now = time.monotonic()
        if now - last_log >= 1.0 / LOG_HZ:
            writer.writerow([round(now - t0, 3), round(mx, 2), round(my, 2),
                             round(mz, 2), round(m, 3), 0,
                             round(b["pressure_hpa"], 2), round(b["temperature_c"], 2)])
            logf.flush()
            last_log = now
        time.sleep(1.0 / DISPLAY_HZ)

    baseline_m = statistics.mean(baseline_mags)
    print(f"\033[2J\033[H", end="")
    print(f"Baseline |m| = {baseline_m:.2f} uT over {BASELINE_S:.0f}s. "
          f"Starting motors!\n")

    # ---------------- phase 2: motors on, live display ----------------
    t_step = threading.Thread(target=stepper_thread, args=(stepper,), daemon=True)
    t_servo = threading.Thread(target=servo_thread, args=(pwm,), daemon=True)
    motors_on.set()
    t_step.start()
    t_servo.start()

    last_disp = 0.0
    last_log = 0.0
    try:
        while True:
            d = imu.read()
            mx, my, mz = d["mag_ut"]
            m = _mag_norm(mx, my, mz)
            min_m = m if min_m == 0.0 else min(min_m, m)
            max_m = max(max_m, m)
            mags_since_motors.append(m)
            if len(mags_since_motors) > DISPLAY_HZ * 10:
                mags_since_motors.pop(0)

            b = baro.read()
            now = time.monotonic()

            if now - last_log >= 1.0 / LOG_HZ:
                writer.writerow([round(now - t0, 3), round(mx, 2), round(my, 2),
                                 round(mz, 2), round(m, 3), 1,
                                 round(b["pressure_hpa"], 2),
                                 round(b["temperature_c"], 2)])
                logf.flush()
                last_log = now

            if now - last_disp >= 1.0 / DISPLAY_HZ:
                delta = m - baseline_m
                sigma = (statistics.pstdev(mags_since_motors)
                         if len(mags_since_motors) > 2 else 0.0)
                spike = "  *** EMI SPIKE ***" if abs(delta) > SPIKE_DELTA_UT else ""

                ax, ay, az = d["accel_ms2"]
                gx, gy, gz = d["gyro_rads"]
                q = d["quaternion"]
                g_mag = _mag_norm(ax, ay, az)

                out = [f"\033[2J\033[H",
                       f"[{now - t0:8.3f}s] BNO085 + BMP388 live | "
                       f"EMI test | motors: {'ON ' if motors_on.is_set() else 'OFF'}{spike}",
                       f"  MAG (EMI):  mx={mx:7.2f} my={my:7.2f} mz={mz:7.2f} uT | "
                       f"|m|={m:6.2f} | d={delta:+6.2f} vs baseline {baseline_m:.2f}",
                       f"  EMI impact: min {min_m:6.2f} / max {max_m:6.2f} / "
                       f"sigma {sigma:5.2f} uT (since motors on)",
                       f"  accel: ({ax:6.3f}, {ay:6.3f}, {az:6.3f}) m/s2 |g|={g_mag:5.2f}",
                       f"  gyro:  ({gx:6.3f}, {gy:6.3f}, {gz:6.3f}) rad/s",
                       f"  quat:  ({q[0]:6.3f}, {q[1]:6.3f}, {q[2]:6.3f}, {q[3]:6.3f})",
                       f"  BMP388: P={b['pressure_hpa']:7.2f} hPa | "
                       f"T={b['temperature_c']:5.2f} C | alt={b['altitude_m']:7.2f} m",
                       f"  servos ch{SERVO_CHANNELS} sweeping | stepper rotating"]
                print("\n".join(out))
                last_disp = now
    except KeyboardInterrupt:
        print("\nStopping motors...")
    finally:
        stop_flag.set()
        motors_on.clear()
        t_step.join(timeout=2.0)
        t_servo.join(timeout=2.0)
        stepper.release()
        pwm.disable_outputs()
        pwm.deinit()
        buzzer.beep_pattern(count=2)
        logf.close()
        peak = max(max_m, 0.0)
        print(f"\nDONE | baseline |m| {baseline_m:.2f} -> peak {peak:.2f} uT "
              f"(d {peak - baseline_m:+.2f} uT) | log: {CSV_PATH}")


if __name__ == "__main__":
    main()