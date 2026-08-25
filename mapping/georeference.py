"""Georeferencing diagnostics for reconstructed camera trajectories."""

from __future__ import annotations

from dataclasses import dataclass

from storage.mission_manifest import ImageMetadata


@dataclass(frozen=True)
class GeoreferenceResult:
    """GPS alignment result summary."""

    success: bool
    estimated_scale: float | None = None
    gps_alignment_rmse_m: float | None = None
    registered_images: int = 0
    message: str = ""


def summarize_gps_priors(images: tuple[ImageMetadata, ...]) -> GeoreferenceResult:
    """Return lightweight georeferencing diagnostics before SfM alignment exists."""
    gps_images = [image for image in images if image.latitude != 0.0 and image.longitude != 0.0]
    if not gps_images:
        return GeoreferenceResult(success=False, message="No GPS priors available.")
    return GeoreferenceResult(
        success=False,
        registered_images=0,
        message=(
            f"{len(gps_images)} GPS camera priors available. Full SfM-to-GPS "
            "alignment requires a successful sparse reconstruction."
        ),
    )
