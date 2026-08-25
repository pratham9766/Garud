"""
gimbal_angle_test.py
---------------------
Quaternion-accurate gimbal bench test.

Angle path:  BNO085 fused quaternion (x,y,z,w) -> rotation matrix ->
Tait-Bryan ZYX euler angles (yaw about Z, pitch about Y, roll about X),
with explicit gimbal-lock handling at pitch = +/-90 deg.  Mag-driven
fusion quality (cal, 0-3) is printed each tick so you can see how
trustworthy the fused yaw is.

Actuation:
    roll (about X)  -> 28BYJ-48 stepper - roll stage counter-rotation
    pitch (about Y) -> PCA9685 channel 0 servo - tilt counter-rotation
    yaw (about Z)   -> not correctable by a 2-axis gimbal (logged only)

Counter-rotation: stage moves to -roll*gain, servo moves to
center - TILT_SIGN*pitch (clamped 0..180).

Run with:  python3 gimbal_angle_test.py
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "libraries"))


import math
import time

from adafruit_bno08x import BNO_REPORT_ROTATION_VECTOR

import bus_manager
import config
from actuators.servo_driver import PCA9685Driver
from actuators.stepper_driver import ULN2003Stepper
from sensors.bno085_sensor import BNO085Sensor


# --------------------------------------------------------------------- #
# quaternion -> rotation matrix -> euler (accurate, lock-safe)
# --------------------------------------------------------------------- #
def quat_to_matrix(qi, qj, qk, qr):
    """Convert (i,j,k,real) quaternion to a 3x3 world->body rotation."""
    w, x, y, z = qr, qi, qj, qk
    return (
        (1.0 - 2.0 * (y * y + z * z), 2.0 * (x * y - w * z), 2.0 * (x * z + w * y)),
        (2.0 * (x * y + w * z), 1.0 - 2.0 * (x * x + z * z), 2.0 * (y * z - w * x)),
        (2.0 * (x * z - w * y), 2.0 * (y * z + w * x), 1.0 - 2.0 * (x * x + y * y)),
    )


def matrix_to_euler(R):
    """Tait-Bryan ZYX: yaw about Z, pitch about Y, roll about X (deg)."""
    sinp = -R[2][0]
    if 1.0 - abs(sinp) < 1e-9:              # gimbal lock at pitch = +/-90
        pitch = math.copysign(math.pi / 2.0, sinp)
        roll = math.atan2(-R[0][1], R[1][1])
        yaw = 0.0
    else:
        pitch = math.asin(sinp)
        roll = math.atan2(R[2][1], R[2][2])
        yaw = math.atan2(R[1][0], R[0][0])
    return tuple(math.degrees(v) for v in (roll, pitch, yaw))


def quat_to_euler(qi, qj, qk, qr):
    return matrix_to_euler(quat_to_matrix(qi, qj, qk, qr))


def main():
    i2c = bus_manager.get_i2c()
    imu = BNO085Sensor(i2c)
    imu.bno.enable_feature(BNO_REPORT_ROTATION_VECTOR)

    pwm = PCA9685Driver(i2c)
    pwm.enable_outputs()
    stepper = ULN2003Stepper()

    deg_per_step = 1.0 / config.GIMBAL_STEPS_PER_DEG
    stage_deg = 0.0
    center = config.GIMBAL_SERVO_CENTER
    pwm.set_angle(0, center)

    print("Gimbal angle test (quaternion-accurate) running (Ctrl+C to stop)...")
    print("  roll  (X) -> stepper | pitch (Y) -> servo ch0 | yaw (Z) logged only")
    print("  Turn the BNO: 'roll' moves the roll stage, 'pitch' moves the servo\n")

    t0 = time.monotonic()
    try:
        while True:
            qi, qj, qk, qr = imu.read()["quaternion"]
            roll, pitch, yaw = quat_to_euler(qi, qj, qk, qr)

            cal = imu.bno.calibration_status   # 0..3 mag-accuracy / fusion quality

            # --- roll: continuous stepper target (wrap-safe) ---
            target = -roll * config.GIMBAL_ROLL_SIGN * config.GIMBAL_ROLL_GAIN
            delta = target - stage_deg
            steps = round(delta / deg_per_step)
            steps = max(-config.GIMBAL_MAX_STEPS_PER_TICK,
                        min(config.GIMBAL_MAX_STEPS_PER_TICK, steps))
            if steps:
                stepper.step(steps)
                stage_deg += steps * deg_per_step

            # --- pitch -> servo tilt ---
            tilt = center - config.GIMBAL_TILT_SIGN * pitch
            tilt = max(config.GIMBAL_SERVO_MIN,
                       min(config.GIMBAL_SERVO_MAX, tilt))
            pwm.set_angle(0, tilt)

            print(f"\r[{time.monotonic() - t0:8.3f}s] "
                  f"roll {roll:+7.1f}  pitch {pitch:+6.1f}  yaw {yaw:+7.1f} | "
                  f"cal {cal}/3 | "
                  f"stage {stage_deg:+7.1f} (tgt {target:+7.1f}) | "
                  f"servo {tilt:6.1f} deg     ", end="", flush=True)
            time.sleep(0.05)
    except KeyboardInterrupt:
        print("\nStopping gimbal test...")
    finally:
        stepper.release()
        pwm.disable_outputs()
        pwm.deinit()
        print("Released.")


if __name__ == "__main__":
    main()