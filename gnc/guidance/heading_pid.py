import math

class HeadingPID:
    def __init__(self, kp, ki, kd, output_limit=30.0):
        self.kp = kp
        self.ki = ki
        self.kd = kd
        
        self.output_limit = output_limit
        
        self.integral = 0.0
        self.prev_error = 0.0
        
    def compute(self, target_heading, current_heading, dt):
        if dt <= 0.0:
            return 0.0
            
        # Angle wrap error between -pi and pi
        error = target_heading - current_heading
        error = (error + math.pi) % (2 * math.pi) - math.pi
        
        self.integral += error * dt
        
        # Anti-windup
        # Assuming the output is related to brake angle in degrees, we can bound the integral
        max_i = self.output_limit / (self.ki + 1e-6)
        self.integral = max(-max_i, min(max_i, self.integral))
        
        derivative = (error - self.prev_error) / dt
        self.prev_error = error
        
        output = (self.kp * error) + (self.ki * self.integral) + (self.kd * derivative)
        
        # Clamp output
        return max(-self.output_limit, min(self.output_limit, output))
