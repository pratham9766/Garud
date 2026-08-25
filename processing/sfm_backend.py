"""Isolated Structure-from-Motion backend adapters."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from mapping.image_graph import ImageGraph
from storage.mission_manifest import ImageMetadata
from vision.geometric_verification import GeometryResult


@dataclass(frozen=True)
class SfMResult:
    """Sparse reconstruction result summary."""

    success: bool
    backend_name: str
    registered_images: int = 0
    sparse_points: int = 0
    output_path: Path | None = None
    message: str = ""


class PyColmapBackend:
    """Thin optional PyCOLMAP adapter.

    The GARUDA pipeline remains importable without pycolmap. Full database
    import/reconstruction is intentionally isolated here.
    """

    backend_name = "pycolmap"

    def __init__(self) -> None:
        try:
            import pycolmap  # noqa: F401
        except Exception as exc:
            self.available = False
            self.unavailable_reason = str(exc)
        else:
            self.available = True
            self.unavailable_reason = ""

    def run_sparse_reconstruction(
        self,
        images: tuple[ImageMetadata, ...],
        graph: ImageGraph,
        geometries: dict[tuple[str, str], GeometryResult],
        output_dir: Path,
    ) -> SfMResult:
        output_dir.mkdir(parents=True, exist_ok=True)
        if not self.available:
            return SfMResult(
                success=False,
                backend_name=self.backend_name,
                message=f"pycolmap unavailable: {self.unavailable_reason}",
                output_path=output_dir,
            )
        verified_edges = sum(1 for geometry in geometries.values() if geometry.accepted)
        if verified_edges == 0:
            return SfMResult(
                success=False,
                backend_name=self.backend_name,
                message="No verified edges available for SfM.",
                output_path=output_dir,
            )
        return SfMResult(
            success=False,
            backend_name=self.backend_name,
            registered_images=0,
            sparse_points=0,
            output_path=output_dir,
            message=(
                "PyCOLMAP is installed, but full COLMAP database import and "
                "mapper execution are not implemented in this lightweight adapter yet."
            ),
        )
