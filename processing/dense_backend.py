"""Optional dense reconstruction backend placeholder."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from processing.sfm_backend import SfMResult


@dataclass(frozen=True)
class DenseResult:
    """Dense reconstruction result summary."""

    success: bool
    backend_name: str
    dense_points: int = 0
    output_path: Path | None = None
    message: str = ""


class ColmapPatchMatchBackend:
    """Isolated optional dense backend.

    Dense MVS is intentionally not required for flight or quick post-flight
    diagnostics.
    """

    backend_name = "COLMAP PatchMatch"

    def run_dense_reconstruction(
        self,
        sfm: SfMResult,
        output_dir: Path,
        enabled: bool = False,
    ) -> DenseResult:
        output_dir.mkdir(parents=True, exist_ok=True)
        if not enabled:
            return DenseResult(
                success=False,
                backend_name=self.backend_name,
                output_path=output_dir,
                message="Dense reconstruction disabled by profile/options.",
            )
        if not sfm.success:
            return DenseResult(
                success=False,
                backend_name=self.backend_name,
                output_path=output_dir,
                message="Dense reconstruction skipped because sparse SfM did not succeed.",
            )
        return DenseResult(
            success=False,
            backend_name=self.backend_name,
            output_path=output_dir,
            message="Dense reconstruction adapter is reserved for future COLMAP/OpenMVS integration.",
        )
