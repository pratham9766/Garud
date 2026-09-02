import math

class AltitudeBudget:
    """
    Manages altitude budget using a nominal glide ratio.
    altitude_needed = distance_to_target / glide_ratio
    altitude_excess = current_altitude - altitude_needed
    """
    def __init__(self, glide_ratio: float, s_turn_excess_threshold: float, s_turn_bank_angle_rad: float):
        self.glide_ratio = glide_ratio
        self.s_turn_excess_threshold = s_turn_excess_threshold
        self.s_turn_bank_angle_rad = s_turn_bank_angle_rad
        self._s_turn_state = 1  # 1 for right, -1 for left
        self._last_s_turn_switch = 0.0

    def compute(self, current_alt: float, target_alt: float, distance_to_target: float, current_time: float) -> float:
        """
        Calculates altitude excess and determines if S-turns are required.
        
        Args:
            current_alt: Current altitude above MSL (m)
            target_alt: Target altitude above MSL (m)
            distance_to_target: Horizontal distance to target (m)
            current_time: Current simulation or system time (s)
            
        Returns:
            Bank angle override for S-turns in radians. If 0.0, use normal guidance.
        """
        alt_above_target = current_alt - target_alt
        
        if alt_above_target <= 0 or self.glide_ratio <= 0.1:
            return 0.0
            
        altitude_needed = distance_to_target / self.glide_ratio
        altitude_excess = alt_above_target - altitude_needed
        
        if altitude_excess > self.s_turn_excess_threshold:
            # We are too high, execute S-turns to bleed energy
            # Switch direction every 5 seconds
            if current_time - self._last_s_turn_switch > 5.0:
                self._s_turn_state *= -1
                self._last_s_turn_switch = current_time
                
            return self.s_turn_bank_angle_rad * self._s_turn_state
            
        # Normal guidance
        return 0.0
