"""Tiny constant-velocity Kalman filter for horizontal navigation."""

from __future__ import annotations

import math


class ConstantVelocityKalman:
    """4-state filter: [north, east, north_velocity, east_velocity]."""

    def __init__(
        self,
        process_noise_position: float,
        process_noise_velocity: float,
    ) -> None:
        self.q_pos = float(process_noise_position)
        self.q_vel = float(process_noise_velocity)
        self.x = [0.0, 0.0, 0.0, 0.0]
        self.p = [[0.0] * 4 for _ in range(4)]
        self.initialized = False

    def initialize(
        self,
        north_m: float,
        east_m: float,
        vn_mps: float = 0.0,
        ve_mps: float = 0.0,
        pos_variance: float = 25.0,
        vel_variance: float = 9.0,
    ) -> None:
        self.x = [float(north_m), float(east_m), float(vn_mps), float(ve_mps)]
        self.p = [
            [float(pos_variance), 0.0, 0.0, 0.0],
            [0.0, float(pos_variance), 0.0, 0.0],
            [0.0, 0.0, float(vel_variance), 0.0],
            [0.0, 0.0, 0.0, float(vel_variance)],
        ]
        self.initialized = True

    def predict(self, dt_s: float) -> None:
        if not self.initialized:
            return
        dt = float(dt_s)
        self.x[0] += self.x[2] * dt
        self.x[1] += self.x[3] * dt

        p = self.p
        f = [
            [1.0, 0.0, dt, 0.0],
            [0.0, 1.0, 0.0, dt],
            [0.0, 0.0, 1.0, 0.0],
            [0.0, 0.0, 0.0, 1.0],
        ]
        fp = [[sum(f[i][k] * p[k][j] for k in range(4)) for j in range(4)] for i in range(4)]
        self.p = [[sum(fp[i][k] * f[j][k] for k in range(4)) for j in range(4)] for i in range(4)]
        q_pos = max(0.0, self.q_pos) * dt * dt
        q_vel = max(0.0, self.q_vel) * dt
        self.p[0][0] += q_pos
        self.p[1][1] += q_pos
        self.p[2][2] += q_vel
        self.p[3][3] += q_vel

    def update_position(self, north_m: float, east_m: float, variance_m2: float) -> None:
        self._update_scalar(0, float(north_m), float(variance_m2))
        self._update_scalar(1, float(east_m), float(variance_m2))

    def update_velocity(self, vn_mps: float, ve_mps: float, variance_m2ps2: float) -> None:
        self._update_scalar(2, float(vn_mps), float(variance_m2ps2))
        self._update_scalar(3, float(ve_mps), float(variance_m2ps2))

    def _update_scalar(self, index: int, measurement: float, variance: float) -> None:
        if not self.initialized:
            return
        r = max(float(variance), 1e-6)
        innovation = measurement - self.x[index]
        s = self.p[index][index] + r
        if not math.isfinite(s) or s <= 1e-12:
            return
        k = [self.p[row][index] / s for row in range(4)]
        for row in range(4):
            self.x[row] += k[row] * innovation
        old = [row[:] for row in self.p]
        for row in range(4):
            for col in range(4):
                self.p[row][col] = old[row][col] - k[row] * old[index][col]
        for i in range(4):
            self.p[i][i] = max(self.p[i][i], 1e-9)

    def is_finite(self) -> bool:
        return all(math.isfinite(v) for v in self.x) and all(
            math.isfinite(v) and abs(v) < 1e18 for row in self.p for v in row
        )
