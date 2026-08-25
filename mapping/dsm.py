"""DSM output adapter."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DsmResult:
    success: bool
    output_path: Path | None = None
    message: str = ""


def generate_dsm_placeholder(output_dir: Path, enabled: bool = False) -> DsmResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    if not enabled:
        return DsmResult(
            success=False,
            output_path=output_dir / "dsm.tif",
            message="DSM generation disabled by profile/options.",
        )
    return DsmResult(
        success=False,
        output_path=output_dir / "dsm.tif",
        message="DSM requires dense reconstruction. No DEM/DTM is claimed.",
    )
