"""
WARNING: This module assumes a fixed-wing, bank-to-turn architecture with a pitch
outer loop and elevator control. It does NOT apply to the actual single-skin
paraglider hardware, which controls altitude implicitly via glide ratio and uses
only asymmetric brake deflection for heading.
Retained for reference only; not used in the active control path.
"""
from .roll_pid import PIDController

class PitchPID(PIDController):
    """
    Glide path / pitch PID (outer loop).
    Holds a target pitch angle near best L/D angle of attack.
    """
    def __init__(self, kp: float, ki: float, kd: float, integral_limit: float, target_pitch: float):
        super().__init__(kp, ki, kd, integral_limit)
        self.target_pitch = target_pitch

    def step(self, pitch_meas: float, pitch_rate: float, dt: float) -> float:
        """
        Args:
            pitch_meas: Measured pitch angle (radians)
            pitch_rate: Measured pitch rate from gyro q (rad/s)
            dt: time step
            
        Returns:
            Pitch command to the mixer
        """
        return self.compute(self.target_pitch, pitch_meas, dt, derivative_measured=pitch_rate)
