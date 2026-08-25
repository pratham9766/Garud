"""Timestamp synchronization helpers for mission CSV rows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import pandas as pd


@dataclass(frozen=True)
class SyncResult:
    """Result of synchronizing an image timestamp to one CSV sample row."""

    image_name: str
    image_timestamp: float
    row_index: int
    sample_timestamp: float
    delta_s: float


def closest_sample(
    df: pd.DataFrame,
    image_name: str,
    image_timestamp: float,
    timestamp_column: str = "timestamp",
) -> SyncResult:
    """Find the closest temporally valid sample for one image."""
    if timestamp_column not in df.columns:
        raise ValueError(f"Missing timestamp column: {timestamp_column}")
    times = pd.to_numeric(df[timestamp_column], errors="coerce")
    deltas = (times - float(image_timestamp)).abs()
    row_index = int(deltas.idxmin())
    sample_timestamp = float(times.loc[row_index])
    return SyncResult(
        image_name=image_name,
        image_timestamp=float(image_timestamp),
        row_index=row_index,
        sample_timestamp=sample_timestamp,
        delta_s=abs(sample_timestamp - float(image_timestamp)),
    )


def sync_image_rows(
    df: pd.DataFrame,
    interpolate: bool = False,
) -> Iterable[tuple[str, pd.Series, SyncResult]]:
    """
    Yield one synchronized row per image.

    Interpolation is intentionally left off by default to preserve existing CSV
    semantics. The hook is present for future GPS/barometer/orientation
    interpolation without changing caller interfaces.
    """
    if "image_name" not in df.columns:
        raise ValueError("Mission CSV does not contain image_name.")
    rows = df[
        df["image_name"].notna() & (df["image_name"].astype(str).str.len() > 0)
    ]
    if "image_timestamp" not in rows.columns:
        rows = rows.copy()
        rows["image_timestamp"] = rows["timestamp"]
    for image_name, group in rows.groupby(rows["image_name"].astype(str), sort=False):
        image_timestamp = float(pd.to_numeric(group["image_timestamp"], errors="coerce").iloc[0])
        result = closest_sample(df, str(image_name), image_timestamp)
        row = df.loc[result.row_index]
        if interpolate:
            # Future extension point: interpolate numeric sensor columns around
            # image_timestamp. Keeping the current nearest-neighbor behavior
            # avoids silently changing existing logs.
            row = row.copy()
        yield str(image_name), row, result
