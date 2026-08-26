"""Finalize comparison artifacts for the Wietrznia SfM test."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
VENV_SITE = PROJECT_ROOT / "venv" / "Lib" / "site-packages"
if VENV_SITE.exists():
    sys.path.insert(0, str(VENV_SITE))

import cv2
import numpy as np
import pycolmap

from processing.sfm_backend import _reprojection_errors, _write_camera_poses


def _read_image(path: Path) -> np.ndarray:
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        raise FileNotFoundError(path)
    return image


def _fit_height(image: np.ndarray, height: int) -> np.ndarray:
    scale = height / image.shape[0]
    return cv2.resize(image, (max(1, int(round(image.shape[1] * scale))), height), interpolation=cv2.INTER_AREA)


def _write_comparison(before: Path, after: Path, output: Path) -> None:
    left = _read_image(before)
    right = _read_image(after)
    height = min(left.shape[0], right.shape[0], 1400)
    left = _fit_height(left, height)
    right = _fit_height(right, height)
    pad = np.full((height, 12, 3), 20, dtype=np.uint8)
    comparison = np.hstack([left, pad, right])
    cv2.imwrite(str(output), comparison, [int(cv2.IMWRITE_JPEG_QUALITY), 92])


def _scatter(points: np.ndarray, output: Path, color: tuple[int, int, int]) -> None:
    canvas = np.full((900, 1200, 3), 255, dtype=np.uint8)
    if len(points) == 0:
        cv2.imwrite(str(output), canvas)
        return
    xy = points[:, :2].astype(np.float64)
    mn = xy.min(axis=0)
    mx = xy.max(axis=0)
    span = np.maximum(mx - mn, 1e-9)
    uv = (xy - mn) / span
    uv[:, 0] = 40 + uv[:, 0] * 1120
    uv[:, 1] = 860 - uv[:, 1] * 820
    for x, y in uv.astype(int):
        cv2.circle(canvas, (int(x), int(y)), 1, color, -1)
    cv2.imwrite(str(output), canvas)


def _trajectory(centers: np.ndarray, output: Path) -> None:
    canvas = np.full((900, 1200, 3), 255, dtype=np.uint8)
    if len(centers) == 0:
        cv2.imwrite(str(output), canvas)
        return
    xy = centers[:, :2].astype(np.float64)
    mn = xy.min(axis=0)
    mx = xy.max(axis=0)
    span = np.maximum(mx - mn, 1e-9)
    uv = (xy - mn) / span
    uv[:, 0] = 60 + uv[:, 0] * 1080
    uv[:, 1] = 840 - uv[:, 1] * 780
    pts = uv.astype(int)
    for idx in range(1, len(pts)):
        cv2.line(canvas, tuple(pts[idx - 1]), tuple(pts[idx]), (40, 120, 220), 2, cv2.LINE_AA)
    for idx, point in enumerate(pts):
        cv2.circle(canvas, tuple(point), 4, (220, 80, 30), -1, cv2.LINE_AA)
        if idx % 5 == 0:
            cv2.putText(canvas, str(idx + 1), tuple(point + np.array([6, -6])), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (20, 20, 20), 1)
    cv2.imwrite(str(output), canvas)


def run(output_dir: Path, baseline_dir: Path) -> None:
    final_dir = output_dir / "final"
    preview_dir = output_dir / "previews"
    sparse_dir = output_dir / "reconstruction" / "sparse"
    final_dir.mkdir(parents=True, exist_ok=True)
    preview_dir.mkdir(parents=True, exist_ok=True)

    before = baseline_dir / "stitched_terrain_before.jpg"
    after = final_dir / "stitched_terrain_after.jpg"
    current = final_dir / "stitched_terrain.jpg"
    if before.exists():
        cv2.imwrite(str(final_dir / "stitched_terrain_before.jpg"), _read_image(before))
    if current.exists():
        cv2.imwrite(str(after), _read_image(current))
        cv2.imwrite(str(final_dir / "orthomosaic_preview.jpg"), _read_image(current))
    if before.exists() and after.exists():
        _write_comparison(before, after, final_dir / "before_after_comparison.jpg")

    reconstruction = pycolmap.Reconstruction(sparse_dir / "model")
    _write_camera_poses(reconstruction, sparse_dir / "camera_poses.csv")
    errors = _reprojection_errors(reconstruction)
    points = np.asarray([point.xyz for point in reconstruction.points3D.values()], dtype=np.float64)
    centers = []
    for image in sorted(reconstruction.images.values(), key=lambda item: item.name):
        centers.append(image.projection_center())
    centers_arr = np.asarray(centers, dtype=np.float64)
    _scatter(points, preview_dir / "sparse_reconstruction.png", (50, 50, 50))
    _trajectory(centers_arr, preview_dir / "camera_trajectory.png")

    report_path = output_dir / "diagnostics" / "reconstruction_report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["sfm"]["registered_images"] = int(reconstruction.num_reg_images())
    report["sfm"]["registration_rate"] = reconstruction.num_reg_images() / max(1, report["dataset"]["selected_images"])
    report["sfm"]["sparse_points"] = int(reconstruction.num_points3D())
    report["sfm"]["mean_reprojection_error"] = float(np.mean(errors)) if errors else None
    report["sfm"]["median_reprojection_error"] = float(np.median(errors)) if errors else None
    report["sfm"]["largest_component_images"] = int(reconstruction.num_reg_images())
    report["final_outputs"] = {
        "stitched_terrain_before": str(final_dir / "stitched_terrain_before.jpg"),
        "stitched_terrain_after": str(after),
        "before_after_comparison": str(final_dir / "before_after_comparison.jpg"),
        "orthomosaic_preview": str(final_dir / "orthomosaic_preview.jpg"),
        "orthomosaic_tif": None,
    }
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    baseline = {}
    baseline_path = baseline_dir / "baseline_report.json"
    if baseline_path.exists():
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    improvement = {
        "before": {
            "method": baseline.get("method", "pairwise_homography_mosaic"),
            "images_used": 16,
            "registered_images": 0,
            "verified_graph_edges": 83,
            "reprojection_error_px": None,
            "sparse_points": 0,
            "dense_points": 0,
            "gps_alignment_rmse_m": None,
            "output_coverage_megapixels": baseline.get("megapixels"),
            "diagnosed_ghosting": "visible duplicated roads/paths and frame seams",
        },
        "after": {
            "method": "pycolmap_global_sfm_plus_existing_mosaic_preview",
            "registered_images": int(reconstruction.num_reg_images()),
            "registration_rate": reconstruction.num_reg_images() / max(1, report["dataset"]["selected_images"]),
            "verified_graph_edges": report["candidate_graph"]["verified_edges"],
            "mean_reprojection_error_px": float(np.mean(errors)) if errors else None,
            "median_reprojection_error_px": float(np.median(errors)) if errors else None,
            "sparse_points": int(reconstruction.num_points3D()),
            "dense_points": 0,
            "gps_alignment_rmse_m": None,
            "output_coverage_megapixels": report["combined_image"].get("megapixels"),
            "diagnosed_ghosting": "not fully solved; dense DSM orthorectification is still skipped",
        },
        "blockers": [
            "No EXIF GPS was available in the visible dataset copy, so GPS/global alignment could not run.",
            "Dense COLMAP PatchMatch/DSM/true orthorectification is not implemented in this run.",
            "The visual after image is still the bounded mosaic preview; the new successful upgrade is sparse global SfM and bundle adjustment.",
        ],
    }
    (output_dir / "diagnostics" / "improvement_report.json").write_text(json.dumps(improvement, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    args = parser.parse_args()
    run(args.output, args.baseline)


if __name__ == "__main__":
    main()
