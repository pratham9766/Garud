"""Memory-conscious post-flight reconstruction pipeline."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import csv
import json
import time
from pathlib import Path

import cv2

import config
from mapping.dsm import generate_dsm_placeholder
from mapping.georeference import summarize_gps_priors
from mapping.image_graph import ImageGraph, build_candidate_graph
from mapping.orthomosaic import generate_orthomosaic_placeholder
from processing.dense_backend import ColmapPatchMatchBackend, DenseResult
from processing.mission_loader import MissionData, load_mission_data, validate_mission_data
from processing.quality_scoring import ImageQuality, score_image_quality
from processing.sfm_backend import PyColmapBackend, SfMResult
from storage.mission_manifest import ImageMetadata
from storage.reconstruction_report import ReconstructionReport, write_report
from vision.feature_cache import FeatureCache, FeatureCacheConfig
from vision.feature_detection import FeatureDetector, FeatureSet
from vision.feature_matching import FeatureMatcher, raw_knn_match_count
from vision.geometric_verification import GeometryResult, verify_geometry
from vision.undistortion import undistort_image


@dataclass(frozen=True)
class ReconstructionProfile:
    """Profile controlling post-flight cost/quality tradeoffs."""

    name: str
    feature_max_dim: int
    max_neighbors_per_image: int
    enable_dense: bool
    enable_orthomosaic: bool
    max_workers: int


@dataclass(frozen=True)
class PipelineResult:
    """Full pipeline result with paths and summaries."""

    mission_id: str
    output_dir: Path
    report: ReconstructionReport
    graph: ImageGraph
    qualities: tuple[ImageQuality, ...]
    geometries: dict[tuple[str, str], GeometryResult]
    sfm: SfMResult
    dense: DenseResult


def profile_from_name(
    name: str,
    skip_dense: bool = False,
    skip_orthomosaic: bool = False,
    max_workers: int | None = None,
) -> ReconstructionProfile:
    """Return a conservative post-flight profile."""
    normalized = name.upper()
    if normalized == "FAST":
        feature_max_dim = min(config.MAPPING_FEATURE_MAX_DIM, 1280)
        neighbors = min(config.MAPPING_MAX_NEIGHBORS_PER_IMAGE, 5)
        dense = False
        ortho = False
    elif normalized == "QUALITY":
        feature_max_dim = max(config.MAPPING_FEATURE_MAX_DIM, 3072)
        neighbors = max(config.MAPPING_MAX_NEIGHBORS_PER_IMAGE, 12)
        dense = config.MAPPING_ENABLE_DENSE_RECONSTRUCTION
        ortho = config.MAPPING_ENABLE_ORTHOMOSAIC
    else:
        normalized = "BALANCED"
        feature_max_dim = config.MAPPING_FEATURE_MAX_DIM
        neighbors = config.MAPPING_MAX_NEIGHBORS_PER_IMAGE
        dense = config.MAPPING_ENABLE_DENSE_RECONSTRUCTION
        ortho = config.MAPPING_ENABLE_ORTHOMOSAIC

    return ReconstructionProfile(
        name=normalized,
        feature_max_dim=feature_max_dim,
        max_neighbors_per_image=neighbors,
        enable_dense=dense and not skip_dense,
        enable_orthomosaic=ortho and not skip_orthomosaic,
        max_workers=max_workers or config.MAPPING_MAX_WORKERS,
    )


def _mission_id(csv_path: Path) -> str:
    return csv_path.stem.replace("flight_log_", "mission_")


def create_output_tree(base_dir: Path, mission_id: str) -> dict[str, Path]:
    """Create the required post-flight output directory structure."""
    root = base_dir / mission_id
    paths = {
        "root": root,
        "orthomosaic": root / "orthomosaic",
        "reconstruction": root / "reconstruction",
        "sparse": root / "reconstruction" / "sparse",
        "dense": root / "reconstruction" / "dense",
        "elevation": root / "elevation",
        "quality": root / "quality",
        "cache": root / "cache",
        "features": root / "cache" / "features",
        "matches": root / "cache" / "matches",
        "debug": root / "debug",
        "debug_graph": root / "debug" / "graph",
        "debug_pose": root / "debug" / "pose",
        "debug_matches": root / "debug" / "matches",
    }
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
    return paths


def _load_image(metadata: ImageMetadata):
    image = cv2.imread(str(metadata.image_path), cv2.IMREAD_COLOR)
    if image is None:
        raise FileNotFoundError(f"Unable to read image: {metadata.image_path}")
    return image


def _score_images(mission: MissionData, quality_dir: Path) -> tuple[ImageQuality, ...]:
    qualities: list[ImageQuality] = []
    for metadata in mission.images:
        try:
            image = _load_image(metadata)
            undistorted = undistort_image(image, metadata.camera)
            quality = score_image_quality(undistorted, metadata)
            del undistorted
            del image
        except Exception:
            quality = ImageQuality(
                image_name=metadata.image_name,
                sharpness_score=0.0,
                exposure_score=0.0,
                motion_score=0.0,
                pose_score=0.0,
                total_score=0.0,
                usable=False,
                rejection_reason="missing_or_corrupt",
                status="REJECTED",
                blur_variance=0.0,
                mean_brightness=0.0,
                clipped_shadow_fraction=0.0,
                clipped_highlight_fraction=0.0,
                tilt_deg=0.0,
                angular_rate_dps=0.0,
                flags=("missing_or_corrupt",),
            )
        qualities.append(quality)

    with open(quality_dir / "image_quality.csv", "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(asdict(qualities[0]).keys()) if qualities else ["image_name"])
        writer.writeheader()
        for quality in qualities:
            row = asdict(quality)
            row["flags"] = ";".join(quality.flags)
            writer.writerow(row)

    with open(quality_dir / "rejected_images.csv", "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["image_name", "status", "rejection_reason"])
        writer.writeheader()
        for quality in qualities:
            if quality.status == "REJECTED":
                writer.writerow(
                    {
                        "image_name": quality.image_name,
                        "status": quality.status,
                        "rejection_reason": quality.rejection_reason,
                    }
                )
    return tuple(qualities)


def _feature_settings(profile: ReconstructionProfile, detector: FeatureDetector) -> FeatureCacheConfig:
    return FeatureCacheConfig(
        backend_name=detector.detector_name,
        max_dim=profile.feature_max_dim,
        max_features=config.MAPPING_FEATURE_MAX_FEATURES,
    )


def _features_for_graph(
    images_by_name: dict[str, ImageMetadata],
    graph: ImageGraph,
    cache: FeatureCache,
    detector: FeatureDetector,
    settings: FeatureCacheConfig,
    force_recompute: bool,
) -> dict[str, FeatureSet]:
    needed = {edge.source for edge in graph.edges} | {edge.target for edge in graph.edges}
    features: dict[str, FeatureSet] = {}
    for image_name in needed:
        features[image_name] = cache.get_or_extract(
            images_by_name[image_name],
            detector,
            settings,
            force_recompute=force_recompute,
        )
    return features


def _match_and_verify(
    graph: ImageGraph,
    images_by_name: dict[str, ImageMetadata],
    features: dict[str, FeatureSet],
    quality_dir: Path,
) -> tuple[dict[tuple[str, str], GeometryResult], dict[tuple[str, str], tuple]]:
    matcher = FeatureMatcher(ratio=config.MAPPING_MATCH_RATIO)
    geometries: dict[tuple[str, str], GeometryResult] = {}
    accepted_matches: dict[tuple[str, str], tuple] = {}
    with open(quality_dir / "match_statistics.csv", "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "source",
                "target",
                "raw_matches",
                "filtered_matches",
                "inliers",
                "inlier_ratio",
                "model",
                "accepted",
            ],
        )
        writer.writeheader()
        for edge in graph.edges:
            first = features.get(edge.source)
            second = features.get(edge.target)
            if first is None or second is None:
                continue
            matches = matcher.match(first, second)
            raw_count = raw_knn_match_count(first, second)
            geometry = verify_geometry(
                first,
                second,
                matches,
                camera=images_by_name[edge.source].camera,
                raw_match_count=raw_count,
            )
            key = (edge.source, edge.target)
            geometries[key] = geometry
            if geometry.accepted:
                accepted_matches[key] = matches
            writer.writerow(
                {
                    "source": edge.source,
                    "target": edge.target,
                    "raw_matches": geometry.raw_match_count,
                    "filtered_matches": geometry.filtered_match_count,
                    "inliers": geometry.inlier_count,
                    "inlier_ratio": f"{geometry.inlier_ratio:.4f}",
                    "model": geometry.model_type,
                    "accepted": geometry.accepted,
                }
            )
    return geometries, accepted_matches


def run_mapping_pipeline(
    csv_path: Path,
    image_dir: Path | None = None,
    output_base: Path | None = None,
    profile_name: str = config.MAPPING_DEFAULT_PROFILE,
    skip_dense: bool = False,
    skip_orthomosaic: bool = False,
    force_recompute: bool = False,
    max_workers: int | None = None,
) -> PipelineResult:
    """Run the GARUDA post-flight mapping pipeline."""
    timings: dict[str, float] = {}
    warnings: list[str] = []
    profile = profile_from_name(profile_name, skip_dense, skip_orthomosaic, max_workers)
    output_base = output_base or config.POSTFLIGHT_SAVE_PATH
    mission_id = _mission_id(Path(csv_path))
    paths = create_output_tree(output_base, mission_id)

    t0 = time.perf_counter()
    mission = load_mission_data(Path(csv_path), image_dir=image_dir)
    validation_issues = validate_mission_data(mission)
    warnings.extend(validation_issues)
    timings["mission_loading"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    qualities = _score_images(mission, paths["quality"])
    quality_by_name = {quality.image_name: quality for quality in qualities}
    timings["quality_scoring"] = time.perf_counter() - t0

    usable_images = tuple(
        image
        for image in mission.images
        if quality_by_name.get(image.image_name)
        and quality_by_name[image.image_name].status in {"GOOD", "MARGINAL"}
    )

    t0 = time.perf_counter()
    graph = build_candidate_graph(
        usable_images,
        qualities=quality_by_name,
        max_neighbors_per_image=profile.max_neighbors_per_image,
    )
    timings["candidate_graph"] = time.perf_counter() - t0
    with open(paths["debug_graph"] / "candidate_graph.json", "w", encoding="utf-8") as handle:
        json.dump(
            {
                "nodes": list(graph.nodes),
                "edges": [
                    {
                        "source": edge.source,
                        "target": edge.target,
                        "score": edge.score,
                        "reason": edge.reason,
                        "distance_m": edge.distance_m,
                        "predicted_overlap": edge.predicted_overlap,
                    }
                    for edge in graph.edges
                ],
            },
            handle,
            indent=2,
        )

    detector = FeatureDetector(
        preferred=config.MAPPING_FEATURE_BACKEND,
        max_features=config.MAPPING_FEATURE_MAX_FEATURES,
    )
    settings = _feature_settings(profile, detector)
    cache = FeatureCache(paths["features"])
    images_by_name = {image.image_name: image for image in mission.images}

    t0 = time.perf_counter()
    features = _features_for_graph(
        images_by_name,
        graph,
        cache,
        detector,
        settings,
        force_recompute,
    )
    timings["feature_extraction"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    geometries, accepted_matches = _match_and_verify(
        graph,
        images_by_name,
        features,
        paths["quality"],
    )
    timings["geometric_verification"] = time.perf_counter() - t0
    del features

    t0 = time.perf_counter()
    sfm_backend = PyColmapBackend()
    sfm = sfm_backend.run_sparse_reconstruction(
        tuple(usable_images),
        graph,
        geometries,
        paths["sparse"],
    )
    if not sfm.success:
        warnings.append(sfm.message)
    timings["sfm"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    dense = ColmapPatchMatchBackend().run_dense_reconstruction(
        sfm,
        paths["dense"],
        enabled=profile.enable_dense,
    )
    if dense.message:
        warnings.append(dense.message)
    timings["mvs"] = time.perf_counter() - t0

    georef = summarize_gps_priors(tuple(usable_images))
    dsm = generate_dsm_placeholder(paths["elevation"], enabled=dense.success)
    ortho = generate_orthomosaic_placeholder(
        paths["orthomosaic"],
        enabled=profile.enable_orthomosaic and dense.success,
    )
    warnings.extend([msg for msg in (georef.message, dsm.message, ortho.message) if msg])

    report = ReconstructionReport(
        total_images=len(mission.images),
        usable_images=sum(1 for quality in qualities if quality.status == "GOOD"),
        marginal_images=sum(1 for quality in qualities if quality.status == "MARGINAL"),
        rejected_images=sum(1 for quality in qualities if quality.status == "REJECTED"),
        registered_images=sfm.registered_images,
        candidate_edges=len(graph.edges),
        verified_edges=sum(1 for geometry in geometries.values() if geometry.accepted),
        sparse_points=sfm.sparse_points,
        dense_points=dense.dense_points,
        gps_alignment_rmse_m=georef.gps_alignment_rmse_m,
        profile=profile.name,
        feature_backend=detector.detector_name,
        matcher_backend="LIGHTGLUE_OPTIONAL_FLANN_FALLBACK",
        sfm_success=sfm.success,
        mvs_success=dense.success,
        orthomosaic_success=ortho.success,
        elapsed_seconds=timings,
        warnings=warnings,
        extra={
            "max_workers": profile.max_workers,
            "feature_max_dim": profile.feature_max_dim,
            "accepted_match_pairs": len(accepted_matches),
        },
    )
    write_report(report, paths["quality"] / "reconstruction_report.json")
    return PipelineResult(
        mission_id=mission_id,
        output_dir=paths["root"],
        report=report,
        graph=graph,
        qualities=qualities,
        geometries=geometries,
        sfm=sfm,
        dense=dense,
    )
