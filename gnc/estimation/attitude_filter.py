import math
from typing import Tuple

class ComplementaryFilter:
    """
    Attitude estimation using a complementary filter.
    angle_estimate = α · gyro_integrated_angle + (1-α) · accel_derived_angle
    """
    def __init__(self, alpha: float = 0.98):
        self.alpha = alpha
        self.roll = 0.0
        self.pitch = 0.0

    def update(self, accel_x: float, accel_y: float, accel_z: float, 
               gyro_p: float, gyro_q: float, dt: float) -> Tuple[float, float]:
        """
        Updates the roll and pitch estimates.
        
        Args:
            accel_x, accel_y, accel_z: Accelerometer readings (m/s^2 or g)
            gyro_p: Roll rate from gyro (rad/s)
            gyro_q: Pitch rate from gyro (rad/s)
            dt: Time step in seconds
            
        Returns:
            Tuple of (roll, pitch) in radians
        """
        # Integrate gyro data
        self.roll += gyro_p * dt
        self.pitch += gyro_q * dt

        # Calculate angles from accelerometer
        # Assuming standard aviation frame: x forward, y right, z down
        # roll: atan2(ay, az)
        accel_roll = math.atan2(accel_y, accel_z)
        
        # pitch: atan2(-ax, sqrt(ay^2 + az^2))
        accel_pitch = math.atan2(-accel_x, math.sqrt(accel_y**2 + accel_z**2))

        # Apply complementary filter
        self.roll = self.alpha * self.roll + (1.0 - self.alpha) * accel_roll
        self.pitch = self.alpha * self.pitch + (1.0 - self.alpha) * accel_pitch

        return self.roll, self.pitch
