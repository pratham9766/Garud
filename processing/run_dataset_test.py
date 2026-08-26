"""Dataset-mode GARUDA terrain mapping test runner."""

from __future__ import annotations

import argparse
import csv
from dataclasses import asdict
from datetime import datetime
import json
import math
from pathlib import Path
import re
import sys
import time
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
VENV_SITE = PROJECT_ROOT / "venv" / "Lib" / "site-packages"
if VENV_SITE.exists():
    sys.path.insert(0, str(VENV_SITE))

import cv2
import numpy as np
from PIL import ExifTags, Image

import config
from mapping.image_graph import ImageGraph, build_candidate_graph
from mapping.dsm import generate_dsm_from_point_cloud
from processing.dense_backend import ColmapPatchMatchBackend
from processing.quality_scoring import ImageQuality, score_image_quality
from processing.sfm_backend import PyColmapBackend
from storage.mission_manifest import CameraModel, ImageMetadata
from vision.feature_cache import FeatureCache, FeatureCacheConfig
from vision.feature_detection import FeatureDetector, FeatureSet, resize_for_features
from vision.feature_matching import FeatureMatcher, raw_knn_match_count
from vision.geometric_verification import GeometryResult, verify_geometry
from vision.feature_tracks import build_feature_tracks_with_diagnostics

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}
GPS_TAGS = ExifTags.GPSTAGS
TAGS = ExifTags.TAGS


def _numeric_key(path: Path) -> tuple[int, str]:
    matches = re.findall(r"\d+", path.stem)
    return (int(matches[-1]) if matches else 10**12, path.name.lower())


def _ratio(value: Any) -> float:
    try:
        return float(value)
    except TypeError:
        return float(value[0]) / float(value[1])


def _dms_to_decimal(values: Any, ref: str) -> float:
    deg, minute, sec = values
    decimal = _ratio(deg) + _ratio(minute) / 60.0 + _ratio(sec) / 3600.0
    if ref in {"S", "W"}:
        decimal *= -1.0
    return decimal


def _exif(path: Path) -> dict[str, Any]:
    try:
        with Image.open(path) as image:
            raw = image.getexif()
            data = {TAGS.get(tag, tag): value for tag, value in raw.items()}
            gps_raw = data.get("GPSInfo") or {}
            data["GPSInfo"] = {GPS_TAGS.get(tag, tag): value for tag, value in gps_raw.items()}
            data["width"], data["height"] = image.size
            return data
    except Exception:
        image = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if image is None:
            return {}
        height, width = image.shape[:2]
        return {"width": width, "height": height, "GPSInfo": {}}


def _exif_timestamp(data: dict[str, Any]) -> float | None:
    value = data.get("DateTimeOriginal") or data.get("DateTimeDigitized") or data.get("DateTime")
    if not value:
        return None
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="ignore")
    for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(str(value), fmt).timestamp()
        except ValueError:
            pass
    return None


def _gps(data: dict[str, Any]) -> tuple[float | None, float | None, float | None]:
    gps = data.get("GPSInfo") or {}
    try:
        lat = _dms_to_decimal(gps["GPSLatitude"], gps.get("GPSLatitudeRef", "N"))
        lon = _dms_to_decimal(gps["GPSLongitude"], gps.get("GPSLongitudeRef", "E"))
    except Exception:
        lat = None
        lon = None
    try:
        alt = _ratio(gps["GPSAltitude"])
        if int(gps.get("GPSAltitudeRef", 0)) == 1:
            alt *= -1.0
    except Exception:
        alt = None
    return lat, lon, alt


def find_images(images_dir: Path) -> list[Path]:
    images = [
        path
        for path in images_dir.iterdir()
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
    ]
    exif_times = {path: _exif_timestamp(_exif(path)) for path in images}
    if any(value is not None for value in exif_times.values()):
        return sorted(images, key=lambda path: (exif_times[path] is None, exif_times[path] or 0.0, _numeric_key(path)))
    return sorted(images, key=_numeric_key)


def create_output_tree(output: Path) -> dict[str, Path]:
    paths = {
        "root": output,
        "final": output / "final",
        "reconstruction": output / "reconstruction",
        "sparse": output / "reconstruction" / "sparse",
        "dense": output / "reconstruction" / "dense",
        "elevation": output / "elevation",
        "diagnostics": output / "diagnostics",
        "previews": output / "previews",
        "matches": output / "previews" / "feature_matches",
        "logs": output / "logs",
        "cache": output / "cache" / "features",
    }
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
    return paths


def metadata_for(paths: list[Path], exif_by_path: dict[Path, dict[str, Any]]) -> list[ImageMetadata]:
    records: list[ImageMetadata] = []
    base_time = None
    for idx, path in enumerate(paths):
        data = exif_by_path[path]
        timestamp = _exif_timestamp(data)
        if timestamp is not None and base_time is None:
            base_time = timestamp
        lat, lon, alt = _gps(data)
        width = int(data.get("width") or config.CAMERA_SENSOR_WIDTH_PX)
        height = int(data.get("height") or config.CAMERA_SENSOR_HEIGHT_PX)
        focal_px = max(width, height) * 0.78
        camera = CameraModel(
            width_px=width,
            height_px=height,
            focal_length_px=focal_px,
            center_x_px=width / 2.0,
            center_y_px=height / 2.0,
        )
        t = (timestamp - base_time) if timestamp is not None and base_time is not None else float(idx)
        records.append(
            ImageMetadata(
                image_name=path.name,
                image_path=path,
                timestamp=t,
                latitude=lat or 0.0,
                longitude=lon or 0.0,
                gps_altitude_m=alt or 0.0,
                baro_altitude_m=0.0,
                roll_deg=0.0,
                pitch_deg=0.0,
                yaw_deg=0.0,
                gyro_x_dps=0.0,
                gyro_y_dps=0.0,
                gyro_z_dps=0.0,
                camera=camera,
                image_timestamp=t,
                mission_state="DATASET_TEST",
            )
        )
    return records


def write_dataset_csv(records: list[ImageMetadata], output_path: Path) -> None:
    fields = [
        "timestamp", "mission_time", "state", "latitude", "longitude", "gps_altitude",
        "baro_altitude", "roll", "pitch", "yaw", "gyro_x", "gyro_y", "gyro_z",
        "image_name", "image_timestamp", "battery", "status",
    ]
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for record in records:
            writer.writerow(
                {
                    "timestamp": record.timestamp,
                    "mission_time": record.timestamp,
                    "state": "DATASET_TEST",
                    "latitude": record.latitude if record.latitude else "",
                    "longitude": record.longitude if record.longitude else "",
                    "gps_altitude": record.gps_altitude_m if record.gps_altitude_m else "",
                    "baro_altitude": "",
                    "roll": "",
                    "pitch": "",
                    "yaw": "",
                    "gyro_x": "",
                    "gyro_y": "",
                    "gyro_z": "",
                    "image_name": record.image_name,
                    "image_timestamp": record.image_timestamp,
                    "battery": "",
                    "status": "DATASET_TEST",
                }
            )


def score_images(records: list[ImageMetadata], out_csv: Path) -> list[ImageQuality]:
    qualities = []
    for record in records:
        image = cv2.imread(str(record.image_path), cv2.IMREAD_COLOR)
        qualities.append(score_image_quality(image, record))
        del image
    with out_csv.open("w", newline="", encoding="utf-8") as handle:
        fields = list(asdict(qualities[0]).keys()) if qualities else ["image_name"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for quality in qualities:
            row = asdict(quality)
            row["flags"] = ";".join(quality.flags)
            writer.writerow(row)
    return qualities


def write_graph_csv(graph: ImageGraph, out_csv: Path) -> None:
    with out_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "image_a", "image_b", "time_difference", "gps_distance", "altitude_ratio",
                "predicted_overlap", "candidate_score", "candidate_reason",
            ],
        )
        writer.writeheader()
        for edge in graph.edges:
            writer.writerow(
                {
                    "image_a": edge.source,
                    "image_b": edge.target,
                    "time_difference": edge.time_delta_s,
                    "gps_distance": edge.distance_m,
                    "altitude_ratio": edge.altitude_ratio,
                    "predicted_overlap": edge.predicted_overlap,
                    "candidate_score": edge.score,
                    "candidate_reason": edge.reason,
                }
            )


def graph_preview(graph: ImageGraph, records: list[ImageMetadata], output: Path) -> None:
    width, height = 1400, 420
    canvas = np.full((height, width, 3), 255, dtype=np.uint8)
    names = [record.image_name for record in records]
    xs = {name: int(40 + i * (width - 80) / max(1, len(names) - 1)) for i, name in enumerate(names)}
    y = height // 2
    for edge in graph.edges:
        cv2.line(canvas, (xs[edge.source], y), (xs[edge.target], y), (210, 180, 80), 1, cv2.LINE_AA)
    for i, name in enumerate(names):
        cv2.circle(canvas, (xs[name], y), 5, (40, 90, 200), -1, cv2.LINE_AA)
        if i % 5 == 0:
            cv2.putText(canvas, Path(name).stem, (xs[name] - 25, y + 28), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (40, 40, 40), 1)
    cv2.imwrite(str(output), canvas)


def extract_features(
    records: list[ImageMetadata],
    cache_dir: Path,
    max_dim: int,
    force: bool,
) -> tuple[dict[str, FeatureSet], dict[str, Any]]:
    detector = FeatureDetector(preferred="SIFT", max_features=config.MAPPING_FEATURE_MAX_FEATURES)
    settings = FeatureCacheConfig(detector.detector_name, max_dim, config.MAPPING_FEATURE_MAX_FEATURES)
    cache = FeatureCache(cache_dir)
    features: dict[str, FeatureSet] = {}
    hits = 0
    misses = 0
    start = time.perf_counter()
    for record in records:
        if not force and cache.load(record, settings) is not None:
            hits += 1
        else:
            misses += 1
        features[record.image_name] = cache.get_or_extract(record, detector, settings, force_recompute=force)
    elapsed = time.perf_counter() - start
    return features, {
        "backend": detector.detector_name,
        "features_per_image": float(np.mean([len(item.keypoints) for item in features.values()])) if features else 0.0,
        "elapsed_seconds": elapsed,
        "cache_hits": hits,
        "cache_misses": misses,
    }


def match_and_verify(
    graph: ImageGraph,
    records_by_name: dict[str, ImageMetadata],
    features: dict[str, FeatureSet],
    out_csv: Path,
) -> tuple[dict[tuple[str, str], GeometryResult], dict[tuple[str, str], tuple[Any, ...]], dict[tuple[str, str], np.ndarray]]:
    matcher = FeatureMatcher(preferred="LIGHTGLUE", ratio=config.MAPPING_MATCH_RATIO)
    geometries: dict[tuple[str, str], GeometryResult] = {}
    matches_by_pair: dict[tuple[str, str], tuple[Any, ...]] = {}
    homographies: dict[tuple[str, str], np.ndarray] = {}
    with out_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "image_a", "image_b", "raw_matches", "filtered_matches", "inliers",
                "inlier_ratio", "selected_geometry", "verification_status",
            ],
        )
        writer.writeheader()
        for edge in graph.edges:
            first = features[edge.source]
            second = features[edge.target]
            matches = matcher.match(first, second)
            geometry = verify_geometry(
                first,
                second,
                matches,
                camera=records_by_name[edge.source].camera,
                raw_match_count=raw_knn_match_count(first, second),
            )
            key = (edge.source, edge.target)
            geometries[key] = geometry
            matches_by_pair[key] = matches
            if len(matches) >= 4:
                pts_a = np.float32([first.keypoints[m.queryIdx].pt for m in matches])
                pts_b = np.float32([second.keypoints[m.trainIdx].pt for m in matches])
                h, mask = cv2.findHomography(pts_a, pts_b, cv2.RANSAC, 4.0)
                if h is not None and mask is not None and int(np.count_nonzero(mask)) >= config.MAPPING_MIN_GEOMETRIC_INLIERS:
                    homographies[key] = h
            writer.writerow(
                {
                    "image_a": edge.source,
                    "image_b": edge.target,
                    "raw_matches": geometry.raw_match_count,
                    "filtered_matches": geometry.filtered_match_count,
                    "inliers": geometry.inlier_count,
                    "inlier_ratio": f"{geometry.inlier_ratio:.4f}",
                    "selected_geometry": geometry.model_type,
                    "verification_status": "ACCEPTED" if geometry.accepted else "REJECTED",
                }
            )
    return geometries, matches_by_pair, homographies


def write_track_stats(
    geometries: dict[tuple[str, str], GeometryResult],
    matches_by_pair: dict[tuple[str, str], tuple[Any, ...]],
    output: Path,
) -> dict[str, Any]:
    accepted = {
        key: matches_by_pair[key]
        for key, geometry in geometries.items()
        if geometry.accepted and key in matches_by_pair
    }
    result = build_feature_tracks_with_diagnostics(accepted)
    lengths = [len(track.observations) for track in result.tracks]
    stats = {
        "total_tracks": len(result.tracks),
        "mean_track_length": float(np.mean(lengths)) if lengths else 0.0,
        "median_track_length": float(np.median(lengths)) if lengths else 0.0,
        "max_track_length": int(max(lengths)) if lengths else 0,
        "tracks_rejected_conflicts": result.rejected_conflict_tracks,
        "tracks_rejected_short": result.rejected_short_tracks,
    }
    output.write_text(json.dumps(stats, indent=2), encoding="utf-8")
    return stats


def write_image_id_map_csv(records: list[ImageMetadata], output: Path) -> None:
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["filename", "filename_to_garuda_id", "garuda_id_to_colmap_id", "colmap_id_to_filename"],
        )
        writer.writeheader()
        for idx, record in enumerate(records, start=1):
            writer.writerow(
                {
                    "filename": record.image_name,
                    "filename_to_garuda_id": idx,
                    "garuda_id_to_colmap_id": idx,
                    "colmap_id_to_filename": record.image_name,
                }
            )


def write_match_previews(
    records_by_name: dict[str, ImageMetadata],
    features: dict[str, FeatureSet],
    matches_by_pair: dict[tuple[str, str], tuple[Any, ...]],
    geometries: dict[tuple[str, str], GeometryResult],
    output_dir: Path,
    max_dim: int,
) -> None:
    ranked = sorted(geometries.items(), key=lambda item: item[1].inlier_count, reverse=True)
    choices = []
    if ranked:
        choices.append(("good", ranked[0][0]))
        choices.append(("average", ranked[len(ranked) // 2][0]))
    rejected = next((key for key, geo in reversed(ranked) if not geo.accepted), None)
    if rejected:
        choices.append(("rejected", rejected))
    for label, key in choices:
        a, b = key
        img_a, _ = resize_for_features(cv2.imread(str(records_by_name[a].image_path)), max_dim)
        img_b, _ = resize_for_features(cv2.imread(str(records_by_name[b].image_path)), max_dim)
        preview = cv2.drawMatches(img_a, features[a].keypoints, img_b, features[b].keypoints, list(matches_by_pair[key])[:80], None)
        cv2.imwrite(str(output_dir / f"{label}_{Path(a).stem}_{Path(b).stem}.jpg"), preview)


def _component_transforms(
    records: list[ImageMetadata],
    homographies: dict[tuple[str, str], np.ndarray],
) -> dict[str, np.ndarray]:
    names = [record.image_name for record in records]
    adjacency: dict[str, list[tuple[str, np.ndarray]]] = {name: [] for name in names}
    for (a, b), h_ab in homographies.items():
        adjacency[a].append((b, h_ab))
        adjacency[b].append((a, np.linalg.inv(h_ab)))
    anchor = names[0]
    transforms = {anchor: np.eye(3)}
    queue = [anchor]
    while queue:
        current = queue.pop(0)
        for neighbor, h_current_to_neighbor in adjacency[current]:
            if neighbor in transforms:
                continue
            transforms[neighbor] = transforms[current] @ np.linalg.inv(h_current_to_neighbor)
            queue.append(neighbor)
    return transforms


def build_mosaic(
    records: list[ImageMetadata],
    homographies: dict[tuple[str, str], np.ndarray],
    output_jpg: Path,
    output_png: Path,
    max_dim: int,
    max_canvas_dim: int,
    max_contributors: int,
) -> dict[str, Any]:
    transforms = _component_transforms(records, homographies)
    if len(transforms) < 3:
        return {"success": False, "reason": "Fewer than three images connected by verified homographies.", "contributors": len(transforms)}
    contributor_names = [
        record.image_name
        for record in records
        if record.image_name in transforms
    ][:max_contributors]
    contributor_names = set(contributor_names)
    corners = []
    sizes: dict[str, tuple[int, int]] = {}
    for record in records:
        if record.image_name not in contributor_names:
            continue
        image = cv2.imread(str(record.image_path))
        resized, _ = resize_for_features(image, max_dim)
        h, w = resized.shape[:2]
        sizes[record.image_name] = (w, h)
        pts = np.float32([[0, 0], [w, 0], [w, h], [0, h]]).reshape(-1, 1, 2)
        corners.append(cv2.perspectiveTransform(pts, transforms[record.image_name]))
        del image
        del resized
    all_pts = np.vstack(corners).reshape(-1, 2)
    min_x, min_y = np.floor(all_pts.min(axis=0)).astype(int)
    max_x, max_y = np.ceil(all_pts.max(axis=0)).astype(int)
    raw_width = max_x - min_x
    raw_height = max_y - min_y
    canvas_scale = min(1.0, max_canvas_dim / float(max(raw_width, raw_height, 1)))
    width = max(1, int(math.ceil(raw_width * canvas_scale)))
    height = max(1, int(math.ceil(raw_height * canvas_scale)))
    offset = np.array(
        [
            [canvas_scale, 0, -min_x * canvas_scale],
            [0, canvas_scale, -min_y * canvas_scale],
            [0, 0, 1],
        ],
        dtype=np.float64,
    )
    accum = np.zeros((height, width, 3), dtype=np.float32)
    weights = np.zeros((height, width), dtype=np.float32)
    for record in records:
        if record.image_name not in contributor_names:
            continue
        image = cv2.imread(str(record.image_path))
        resized, _ = resize_for_features(image, max_dim)
        h, w = resized.shape[:2]
        mask = np.ones((h, w), dtype=np.uint8)
        dist = cv2.distanceTransform(mask, cv2.DIST_L2, 3)
        dist = dist / max(float(dist.max()), 1.0)
        warp = offset @ transforms[record.image_name]
        warped = cv2.warpPerspective(resized, warp, (width, height))
        warped_weight = cv2.warpPerspective(dist, warp, (width, height))
        valid = warped_weight > 0
        accum[valid] += warped[valid].astype(np.float32) * warped_weight[valid, None]
        weights[valid] += warped_weight[valid]
        del image
        del resized
        del warped
        del warped_weight
    valid = weights > 1e-6
    mosaic = np.zeros_like(accum, dtype=np.uint8)
    mosaic[valid] = np.clip(accum[valid] / weights[valid, None], 0, 255).astype(np.uint8)
    ys, xs = np.where(valid)
    if len(xs) and len(ys):
        mosaic = mosaic[ys.min(): ys.max() + 1, xs.min(): xs.max() + 1]
    cv2.imwrite(str(output_jpg), mosaic, [int(cv2.IMWRITE_JPEG_QUALITY), 92])
    cv2.imwrite(str(output_png), mosaic)
    h, w = mosaic.shape[:2]
    one_w, one_h = next(iter(sizes.values()))
    return {
        "success": True,
        "type": "mosaic_preview",
        "contributors": len(contributor_names),
        "connected_images": len(transforms),
        "width": w,
        "height": h,
        "megapixels": round(w * h / 1_000_000, 3),
        "coverage_increase_estimate": round((w * h) / max(1, one_w * one_h), 3),
        "canvas_scale": canvas_scale,
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    paths = create_output_tree(args.output)
    timings: dict[str, float] = {}
    t0 = time.perf_counter()
    images = find_images(args.images)
    if not images:
        raise FileNotFoundError(f"No supported images found in {args.images}")
    exif_by_path = {path: _exif(path) for path in images}
    selected = images[: min(args.max_images, len(images))]
    all_metadata = metadata_for(images, exif_by_path)
    selected_metadata = metadata_for(selected, exif_by_path)
    write_dataset_csv(selected_metadata, paths["root"] / "dataset_flight_log.csv")
    timings["dataset_loading"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    qualities = score_images(selected_metadata, paths["diagnostics"] / "image_quality.csv")
    quality_by_name = {quality.image_name: quality for quality in qualities}
    timings["quality_scoring"] = time.perf_counter() - t0
    usable = [record for record in selected_metadata if quality_by_name[record.image_name].status in {"GOOD", "MARGINAL"}]

    t0 = time.perf_counter()
    graph = build_candidate_graph(usable, qualities=quality_by_name, max_neighbors_per_image=args.neighbors)
    write_graph_csv(graph, paths["diagnostics"] / "candidate_graph.csv")
    graph_preview(graph, usable, paths["previews"] / "graph_preview.png")
    timings["candidate_graph"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    features, feature_stats = extract_features(usable, paths["cache"], args.feature_max_dim, args.force_recompute)
    timings["feature_extraction"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    by_name = {record.image_name: record for record in usable}
    geometries, matches_by_pair, homographies = match_and_verify(
        graph,
        by_name,
        features,
        paths["diagnostics"] / "verified_matches.csv",
    )
    track_stats = write_track_stats(
        geometries,
        matches_by_pair,
        paths["diagnostics"] / "feature_track_stats.json",
    )
    write_match_previews(by_name, features, matches_by_pair, geometries, paths["matches"], args.feature_max_dim)
    timings["geometric_verification"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    sfm = PyColmapBackend().run_sparse_reconstruction(
        tuple(usable),
        graph,
        geometries,
        paths["sparse"],
        features=features,
        pair_matches=matches_by_pair,
    )
    write_image_id_map_csv(usable, paths["diagnostics"] / "image_id_map.csv")
    sfm_metrics = {
        "status": "SUCCESS" if sfm.success else "FAILED",
        "registered_images": sfm.registered_images,
        "registration_rate": sfm.registered_images / max(1, len(usable)),
        "sparse_points": sfm.sparse_points,
        "mean_reprojection_error_after_ba": sfm.mean_reprojection_error_px,
        "median_reprojection_error_after_ba": sfm.median_reprojection_error_px,
        "largest_component_images": sfm.largest_component_images,
        "bundle_adjustment": "completed" if sfm.success else "not_completed",
        "message": sfm.message,
    }
    (paths["diagnostics"] / "sfm_metrics.json").write_text(json.dumps(sfm_metrics, indent=2), encoding="utf-8")
    timings["sfm"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    dense_enabled = args.enable_dense and sfm.success and sfm.registered_images / max(1, len(usable)) >= 0.8
    dense = ColmapPatchMatchBackend().run_dense_reconstruction(
        sfm,
        paths["dense"],
        enabled=dense_enabled,
        max_image_size=args.dense_max_image_size,
        num_threads=args.dense_threads,
    )
    timings["dense_mvs"] = time.perf_counter() - t0
    dense_metrics = {
        "status": "SUCCESS" if dense.success else "FAILED" if args.enable_dense else "SKIPPED",
        "dense_points": dense.dense_points,
        "runtime": dense.elapsed_seconds,
        "output_path": str(dense.output_path) if dense.output_path else None,
        "output_size_bytes": dense.output_size_bytes,
        "message": dense.message,
    }
    (paths["diagnostics"] / "dense_metrics.json").write_text(json.dumps(dense_metrics, indent=2), encoding="utf-8")

    t0 = time.perf_counter()
    dsm = generate_dsm_from_point_cloud(dense.output_path, paths["elevation"]) if dense.success and dense.output_path else None
    timings["dsm"] = time.perf_counter() - t0
    dsm_metrics = {
        "status": "SUCCESS" if dsm and dsm.success else "SKIPPED" if not dense.success else "FAILED",
        "path": str(dsm.output_path) if dsm and dsm.output_path else None,
        "width": dsm.width if dsm else 0,
        "height": dsm.height if dsm else 0,
        "resolution": dsm.resolution if dsm else 0.0,
        "message": dsm.message if dsm else "DSM skipped because dense reconstruction did not succeed.",
    }
    (paths["diagnostics"] / "dsm_metrics.json").write_text(json.dumps(dsm_metrics, indent=2), encoding="utf-8")

    gps_available = any(_gps(data)[0] is not None and _gps(data)[1] is not None for data in exif_by_path.values())
    alt_available = any(_gps(data)[2] is not None for data in exif_by_path.values())
    time_available = any(_exif_timestamp(data) is not None for data in exif_by_path.values())
    gps_report = {
        "available": gps_available,
        "observations": 0,
        "used": 0,
        "rejected": 0,
        "rmse": None,
        "message": "No EXIF GPS available in this dataset copy." if not gps_available else "GPS similarity alignment not yet executed.",
    }
    (paths["diagnostics"] / "gps_alignment.json").write_text(json.dumps(gps_report, indent=2), encoding="utf-8")

    t0 = time.perf_counter()
    mosaic = build_mosaic(
        usable,
        homographies,
        paths["final"] / "stitched_terrain.jpg",
        paths["final"] / "stitched_terrain.png",
        args.mosaic_max_dim,
        args.max_canvas_dim,
        args.max_mosaic_images,
    )
    timings["combined_image"] = time.perf_counter() - t0

    with (paths["diagnostics"] / "stage_timings.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["stage", "elapsed_seconds"])
        writer.writeheader()
        for stage, elapsed in timings.items():
            writer.writerow({"stage": stage, "elapsed_seconds": elapsed})
    with (paths["diagnostics"] / "rejected_images.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["image_name", "status", "rejection_reason"])
        writer.writeheader()
        for quality in qualities:
            if quality.status == "REJECTED":
                writer.writerow({"image_name": quality.image_name, "status": quality.status, "rejection_reason": quality.rejection_reason})

    statuses = {quality.status: sum(1 for item in qualities if item.status == quality.status) for quality in qualities}
    verified_edges = sum(1 for geo in geometries.values() if geo.accepted)
    report = {
        "test_name": "GARUDA TERRAIN MAPPING DATASET TEST",
        "dataset": {
            "path": str(args.images),
            "total_images": len(images),
            "selected_images": len(selected_metadata),
            "image_dimensions": f"{selected_metadata[0].camera.width_px}x{selected_metadata[0].camera.height_px}",
            "exif_gps_available": gps_available,
            "exif_altitude_available": alt_available,
            "exif_timestamp_available": time_available,
        },
        "quality": {
            "good": statuses.get("GOOD", 0),
            "marginal": statuses.get("MARGINAL", 0),
            "rejected": statuses.get("REJECTED", 0),
        },
        "candidate_graph": {"candidate_edges": len(graph.edges), "verified_edges": verified_edges},
        "tracks": track_stats,
        "feature_backend": feature_stats,
        "matcher_backend": "SIFT_FLANN_OR_BF",
        "sfm": {
            "success": sfm.success,
            "registered_images": sfm.registered_images,
            "registration_rate": sfm.registered_images / max(1, len(usable)),
            "sparse_points": sfm.sparse_points,
            "mean_reprojection_error": sfm.mean_reprojection_error_px,
            "median_reprojection_error": sfm.median_reprojection_error_px,
            "largest_component_images": sfm.largest_component_images,
            "message": sfm.message,
        },
        "dense_mvs": dense_metrics,
        "dsm": dsm_metrics,
        "gps_alignment": gps_report,
        "combined_image": {
            "status": "SUCCESS" if mosaic.get("success") else "FAILED",
            "path": str(paths["final"] / "stitched_terrain.jpg"),
            **mosaic,
        },
        "dense_reconstruction": dense_metrics["status"],
        "true_orthomosaic": "SKIPPED" if not (dsm and dsm.success) else "PENDING_ORTHORECTIFICATION",
        "runtime": {"elapsed_seconds": timings, "peak_ram": None},
        "ability_test": {
            "multi_image_overlap_discovery": "PASS" if len(graph.edges) else "FAIL",
            "non_sequential_matching": "PASS" if any(abs(_numeric_key(Path(a))[0] - _numeric_key(Path(b))[0]) > 1 and geo.accepted for (a, b), geo in geometries.items()) else "PARTIAL",
            "rotation_robustness": "PARTIAL",
            "scale_perspective_tolerance": "PASS" if verified_edges else "FAIL",
            "rejection_of_weak_pairs": "PASS" if any(not geo.accepted for geo in geometries.values()) else "PARTIAL",
            "recovery_around_missing_frames": "SKIPPED",
            "sparse_reconstruction": "PASS" if sfm.success else "FAIL",
            "combined_terrain_generation": "PASS" if mosaic.get("success") else "FAIL",
            "graceful_behavior_without_imu": "PASS",
            "controlled_ram_usage": "PARTIAL",
        },
        "overall": "PARTIAL" if sfm.success or (mosaic.get("success") and verified_edges) else "FAIL",
    }
    (paths["diagnostics"] / "reconstruction_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    summary = [
        "GARUDA TERRAIN MAPPING DATASET TEST",
        "",
        f"Dataset: {args.images}",
        f"Images found: {len(images)}",
        f"Images selected: {len(selected_metadata)}",
        f"Good: {statuses.get('GOOD', 0)}",
        f"Marginal: {statuses.get('MARGINAL', 0)}",
        f"Rejected: {statuses.get('REJECTED', 0)}",
        f"Candidate edges: {len(graph.edges)}",
        f"Verified edges: {verified_edges}",
        f"Feature backend: {feature_stats['backend']}",
        f"SfM: {'SUCCESS' if sfm.success else 'FAILED'}",
        f"Dense MVS: {dense_metrics['status']}",
        f"DSM: {dsm_metrics['status']}",
        f"Combined image: {report['combined_image']['status']}",
        f"Path: {paths['final'] / 'stitched_terrain.jpg'}",
        "True orthomosaic: SKIPPED",
        f"Overall: {report['overall']}",
    ]
    (paths["logs"] / "terrain_mapping_test.log").write_text("\n".join(summary) + "\n", encoding="utf-8")
    print("\n".join(summary))
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run GARUDA mapping against an external image dataset.")
    parser.add_argument("--images", required=True, type=Path, help="Directory containing ordered aerial images.")
    parser.add_argument("--output", type=Path, default=Path("output/terrain_mapping_test"))
    parser.add_argument("--profile", choices=("fast", "balanced", "quality"), default="balanced")
    parser.add_argument("--max-images", type=int, default=50)
    parser.add_argument("--neighbors", type=int, default=8)
    parser.add_argument("--feature-max-dim", type=int, default=config.MAPPING_FEATURE_MAX_DIM)
    parser.add_argument("--mosaic-max-dim", type=int, default=900)
    parser.add_argument("--max-canvas-dim", type=int, default=5000)
    parser.add_argument("--max-mosaic-images", type=int, default=20)
    parser.add_argument("--enable-dense", action="store_true")
    parser.add_argument("--dense-max-image-size", type=int, default=1200)
    parser.add_argument("--dense-threads", type=int, default=2)
    parser.add_argument("--force-recompute", action="store_true")
    return parser


def main() -> None:
    run(build_parser().parse_args())


if __name__ == "__main__":
    main()
