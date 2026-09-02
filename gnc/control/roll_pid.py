"""
WARNING: This module assumes a fixed-wing, elevon/bank-to-turn aircraft architecture.
It does NOT apply to the actual single-skin paraglider hardware which uses direct asymmetric brake deflection.
Retained for reference only; not used in the active control path.
"""

class PIDController:
    """
    A standard PID controller with integral anti-windup.
    """
    def __init__(self, kp: float, ki: float, kd: float, integral_limit: float = 0.0):
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.integral_limit = integral_limit
        self.integral = 0.0
        self.prev_error = 0.0

    def compute(self, target: float, measured: float, dt: float, derivative_measured: float = None) -> float:
        """
        Computes the PID control action.
        
        Args:
            target: Setpoint
            measured: Current measured value
            dt: Time step in seconds
            derivative_measured: Optional direct derivative measurement (e.g. from a gyro). 
                                 If provided, Kd term uses `kd * (0 - derivative_measured)`.
                                 Otherwise, uses `kd * (error - prev_error) / dt`.
        """
        error = target - measured
        
        # Integral with anti-windup
        if dt > 0:
            self.integral += error * dt
            
            if self.integral_limit > 0:
                self.integral = max(-self.integral_limit, min(self.integral_limit, self.integral))
                
        # Derivative
        if derivative_measured is not None:
            # e.g., for roll rate from gyro: error derivative is (0 - p) if target rate is 0
            derivative = -derivative_measured
        else:
            derivative = (error - self.prev_error) / dt if dt > 0 else 0.0
            
        self.prev_error = error
        
        return self.kp * error + self.ki * self.integral + self.kd * derivative

class RollPID(PIDController):
    """
    Roll stabilization PID (inner loop).
    δ_aileron = Kp·(φ_cmd − φ_measured) + Kd·(0 − p)
    where p is roll rate from the gyro.
    """
    def __init__(self, kp: float, ki: float, kd: float, integral_limit: float):
        super().__init__(kp, ki, kd, integral_limit)

    def step(self, roll_cmd: float, roll_meas: float, roll_rate: float, dt: float) -> float:
        """
        Args:
            roll_cmd: Commanded roll angle (radians)
            roll_meas: Measured roll angle (radians)
            roll_rate: Measured roll rate from gyro p (rad/s)
            dt: time step
        """
        return self.compute(roll_cmd, roll_meas, dt, derivative_measured=roll_rate)
