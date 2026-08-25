"""
actuators/gimbal.py
--------------------
Two-axis camera gimbal stabilization (orientation hold).
Gyro rate channels (deadbanded, projected, counter-rotated) plus an
accelerometer-derived absolute leveling term for the servo.

Mounting (IMU frame, per user):
  - 28BYJ-48 stepper (ULN2003) = ROLL stage. Camera optical axis and
    stepper axis s1 point along IMU Z (down-look).
  - Positional servo on PCA9685 channel 0 = TILT. With the roll stage
    at home (theta1 = 0) the servo shaft points along IMU Y (s2z).

The servo axis is nested in the roll stage, so its body-frame
direction rotates with the current roll angle.  After the CanSat rolls,
"pitch" measured by the body-fixed IMU is no longer along the servo
shaft.  Each tick we low-pass + deadband the gyro, project it onto the
current actuator axes, and counter-rotate:

    dotRoll  =  w . s1
    dotTilt  =  w . s2(theta1)

    steps = round(-ROLL_SIGN * dotRoll * dt / deg_per_step)
    tilt  += -TILT_SIGN * dotTilt * dt            (clamped 0..180)

Roll is dead-reckoned from the stepper steps (open loop, no homing).
A 2-axis gimbal cannot cancel yaw about the missing third axis - the
image rotates but keeps pointing at the ground.

Signs / axis constants live in config.py; flip a sign if the gimbal
amplifies motion instead of cancelling it.
"""
import math
import time

import config


class GimbalController:
    """Orientation-hold controller driving a stepper (roll) + servo (tilt)."""

    def __init__(self, imu, pwm, stepper,
                 servo_channel=config.GIMBAL_SERVO_CHANNEL):
        self._imu = imu
        self._pwm = pwm
        self._stepper = stepper
        self._roll_axis = tuple(float(v) for v in config.GIMBAL_ROLL_AXIS)
        self._servo_axis_zero = tuple(float(v) for v in config.GIMBAL_SERVO_AXIS_ZERO)
        self._servo = pwm.attach_servo(servo_channel)

        self.roll_deg = 0.0
        self.tilt_deg = config.GIMBAL_SERVO_CENTER
        self._filtered = None
        self._accel_filtered = None
        self._tilt_error_deg = 0.0
        self._roll_accum = 0.0
        self._unwinding = False
        pwm.set_angle(servo_channel, self.tilt_deg)

    # ------------------------------------------------------------------ #
    # vector helpers (no numpy dependency)
    # ------------------------------------------------------------------ #
    @staticmethod
    def _dot(a, b):
        return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]

    @staticmethod
    def _cross(a, b):
        return (
            a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0],
        )

    def _rotate(self, axis, angle_deg):
        """Rodrigues rotation of `axis` by `angle_deg` about the roll axis."""
        theta = math.radians(angle_deg)
        c = math.cos(theta)
        s = math.sin(theta)
        k = self._roll_axis
        dot = self._dot(axis, k)
        cr = self._cross(k, axis)
        return (
            axis[0] * c + cr[0] * s + k[0] * dot * (1.0 - c),
            axis[1] * c + cr[1] * s + k[1] * dot * (1.0 - c),
            axis[2] * c + cr[2] * s + k[2] * dot * (1.0 - c),
        )

    # ------------------------------------------------------------------ #
    # control
    # ------------------------------------------------------------------ #
    def _read_gyro_dps(self):
        gx, gy, gz = self._imu.read()["gyro_rads"]
        if self._filtered is None:
            self._filtered = (gx, gy, gz)
        else:
            a = config.GIMBAL_FILTER_ALPHA
            f = self._filtered
            self._filtered = (
                a * gx + (1.0 - a) * f[0],
                a * gy + (1.0 - a) * f[1],
                a * gz + (1.0 - a) * f[2],
            )
        return tuple(math.degrees(v) for v in self._filtered)

    def _read_gravity(self):
        """Low-passed, normalized specific-force vector (m/s2 -> unit).

        When the camera looks straight down (level), the IMU Z axis is
        up, so g_hat . Z = +1.  Tilting the rig rotates g_hat away from
        Z, which is exactly the absolute reference the servo needs.
        """
        ax, ay, az = self._imu.read()["accel_ms2"]
        if self._accel_filtered is None:
            self._accel_filtered = (ax, ay, az)
        else:
            a = config.GIMBAL_ACCEL_ALPHA
            f = self._accel_filtered
            self._accel_filtered = (
                a * ax + (1.0 - a) * f[0],
                a * ay + (1.0 - a) * f[1],
                a * az + (1.0 - a) * f[2],
            )
        gx, gy, gz = self._accel_filtered
        norm = math.sqrt(gx * gx + gy * gy + gz * gz)
        if norm < 1.0:
            return (0.0, 0.0, 1.0)
        return (gx / norm, gy / norm, gz / norm)

    @property
    def state(self):
        """'UNWINDING' while the stage resets to 0 deg, else 'NORMAL'."""
        return "UNWINDING" if self._unwinding else "NORMAL"

    def update(self, dt):
        """One control tick. `dt` = seconds since the previous tick.

        Returns (roll_deg, tilt_deg, roll_rate, steps, state, tilt_error).
        """
        w = self._read_gyro_dps()
        g_hat = self._read_gravity()

        roll_rate = self._dot(w, self._roll_axis)                      # deg/s
        tilt_axis = self._rotate(self._servo_axis_zero, self.roll_deg) # s2(theta1)
        tilt_rate = self._dot(w, tilt_axis)                            # deg/s

        db = config.GIMBAL_DEADBAND_DPS
        if abs(roll_rate) < db:
            roll_rate = 0.0
        if abs(tilt_rate) < db:
            tilt_rate = 0.0

        steps = self._roll_steps(roll_rate, dt)

        # --- tilt (servo): absolute leveling + rate feed-forward ---
        # The IMU rides on the rig, so the accelerometer measures the RIG's
        # tilt about the current servo axis, never the camera's.  The
        # camera's world attitude error is that rig tilt plus the angle
        # the servo has already rotated the camera away from center:
        #     e_cam = e_rig + TILT_SIGN * (tilt_deg - center)
        # A proportional velocity drives e_cam to zero (camera exactly
        # level, no over-correction), and the gyro rate channel handles
        # fast transients.  Both share TILT_SIGN, so one sign constant
        # makes the whole tilt axis self-consistent.
        self._tilt_error_deg = math.degrees(
            math.atan2(self._dot(g_hat, tilt_axis),
                       self._dot(g_hat, self._roll_axis)))
        e_cam = (self._tilt_error_deg
                 + config.GIMBAL_TILT_SIGN
                 * (self.tilt_deg - config.GIMBAL_SERVO_CENTER))
        limit = config.GIMBAL_SERVO_RATE_LIMIT_DPS
        p_vel = max(-limit, min(limit, config.GIMBAL_SERVO_P * e_cam))
        self.tilt_deg += (-config.GIMBAL_TILT_SIGN
                          * (p_vel + tilt_rate)) * dt
        self.tilt_deg = max(config.GIMBAL_SERVO_MIN,
                            min(config.GIMBAL_SERVO_MAX, self.tilt_deg))
        self._pwm.set_angle(config.GIMBAL_SERVO_CHANNEL, self.tilt_deg)

        return (self.roll_deg, self.tilt_deg, roll_rate, steps,
                self.state, self._tilt_error_deg)

    def _roll_steps(self, roll_rate, dt):
        """Stepper command for this tick: cable-safety unwind, else roll
        counter-rotation accumulated fractionally. Executes and returns
        the number of steps taken."""
        # --- unwind mode: run toward 0 deg at full speed ---
        if self._unwinding:
            deg_per_step = 1.0 / config.GIMBAL_STEPS_PER_DEG
            if abs(self.roll_deg) < deg_per_step:
                self._unwinding = False
                self._roll_accum = 0.0
                self.roll_deg = 0.0
                return 0
            direction = -1 if self.roll_deg > 0 else 1
            steps = direction * config.GIMBAL_MAX_STEPS_PER_TICK
            if abs(self.roll_deg) <= abs(steps) * deg_per_step:
                steps = round(-self.roll_deg * config.GIMBAL_STEPS_PER_DEG)
            self._stepper.step(steps)
            self.roll_deg += steps * deg_per_step
            if abs(self.roll_deg) < deg_per_step:
                self.roll_deg = 0.0
            return steps

        # --- normal mode: enter unwind once the cable limit is reached ---
        if abs(self.roll_deg) >= config.GIMBAL_UNWIND_LIMIT_DEG:
            self._unwinding = True
            self._roll_accum = 0.0
            return 0

        # --- roll stage: counter-rotate at the projected rate ---
        self._roll_accum += (-config.GIMBAL_ROLL_SIGN
                             * config.GIMBAL_ROLL_GAIN * roll_rate * dt
                             * config.GIMBAL_STEPS_PER_DEG)
        steps = int(self._roll_accum)
        steps = max(-config.GIMBAL_MAX_STEPS_PER_TICK,
                    min(config.GIMBAL_MAX_STEPS_PER_TICK, steps))
        if steps:
            self._stepper.step(steps)
            self.roll_deg += steps / config.GIMBAL_STEPS_PER_DEG
        self._roll_accum -= steps
        return steps

    def run(self):
        """Blocking control loop at config.GIMBAL_LOOP_HZ until Ctrl+C."""
        period = 1.0 / config.GIMBAL_LOOP_HZ
        prev = time.monotonic()
        try:
            while True:
                now = time.monotonic()
                self.update(now - prev)
                prev = now
                time.sleep(period)
        except KeyboardInterrupt:
            raise

    def release(self):
        """Stop the stage: de-energize stepper, PWM outputs off."""
        self._stepper.release()
        self._pwm.disable_outputs()