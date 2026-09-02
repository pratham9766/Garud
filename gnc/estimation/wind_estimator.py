import math
import numpy as np
from typing import Tuple

class WindEstimatorRLS:
    """
    Recursive Least Squares (RLS) estimator for wind.
    Assuming V_ground = Va * [cos(psi), sin(psi)] + [Vw_x, Vw_y]
    We want to solve for [Vw_x, Vw_y] and optionally Va.
    
    Rearranging: V_ground_x = Va*cos(psi) + Vw_x
                 V_ground_y = Va*sin(psi) + Vw_y
    """
    def __init__(self, lambda_factor: float = 0.98, initial_covariance: float = 100.0):
        self.lambda_factor = lambda_factor
        
        # State vector: [Va, Vw_x, Vw_y]^T
        self.theta = np.zeros((3, 1))
        self.theta[0, 0] = 15.0 # Initial guess for Va
        
        # Covariance matrix
        self.P = np.eye(3) * initial_covariance

    def update(self, v_ground_x: float, v_ground_y: float, heading_rad: float) -> Tuple[float, float, float]:
        """
        Performs one RLS update step.
        
        Args:
            v_ground_x: GPS ground speed x (North)
            v_ground_y: GPS ground speed y (East)
            heading_rad: Current yaw/heading angle
            
        Returns:
            Tuple of (Vw_x, Vw_y, Va_estimated)
        """
        # Observation vector: y = [v_ground_x, v_ground_y]^T
        y = np.array([[v_ground_x], [v_ground_y]])
        
        # Observation matrix: H
        # y = H * theta
        # v_ground_x = Va*cos(psi) + Vw_x*1 + Vw_y*0
        # v_ground_y = Va*sin(psi) + Vw_x*0 + Vw_y*1
        H = np.array([
            [math.cos(heading_rad), 1.0, 0.0],
            [math.sin(heading_rad), 0.0, 1.0]
        ])
        
        # RLS Gain: K = P * H^T * (lambda * I + H * P * H^T)^-1
        S = self.lambda_factor * np.eye(2) + H @ self.P @ H.T
        try:
            S_inv = np.linalg.inv(S)
        except np.linalg.LinAlgError:
            return self.theta[1,0], self.theta[2,0], self.theta[0,0] # fallback

        K = self.P @ H.T @ S_inv
        
        # Innovation (error)
        error = y - H @ self.theta
        
        # Update estimate
        self.theta = self.theta + K @ error
        
        # Update covariance
        self.P = (self.P - K @ H @ self.P) / self.lambda_factor
        
        # Prevent Covariance Wind-up
        max_p = 1000.0
        if np.trace(self.P) > max_p:
            self.P = self.P * (max_p / np.trace(self.P))
        
        return float(self.theta[1, 0]), float(self.theta[2, 0]), float(self.theta[0, 0])

    def get_wind_estimate(self) -> Tuple[float, float]:
        """Returns the current wind estimate (Vw_x, Vw_y)."""
        return float(self.theta[1, 0]), float(self.theta[2, 0])
