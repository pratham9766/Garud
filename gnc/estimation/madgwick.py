# RETAINED FOR REFERENCE ONLY
# Not used in the active flight path — BNO085 provides built-in AHRS fusion
# that replaces this filter on real hardware. Do not import from flight_computer.py.
# Active in SITL simulation mode only (SimulatedHardware bypasses BNO085).
import math
from typing import Tuple

class MadgwickFilter:
    """
    Madgwick's sensor fusion algorithm for 9-DOF IMU.
    Fuses Accel, Gyro, and Mag into a quaternion.
    """
    def __init__(self, beta: float = 0.1):
        self.beta = beta
        self.q = [1.0, 0.0, 0.0, 0.0]

    def update(self, ax: float, ay: float, az: float,
               gx: float, gy: float, gz: float,
               mx: float, my: float, mz: float,
               dt: float):
        """
        Update step.
        Accel in m/s^2 or g
        Gyro in rad/s
        Mag in uT or normalized
        """
        q1, q2, q3, q4 = self.q

        # Normalize accelerometer
        norm = math.sqrt(ax * ax + ay * ay + az * az)
        if norm == 0.0: return
        ax /= norm
        ay /= norm
        az /= norm

        # Normalize magnetometer
        norm = math.sqrt(mx * mx + my * my + mz * mz)
        if norm == 0.0: return
        mx /= norm
        my /= norm
        mz /= norm

        # Reference direction of Earth's magnetic field
        hx = 2.0 * mx * (0.5 - q3 * q3 - q4 * q4) + 2.0 * my * (q2 * q3 - q1 * q4) + 2.0 * mz * (q2 * q4 + q1 * q3)
        hy = 2.0 * mx * (q2 * q3 + q1 * q4) + 2.0 * my * (0.5 - q2 * q2 - q4 * q4) + 2.0 * mz * (q3 * q4 - q1 * q2)
        bx = math.sqrt(hx * hx + hy * hy)
        bz = 2.0 * mx * (q2 * q4 - q1 * q3) + 2.0 * my * (q3 * q4 + q1 * q2) + 2.0 * mz * (0.5 - q2 * q2 - q3 * q3)

        # Gradient descent algorithm corrective step
        s1 = -2.0 * q3 * (2.0 * q2 * q4 - 2.0 * q1 * q3 - ax) + 2.0 * q2 * (2.0 * q1 * q2 + 2.0 * q3 * q4 - ay) - \
             bz * q3 * (bz * (0.5 - q3 * q3 - q4 * q4) + bx * (q2 * q4 - q1 * q3) - mz) + \
             (-bx * q4 + bz * q2) * (bx * (0.5 - q2 * q2 - q4 * q4) + bz * (q3 * q4 + q1 * q2) - my) + \
             bx * q3 * (bx * (q2 * q3 - q1 * q4) + bz * (q2 * q4 + q1 * q3) - mx)
             
        s2 = 2.0 * q4 * (2.0 * q2 * q4 - 2.0 * q1 * q3 - ax) + 2.0 * q1 * (2.0 * q1 * q2 + 2.0 * q3 * q4 - ay) - \
             4.0 * q2 * (1.0 - 2.0 * q2 * q2 - 2.0 * q3 * q3 - az) + \
             bz * q4 * (bz * (0.5 - q3 * q3 - q4 * q4) + bx * (q2 * q4 - q1 * q3) - mz) + \
             (bx * q3 + bz * q1) * (bx * (0.5 - q2 * q2 - q4 * q4) + bz * (q3 * q4 + q1 * q2) - my) + \
             (bx * q4 - 4.0 * bx * q2) * (bx * (q2 * q3 - q1 * q4) + bz * (q2 * q4 + q1 * q3) - mx)
             
        s3 = -2.0 * q1 * (2.0 * q2 * q4 - 2.0 * q1 * q3 - ax) + 2.0 * q4 * (2.0 * q1 * q2 + 2.0 * q3 * q4 - ay) - \
             4.0 * q3 * (1.0 - 2.0 * q2 * q2 - 2.0 * q3 * q3 - az) + \
             (-4.0 * bz * q3 - bx * q1) * (bz * (0.5 - q3 * q3 - q4 * q4) + bx * (q2 * q4 - q1 * q3) - mz) + \
             (bx * q2 + bz * q4) * (bx * (0.5 - q2 * q2 - q4 * q4) + bz * (q3 * q4 + q1 * q2) - my) + \
             (bx * q2 - 4.0 * bz * q3) * (bx * (q2 * q3 - q1 * q4) + bz * (q2 * q4 + q1 * q3) - mx)
             
        s4 = 2.0 * q2 * (2.0 * q2 * q4 - 2.0 * q1 * q3 - ax) + 2.0 * q3 * (2.0 * q1 * q2 + 2.0 * q3 * q4 - ay) + \
             (-4.0 * bz * q4 + bx * q2) * (bz * (0.5 - q3 * q3 - q4 * q4) + bx * (q2 * q4 - q1 * q3) - mz) + \
             (-bx * q1 + bz * q3) * (bx * (0.5 - q2 * q2 - q4 * q4) + bz * (q3 * q4 + q1 * q2) - my) + \
             bx * q1 * (bx * (q2 * q3 - q1 * q4) + bz * (q2 * q4 + q1 * q3) - mx)

        norm = math.sqrt(s1 * s1 + s2 * s2 + s3 * s3 + s4 * s4)
        if norm > 0.0:
            s1 /= norm
            s2 /= norm
            s3 /= norm
            s4 /= norm

        # Compute rate of change of quaternion
        qDot1 = 0.5 * (-q2 * gx - q3 * gy - q4 * gz) - self.beta * s1
        qDot2 = 0.5 * (q1 * gx + q3 * gz - q4 * gy) - self.beta * s2
        qDot3 = 0.5 * (q1 * gy - q2 * gz + q4 * gx) - self.beta * s3
        qDot4 = 0.5 * (q1 * gz + q2 * gy - q3 * gx) - self.beta * s4

        # Integrate to yield quaternion
        self.q[0] += qDot1 * dt
        self.q[1] += qDot2 * dt
        self.q[2] += qDot3 * dt
        self.q[3] += qDot4 * dt

        # Normalize quaternion
        norm = math.sqrt(self.q[0]**2 + self.q[1]**2 + self.q[2]**2 + self.q[3]**2)
        self.q = [x / norm for x in self.q]

    def get_euler_angles(self) -> Tuple[float, float, float]:
        """Returns roll, pitch, yaw in radians."""
        q1, q2, q3, q4 = self.q
        
        roll = math.atan2(2.0 * (q1 * q2 + q3 * q4), 1.0 - 2.0 * (q2 * q2 + q3 * q3))
        pitch = math.asin(max(-1.0, min(1.0, 2.0 * (q1 * q3 - q4 * q2))))
        yaw = math.atan2(2.0 * (q1 * q4 + q2 * q3), 1.0 - 2.0 * (q3 * q3 + q4 * q4))
        
        return roll, pitch, yaw
