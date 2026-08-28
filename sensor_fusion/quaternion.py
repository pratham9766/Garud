"""
Quaternion helpers for GARUDA attitude estimation.

Canonical order is q = (w, x, y, z).  Euler angles use intrinsic aerospace
roll/pitch/yaw in degrees: roll about body X, pitch about body Y, yaw about Z.
The existing mapping convention composes R = Rz(yaw) * Ry(pitch) * Rx(roll),
so these helpers preserve that convention rather than changing frames silently.
"""

from __future__ import annotations

import math
from typing import Iterable

Quaternion = tuple[float, float, float, float]


def is_finite_quaternion(q: Iterable[float]) -> bool:
    values = tuple(q)
    return len(values) == 4 and all(math.isfinite(v) for v in values)


def norm(q: Quaternion) -> float:
    w, x, y, z = q
    return math.sqrt(w * w + x * x + y * y + z * z)


def normalize(q: Quaternion, *, min_norm: float = 1e-12) -> Quaternion | None:
    if not is_finite_quaternion(q):
        return None
    n = norm(q)
    if not math.isfinite(n) or n < min_norm:
        return None
    inv = 1.0 / n
    return (q[0] * inv, q[1] * inv, q[2] * inv, q[3] * inv)


def multiply(a: Quaternion, b: Quaternion) -> Quaternion:
    aw, ax, ay, az = a
    bw, bx, by, bz = b
    return (
        aw * bw - ax * bx - ay * by - az * bz,
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
    )


def conjugate(q: Quaternion) -> Quaternion:
    w, x, y, z = q
    return (w, -x, -y, -z)


def from_euler_deg(roll_deg: float, pitch_deg: float, yaw_deg: float) -> Quaternion:
    roll = math.radians(roll_deg)
    pitch = math.radians(pitch_deg)
    yaw = math.radians(yaw_deg)
    cr = math.cos(roll * 0.5)
    sr = math.sin(roll * 0.5)
    cp = math.cos(pitch * 0.5)
    sp = math.sin(pitch * 0.5)
    cy = math.cos(yaw * 0.5)
    sy = math.sin(yaw * 0.5)
    return normalize((
        cr * cp * cy + sr * sp * sy,
        sr * cp * cy - cr * sp * sy,
        cr * sp * cy + sr * cp * sy,
        cr * cp * sy - sr * sp * cy,
    )) or (1.0, 0.0, 0.0, 0.0)


def to_euler_deg(q: Quaternion) -> tuple[float, float, float]:
    nq = normalize(q)
    if nq is None:
        raise ValueError("Invalid quaternion")
    w, x, y, z = nq

    sinr_cosp = 2.0 * (w * x + y * z)
    cosr_cosp = 1.0 - 2.0 * (x * x + y * y)
    roll = math.degrees(math.atan2(sinr_cosp, cosr_cosp))

    sinp = 2.0 * (w * y - z * x)
    if abs(sinp) >= 1.0:
        pitch = math.degrees(math.copysign(math.pi / 2.0, sinp))
    else:
        pitch = math.degrees(math.asin(sinp))

    siny_cosp = 2.0 * (w * z + x * y)
    cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
    yaw = math.degrees(math.atan2(siny_cosp, cosy_cosp)) % 360.0
    return roll, pitch, yaw


def angular_difference_rad(a: Quaternion, b: Quaternion) -> float:
    na = normalize(a)
    nb = normalize(b)
    if na is None or nb is None:
        return math.inf
    delta = multiply(conjugate(na), nb)
    w = max(-1.0, min(1.0, abs(delta[0])))
    return 2.0 * math.acos(w)


def rotate_vector(q: Quaternion, v: tuple[float, float, float]) -> tuple[float, float, float]:
    nq = normalize(q)
    if nq is None:
        raise ValueError("Invalid quaternion")
    rotated = multiply(multiply(nq, (0.0, v[0], v[1], v[2])), conjugate(nq))
    return rotated[1], rotated[2], rotated[3]


def bno_xyzw_to_wxyz(i: float, j: float, k: float, real: float) -> Quaternion | None:
    return normalize((real, i, j, k))
