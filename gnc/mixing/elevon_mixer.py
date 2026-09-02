class ElevonMixer:
    """
    Combines roll + pitch commands into left/right PWM.
    left_servo_cmd  = trim + pitch_cmd − roll_cmd
    right_servo_cmd = trim + pitch_cmd + roll_cmd
    """
    def __init__(self, min_pwm: float, max_pwm: float, neutral: float, left_trim: float, right_trim: float):
        self.min_pwm = min_pwm
        self.max_pwm = max_pwm
        self.neutral = neutral
        self.left_trim = left_trim
        self.right_trim = right_trim

    def mix(self, roll_effort: float, pitch_effort: float) -> tuple[float, float]:
        """
        Args:
            roll_effort: Command from roll PID (arbitrary units, typically scaled to servo degrees)
            pitch_effort: Command from pitch PID (arbitrary units, typically scaled to servo degrees)
            
        Returns:
            (left_servo_pwm, right_servo_pwm) strictly bounded
        """
        # Positive roll_effort -> roll LEFT (right wing up, left wing down)
        left = self.neutral + self.left_trim + pitch_effort - roll_effort
        right = self.neutral + self.right_trim + pitch_effort + roll_effort
        
        # Clamp
        left = max(self.min_pwm, min(self.max_pwm, left))
        right = max(self.min_pwm, min(self.max_pwm, right))
        
        return left, right
