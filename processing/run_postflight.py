"""Command-line entry point for GARUDA post-flight mapping."""

from __future__ import annotations

import argparse
from pathlib import Path

from processing.mapping_pipeline import run_mapping_pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run GARUDA post-flight mapping.")
    parser.add_argument("--log", required=True, type=Path, help="Mission CSV log path.")
    parser.add_argument("--images", type=Path, default=None, help="Recovered image directory.")
    parser.add_argument("--output", type=Path, default=None, help="Post-flight output base directory.")
    parser.add_argument(
        "--profile",
        choices=("fast", "balanced", "quality"),
        default="balanced",
        help="Reconstruction quality profile.",
    )
    parser.add_argument("--skip-dense", action="store_true", help="Skip dense MVS.")
    parser.add_argument("--skip-orthomosaic", action="store_true", help="Skip orthomosaic generation.")
    parser.add_argument("--force-recompute", action="store_true", help="Ignore feature cache.")
    parser.add_argument("--max-workers", type=int, default=None, help="Limit heavy post-flight workers.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    result = run_mapping_pipeline(
        csv_path=args.log,
        image_dir=args.images,
        output_base=args.output,
        profile_name=args.profile,
        skip_dense=args.skip_dense,
        skip_orthomosaic=args.skip_orthomosaic,
        force_recompute=args.force_recompute,
        max_workers=args.max_workers,
    )
    print(f"Mission: {result.mission_id}")
    print(f"Output: {result.output_dir}")
    print(f"Images: {result.report.total_images}")
    print(f"Candidate edges: {result.report.candidate_edges}")
    print(f"Verified edges: {result.report.verified_edges}")
    print(f"SfM success: {result.report.sfm_success}")


if __name__ == "__main__":
    main()
