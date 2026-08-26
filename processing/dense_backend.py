"""Optional dense reconstruction backend placeholder."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys
import time

from processing.sfm_backend import SfMResult

PROJECT_ROOT = Path(__file__).resolve().parents[1]
VENV_SITE = PROJECT_ROOT / "venv" / "Lib" / "site-packages"
if VENV_SITE.exists():
    sys.path.insert(0, str(VENV_SITE))


@dataclass(frozen=True)
class DenseResult:
    """Dense reconstruction result summary."""

    success: bool
    backend_name: str
    dense_points: int = 0
    output_path: Path | None = None
    message: str = ""
    elapsed_seconds: float = 0.0
    output_size_bytes: int = 0


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
        max_image_size: int = 1200,
        num_threads: int = 2,
    ) -> DenseResult:
        output_dir.mkdir(parents=True, exist_ok=True)
        start = time.perf_counter()
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
        if sfm.output_path is None or not Path(sfm.output_path).exists():
            return DenseResult(
                success=False,
                backend_name=self.backend_name,
                output_path=output_dir,
                message="Dense reconstruction skipped because sparse model path is missing.",
            )
        try:
            import pycolmap
        except Exception as exc:
            return DenseResult(
                success=False,
                backend_name=self.backend_name,
                output_path=output_dir,
                message=f"pycolmap unavailable for dense reconstruction: {exc}",
            )

        sparse_model = Path(sfm.output_path)
        sparse_root = sparse_model.parent
        image_root = sparse_root / "images"
        workspace = output_dir / "colmap_workspace"
        fused_ply = output_dir / "fused.ply"
        try:
            undistort_options = pycolmap.UndistortCameraOptions()
            undistort_options.max_image_size = int(max_image_size)
            pycolmap.undistort_images(
                workspace,
                sparse_model,
                image_root,
                output_type="COLMAP",
                undistort_options=undistort_options,
                num_threads=int(num_threads),
            )

            patch_options = pycolmap.PatchMatchOptions()
            patch_options.max_image_size = int(max_image_size)
            patch_options.num_threads = int(num_threads)
            patch_options.cache_size = 2.0
            patch_options.gpu_index = "-1"
            pycolmap.patch_match_stereo(
                workspace,
                workspace_format="COLMAP",
                options=patch_options,
            )

            fusion_options = pycolmap.StereoFusionOptions()
            fusion_options.max_image_size = int(max_image_size)
            fusion_options.num_threads = int(num_threads)
            fusion_options.cache_size = 2.0
            dense_reconstruction = pycolmap.stereo_fusion(
                fused_ply,
                workspace,
                workspace_format="COLMAP",
                input_type="geometric",
                options=fusion_options,
                output_type="PLY",
            )
        except Exception as exc:
            return DenseResult(
                success=False,
                backend_name=self.backend_name,
                output_path=fused_ply,
                message=f"COLMAP dense reconstruction failed: {exc}",
                elapsed_seconds=time.perf_counter() - start,
            )

        point_count = 0
        if dense_reconstruction is not None and hasattr(dense_reconstruction, "num_points3D"):
            point_count = int(dense_reconstruction.num_points3D())
        size = fused_ply.stat().st_size if fused_ply.exists() else 0
        return DenseResult(
            success=fused_ply.exists() and size > 0 and point_count > 0,
            backend_name=self.backend_name,
            dense_points=point_count,
            output_path=fused_ply,
            message="COLMAP dense PatchMatch and stereo fusion completed.",
            elapsed_seconds=time.perf_counter() - start,
            output_size_bytes=size,
        )
