"""Isolated Structure-from-Motion backend adapters."""

from __future__ import annotations

from dataclasses import dataclass
import csv
import json
from pathlib import Path
import shutil
import sys

import numpy as np

from mapping.image_graph import ImageGraph
from storage.mission_manifest import ImageMetadata
from vision.feature_detection import FeatureSet
from vision.geometric_verification import GeometryResult

PROJECT_ROOT = Path(__file__).resolve().parents[1]
VENV_SITE = PROJECT_ROOT / "venv" / "Lib" / "site-packages"
if VENV_SITE.exists():
    sys.path.insert(0, str(VENV_SITE))


@dataclass(frozen=True)
class SfMResult:
    """Sparse reconstruction result summary."""

    success: bool
    backend_name: str
    registered_images: int = 0
    sparse_points: int = 0
    output_path: Path | None = None
    message: str = ""
    mean_reprojection_error_px: float | None = None
    median_reprojection_error_px: float | None = None
    largest_component_images: int = 0


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
        features: dict[str, FeatureSet] | None = None,
        pair_matches: dict[tuple[str, str], tuple] | None = None,
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
        if features is not None and pair_matches is not None:
            return self._run_from_garuda_features(
                images,
                geometries,
                features,
                pair_matches,
                output_dir,
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

    def _run_from_garuda_features(
        self,
        images: tuple[ImageMetadata, ...],
        geometries: dict[tuple[str, str], GeometryResult],
        features: dict[str, FeatureSet],
        pair_matches: dict[tuple[str, str], tuple],
        output_dir: Path,
    ) -> SfMResult:
        import pycolmap

        database_path = output_dir / "garuda_colmap.db"
        image_root = output_dir / "images"
        model_root = output_dir / "models"
        if database_path.exists():
            database_path.unlink()
        if image_root.exists():
            shutil.rmtree(image_root)
        if model_root.exists():
            shutil.rmtree(model_root)
        image_root.mkdir(parents=True, exist_ok=True)
        model_root.mkdir(parents=True, exist_ok=True)

        for metadata in images:
            link_path = image_root / metadata.image_name
            if not link_path.exists():
                shutil.copy2(metadata.image_path, link_path)

        db = pycolmap.Database.open(database_path)
        camera = pycolmap.Camera.create_from_model_name(
            1,
            "SIMPLE_RADIAL",
            float(images[0].camera.focal_length_px),
            int(images[0].camera.width_px),
            int(images[0].camera.height_px),
        )
        camera.params[1] = float(images[0].camera.center_x_px)
        camera.params[2] = float(images[0].camera.center_y_px)
        if len(camera.params) > 3:
            camera.params[3] = 0.0
        db.write_camera(camera, use_camera_id=True)

        garuda_to_colmap: dict[str, int] = {}
        colmap_to_garuda: dict[int, str] = {}
        for image_id, metadata in enumerate(images, start=1):
            image = pycolmap.Image()
            image.image_id = image_id
            image.name = metadata.image_name
            image.camera_id = 1
            db.write_image(image, use_image_id=True)
            garuda_to_colmap[metadata.image_name] = image_id
            colmap_to_garuda[image_id] = metadata.image_name
            feature_set = features.get(metadata.image_name)
            if feature_set is None:
                continue
            db.write_keypoints(image_id, keypoints_to_original_array(feature_set))

        accepted_pairs = 0
        for key, geometry in geometries.items():
            if not geometry.accepted:
                continue
            matches = pair_matches.get(key)
            if not matches:
                continue
            inlier_matches = matches
            if geometry.inlier_mask is not None:
                mask = np.asarray(geometry.inlier_mask).reshape(-1).astype(bool)
                inlier_matches = tuple(match for match, keep in zip(matches, mask) if keep)
            if not inlier_matches:
                continue
            image_id1 = garuda_to_colmap[key[0]]
            image_id2 = garuda_to_colmap[key[1]]
            matrix = np.asarray(
                [[int(match.queryIdx), int(match.trainIdx)] for match in inlier_matches],
                dtype=np.uint32,
            )
            db.write_matches(image_id1, image_id2, matrix)
            two_view = pycolmap.TwoViewGeometry()
            two_view.inlier_matches = matrix
            if geometry.model_type == "ESSENTIAL":
                two_view.config = int(pycolmap.TwoViewGeometryConfiguration.CALIBRATED)
                two_view.E = np.asarray(geometry.matrix, dtype=np.float64)
            elif geometry.model_type == "FUNDAMENTAL":
                two_view.config = int(pycolmap.TwoViewGeometryConfiguration.UNCALIBRATED)
                two_view.F = np.asarray(geometry.matrix, dtype=np.float64)
            elif geometry.model_type == "HOMOGRAPHY":
                two_view.config = int(pycolmap.TwoViewGeometryConfiguration.PLANAR)
                two_view.H = np.asarray(geometry.matrix, dtype=np.float64)
            else:
                two_view.config = int(pycolmap.TwoViewGeometryConfiguration.UNDEFINED)
            db.write_two_view_geometry(image_id1, image_id2, two_view)
            accepted_pairs += 1

        db.close()
        with open(output_dir / "image_id_map.json", "w", encoding="utf-8") as handle:
            json.dump(
                {
                    "garuda_to_colmap_image_id": garuda_to_colmap,
                    "colmap_to_garuda_image_id": colmap_to_garuda,
                    "accepted_pairs_inserted": accepted_pairs,
                },
                handle,
                indent=2,
            )

        try:
            options = pycolmap.IncrementalPipelineOptions()
            reconstructions = pycolmap.incremental_mapping(
                database_path,
                image_root,
                model_root,
                options,
            )
        except Exception as exc:
            return SfMResult(
                success=False,
                backend_name=self.backend_name,
                output_path=output_dir,
                message=f"PyCOLMAP mapping failed after database import: {exc}",
            )

        if not reconstructions:
            return SfMResult(
                success=False,
                backend_name=self.backend_name,
                output_path=output_dir,
                message="PyCOLMAP produced no reconstruction from imported GARUDA graph.",
            )

        reconstruction = max(reconstructions.values(), key=lambda item: item.num_reg_images())
        try:
            pycolmap.bundle_adjustment(reconstruction)
        except Exception:
            pass
        model_path = output_dir / "model"
        model_path.mkdir(parents=True, exist_ok=True)
        reconstruction.write(model_path)
        errors = _reprojection_errors(reconstruction)
        _write_camera_poses(reconstruction, output_dir / "camera_poses.csv")
        return SfMResult(
            success=reconstruction.num_reg_images() > 0,
            backend_name=self.backend_name,
            registered_images=int(reconstruction.num_reg_images()),
            sparse_points=int(reconstruction.num_points3D()),
            output_path=model_path,
            message="PyCOLMAP sparse reconstruction completed from imported GARUDA features.",
            mean_reprojection_error_px=float(np.mean(errors)) if errors else None,
            median_reprojection_error_px=float(np.median(errors)) if errors else None,
            largest_component_images=int(reconstruction.num_reg_images()),
        )


def keypoints_to_original_array(features: FeatureSet) -> np.ndarray:
    """Return COLMAP keypoints in original image coordinates."""
    inv_scale = 1.0 / max(float(features.scale), 1e-12)
    rows = [
        [kp.pt[0] * inv_scale, kp.pt[1] * inv_scale, kp.size * inv_scale, kp.angle]
        for kp in features.keypoints
    ]
    return np.asarray(rows, dtype=np.float32)


def _reprojection_errors(reconstruction) -> list[float]:
    errors: list[float] = []
    for point in reconstruction.points3D.values():
        if hasattr(point, "error"):
            errors.append(float(point.error))
    return errors


def _write_camera_poses(reconstruction, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "filename",
                "camera_id",
                "qw",
                "qx",
                "qy",
                "qz",
                "tx",
                "ty",
                "tz",
                "center_x",
                "center_y",
                "center_z",
            ],
        )
        writer.writeheader()
        for image in reconstruction.images.values():
            try:
                cam_from_world = image.cam_from_world()
                rotation_xyzw = cam_from_world.rotation.quat
                rotation = [
                    rotation_xyzw[3],
                    rotation_xyzw[0],
                    rotation_xyzw[1],
                    rotation_xyzw[2],
                ]
                translation = cam_from_world.translation
                center = image.projection_center()
            except Exception:
                rotation = [float("nan")] * 4
                translation = [float("nan")] * 3
                center = [float("nan")] * 3
            writer.writerow(
                {
                    "filename": image.name,
                    "camera_id": image.camera_id,
                    "qw": rotation[0],
                    "qx": rotation[1],
                    "qy": rotation[2],
                    "qz": rotation[3],
                    "tx": translation[0],
                    "ty": translation[1],
                    "tz": translation[2],
                    "center_x": center[0],
                    "center_y": center[1],
                    "center_z": center[2],
                }
            )
