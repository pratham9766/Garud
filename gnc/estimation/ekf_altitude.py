import numpy as np

class EKFAltitude:
    """
    1D Extended Kalman Filter for Altitude Fusion.
    State vector: x = [altitude, vertical_velocity]^T
    Prediction uses vertical acceleration from IMU (earth-frame Z).
    Update uses Barometer altitude and GPS altitude.
    """
    def __init__(self, dt: float, initial_alt: float = 0.0):
        self.dt = dt
        self.x = np.array([[initial_alt], [0.0]])
        self.P = np.eye(2) * 10.0
        
        # State transition matrix
        self.F = np.array([[1.0, dt],
                           [0.0, 1.0]])
                           
        # Control input matrix
        self.B = np.array([[0.5 * dt**2],
                           [dt]])
                           
        # Process noise covariance
        self.Q = np.array([[0.01, 0.0],
                           [0.0,  0.1]])

    def predict(self, accel_z_earth: float):
        """
        Prediction step.
        accel_z_earth: vertical acceleration without gravity (m/s^2), upward positive.
        """
        # x_k|k-1 = F * x_k-1|k-1 + B * u
        u = np.array([[accel_z_earth]])
        self.x = self.F @ self.x + self.B @ u
        
        # P_k|k-1 = F * P_k-1|k-1 * F^T + Q
        self.P = self.F @ self.P @ self.F.T + self.Q

    def update_baro(self, baro_alt: float, R_baro: float = 2.0):
        """
        Update using Barometer altitude.
        """
        H = np.array([[1.0, 0.0]])
        z = np.array([[baro_alt]])
        R = np.array([[R_baro]])
        self._update(H, z, R)

    def update_gps(self, gps_alt: float, R_gps: float = 5.0):
        """
        Update using GPS altitude.
        """
        H = np.array([[1.0, 0.0]])
        z = np.array([[gps_alt]])
        R = np.array([[R_gps]])
        self._update(H, z, R)

    def _update(self, H, z, R):
        # Innovation y = z - H * x
        y = z - H @ self.x
        
        # Innovation covariance S = H * P * H^T + R
        S = H @ self.P @ H.T + R
        
        # Kalman Gain K = P * H^T * S^-1
        K = self.P @ H.T @ np.linalg.inv(S)
        
        # x_k|k = x_k|k-1 + K * y
        self.x = self.x + K @ y
        
        # P_k|k = (I - K * H) * P_k|k-1
        self.P = (np.eye(2) - K @ H) @ self.P

    @property
    def altitude(self) -> float:
        return float(self.x[0, 0])

    @property
    def vertical_velocity(self) -> float:
        return float(self.x[1, 0])

    def set_altitude(self, altitude: float, velocity: float = 0.0) -> None:
        """
        Seed the EKF state directly — used by reset recovery.

        Called at boot when a valid .state snapshot exists, so the filter
        starts from the last known position instead of re-converging from zero.
        Also resets covariance to a moderate uncertainty (not zero, since the
        values come from a crashed state, not a fresh measurement).

        Args:
            altitude: Last known AGL altitude (metres)
            velocity: Last known vertical velocity (m/s), negative = descending
        """
        self.x = np.array([[altitude], [velocity]])
        # Moderate covariance — we trust the saved value but it may be stale
        self.P = np.array([[25.0, 0.0],
                           [0.0,  4.0]])
