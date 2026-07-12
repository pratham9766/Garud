"""
KML flight-path export using simplekml.

Reads CSV log and writes data/maps/flight_path.kml.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
import simplekml

import config

logger = logging.getLogger(__name__)


def generate_kml(
    csv_path: Path,
    output_path: Path | None = None,
) -> Path:
    """
    Generate a KML file from a flight CSV log.

    Args:
        csv_path: Input CSV log file.
        output_path: Output KML path (default: config.MAP_SAVE_PATH/flight_path.kml).

    Returns:
        Path to the generated KML file.
    """
    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV log not found: {csv_path}")

    output_path = output_path or (config.MAP_SAVE_PATH / "flight_path.kml")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(csv_path)
    if df.empty:
        raise ValueError(f"CSV log is empty: {csv_path}")

    kml = simplekml.Kml()
    kml.document.name = "Ground Mapping Flight Path"

    # Flight path line
    line = kml.newlinestring(name="Flight Path")
    line.coords = list(zip(df["longitude"], df["latitude"], df["baro_altitude"]))
    line.style.linestyle.color = simplekml.Color.blue
    line.style.linestyle.width = 3

    # Image capture placemarks
    image_rows = df[
        df["image_name"].notna() & (df["image_name"].astype(str).str.len() > 0)
    ]
    for _, row in image_rows.iterrows():
        pt = kml.newpoint(name=str(row["image_name"]))
        pt.coords = [(row["longitude"], row["latitude"], row.get("baro_altitude", 0))]
        pt.description = (
            f"Timestamp: {row.get('timestamp', 'N/A')}\n"
            f"Altitude: {row.get('baro_altitude', 'N/A')} m\n"
            f"State: {row.get('state', 'N/A')}"
        )
        pt.style.iconstyle.icon.href = (
            "http://maps.google.com/mapfiles/kml/shapes/camera.png"
        )

    kml.save(str(output_path))
    logger.info("KML saved: %s", output_path)
    return output_path


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    import sys

    path = Path(sys.argv[1]) if len(sys.argv) > 1 else config.LOG_SAVE_PATH / "flight_log.csv"
    generate_kml(path)
