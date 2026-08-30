"""Browser dashboard for live GARUDA real sensor, AHRS, and camera-frame checks.

Run on the Raspberry Pi for hardware:
    python hardware_tests/web_sensor_dashboard.py --mode bno085 --host 0.0.0.0
"""

from __future__ import annotations

import argparse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
from pathlib import Path
import sys
import threading
import time
from typing import Any
from urllib.parse import urlparse

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import config
from camera.camera_manager import create_camera
from core.shared_data import SharedData
from sensors.barometer import create_barometer
from sensors.gps import create_gps
from sensors.imu import create_imu
from sensor_fusion.ahrs import AHRSManager, AHRSMode, raw_from_reading
from telemetry.telemetry_packet import build_telemetry_packet


HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>GARUDA Live Dashboard</title>
<style>
:root { color-scheme: dark; font-family: Inter, Segoe UI, Arial, sans-serif; }
* { box-sizing: border-box; }
body { margin: 0; background: #111318; color: #eef2f7; }
header { display: flex; justify-content: space-between; align-items: center; padding: 14px 18px; border-bottom: 1px solid #2b313c; background: #171b22; }
h1 { margin: 0; font-size: 20px; letter-spacing: 0; }
.status { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; font-size: 13px; color: #cbd5e1; }
.pill { padding: 5px 9px; border-radius: 999px; background: #242b36; border: 1px solid #394151; }
.ok { color: #8ff0b1; }
.bad { color: #ff9c9c; }
main { display: grid; grid-template-columns: minmax(320px, 1.25fr) minmax(320px, .75fr); gap: 14px; padding: 14px; }
section { background: #171b22; border: 1px solid #2b313c; border-radius: 8px; padding: 14px; min-width: 0; }
.video { display: grid; gap: 10px; }
#frame { width: 100%; aspect-ratio: 4 / 3; object-fit: contain; background: #07090d; border: 1px solid #303846; border-radius: 6px; }
.grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; }
.tile { background: #202631; border: 1px solid #313948; border-radius: 6px; padding: 10px; min-height: 74px; }
.label { color: #96a3b6; font-size: 12px; margin-bottom: 6px; }
.value { font-size: 22px; font-variant-numeric: tabular-nums; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.small { font-size: 14px; color: #d4dbe7; font-variant-numeric: tabular-nums; }
.wide { grid-column: 1 / -1; }
pre { margin: 0; overflow: auto; color: #cdd6e4; line-height: 1.35; font-size: 12px; max-height: 220px; }
@media (max-width: 900px) { main { grid-template-columns: 1fr; } .grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 520px) { .grid { grid-template-columns: 1fr; } header { align-items: flex-start; flex-direction: column; gap: 8px; } }
</style>
</head>
<body>
<header>
  <h1>GARUDA Live Dashboard</h1>
  <div class="status">
    <span class="pill" id="runtime">runtime --</span>
    <span class="pill" id="mode">mode --</span>
    <span class="pill" id="health">health --</span>
  </div>
</header>
<main>
  <section class="video">
    <div class="status"><span class="pill" id="camera">camera --</span><span class="pill" id="imageName">image --</span></div>
    <img id="frame" alt="latest camera frame">
  </section>
  <section>
    <div class="grid">
      <div class="tile"><div class="label">Roll</div><div class="value" id="roll">--</div></div>
      <div class="tile"><div class="label">Pitch</div><div class="value" id="pitch">--</div></div>
      <div class="tile"><div class="label">Yaw</div><div class="value" id="yaw">--</div></div>
      <div class="tile"><div class="label">Altitude</div><div class="value" id="alt">--</div></div>
      <div class="tile"><div class="label">GPS</div><div class="small" id="gps">--</div></div>
      <div class="tile"><div class="label">Sample Age</div><div class="value" id="age">--</div></div>
      <div class="tile wide"><div class="label">Quaternion w,x,y,z</div><div class="small" id="quat">--</div></div>
      <div class="tile wide"><div class="label">Raw IMU</div><div class="small" id="raw">--</div></div>
      <div class="tile wide"><div class="label">Telemetry Preview</div><pre id="packet">--</pre></div>
    </div>
  </section>
</main>
<script>
function fmt(n, d=2, suffix='') { return Number.isFinite(n) ? n.toFixed(d) + suffix : '--'; }
async function refresh() {
  const res = await fetch('/api/state', { cache: 'no-store' });
  const s = await res.json();
  document.getElementById('runtime').textContent = `runtime ${fmt(s.runtime_s,1,'s')}`;
  document.getElementById('mode').textContent = `mode ${s.mode}`;
  const h = document.getElementById('health');
  h.textContent = `AHRS ${s.ahrs.source} ${s.ahrs.confidence}`;
  h.className = `pill ${s.ahrs.healthy ? 'ok' : 'bad'}`;
  document.getElementById('camera').textContent = `camera ${s.health.camera}`;
  document.getElementById('imageName').textContent = s.image.name || 'image --';
  document.getElementById('roll').textContent = fmt(s.ahrs.roll_deg, 2, ' deg');
  document.getElementById('pitch').textContent = fmt(s.ahrs.pitch_deg, 2, ' deg');
  document.getElementById('yaw').textContent = fmt(s.ahrs.yaw_deg, 2, ' deg');
  document.getElementById('alt').textContent = fmt(s.baro.altitude_m, 1, ' m');
  document.getElementById('gps').textContent = `${s.gps.fix ? 'fix' : 'no fix'}  ${fmt(s.gps.lat,6)}, ${fmt(s.gps.lon,6)}`;
  document.getElementById('age').textContent = fmt(s.ahrs.sample_age_ms, 1, ' ms');
  document.getElementById('quat').textContent = s.ahrs.quaternion.map(v => fmt(v, 5)).join(', ');
  document.getElementById('raw').textContent = `accel ${s.raw.accel.join(', ')} | gyro ${s.raw.gyro.join(', ')} | mag ${s.raw.mag.join(', ')}`;
  document.getElementById('packet').textContent = s.telemetry;
  if (s.image.url) document.getElementById('frame').src = s.image.url + '&t=' + Date.now();
}
refresh();
setInterval(refresh, 500);
</script>
</body>
</html>
"""


class DashboardState:
    def __init__(self, mode: str, camera_interval: float) -> None:
        self.mode = mode
        self.camera_interval = camera_interval
        self.started = time.monotonic()
        self.shared = SharedData()
        self.ahrs = AHRSManager(mode=mode, enabled=mode != "OFF")
        self.lock = threading.Lock()
        self.latest_image: Path | None = None
        self.health = {"gps": "INIT", "barometer": "INIT", "imu": "INIT", "camera": "INIT"}
        self.last_raw = {
            "accel": ["--", "--", "--"],
            "gyro": ["--", "--", "--"],
            "mag": ["--", "--", "--"],
        }

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            snap = self.shared.get_snapshot()
            packet = build_telemetry_packet(snap)
            image_url = f"/frame?name={self.latest_image.name}" if self.latest_image else ""
            return {
                "runtime_s": time.monotonic() - self.started,
                "mode": self.mode,
                "health": dict(self.health),
                "gps": {
                    "fix": snap.gps_ok,
                    "lat": snap.latitude,
                    "lon": snap.longitude,
                    "altitude_m": snap.gps_altitude,
                },
                "baro": {"altitude_m": snap.baro_altitude},
                "ahrs": {
                    "source": snap.ahrs_source,
                    "valid": snap.ahrs_valid,
                    "healthy": snap.ahrs_healthy,
                    "confidence": snap.ahrs_confidence,
                    "roll_deg": snap.ahrs_roll,
                    "pitch_deg": snap.ahrs_pitch,
                    "yaw_deg": snap.ahrs_yaw,
                    "sample_age_ms": snap.imu_sample_age_ms,
                    "quaternion": [snap.quat_w, snap.quat_x, snap.quat_y, snap.quat_z],
                },
                "raw": dict(self.last_raw),
                "image": {"name": snap.image_name, "url": image_url},
                "telemetry": packet,
            }


def _fmt_tuple(values: tuple[float, ...] | None, precision: int = 3) -> list[str]:
    if values is None:
        return ["--", "--", "--"]
    return [f"{v:+.{precision}f}" for v in values]


def _sensor_loop(state: DashboardState, stop: threading.Event) -> None:
    config.USE_MOCK_HARDWARE = False
    gps = create_gps()
    baro = create_barometer()
    imu = create_imu()
    try:
        while not stop.is_set():
            try:
                gps_reading = gps.read()
                with state.lock:
                    state.shared.update(
                        latitude=gps_reading.get("latitude", 0.0),
                        longitude=gps_reading.get("longitude", 0.0),
                        gps_altitude=gps_reading.get("altitude", 0.0),
                        gps_ok=bool(gps_reading.get("fix_ok")),
                    )
                    state.health["gps"] = "OK"
            except Exception as exc:
                with state.lock:
                    state.health["gps"] = f"ERR {type(exc).__name__}"

            try:
                baro_reading = baro.read()
                with state.lock:
                    state.shared.update(
                        baro_altitude=baro_reading.get("altitude", 0.0),
                        barometer_ok=True,
                    )
                    state.health["barometer"] = "OK"
            except Exception as exc:
                with state.lock:
                    state.health["barometer"] = f"ERR {type(exc).__name__}"

            try:
                imu_reading = imu.read()
                raw = raw_from_reading(imu_reading)
                attitude = state.ahrs.update(raw)
                with state.lock:
                    state.shared.publish_attitude(attitude)
                    state.shared.update(imu_ok=True)
                    state.last_raw = {
                        "accel": _fmt_tuple(raw.accel_mps2),
                        "gyro": _fmt_tuple(raw.gyro_rads),
                        "mag": _fmt_tuple(raw.mag_ut),
                    }
                    state.health["imu"] = "OK"
            except Exception as exc:
                with state.lock:
                    state.health["imu"] = f"ERR {type(exc).__name__}"

            stop.wait(1.0 / max(1.0, config.AHRS_RATE_HZ))
    finally:
        for device in (imu, baro, gps):
            try:
                device.close()
            except Exception:
                pass


def _camera_loop(state: DashboardState, stop: threading.Event) -> None:
    config.USE_MOCK_HARDWARE = False
    camera = create_camera()
    try:
        while not stop.is_set():
            try:
                with state.lock:
                    snap = state.shared.get_snapshot()
                filename = camera.capture(latitude=snap.latitude, longitude=snap.longitude)
                image_path = config.IMAGE_SAVE_PATH / filename
                with state.lock:
                    state.latest_image = image_path
                    state.shared.update(
                        image_name=filename,
                        image_timestamp=time.time(),
                        camera_ok=True,
                    )
                    state.health["camera"] = "OK"
            except Exception as exc:
                with state.lock:
                    state.health["camera"] = f"ERR {type(exc).__name__}"
            stop.wait(max(0.1, state.camera_interval))
    finally:
        try:
            camera.close()
        except Exception:
            pass


def _make_handler(state: DashboardState):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:
            return

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/":
                self._send_bytes(HTML.encode("utf-8"), "text/html; charset=utf-8")
            elif parsed.path == "/api/state":
                self._send_bytes(
                    json.dumps(state.snapshot()).encode("utf-8"),
                    "application/json",
                )
            elif parsed.path == "/frame":
                self._send_frame()
            else:
                self.send_error(HTTPStatus.NOT_FOUND)

        def _send_frame(self) -> None:
            with state.lock:
                image_path = state.latest_image
            if image_path is None or not image_path.exists():
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            content_type = mimetypes.guess_type(str(image_path))[0] or "image/jpeg"
            self._send_bytes(image_path.read_bytes(), content_type)

        def _send_bytes(self, data: bytes, content_type: str) -> None:
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

    return Handler


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=[m.value.lower() for m in AHRSMode], default=config.AHRS_MODE.lower())
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--camera-interval", type=float, default=0.5)
    parser.add_argument("--duration", type=float, default=0.0, help="Optional duration for smoke tests; 0 runs until Ctrl+C.")
    args = parser.parse_args()

    config.USE_MOCK_HARDWARE = False
    state = DashboardState(args.mode.upper(), args.camera_interval)
    stop = threading.Event()
    threads = [
        threading.Thread(target=_sensor_loop, args=(state, stop), name="dashboard-sensors"),
        threading.Thread(target=_camera_loop, args=(state, stop), name="dashboard-camera"),
    ]
    for thread in threads:
        thread.start()

    server = ThreadingHTTPServer((args.host, args.port), _make_handler(state))
    server.timeout = 0.5
    url_host = "localhost" if args.host in ("0.0.0.0", "127.0.0.1") else args.host
    print(f"GARUDA dashboard running at http://{url_host}:{args.port}")
    print("Ctrl+C to stop. The dashboard reads real sensors and captures frames; it does not move servos.")
    deadline = None if args.duration <= 0 else time.monotonic() + args.duration
    try:
        while deadline is None or time.monotonic() < deadline:
            server.handle_request()
    except KeyboardInterrupt:
        print("\nStopping dashboard.")
    finally:
        stop.set()
        server.server_close()
        for thread in threads:
            thread.join(timeout=2.0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
