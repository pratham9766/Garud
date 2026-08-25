"""
Create pose-normalized working images without discarding raw geometry.

The output canvas is expanded so rotated content is preserved for later final
cropping after mosaic generation.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass(frozen=True)
class NormalizedImage:
    """Pose-normalized image plus the transform applied to create it."""

    image: np.ndarray
    transform: np.ndarray
    canvas_size: tuple[int, int]


def warp_to_expanded_canvas(
    image: np.ndarray,
    homography: np.ndarray,
    canvas_size: tuple[int, int] | None = None,
) -> NormalizedImage:
    """
    Warp an image onto an expanded transparent canvas.

    Args:
        image: Source BGR/RGB/gray image.
        homography: Prior transform from source image to normalized image.
        canvas_size: Optional ``(width, height)``. If omitted, a square canvas
            large enough to hold arbitrary in-plane rotation is used.
    """
    height, width = image.shape[:2]
    if canvas_size is None:
        side = int(np.ceil(np.hypot(width, height)))
        canvas_size = (side, side)

    canvas_width, canvas_height = canvas_size
    translate = np.array(
        [
            [1.0, 0.0, (canvas_width - width) / 2.0],
            [0.0, 1.0, (canvas_height - height) / 2.0],
            [0.0, 0.0, 1.0],
        ],
        dtype=np.float64,
    )
    transform = translate @ homography
    warped = cv2.warpPerspective(
        image,
        transform,
        canvas_size,
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0, 0, 0, 0),
    )
    return NormalizedImage(
        image=warped,
        transform=transform,
        canvas_size=canvas_size,
    )

