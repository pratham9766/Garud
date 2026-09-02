"""
WARNING: L1Guidance outputs a commanded bank angle, which requires a downstream
roll-control PID and elevon mixing. This architecture assumes a fixed-wing aircraft.
It does NOT apply to the actual paraglider hardware, which uses direct asymmetric
brake deflection for heading control — there is no bank angle command or roll loop.
The active heading controller is guidance/heading_pid.py.
Retained for reference only; not used in the active control path.
"""
import math
from typing import Tuple

class L1Guidance:
    """
    L1 Lateral Guidance law for following a path to a target.
    a_cmd = (2 * V^2 / L1) * sin(eta)
    phi_cmd = atan(a_cmd / g)
    """
    def __init__(self, period: float, damping: float = 0.7, max_bank_rad: float = math.radians(35)):
        self.period = period
        self.damping = damping
        self.max_bank_rad = max_bank_rad
        self.gravity = 9.81

    def compute(self, current_pos_x: float, current_pos_y: float, 
                target_pos_x: float, target_pos_y: float,
                ground_speed: float, heading_rad: float) -> float:
        """
        Computes the commanded bank angle.
        
        Args:
            current_pos_x, current_pos_y: Current position (m)
            target_pos_x, target_pos_y: Target position (m)
            ground_speed: Current ground speed (m/s)
            heading_rad: Current heading angle (rad)
            
        Returns:
            Commanded bank angle in radians
        """
        if ground_speed < 0.1:
            return 0.0

        # L1 distance auto-tuned by airspeed: L1 = k * V * T_L1
        # where T_L1 is self.period, and we divide by pi for scaling
        L1 = self.period * ground_speed / math.pi
        
        # Vector to target
        dx = target_pos_x - current_pos_x
        dy = target_pos_y - current_pos_y
        
        # Bearing to target
        target_bearing = math.atan2(dy, dx)
        
        # Angle between velocity vector and L1 reference point (eta)
        eta = target_bearing - heading_rad
        
        # Normalize eta to [-pi, pi]
        eta = (eta + math.pi) % (2 * math.pi) - math.pi
        
        # Lateral acceleration command
        if abs(eta) > math.pi / 2:
            # Target is behind us! Command max turn in the direction of eta.
            # Using max bank angle directly.
            bank_cmd = math.copysign(self.max_bank_rad, eta)
        else:
            a_cmd = (2 * ground_speed**2 / L1) * math.sin(eta)
            # Bank angle command
            bank_cmd = math.atan(a_cmd / self.gravity)
        
        # Clamp to max bank
        return max(-self.max_bank_rad, min(self.max_bank_rad, bank_cmd))
