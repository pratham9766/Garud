"""Reconstruction report structures and JSON persistence."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
from typing import Any


@dataclass
class ReconstructionReport:
    """Machine-readable post-flight reconstruction summary."""

    total_images: int = 0
    usable_images: int = 0
    marginal_images: int = 0
    rejected_images: int = 0
    registered_images: int = 0
    candidate_edges: int = 0
    verified_edges: int = 0
    sparse_points: int = 0
    dense_points: int = 0
    gps_alignment_rmse_m: float | None = None
    coverage_area_m2: float | None = None
    profile: str = "BALANCED"
    feature_backend: str = ""
    matcher_backend: str = ""
    sfm_success: bool = False
    mvs_success: bool = False
    orthomosaic_success: bool = False
    elapsed_seconds: dict[str, float] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def write_report(report: ReconstructionReport, path: Path) -> Path:
    """Write a reconstruction report as pretty JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(report.to_dict(), handle, indent=2, sort_keys=True)
        handle.write("\n")
    return path
