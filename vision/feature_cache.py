"""Disk-backed compact feature cache for post-flight processing."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np

import config
from storage.mission_manifest import ImageMetadata
from vision.feature_detection import FeatureBackend, FeatureSet, resize_for_features
from vision.undistortion import undistort_image


@dataclass(frozen=True)
class FeatureCacheConfig:
    """Settings that affect cache invalidation."""

    backend_name: str
    max_dim: int
    max_features: int
    cache_version: str = config.MAPPING_CACHE_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "backend_name": self.backend_name,
            "max_dim": self.max_dim,
            "max_features": self.max_features,
            "cache_version": self.cache_version,
        }


def _keypoint_to_tuple(keypoint: cv2.KeyPoint) -> tuple[float, ...]:
    return (
        keypoint.pt[0],
        keypoint.pt[1],
        keypoint.size,
        keypoint.angle,
        keypoint.response,
        float(keypoint.octave),
        float(keypoint.class_id),
    )


def _tuple_to_keypoint(values: np.ndarray) -> cv2.KeyPoint:
    return cv2.KeyPoint(
        x=float(values[0]),
        y=float(values[1]),
        size=float(values[2]),
        angle=float(values[3]),
        response=float(values[4]),
        octave=int(values[5]),
        class_id=int(values[6]),
    )


def _image_signature(path: Path, settings: FeatureCacheConfig) -> str:
    stat = path.stat()
    payload = {
        "path": str(path.resolve()),
        "mtime_ns": stat.st_mtime_ns,
        "size": stat.st_size,
        "settings": settings.to_dict(),
    }
    raw = json.dumps(payload, sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


class FeatureCache:
    """Cache keypoints/descriptors without storing decoded image buffers."""

    def __init__(self, cache_dir: Path) -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def path_for(self, metadata: ImageMetadata, settings: FeatureCacheConfig) -> Path:
        signature = _image_signature(metadata.image_path, settings)
        stem = Path(metadata.image_name).stem
        return self.cache_dir / f"{stem}_{signature[:16]}.npz"

    def load(self, metadata: ImageMetadata, settings: FeatureCacheConfig) -> FeatureSet | None:
        path = self.path_for(metadata, settings)
        if not path.exists():
            return None
        data = np.load(path, allow_pickle=False)
        keypoints = tuple(_tuple_to_keypoint(row) for row in data["keypoints"])
        descriptors = data["descriptors"]
        if descriptors.size == 0:
            descriptors = None
        detector_name = data["detector_name"]
        detector_name = str(detector_name.item() if hasattr(detector_name, "item") else detector_name)
        return FeatureSet(
            detector_name=detector_name,
            keypoints=keypoints,
            descriptors=descriptors,
            image_shape=tuple(int(v) for v in data["image_shape"]),
            scale=float(data["scale"]),
        )

    def save(
        self,
        metadata: ImageMetadata,
        settings: FeatureCacheConfig,
        features: FeatureSet,
    ) -> Path:
        path = self.path_for(metadata, settings)
        keypoints = np.asarray([_keypoint_to_tuple(kp) for kp in features.keypoints], dtype=np.float32)
        descriptors = features.descriptors
        if descriptors is None:
            descriptors = np.empty((0, 0), dtype=np.float32)
        np.savez_compressed(
            path,
            detector_name=np.asarray(features.detector_name),
            keypoints=keypoints,
            descriptors=descriptors,
            image_shape=np.asarray(features.image_shape or (0, 0), dtype=np.int32),
            scale=np.asarray(features.scale, dtype=np.float32),
        )
        return path

    def get_or_extract(
        self,
        metadata: ImageMetadata,
        backend: FeatureBackend,
        settings: FeatureCacheConfig,
        force_recompute: bool = False,
    ) -> FeatureSet:
        if not force_recompute:
            cached = self.load(metadata, settings)
            if cached is not None:
                return cached

        image = cv2.imread(str(metadata.image_path), cv2.IMREAD_COLOR)
        if image is None:
            raise FileNotFoundError(f"Unable to read image: {metadata.image_path}")
        undistorted = undistort_image(image, metadata.camera)
        working, scale = resize_for_features(undistorted, settings.max_dim)
        try:
            features = backend.extract(working)
            features = FeatureSet(
                detector_name=features.detector_name,
                keypoints=features.keypoints,
                descriptors=features.descriptors,
                image_shape=working.shape[:2],
                scale=scale,
            )
            self.save(metadata, settings, features)
            return features
        finally:
            del working
            del undistorted
            del image
