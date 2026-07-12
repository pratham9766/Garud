"""
Interactive HTML flight-path map using folium.

Reads CSV log and writes data/maps/flight_path.html.
"""

from __future__ import annotations

import logging
from pathlib import Path

import folium
import pandas as pd

import config

logger = logging.getLogger(__name__)


def generate_flight_map(
    csv_path: Path,
    output_path: Path | None = None,
) -> Path:
    """
    Generate an interactive HTML map from a flight CSV log.

    Plots:
      - GPS path polyline
      - Markers at image capture points with popup details

    Args:
        csv_path: Input CSV log file.
        output_path: Output HTML path (default: config.MAP_SAVE_PATH/flight_path.html).

    Returns:
        Path to the generated HTML file.
    """
    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV log not found: {csv_path}")

    output_path = output_path or (config.MAP_SAVE_PATH / "flight_path.html")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(csv_path)
    if df.empty:
        raise ValueError(f"CSV log is empty: {csv_path}")

    # Centre map on mean coordinates
    center_lat = df["latitude"].mean()
    center_lon = df["longitude"].mean()
    fmap = folium.Map(location=[center_lat, center_lon], zoom_start=15)

    # Flight path line
    path_coords = df[["latitude", "longitude"]].values.tolist()
    folium.PolyLine(
        path_coords,
        color="blue",
        weight=3,
        opacity=0.8,
        tooltip="Flight path",
    ).add_to(fmap)

    # Start / end markers
    folium.Marker(
        [df.iloc[0]["latitude"], df.iloc[0]["longitude"]],
        popup="Start",
        icon=folium.Icon(color="green", icon="play"),
    ).add_to(fmap)
    folium.Marker(
        [df.iloc[-1]["latitude"], df.iloc[-1]["longitude"]],
        popup="End",
        icon=folium.Icon(color="red", icon="stop"),
    ).add_to(fmap)

    # Image capture markers
    image_rows = df[
        df["image_name"].notna() & (df["image_name"].astype(str).str.len() > 0)
    ]
    for _, row in image_rows.iterrows():
        popup_html = (
            f"<b>Time:</b> {row.get('timestamp', 'N/A')}<br>"
            f"<b>Mission:</b> {row.get('mission_time', 'N/A')} s<br>"
            f"<b>Alt (GPS):</b> {row.get('gps_altitude', 'N/A')} m<br>"
            f"<b>Alt (Baro):</b> {row.get('baro_altitude', 'N/A')} m<br>"
            f"<b>Image:</b> {row['image_name']}<br>"
            f"<b>State:</b> {row.get('state', 'N/A')}"
        )
        folium.Marker(
            [row["latitude"], row["longitude"]],
            popup=folium.Popup(popup_html, max_width=300),
            icon=folium.Icon(color="orange", icon="camera"),
        ).add_to(fmap)

    fmap.save(str(output_path))
    logger.info("Flight map saved: %s", output_path)
    return output_path


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    import sys

    path = Path(sys.argv[1]) if len(sys.argv) > 1 else config.LOG_SAVE_PATH / "flight_log.csv"
    generate_flight_map(path)
