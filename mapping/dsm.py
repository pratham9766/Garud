"""DSM output adapter."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import struct

import numpy as np

try:
    import tifffile
except Exception:  # pragma: no cover - optional convenience writer
    tifffile = None


@dataclass(frozen=True)
class DsmResult:
    success: bool
    output_path: Path | None = None
    message: str = ""
    width: int = 0
    height: int = 0
    resolution: float = 0.0


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


def _read_ply_xyz(path: Path) -> np.ndarray:
    with open(path, "rb") as handle:
        header_lines: list[bytes] = []
        while True:
            line = handle.readline()
            if not line:
                raise ValueError("PLY header did not terminate.")
            header_lines.append(line)
            if line.strip() == b"end_header":
                break
        header = b"".join(header_lines).decode("ascii", errors="ignore")
        vertex_count = 0
        properties: list[tuple[str, str]] = []
        in_vertex = False
        fmt = "ascii"
        for line in header.splitlines():
            parts = line.split()
            if not parts:
                continue
            if parts[:2] == ["format", "binary_little_endian"]:
                fmt = "binary_little_endian"
            elif parts[:2] == ["format", "ascii"]:
                fmt = "ascii"
            elif parts[:1] == ["element"]:
                in_vertex = len(parts) >= 3 and parts[1] == "vertex"
                if in_vertex:
                    vertex_count = int(parts[2])
            elif in_vertex and parts[:1] == ["property"] and len(parts) >= 3:
                properties.append((parts[1], parts[2]))

        names = [name for _, name in properties]
        try:
            x_idx, y_idx, z_idx = names.index("x"), names.index("y"), names.index("z")
        except ValueError as exc:
            raise ValueError("PLY does not contain x/y/z vertex properties.") from exc

        if fmt == "ascii":
            rows = []
            for _ in range(vertex_count):
                values = handle.readline().decode("ascii", errors="ignore").split()
                if len(values) > max(x_idx, y_idx, z_idx):
                    rows.append([float(values[x_idx]), float(values[y_idx]), float(values[z_idx])])
            return np.asarray(rows, dtype=np.float64)

        type_map = {
            "float": "f",
            "float32": "f",
            "double": "d",
            "float64": "d",
            "uchar": "B",
            "uint8": "B",
            "char": "b",
            "int8": "b",
            "ushort": "H",
            "uint16": "H",
            "short": "h",
            "int16": "h",
            "uint": "I",
            "uint32": "I",
            "int": "i",
            "int32": "i",
        }
        fmt_chars = [type_map[prop_type] for prop_type, _ in properties]
        row_struct = struct.Struct("<" + "".join(fmt_chars))
        rows = np.empty((vertex_count, 3), dtype=np.float64)
        for idx in range(vertex_count):
            values = row_struct.unpack(handle.read(row_struct.size))
            rows[idx] = (values[x_idx], values[y_idx], values[z_idx])
        return rows


def generate_dsm_from_point_cloud(
    point_cloud_path: Path,
    output_dir: Path,
    resolution: float = 0.25,
    percentile: float = 90.0,
) -> DsmResult:
    """Rasterize a dense point cloud into a DSM using robust per-cell elevation."""
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "dsm.tif"
    if not point_cloud_path.exists():
        return DsmResult(False, output_path, f"Dense point cloud not found: {point_cloud_path}")
    points = _read_ply_xyz(point_cloud_path)
    if len(points) < 100:
        return DsmResult(False, output_path, f"Dense point cloud too small for DSM: {len(points)} points")
    finite = np.isfinite(points).all(axis=1)
    points = points[finite]
    z = points[:, 2]
    lo, hi = np.percentile(z, [1.0, 99.0])
    points = points[(z >= lo) & (z <= hi)]
    min_xy = points[:, :2].min(axis=0)
    max_xy = points[:, :2].max(axis=0)
    width = int(np.ceil((max_xy[0] - min_xy[0]) / resolution)) + 1
    height = int(np.ceil((max_xy[1] - min_xy[1]) / resolution)) + 1
    if width <= 1 or height <= 1 or width * height > 50_000_000:
        return DsmResult(False, output_path, f"DSM grid dimensions are invalid or too large: {width}x{height}")
    cols = np.clip(((points[:, 0] - min_xy[0]) / resolution).astype(int), 0, width - 1)
    rows = np.clip(((max_xy[1] - points[:, 1]) / resolution).astype(int), 0, height - 1)
    buckets: dict[int, list[float]] = {}
    for row, col, value in zip(rows, cols, points[:, 2]):
        buckets.setdefault(int(row) * width + int(col), []).append(float(value))
    dsm = np.full((height, width), np.nan, dtype=np.float32)
    for key, values in buckets.items():
        row, col = divmod(key, width)
        dsm[row, col] = np.percentile(values, percentile)
    if tifffile is not None:
        tifffile.imwrite(output_path, dsm)
    else:
        np.save(output_dir / "dsm.npy", dsm)
        output_path = output_dir / "dsm.npy"
    return DsmResult(
        success=True,
        output_path=output_path,
        message="DSM rasterized from dense point cloud.",
        width=width,
        height=height,
        resolution=resolution,
    )
