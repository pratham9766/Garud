"""
Interactive HTML flight-path map using folium.

Reads CSV log and writes data/maps/flight_path.html.
"""

from __future__ import annotations

import logging
from html import escape
from pathlib import Path
from datetime import datetime

import pandas as pd

try:
    import folium
except ImportError:  # pragma: no cover - exercised in lean runtime installs
    folium = None

import config
from mapping.coverage import build_image_footprints, estimate_coverage_area

logger = logging.getLogger(__name__)


def generate_flight_map(
    csv_path: Path,
    output_path: Path | None = None,
) -> Path:
    """
    Generate an interactive HTML map from a flight CSV log.

    Plots:
      - GPS path polyline
      - Camera footprint polygons for each geotagged image
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

    if folium is None:
        return _generate_basic_html_map(df, output_path)

    # Centre map on mean coordinates
    center_lat = df["latitude"].mean()
    center_lon = df["longitude"].mean()
    fmap = folium.Map(location=[center_lat, center_lon], zoom_start=15)
    footprints = build_image_footprints(df)
    coverage = estimate_coverage_area(footprints)

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

    footprint_group = folium.FeatureGroup(name="Estimated image footprints")
    for footprint in footprints:
        popup_html = (
            f"<b>Image:</b> {footprint.image_name}<br>"
            f"<b>Altitude:</b> {footprint.altitude_m:.1f} m<br>"
            f"<b>Footprint:</b> {footprint.width_m:.1f} m x "
            f"{footprint.height_m:.1f} m<br>"
            f"<b>Area:</b> {footprint.area_m2:.0f} m^2"
        )
        folium.Polygon(
            locations=footprint.corners,
            color="#1f78b4",
            weight=2,
            fill=True,
            fill_color="#1f78b4",
            fill_opacity=0.18,
            popup=folium.Popup(popup_html, max_width=320),
            tooltip=f"Footprint: {footprint.image_name}",
        ).add_to(footprint_group)
    footprint_group.add_to(fmap)

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

    summary_html = (
        "<div style='position: fixed; bottom: 24px; left: 24px; z-index: 9999; "
        "background: white; padding: 10px 12px; border: 1px solid #999; "
        "font-size: 13px; line-height: 1.35;'>"
        "<b>Mapping summary</b><br>"
        f"Images: {coverage['image_count']}<br>"
        f"Unique coverage: {coverage['unique_area_m2']:.0f} m^2<br>"
        f"Overlap estimate: {coverage['overlap_area_m2']:.0f} m^2<br>"
        f"Grid: {coverage['coverage_grid_m']:.1f} m"
        "</div>"
    )
    fmap.get_root().html.add_child(folium.Element(summary_html))
    folium.LayerControl().add_to(fmap)

    try:
        fmap.save(str(output_path))
    except PermissionError:
        fallback_name = f"{output_path.stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{output_path.suffix}"
        output_path = output_path.with_name(fallback_name)
        fmap.save(str(output_path))
    logger.info("Flight map saved: %s", output_path)
    return output_path


def _write_text_with_fallback(output_path: Path, content: str) -> Path:
    try:
        output_path.write_text(content, encoding="utf-8")
        return output_path
    except PermissionError:
        fallback_name = f"{output_path.stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{output_path.suffix}"
        fallback_path = output_path.with_name(fallback_name)
        fallback_path.write_text(content, encoding="utf-8")
        return fallback_path


def _generate_basic_html_map(df: pd.DataFrame, output_path: Path) -> Path:
    """Generate a dependency-light map report when folium is unavailable."""
    footprints = build_image_footprints(df)
    coverage = estimate_coverage_area(footprints)
    path_rows = []
    for _, row in df.iterrows():
        path_rows.append(
            "<tr>"
            f"<td>{escape(str(row.get('timestamp', '')))}</td>"
            f"<td>{float(row['latitude']):.7f}</td>"
            f"<td>{float(row['longitude']):.7f}</td>"
            f"<td>{float(row.get('altitude', row.get('baro_altitude', 0.0))):.2f}</td>"
            f"<td>{escape(str(row.get('image_name', '')))}</td>"
            "</tr>"
        )

    footprint_rows = []
    for footprint in footprints:
        footprint_rows.append(
            "<tr>"
            f"<td>{escape(footprint.image_name)}</td>"
            f"<td>{footprint.altitude_m:.1f}</td>"
            f"<td>{footprint.width_m:.1f}</td>"
            f"<td>{footprint.height_m:.1f}</td>"
            f"<td>{footprint.area_m2:.0f}</td>"
            "</tr>"
        )

    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>GARUDA Flight Map Report</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 24px; color: #17212b; }}
    h1, h2 {{ margin-bottom: 8px; }}
    table {{ border-collapse: collapse; width: 100%; margin: 12px 0 28px; }}
    th, td {{ border: 1px solid #cbd5df; padding: 6px 8px; text-align: left; }}
    th {{ background: #eef3f8; }}
    .summary {{ display: grid; grid-template-columns: repeat(4, minmax(120px, 1fr)); gap: 10px; max-width: 760px; }}
    .metric {{ border: 1px solid #cbd5df; padding: 10px; border-radius: 6px; }}
    .metric b {{ display: block; font-size: 12px; color: #536579; }}
  </style>
</head>
<body>
  <h1>GARUDA Flight Map Report</h1>
  <p>Generated without folium; this report preserves path and footprint data for simulation checks.</p>
  <div class="summary">
    <div class="metric"><b>Images</b>{coverage['image_count']}</div>
    <div class="metric"><b>Unique coverage</b>{coverage['unique_area_m2']:.0f} m^2</div>
    <div class="metric"><b>Overlap estimate</b>{coverage['overlap_area_m2']:.0f} m^2</div>
    <div class="metric"><b>Grid</b>{coverage['coverage_grid_m']:.1f} m</div>
  </div>
  <h2>Flight Path Samples</h2>
  <table>
    <thead><tr><th>Timestamp</th><th>Latitude</th><th>Longitude</th><th>Altitude m</th><th>Image</th></tr></thead>
    <tbody>{''.join(path_rows)}</tbody>
  </table>
  <h2>Image Footprints</h2>
  <table>
    <thead><tr><th>Image</th><th>Altitude m</th><th>Width m</th><th>Height m</th><th>Area m^2</th></tr></thead>
    <tbody>{''.join(footprint_rows)}</tbody>
  </table>
</body>
</html>
"""
    saved_path = _write_text_with_fallback(output_path, html)
    logger.info("Basic flight map report saved: %s", saved_path)
    return saved_path


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    import sys

    path = Path(sys.argv[1]) if len(sys.argv) > 1 else config.LOG_SAVE_PATH / "flight_log.csv"
    generate_flight_map(path)
