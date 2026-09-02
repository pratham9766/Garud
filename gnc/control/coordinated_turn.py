"""
WARNING: This module assumes a fixed-wing, elevon/bank-to-turn aircraft architecture.
It does NOT apply to the actual single-skin paraglider hardware which uses direct asymmetric brake deflection.
Retained for reference only; not used in the active control path.
"""
import math

GRAVITY = 9.81

def turn_rate_to_bank_angle(turn_rate_rad_s: float, airspeed: float) -> float:
    """
    Inverse coordinated turn relation: φ_cmd = atan(ψ̇_cmd · V / g)
    Converts a commanded turn rate to a required bank angle (roll angle).
    
    Args:
        turn_rate_rad_s: Commanded heading rate of change in rad/s
        airspeed: Current airspeed in m/s
        
    Returns:
        Commanded bank angle in radians
    """
    if airspeed < 0.1:
        return 0.0  # Prevent division by zero or unrealistic behavior near zero speed
        
    return math.atan(turn_rate_rad_s * airspeed / GRAVITY)

def bank_angle_to_turn_rate(bank_angle_rad: float, airspeed: float) -> float:
    """
    Forward coordinated turn relation: ψ̇ = g·tan(φ) / V
    Converts a bank angle to the resulting turn rate.
    
    Args:
        bank_angle_rad: Bank angle in radians
        airspeed: Current airspeed in m/s
        
    Returns:
        Turn rate in rad/s
    """
    if airspeed < 0.1:
        return 0.0
        
    return (GRAVITY * math.tan(bank_angle_rad)) / airspeed
