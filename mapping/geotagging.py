"""
Geotagging utilities — associate images with GPS coordinates.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)


def load_geotagged_records(csv_path: Path) -> pd.DataFrame:
    """
    Load CSV log and return rows that have both coordinates and an image name.

    Args:
        csv_path: Path to flight CSV log.

    Returns:
        DataFrame filtered to geotagged image capture events.
    """
    df = pd.read_csv(csv_path)
    mask = (
        df["latitude"].notna()
        & df["longitude"].notna()
        & (df["latitude"] != 0)
        & (df["longitude"] != 0)
        & df["image_name"].notna()
        & (df["image_name"].astype(str).str.len() > 0)
    )
    return df[mask].copy()


def geotag_summary(csv_path: Path) -> dict:
    """Return a summary of geotagged images in a CSV log."""
    tagged = load_geotagged_records(csv_path)
    return {
        "total_records": len(pd.read_csv(csv_path)),
        "geotagged_images": len(tagged),
        "unique_images": tagged["image_name"].nunique() if len(tagged) else 0,
    }
