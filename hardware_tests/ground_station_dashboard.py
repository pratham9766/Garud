"""Temporary GARUDA ground-station dashboard for integrated payload testing.

Run from the project root:
    python hardware_tests/ground_station_dashboard.py --host 0.0.0.0
"""

from __future__ import annotations

import argparse
import csv
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import logging
import mimetypes
import socket
from datetime import datetime
from pathlib import Path
import sys
import threading
import time
from typing import Any
from urllib.parse import parse_qs, urlparse

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config
from camera.camera_manager import camera_worker
from core.flight_state_machine import FlightStateController
from core.health_monitor import health_monitor_loop
from core.mission_state import MissionState, next_state
from core.payload_diagnostics import image_quality_worker, storage_validation_worker
from core.shared_data import SharedData
from core.system_health import system_health_worker
from core.thread_manager import ManagedThread, ThreadManager
from gimbal.gimbal_stabilizer import gimbal_worker
from logging_system.data_logger import DataLogger, logger_worker
from navigation.navigation_estimator import navigation_worker
from sensors.barometer import barometer_worker
from sensors.gps import gps_worker
from sensors.imu import imu_worker
from sensors.power_monitor import power_worker
from telemetry.telemetry_packet import build_telemetry_packet
from telemetry.xbee_sender import telemetry_worker

logger = logging.getLogger(__name__)


HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>GARUDA Ground Station</title>
<style>
:root {
  color-scheme: dark;
  font-family: Inter, "Segoe UI", Arial, sans-serif;
  background: #0c0f14;
  color: #e8edf5;
}
* { box-sizing: border-box; }
body { margin: 0; background: #0c0f14; }
header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 12px 16px;
  border-bottom: 1px solid #2d3440;
  background: #151a22;
}
h1 { margin: 0; font-size: 20px; font-weight: 750; letter-spacing: 0; }
button, select {
  background: #222a35;
  color: #e8edf5;
  border: 1px solid #3a4656;
  border-radius: 6px;
  padding: 8px 10px;
  font: inherit;
}
button { cursor: pointer; }
button:hover { background: #2b3543; }
.topline, .controls, .status-row { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.tabs { display: flex; gap: 6px; padding: 8px 12px 0; flex-wrap: wrap; }
.tab.active { background: #334155; border-color: #607089; }
.view { display: none; }
.view.active { display: block; grid-column: 1 / -1; }
.pill {
  border: 1px solid #394556;
  border-radius: 999px;
  padding: 6px 9px;
  background: #202734;
  color: #b9c4d5;
  font-size: 13px;
}
.ok { color: #8ef0b0; border-color: #2f7650; }
.bad { color: #ff9d9d; border-color: #7a3737; }
.amber { color: #f2c66d; border-color: #81662e; }
.gray { color: #a8b1bf; border-color: #4a5260; }
main {
  display: grid;
  grid-template-columns: minmax(360px, 1.25fr) minmax(330px, .75fr);
  gap: 12px;
  padding: 12px;
}
section {
  border: 1px solid #2d3440;
  background: #151a22;
  border-radius: 8px;
  padding: 12px;
  min-width: 0;
}
.mission-grid {
  display: grid;
  grid-template-columns: minmax(520px, 1.15fr) minmax(340px, .85fr);
  gap: 10px;
}
.mission-side {
  display: grid;
  gap: 10px;
  align-content: start;
}
.compact-list {
  display: grid;
  gap: 6px;
  max-height: 180px;
  overflow: auto;
}
.compact-item {
  border-bottom: 1px solid #2d3440;
  padding-bottom: 6px;
}
.compact-item:last-child { border-bottom: 0; padding-bottom: 0; }
.cards {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}
.card {
  border: 1px solid #303948;
  background: #1d2430;
  border-radius: 6px;
  padding: 10px;
  min-height: 80px;
}
.label { color: #98a6b8; font-size: 12px; margin-bottom: 8px; }
.value {
  font-size: 22px;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.small { font-size: 13px; color: #d4dce8; line-height: 1.45; font-variant-numeric: tabular-nums; }
.wide { grid-column: 1 / -1; }
.charts { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 10px; }
canvas {
  width: 100%;
  height: 180px;
  background: #0e1218;
  border: 1px solid #2d3440;
  border-radius: 6px;
}
#frame {
  width: 100%;
  aspect-ratio: 4 / 3;
  object-fit: contain;
  background: #080b10;
  border: 1px solid #2d3440;
  border-radius: 6px;
}
pre {
  margin: 0;
  max-height: 160px;
  overflow: auto;
  color: #d4dce8;
  font-size: 12px;
  line-height: 1.35;
}
table { width: 100%; border-collapse: collapse; font-size: 12px; }
th, td { border-bottom: 1px solid #2d3440; padding: 6px; text-align: left; vertical-align: top; }
th { color: #98a6b8; font-weight: 650; }
@media (max-width: 1050px) {
  main { grid-template-columns: 1fr; }
  .cards { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .mission-grid { grid-template-columns: 1fr; }
}
@media (max-width: 560px) {
  header { align-items: flex-start; flex-direction: column; }
  .cards, .charts { grid-template-columns: 1fr; }
  .value { font-size: 20px; }
}
</style>
</head>
<body>
<header>
  <div>
    <h1>GARUDA Ground Station</h1>
    <div class="topline">
      <span class="pill" id="mode">mode --</span>
      <span class="pill" id="state">Current State --</span>
      <span class="pill" id="auto">auto --</span>
      <span class="pill" id="log">log --</span>
    </div>
  </div>
</header>
<nav class="tabs">
  <button class="tab active" onclick="showTab('mission', this)">Mission</button>
  <button class="tab" onclick="showTab('sensors', this)">Sensors</button>
  <button class="tab" onclick="showTab('payload', this)">Payload</button>
  <button class="tab" onclick="showTab('system', this)">System</button>
  <button class="tab" onclick="showTab('telemetry', this)">Telemetry</button>
  <button class="tab" onclick="showTab('test', this)">Test</button>
</nav>
<main>
  <section class="view active" id="missionView">
    <div class="mission-grid">
      <div>
        <div class="cards">
          <div class="card"><div class="label">Current State</div><div class="value" id="currentState">--</div></div>
          <div class="card"><div class="label">Previous State</div><div class="value" id="previousState">--</div></div>
          <div class="card"><div class="label">Time in State</div><div class="value" id="timeInState">--</div></div>
          <div class="card"><div class="label">Mission Time</div><div class="value" id="time">--</div></div>
          <div class="card"><div class="label">Baro AGL</div><div class="value" id="baro">--</div></div>
          <div class="card"><div class="label">Baro Raw / Filtered</div><div class="small" id="baroDetail">--</div></div>
          <div class="card"><div class="label">GPS Altitude</div><div class="value" id="gpsAlt">--</div></div>
          <div class="card"><div class="label">Max AGL</div><div class="value" id="maxAlt">--</div></div>
          <div class="card"><div class="label">Vertical Rate</div><div class="value" id="vz">--</div></div>
          <div class="card"><div class="label">Roll</div><div class="value" id="roll">--</div></div>
          <div class="card"><div class="label">Pitch</div><div class="value" id="pitch">--</div></div>
          <div class="card"><div class="label">Yaw</div><div class="value" id="yaw">--</div></div>
          <div class="card wide"><div class="label">Transition Reason</div><div class="small" id="transitionReason">--</div></div>
          <div class="card wide"><div class="label">Subsystem Health</div><div class="status-row" id="health"></div></div>
          <div class="card wide"><div class="label">Verification Summary</div><div class="status-row" id="verificationSummary"></div></div>
        </div>
        <div class="charts">
          <canvas id="altChart" width="520" height="180"></canvas>
          <canvas id="attChart" width="520" height="180"></canvas>
          <canvas id="rateChart" width="520" height="180"></canvas>
          <canvas id="gimbalChart" width="520" height="180"></canvas>
        </div>
      </div>
      <div class="mission-side">
        <div class="card"><div class="label">Active Warnings / Faults</div><div class="compact-list small" id="activeWarnings">--</div></div>
        <div class="card"><div class="label">Recent Mission Events</div><div class="compact-list small" id="missionEvents">--</div></div>
        <div class="card"><div class="label">State Transition History</div><div class="compact-list small" id="missionStateHistory">--</div></div>
        <div class="card"><div class="label">Worker Heartbeat</div><div class="compact-list small" id="missionWorkers">--</div></div>
      </div>
    </div>
  </section>
  <section class="view" id="payloadView">
    <div class="status-row">
      <span class="pill" id="camera">camera --</span>
      <span class="pill" id="imageName">image --</span>
    </div>
    <img id="frame" alt="latest payload camera frame">
    <div class="card wide" style="margin-top:10px">
      <div class="label">Image Quality / Sync</div>
      <div class="small" id="imageQuality">--</div>
    </div>
    <div class="card wide" style="margin-top:10px">
      <div class="label">GPS</div>
      <div class="small" id="gps">--</div>
    </div>
    <div class="card wide" style="margin-top:10px">
      <div class="label">Estimated Navigation</div>
      <div class="small" id="navigation">--</div>
    </div>
    <div class="card wide" style="margin-top:10px">
      <div class="label">Raw IMU</div>
      <div class="small" id="raw">--</div>
    </div>
    <div class="card wide" style="margin-top:10px">
      <div class="label">Telemetry Packet Preview</div>
      <pre id="packet">--</pre>
    </div>
    <div class="card wide" style="margin-top:10px">
      <div class="label">Worker Health</div>
      <table>
        <thead><tr><th>Worker</th><th>Status</th><th>Actual</th><th>Expected</th><th>Age</th><th>Errors</th><th>Reason</th></tr></thead>
        <tbody id="workers"></tbody>
      </table>
    </div>
    <div class="card wide" style="margin-top:10px">
      <div class="label">State History</div>
      <table>
        <thead><tr><th>T+</th><th>From</th><th>To</th><th>Reason</th></tr></thead>
        <tbody id="stateHistory"></tbody>
      </table>
    </div>
    <div class="card wide" style="margin-top:10px">
      <div class="label">Event Log</div>
      <table>
        <thead><tr><th>T+</th><th>Severity</th><th>Source</th><th>Type</th><th>Message</th></tr></thead>
        <tbody id="events"></tbody>
      </table>
    </div>
  </section>
  <section class="view" id="sensorsView">
    <div class="cards">
      <div class="card wide"><div class="label">GPS Diagnostics</div><div class="small" id="gpsDiag">--</div></div>
      <div class="card wide"><div class="label">Barometer Diagnostics</div><div class="small" id="baroDiag">--</div></div>
      <div class="card wide"><div class="label">IMU / AHRS Diagnostics</div><div class="small" id="imuDiag">--</div></div>
      <div class="card wide"><div class="label">Detector Conditions</div><pre id="detectors">--</pre></div>
    </div>
  </section>
  <section class="view" id="systemView">
    <div class="cards">
      <div class="card"><div class="label">Voltage</div><div class="value" id="voltage">--</div></div>
      <div class="card"><div class="label">Current</div><div class="value" id="current">--</div></div>
      <div class="card"><div class="label">Power</div><div class="value" id="power">--</div></div>
      <div class="card"><div class="label">Undervoltage</div><div class="value" id="uvEvents">--</div></div>
      <div class="card wide"><div class="label">Worker Health</div><table><thead><tr><th>Worker</th><th>Status</th><th>Actual</th><th>Expected</th><th>Age</th><th>Errors</th><th>Reason</th></tr></thead><tbody id="workersSystem"></tbody></table></div>
      <div class="card wide"><div class="label">Storage Validation</div><div class="small" id="storage">--</div></div>
    </div>
  </section>
  <section class="view" id="telemetryView">
    <div class="cards">
      <div class="card"><div class="label">TX Sequence</div><div class="value" id="txSeq">--</div></div>
      <div class="card"><div class="label">TX Count</div><div class="value" id="txCount">--</div></div>
      <div class="card wide"><div class="label">Packet Preview</div><pre id="packet2">--</pre></div>
    </div>
  </section>
  <section class="view" id="testView">
    <div class="cards">
      <div class="card wide"><div class="label">Manual FSM Override</div><div class="controls"><span class="pill" id="manualLock">manual --</span><select id="stateSelect"></select><button id="setStateBtn" onclick="setState()">Set State</button><button id="nextBtn" onclick="nextState()">Next</button><button id="autoOnBtn" onclick="setAuto(true)">Auto On</button><button id="autoOffBtn" onclick="setAuto(false)">Auto Off</button></div></div>
      <div class="card wide"><div class="label">Test Recording</div><div class="controls"><button onclick="testAction('start')">Start Test</button><button onclick="testAction('stop')">Stop Test</button><button onclick="testAction('reset')">Reset Test</button><span class="pill" id="testStatus">test --</span></div></div>
      <div class="card wide"><div class="label">Mock Fault Injection</div><div class="controls" id="faultControls"></div></div>
    </div>
  </section>
</main>
<script>
const states = [];
const history = [];
const maxPoints = 180;
const colors = ["#7cc7ff", "#f2c66d", "#87e39d", "#ff8f8f"];
const faults = ["gps_loss", "gps_high_hdop", "freeze_gps", "freeze_imu", "imu_drift", "freeze_barometer", "barometer_drift", "camera_timeout", "camera_dropped_frame", "telemetry_drop", "logger_write_failure", "gimbal_saturation", "low_voltage", "high_cpu_temperature"];

function showTab(name, button) {
  document.querySelectorAll(".view").forEach(v => v.classList.remove("active"));
  document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
  document.getElementById(name + "View").classList.add("active");
  button.classList.add("active");
}

function fmt(n, d=1, suffix="") {
  return Number.isFinite(n) ? n.toFixed(d) + suffix : "--";
}

function displayMode(mode) {
  if (mode === "MOCK") return "SIMULATION / MOCK";
  return mode || "--";
}

function displayStatus(status) {
  if (status === "ERROR" || status === "STALE") return "FAILED";
  return status || "INITIALIZING";
}

function statusClass(status) {
  status = displayStatus(status);
  if (status === "HEALTHY") return "ok";
  if (status === "DEGRADED" || status === "INITIALIZING") return "amber";
  if (status === "DISABLED") return "gray";
  return "bad";
}

function pill(name, health) {
  const span = document.createElement("span");
  const status = displayStatus(health.status);
  const reason = health.reason || "No reason reported.";
  span.className = "pill " + statusClass(status);
  span.title = reason;
  span.textContent = `${name} ${status} - ${reason}`;
  return span;
}

function verdictClass(status) {
  if (status === "PASS") return "ok";
  if (status === "WARN") return "amber";
  if (status === "SKIP") return "gray";
  return "bad";
}

function drawChart(id, title, series, markers=[]) {
  const canvas = document.getElementById(id);
  const ctx = canvas.getContext("2d");
  const w = canvas.width;
  const h = canvas.height;
  ctx.clearRect(0, 0, w, h);
  ctx.fillStyle = "#0e1218";
  ctx.fillRect(0, 0, w, h);
  ctx.strokeStyle = "#25303c";
  ctx.lineWidth = 1;
  for (let i = 1; i < 4; i++) {
    const y = i * h / 4;
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(w, y);
    ctx.stroke();
  }
  const all = series.flatMap(s => s.values).filter(Number.isFinite);
  let min = all.length ? Math.min(...all) : -1;
  let max = all.length ? Math.max(...all) : 1;
  if (Math.abs(max - min) < 1e-6) { max += 1; min -= 1; }
  const pad = (max - min) * 0.15;
  min -= pad;
  max += pad;
  ctx.fillStyle = "#aeb9c9";
  ctx.font = "12px Segoe UI, Arial";
  ctx.fillText(title, 10, 18);
  ctx.fillText(max.toFixed(1), 10, 36);
  ctx.fillText(min.toFixed(1), 10, h - 10);
  series.forEach((s, idx) => {
    ctx.strokeStyle = colors[idx % colors.length];
    ctx.lineWidth = 2;
    ctx.beginPath();
    let started = false;
    s.values.forEach((value, i) => {
      if (!Number.isFinite(value)) return;
      const x = (i / Math.max(1, maxPoints - 1)) * w;
      const y = h - ((value - min) / (max - min)) * h;
      if (!started) {
        ctx.moveTo(x, y);
        started = true;
      }
      else ctx.lineTo(x, y);
    });
    if (started) ctx.stroke();
    ctx.fillStyle = colors[idx % colors.length];
    ctx.fillText(s.name, w - 92, 18 + idx * 16);
  });
  if (history.length > 1) {
    const startT = history[0].mission_time;
    const endT = history[history.length - 1].mission_time;
    markers.forEach(m => {
      if (!Number.isFinite(m.mission_time) || m.mission_time < startT || m.mission_time > endT) return;
      const x = ((m.mission_time - startT) / Math.max(0.001, endT - startT)) * w;
      ctx.strokeStyle = m.severity === "ERROR" ? "#ff8f8f" : "#f2c66d";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, h);
      ctx.stroke();
    });
  }
}

async function postJson(url, body) {
  await fetch(url, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(body)
  });
}

async function setState() {
  await postJson("/api/state", {state: document.getElementById("stateSelect").value});
}

async function nextState() {
  await postJson("/api/next", {});
}

async function setAuto(enabled) {
  await postJson("/api/auto", {enabled});
}

async function setFault(name, enabled) {
  await postJson("/api/fault", {name, enabled});
}

async function testAction(action) {
  const res = await fetch(`/api/test/${action}`, {method: "POST", headers: {"Content-Type": "application/json"}, body: "{}"});
  const payload = await res.json();
  if (payload.report_paths) alert("Reports saved:\n" + JSON.stringify(payload.report_paths, null, 2));
}

function initFaultControls() {
  const box = document.getElementById("faultControls");
  if (box.childElementCount) return;
  faults.forEach(name => {
    const label = document.createElement("label");
    label.className = "pill gray";
    label.innerHTML = `<input type="checkbox" id="fault_${name}" onchange="setFault('${name}', this.checked)"> ${name}`;
    box.appendChild(label);
  });
}

function updateStateList(list) {
  if (states.length) return;
  states.push(...list);
  const select = document.getElementById("stateSelect");
  states.forEach(s => {
    const option = document.createElement("option");
    option.value = s;
    option.textContent = s;
    select.appendChild(option);
  });
}

function renderWorkerTable(workers) {
  const body = document.getElementById("workers");
  body.replaceChildren();
  const systemBody = document.getElementById("workersSystem");
  if (systemBody) systemBody.replaceChildren();
  Object.values(workers).forEach(w => {
    const row = document.createElement("tr");
    const age = w.data_age_ms === null ? "N/A" : fmt(w.data_age_ms, 0, " ms");
    row.innerHTML = `<td>${w.name}</td><td class="${statusClass(w.status)}">${w.status}</td><td>${fmt(w.actual_hz, 1, " Hz")}</td><td>${fmt(w.expected_hz, 1, " Hz")}</td><td>${age}</td><td>${w.error_count}</td><td>${w.reason || ""}</td>`;
    body.appendChild(row);
    if (systemBody) systemBody.appendChild(row.cloneNode(true));
  });
}

function renderStateHistory(items) {
  const body = document.getElementById("stateHistory");
  body.replaceChildren();
  items.slice(-8).reverse().forEach(e => {
    const row = document.createElement("tr");
    row.innerHTML = `<td>${fmt(e.mission_time, 2, " s")}</td><td>${e.from}</td><td>${e.to}</td><td>${e.reason}</td>`;
    body.appendChild(row);
  });
}

function renderEvents(items) {
  const body = document.getElementById("events");
  body.replaceChildren();
  items.slice(-10).reverse().forEach(e => {
    const row = document.createElement("tr");
    row.innerHTML = `<td>${fmt(e.mission_time, 2, " s")}</td><td>${e.severity}</td><td>${e.source}</td><td>${e.event_type}</td><td>${e.message}</td>`;
    body.appendChild(row);
  });
}

function renderVerificationSummary(summary) {
  const target = document.getElementById("verificationSummary");
  if (!target) return;
  target.replaceChildren();
  Object.entries(summary.categories || {}).forEach(([name, item]) => {
    const span = document.createElement("span");
    span.className = "pill " + verdictClass(item.status);
    span.title = (item.reasons || []).join(" | ");
    span.textContent = `${name} ${item.status}`;
    target.appendChild(span);
  });
}

function renderCompactList(id, items, emptyText) {
  const target = document.getElementById(id);
  if (!target) return;
  target.replaceChildren();
  if (!items.length) {
    target.textContent = emptyText;
    return;
  }
  items.forEach(text => {
    const div = document.createElement("div");
    div.className = "compact-item";
    div.textContent = text;
    target.appendChild(div);
  });
}

function renderMissionSide(s) {
  const warnings = [];
  Object.values(s.health || {}).forEach(w => {
    const status = displayStatus(w.status);
    if (status === "DEGRADED" || status === "FAILED") warnings.push(`${w.name} ${status} - ${w.reason || "No reason reported."}`);
  });
  Object.entries(s.diagnostics.faults || {}).forEach(([name, enabled]) => {
    if (enabled) warnings.push(`FAULT INJECTED - ${name}`);
  });
  Object.entries((s.verification || {}).categories || {}).forEach(([name, item]) => {
    if (item.status === "WARN" || item.status === "FAIL") warnings.push(`${name} ${item.status} - ${(item.reasons || []).join(" | ")}`);
  });
  renderCompactList("activeWarnings", warnings.slice(0, 8), "No active warnings or faults.");

  const events = (s.diagnostics.events || []).slice(-6).reverse().map(e => `${fmt(e.mission_time, 2, " s")} ${e.severity} ${e.source}: ${e.message}`);
  renderCompactList("missionEvents", events, "No mission events recorded.");

  const states = (s.diagnostics.state_history || []).slice(-6).reverse().map(e => `${fmt(e.mission_time, 2, " s")} ${e.from} -> ${e.to} (${e.reason})`);
  renderCompactList("missionStateHistory", states, "No state transitions recorded.");

  const workers = Object.values(s.diagnostics.workers || {}).slice(0, 10).map(w => {
    const age = w.data_age_ms === null ? "N/A" : fmt(w.data_age_ms, 0, " ms");
    return `${w.name}: ${displayStatus(w.status)} | ${fmt(w.actual_hz, 1, " Hz")}/${fmt(w.expected_hz, 1, " Hz")} | age ${age} | err ${w.error_count}`;
  });
  renderCompactList("missionWorkers", workers, "No worker heartbeat yet.");
}

function chartMarkers(s) {
  const eventMarkers = (s.diagnostics.events || []).map(e => ({mission_time: e.mission_time, severity: e.severity}));
  const stateMarkers = (s.diagnostics.state_history || []).map(e => ({mission_time: e.mission_time, severity: "STATE"}));
  return eventMarkers.concat(stateMarkers);
}

async function refresh() {
  const res = await fetch("/api/state", {cache: "no-store"});
  const s = await res.json();
  initFaultControls();
  updateStateList(s.states);
  document.getElementById("mode").textContent = displayMode(s.mode);
  document.getElementById("state").textContent = `Current State ${s.state}`;
  document.getElementById("auto").textContent = "auto " + (s.auto_transitions ? "ON" : "OFF");
  document.getElementById("log").textContent = s.log_path ? "log " + s.log_path.split(/[\\/]/).pop() : "log off";
  document.getElementById("currentState").textContent = s.state;
  document.getElementById("previousState").textContent = s.previous_state || "N/A";
  document.getElementById("timeInState").textContent = fmt(s.time_in_state, 1, " s");
  document.getElementById("transitionReason").textContent = s.transition_reason || "No transition reason recorded.";
  document.getElementById("time").textContent = fmt(s.mission_time, 1, " s");
  document.getElementById("baro").textContent = fmt(s.baro.agl_m, 1, " m");
  document.getElementById("baroDetail").textContent = `raw ${fmt(s.baro.raw_agl_m, 1, " m")} | filtered ${fmt(s.baro.filtered_agl_m, 1, " m")} | pressure ${fmt(s.baro.pressure_hpa, 2, " hPa")} | temp ${fmt(s.baro.temperature_c, 1, " C")}`;
  document.getElementById("gpsAlt").textContent = fmt(s.gps_altitude, 1, " m");
  document.getElementById("vz").textContent = fmt(s.vertical_velocity, 2, " m/s");
  document.getElementById("maxAlt").textContent = fmt(s.max_altitude, 1, " m");
  document.getElementById("roll").textContent = fmt(s.roll, 2, " deg");
  document.getElementById("pitch").textContent = fmt(s.pitch, 2, " deg");
  document.getElementById("yaw").textContent = fmt(s.yaw, 2, " deg");
  document.getElementById("gimbal").textContent = `stepper ${fmt(s.gimbal.stepper, 1, " deg")} | servo cmd ${fmt(s.gimbal.servo, 1, " deg")} | steps ${s.gimbal.steps}`;
  const gpsDetails = s.health.gps.details || {};
  document.getElementById("gps").textContent = `${s.gps.fix_type || gpsDetails.fix_type || "N/A"} | sats ${s.gps.satellites ?? gpsDetails.satellites ?? "N/A"} | HDOP ${s.gps.hdop ?? gpsDetails.hdop ?? "N/A"} | lat ${fmt(s.latitude, 6)} | lon ${fmt(s.longitude, 6)} | GPS MSL ${fmt(s.gps_altitude, 1, " m")} | speed ${fmt(s.gps.speed_mps, 1, " m/s")} | course ${fmt(s.gps.course_deg, 1, " deg")} | age ${fmt(s.navigation.gps_age_ms, 0, " ms")}`;
  document.getElementById("navigation").textContent = `${s.navigation.mode} | pos ${s.navigation.position_quality} | head ${s.navigation.heading_quality} | alt ${s.navigation.altitude_quality} | est ${fmt(s.navigation.latitude, 6)}, ${fmt(s.navigation.longitude, 6)} | N/E ${fmt(s.navigation.north_m, 1, " m")}, ${fmt(s.navigation.east_m, 1, " m")} | VN/VE ${fmt(s.navigation.vn_mps, 1, " m/s")}, ${fmt(s.navigation.ve_mps, 1, " m/s")} | gs ${fmt(s.navigation.ground_speed_mps, 1, " m/s")} | course ${fmt(s.navigation.course_deg, 1, " deg")} | heading ${fmt(s.navigation.heading_deg, 1, " deg")} | alt ${fmt(s.navigation.altitude_m, 1, " m")} | GPS error ${fmt(s.navigation.gps_position_error_m, 1, " m")} | rejected ${s.navigation.gps_rejected} ${s.navigation.gps_rejection_reason} | DR ${s.navigation.dead_reckoning_active} ${fmt(s.navigation.dead_reckoning_age_s, 1, " s")} | recovery ${s.navigation.recovery_active} | safe ${s.navigation.safe_for_guidance}`;
  document.getElementById("raw").textContent = `gyro ${s.raw.gyro.map(v => fmt(v, 3)).join(", ")} | accel ${s.raw.accel.map(v => fmt(v, 2)).join(", ")} | mag ${s.raw.mag.map(v => fmt(v, 2)).join(", ")}`;
  document.getElementById("packet").textContent = s.telemetry;
  document.getElementById("packet2").textContent = s.telemetry;
  document.getElementById("imageQuality").textContent = `quality ${s.camera.quality_status} | sharpness ${fmt(s.camera.quality_sharpness, 1)} | brightness ${fmt(s.camera.quality_brightness, 1)} | under ${fmt(s.camera.quality_underexposed_fraction * 100, 1, "%")} | over ${fmt(s.camera.quality_overexposed_fraction * 100, 1, "%")} | sync IMU ${fmt(s.camera.sync_imu_delta_ms, 0, " ms")} GPS ${fmt(s.camera.sync_gps_delta_ms, 0, " ms")} BARO ${fmt(s.camera.sync_baro_delta_ms, 0, " ms")}`;
  document.getElementById("camera").textContent = "camera " + s.health.camera.status;
  document.getElementById("camera").className = "pill " + statusClass(s.health.camera.status);
  document.getElementById("imageName").textContent = s.image_name || "image --";
  if (s.image_url) document.getElementById("frame").src = s.image_url + "&t=" + Date.now();
  const health = document.getElementById("health");
  document.getElementById("setStateBtn").disabled = !s.manual_state_allowed;
  document.getElementById("nextBtn").disabled = !s.manual_state_allowed;
  document.getElementById("manualLock").textContent = s.manual_state_allowed ? "manual override ENABLED" : "manual override LOCKED";
  document.getElementById("manualLock").className = "pill " + (s.manual_state_allowed ? "amber" : "gray");
  const select = document.getElementById("stateSelect");
  if (select && select.value !== s.state) select.value = s.state;
  health.replaceChildren(
    pill("GPS", s.health.gps),
    pill("IMU", s.health.imu),
    pill("BARO", s.health.barometer),
    pill("CAM", s.health.camera),
    pill("GIMBAL", s.health.gimbal),
    pill("NAV", s.health.navigation),
    pill("TELEM", s.health.telemetry),
    pill("LOG", s.health.logging),
    pill("SYS", s.health.system)
  );
  renderVerificationSummary(s.verification || {});
  renderMissionSide(s);
  renderWorkerTable(s.diagnostics.workers);
  renderStateHistory(s.diagnostics.state_history);
  renderEvents(s.diagnostics.events);
  document.getElementById("gpsDiag").textContent = JSON.stringify(s.health.gps.details || {}, null, 2);
  document.getElementById("baroDiag").textContent = JSON.stringify(s.health.barometer.details || {}, null, 2);
  document.getElementById("imuDiag").textContent = JSON.stringify(s.health.imu.details || {}, null, 2);
  document.getElementById("detectors").textContent = JSON.stringify(s.detectors, null, 2);
  document.getElementById("voltage").textContent = fmt(s.power.bus_voltage_v, 2, " V");
  document.getElementById("current").textContent = fmt(s.power.current_a, 2, " A");
  document.getElementById("power").textContent = fmt(s.power.power_w, 2, " W");
  document.getElementById("uvEvents").textContent = s.power.undervoltage_events;
  document.getElementById("storage").textContent = `referenced ${s.storage.images_referenced} | present ${s.storage.images_present} | missing ${s.storage.images_missing} | orphan ${s.storage.images_orphan}`;
  document.getElementById("txSeq").textContent = s.telemetry_sequence;
  document.getElementById("txCount").textContent = s.telemetry_tx_count;
  const test = s.diagnostics.test || {};
  document.getElementById("testStatus").textContent = test.active ? `recording ${test.sample_count} samples` : "test idle";
  Object.entries(s.diagnostics.faults || {}).forEach(([name, enabled]) => {
    const input = document.getElementById("fault_" + name);
    if (input) input.checked = !!enabled;
  });
  faults.forEach(name => {
    const input = document.getElementById("fault_" + name);
    if (input) input.disabled = !s.mock;
  });
  history.push(s);
  while (history.length > maxPoints) history.shift();
  const vals = key => {
    const arr = history.map(item => key(item));
    while (arr.length < maxPoints) arr.unshift(NaN);
    return arr;
  };
  const markers = chartMarkers(s);
  drawChart("altChart", "Altitude", [
    {name: "baro raw", values: vals(x => x.baro.raw_agl_m)},
    {name: "baro filt", values: vals(x => x.baro.filtered_agl_m)},
    {name: "gps", values: vals(x => x.gps_altitude)}
  ], markers);
  drawChart("attChart", "Attitude", [
    {name: "roll", values: vals(x => x.roll)},
    {name: "pitch", values: vals(x => x.pitch)},
    {name: "yaw", values: vals(x => x.yaw)}
  ], markers);
  drawChart("rateChart", "Rates", [
    {name: "vz", values: vals(x => x.vertical_velocity)},
    {name: "gx", values: vals(x => x.raw.gyro[0])},
    {name: "gy", values: vals(x => x.raw.gyro[1])},
    {name: "gz", values: vals(x => x.raw.gyro[2])}
  ], markers);
  const gimbalChart = document.getElementById("gimbalChart");
  if (displayStatus(s.health.gimbal.status) === "DISABLED") {
    gimbalChart.style.display = "none";
  } else {
    gimbalChart.style.display = "block";
    drawChart("gimbalChart", "Gimbal", [
      {name: "stepper", values: vals(x => x.gimbal.stepper)},
      {name: "servo", values: vals(x => x.gimbal.servo)}
    ], markers);
  }
}
refresh();
setInterval(refresh, 500);
</script>
</body>
</html>
"""


class DashboardControl:
    def __init__(self, auto_transitions: bool, manual_state_allowed: bool) -> None:
        self._lock = threading.Lock()
        self.auto_transitions = auto_transitions
        self.manual_state_allowed = manual_state_allowed

    def set_auto(self, enabled: bool) -> None:
        with self._lock:
            self.auto_transitions = enabled

    def is_auto(self) -> bool:
        with self._lock:
            return self.auto_transitions

    def can_mutate_state(self) -> bool:
        with self._lock:
            return self.manual_state_allowed


def setup_logging() -> None:
    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def ensure_directories() -> None:
    for path in (config.IMAGE_SAVE_PATH, config.LOG_SAVE_PATH, config.MAP_SAVE_PATH):
        path.mkdir(parents=True, exist_ok=True)


def state_updates(state: MissionState) -> dict[str, Any]:
    updates: dict[str, Any] = {"status": f"DASH_{state.value}"}
    if state == MissionState.ARMED_PAD:
        updates["status"] = "DASH_ARMED"
    elif state == MissionState.BOOST:
        updates["launch_detected"] = True
    elif state == MissionState.APOGEE:
        updates["apogee_detected"] = True
        updates["payload_ejected"] = True
    elif state == MissionState.GLIDER_DEPLOY:
        updates["glider_deployed"] = True
    elif state == MissionState.GUIDED_DESCENT:
        updates["glider_deployed"] = True
        updates["actuation_enabled"] = True
    elif state in {MissionState.DISARMED, MissionState.IDLE, MissionState.LANDED, MissionState.ABORT, MissionState.ERROR}:
        updates["actuation_enabled"] = False
    return updates


def force_state(shared: SharedData, state: MissionState) -> None:
    shared.transition_state(
        state,
        reason="dashboard_manual_override",
        source="GROUND_STATION",
        **state_updates(state),
    )
    logger.info("Dashboard forced state: %s", state.value)


def start_workers(shared: SharedData, thread_mgr: ThreadManager, data_logger: DataLogger | None) -> None:
    if config.ENABLE_GPS:
        thread_mgr.register(ManagedThread("GPS", lambda evt: gps_worker(shared, evt)))
    else:
        shared.set_worker_disabled("GPS")
    if config.ENABLE_IMU:
        thread_mgr.register(ManagedThread("IMU", lambda evt: imu_worker(shared, evt)))
    else:
        shared.set_worker_disabled("IMU")
    if config.ENABLE_BAROMETER:
        thread_mgr.register(ManagedThread("Barometer", lambda evt: barometer_worker(shared, evt)))
    else:
        shared.set_worker_disabled("Barometer")
    if config.ENABLE_CAMERA:
        thread_mgr.register(ManagedThread("Camera", lambda evt: camera_worker(shared, evt)))
    else:
        shared.set_worker_disabled("Camera")
    if config.ENABLE_GIMBAL:
        thread_mgr.register(ManagedThread("Gimbal", lambda evt: gimbal_worker(shared, evt)))
    else:
        shared.set_worker_disabled("Gimbal")
    if config.ENABLE_NAVIGATION_ESTIMATOR:
        thread_mgr.register(ManagedThread("Navigation", lambda evt: navigation_worker(shared, evt)))
    else:
        shared.set_worker_disabled("Navigation")
    if config.ENABLE_TELEMETRY:
        thread_mgr.register(ManagedThread("Telemetry", lambda evt: telemetry_worker(shared, evt)))
    else:
        shared.set_worker_disabled("Telemetry")
    if config.ENABLE_LOGGING and data_logger is not None:
        thread_mgr.register(ManagedThread("DataLogger", lambda evt: logger_worker(shared, data_logger, evt)))
    else:
        shared.set_worker_disabled("DataLogger")
    thread_mgr.register(ManagedThread("Power", lambda evt: power_worker(shared, evt)))
    thread_mgr.register(ManagedThread("ImageQuality", lambda evt: image_quality_worker(shared, evt)))
    thread_mgr.register(ManagedThread("Storage", lambda evt: storage_validation_worker(shared, evt, data_logger.path if data_logger else None)))
    thread_mgr.register(ManagedThread("HealthMonitor", lambda evt: health_monitor_loop(shared, evt, interval_sec=5.0)))
    thread_mgr.register(ManagedThread("System", lambda evt: system_health_worker(shared, evt)))
    thread_mgr.start_all()


def auto_transition_loop(shared: SharedData, control: DashboardControl, stop_event: threading.Event) -> None:
    controller = FlightStateController(shared)
    while not stop_event.is_set():
        if control.is_auto():
            try:
                controller.update()
            except Exception as exc:
                logger.error("Dashboard auto transition error: %s", exc)
        stop_event.wait(0.1)


def test_recording_loop(shared: SharedData, stop_event: threading.Event) -> None:
    while not stop_event.is_set():
        shared.record_test_sample()
        stop_event.wait(1.0)


def image_url_for(snap) -> str:
    if not snap.image_name:
        return ""
    return f"/frame?name={snap.image_name}"


def build_verification_summary(snap, diagnostics: dict[str, Any], data_logging_enabled: bool) -> dict[str, Any]:
    workers: dict[str, dict[str, Any]] = diagnostics.get("workers", {})
    events = diagnostics.get("events", [])

    def status_order(status: str) -> int:
        return {"SKIP": 0, "PASS": 1, "WARN": 2, "FAIL": 3}.get(status, 0)

    def worker_verdict(name: str, enabled: bool) -> tuple[str, str]:
        if not enabled:
            return "SKIP", f"{name} skipped by active test profile."
        worker = workers.get(name)
        if worker is None:
            return "WARN", f"{name} has not reported yet."
        status = worker.get("status", "INITIALIZING")
        reason = worker.get("reason") or status
        if status == "DISABLED":
            return "SKIP", f"{name} skipped: {reason}"
        if status in ("ERROR", "STALE", "FAILED"):
            return "FAIL", f"{name}: {reason}"
        if status in ("DEGRADED", "INITIALIZING"):
            return "WARN", f"{name}: {reason}"
        return "PASS", f"{name}: {reason}"

    def category(items: list[tuple[str, bool]], extra_reasons: list[str] | None = None) -> dict[str, Any]:
        reasons: list[str] = []
        statuses: list[str] = []
        for name, enabled in items:
            status, reason = worker_verdict(name, enabled)
            statuses.append(status)
            if status != "PASS":
                reasons.append(reason)
        for reason in extra_reasons or []:
            statuses.append("WARN")
            reasons.append(reason)
        if not statuses or all(status == "SKIP" for status in statuses):
            return {"status": "SKIP", "reasons": reasons[:6] or ["Skipped by active test profile."]}
        worst = max(statuses, key=status_order)
        if worst == "PASS":
            reasons = ["Nominal."]
        return {"status": worst, "reasons": reasons[:6]}

    sensors = category(
        [
            ("GPS", config.ENABLE_GPS),
            ("IMU", config.ENABLE_IMU),
            ("Barometer", config.ENABLE_BAROMETER),
        ]
    )
    payload_reasons = []
    if config.ENABLE_CAMERA:
        if snap.images_missing:
            payload_reasons.append(f"{snap.images_missing} referenced image(s) missing from storage.")
        if snap.camera_failed_captures:
            payload_reasons.append(f"{snap.camera_failed_captures} camera capture failure(s).")
        if snap.camera_dropped_captures:
            payload_reasons.append(f"{snap.camera_dropped_captures} dropped camera frame(s).")
        if snap.image_quality_status in ("LOW_SHARPNESS", "BAD_EXPOSURE", "UNAVAILABLE"):
            payload_reasons.append(f"Image quality {snap.image_quality_status}.")
    payload = category(
        [
            ("Camera", config.ENABLE_CAMERA),
            ("Gimbal", config.ENABLE_GIMBAL),
            ("ImageQuality", config.ENABLE_CAMERA),
            ("Storage", config.ENABLE_CAMERA),
        ],
        payload_reasons,
    )
    logging_reasons = []
    if data_logging_enabled:
        if snap.logger_errors:
            logging_reasons.append(f"{snap.logger_errors} logger error(s).")
        if snap.logger_rows_written == 0 and snap.mission_time > 2.0:
            logging_reasons.append("Logger has not written rows yet.")
    logging_summary = category([("DataLogger", config.ENABLE_LOGGING and data_logging_enabled)], logging_reasons)
    power_reasons = []
    if snap.undervoltage_events:
        power_reasons.append(f"{snap.undervoltage_events} undervoltage event(s).")
    power = category([("Power", True)], power_reasons)
    telemetry_reasons = []
    telemetry = workers.get("Telemetry")
    if config.ENABLE_TELEMETRY and telemetry and telemetry.get("status") not in ("DISABLED", "ERROR", "STALE", "FAILED") and snap.telemetry_tx_count == 0 and snap.mission_time > 2.0:
        telemetry_reasons.append("Telemetry worker has not transmitted yet.")
    telemetry_summary = category([("Telemetry", config.ENABLE_TELEMETRY)], telemetry_reasons)
    navigation_summary = category([("Navigation", config.ENABLE_NAVIGATION_ESTIMATOR)])
    system_summary = category([("System", True)])
    state_reasons = []
    blocked = [event for event in events if event.get("event_type") == "STATE_TRANSITION_BLOCKED"]
    if blocked:
        state_reasons.append(f"{len(blocked)} blocked state transition(s).")
    if snap.test_mode == "FLIGHT" and any(diagnostics.get("faults", {}).values()):
        state_reasons.append("Fault injection should not be active in flight mode.")
    state_flow = {
        "status": "FAIL" if snap.state == MissionState.ERROR.value else ("WARN" if state_reasons else "PASS"),
        "reasons": state_reasons or [f"Current state {snap.state}; reason {snap.state_transition_reason}."],
    }
    categories = {
        "Sensors": sensors,
        "Payload": payload,
        "Logging": logging_summary,
        "Power": power,
        "Navigation": navigation_summary,
        "Telemetry": telemetry_summary,
        "System": system_summary,
        "StateFlow": state_flow,
    }
    overall = max((item["status"] for item in categories.values()), key=status_order)
    return {"overall": overall, "profile": snap.test_mode, "categories": categories}


def build_report_verification_summary(report: dict[str, Any]) -> dict[str, Any]:
    workers = report.get("workers", {})
    events = report.get("events", [])
    profile_config = report.get("config", {})

    def enabled(key: str) -> bool:
        return bool(profile_config.get(key, getattr(config, key, False)))

    def summarize(items: list[tuple[str, bool]]) -> dict[str, Any]:
        active = False
        status = "PASS"
        reasons: list[str] = []
        for name, is_enabled in items:
            if not is_enabled:
                reasons.append(f"{name} skipped by active test profile.")
                continue
            worker = workers.get(name)
            if not worker:
                status = "WARN" if status == "PASS" else status
                reasons.append(f"{name} did not report.")
                continue
            worker_status = worker.get("status", "INITIALIZING")
            if worker_status == "DISABLED":
                reasons.append(f"{name} skipped: {worker.get('reason') or 'Disabled by config.'}")
                continue
            active = True
            if worker_status in ("ERROR", "STALE", "FAILED"):
                status = "FAIL"
            elif worker_status in ("DEGRADED", "INITIALIZING") and status != "FAIL":
                status = "WARN"
            if worker_status != "HEALTHY":
                reasons.append(f"{name}: {worker.get('reason') or worker_status}")
        if not active and status != "FAIL":
            status = "SKIP"
        return {"status": status, "reasons": reasons or ["Nominal."]}

    state_reasons = []
    blocked = [event for event in events if event.get("event_type") == "STATE_TRANSITION_BLOCKED"]
    if blocked:
        state_reasons.append(f"{len(blocked)} blocked state transition(s).")
    categories = {
        "Sensors": summarize([("GPS", enabled("ENABLE_GPS")), ("IMU", enabled("ENABLE_IMU")), ("Barometer", enabled("ENABLE_BAROMETER"))]),
        "Payload": summarize([("Camera", enabled("ENABLE_CAMERA")), ("Gimbal", enabled("ENABLE_GIMBAL")), ("ImageQuality", enabled("ENABLE_CAMERA")), ("Storage", enabled("ENABLE_CAMERA"))]),
        "Logging": summarize([("DataLogger", enabled("ENABLE_LOGGING"))]),
        "Power": summarize([("Power", True)]),
        "Navigation": summarize([("Navigation", enabled("ENABLE_NAVIGATION_ESTIMATOR"))]),
        "Telemetry": summarize([("Telemetry", enabled("ENABLE_TELEMETRY"))]),
        "System": summarize([("System", True)]),
        "StateFlow": {"status": "WARN" if state_reasons else "PASS", "reasons": state_reasons or ["No blocked transitions recorded."]},
    }
    order = {"FAIL": 3, "WARN": 2, "PASS": 1, "SKIP": 0}
    overall = max((item["status"] for item in categories.values()), key=lambda value: order.get(value, 0))
    return {"overall": overall, "categories": categories}


def dashboard_snapshot(
    shared: SharedData,
    control: DashboardControl,
    data_logger: DataLogger | None,
) -> dict[str, Any]:
    snap = shared.get_snapshot()
    diagnostics = shared.get_diagnostics_snapshot()
    workers = diagnostics["workers"]

    def worker_status(name: str, legacy_ok: bool) -> dict[str, Any]:
        metric = workers.get(name)
        if metric:
            return metric
        return {
            "name": name,
            "status": "HEALTHY" if legacy_ok else "INITIALIZING",
            "reason": "Legacy status flag only.",
            "actual_hz": 0.0,
            "expected_hz": 0.0,
            "data_age_ms": None,
            "error_count": 0,
            "consecutive_errors": 0,
            "details": {},
        }

    accel_norm = (snap.raw_accel_x**2 + snap.raw_accel_y**2 + snap.raw_accel_z**2) ** 0.5
    accel_g = accel_norm / 9.80665 if accel_norm > 0 else 1.0
    detector = {
        "launch": {
            "accel_g": accel_g,
            "accel_threshold_g": config.LAUNCH_DETECT_ACCEL_G,
            "altitude_agl_m": snap.baro_altitude,
            "altitude_threshold_m": config.LAUNCH_DETECT_ALTITUDE_AGL_M,
            "pass": accel_g > config.LAUNCH_DETECT_ACCEL_G or snap.baro_altitude > config.LAUNCH_DETECT_ALTITUDE_AGL_M,
        },
        "apogee": {
            "vertical_velocity_mps": snap.vertical_velocity,
            "velocity_threshold_mps": config.APOGEE_DESCENT_VELOCITY_MPS,
            "max_altitude_m": snap.max_altitude,
            "altitude_drop_m": snap.max_altitude - snap.baro_altitude,
            "required_drop_m": config.APOGEE_ALTITUDE_DROP_M,
            "pass": snap.vertical_velocity < config.APOGEE_DESCENT_VELOCITY_MPS and snap.max_altitude - snap.baro_altitude > config.APOGEE_ALTITUDE_DROP_M,
        },
        "glider_deploy": {
            "altitude_agl_m": snap.baro_altitude,
            "threshold_m": config.GLIDER_DEPLOY_ALTITUDE_AGL_M,
            "vertical_velocity_mps": snap.vertical_velocity,
            "pass": snap.baro_altitude <= config.GLIDER_DEPLOY_ALTITUDE_AGL_M and snap.vertical_velocity < 0.0,
        },
        "landing": {
            "altitude_agl_m": snap.baro_altitude,
            "altitude_threshold_m": config.LANDING_DETECT_ALTITUDE_AGL_M,
            "vertical_velocity_mps": snap.vertical_velocity,
            "velocity_threshold_mps": config.LANDING_DETECT_VELOCITY_MPS,
            "accel_g": accel_g,
            "persistence_sec": config.LANDING_DETECT_TIME_SEC,
            "pass": snap.baro_altitude < config.LANDING_DETECT_ALTITUDE_AGL_M and abs(snap.vertical_velocity) < config.LANDING_DETECT_VELOCITY_MPS and 0.8 <= accel_g <= 1.2,
        },
    }
    verification = build_verification_summary(snap, diagnostics, bool(data_logger))

    return {
        "states": [state.value for state in MissionState],
        "mock": config.USE_MOCK_HARDWARE,
        "mode": snap.test_mode,
        "test_profile": snap.test_mode,
        "manual_state_allowed": control.can_mutate_state(),
        "auto_transitions": control.is_auto(),
        "state": snap.state,
        "mission_time": snap.mission_time,
        "latitude": snap.latitude,
        "longitude": snap.longitude,
        "gps_altitude": snap.gps_altitude,
        "baro_altitude": snap.baro_altitude,
        "baro": {
            "agl_m": snap.baro_altitude,
            "raw_agl_m": getattr(snap, "raw_baro_altitude_m", snap.baro_altitude),
            "filtered_agl_m": snap.baro_altitude,
            "pressure_hpa": snap.raw_baro_pressure_hpa,
            "temperature_c": snap.raw_baro_temperature_c,
        },
        "vertical_velocity": snap.vertical_velocity,
        "max_altitude": snap.max_altitude,
        "roll": snap.ahrs_roll if snap.ahrs_healthy else snap.roll,
        "pitch": snap.ahrs_pitch if snap.ahrs_healthy else snap.pitch,
        "yaw": snap.ahrs_yaw if snap.ahrs_healthy else snap.yaw,
        "image_name": snap.image_name,
        "image_url": image_url_for(snap),
        "log_path": str(data_logger.path) if data_logger else "",
        "previous_state": snap.previous_state,
        "state_entry_mission_time": snap.state_entry_mission_time,
        "time_in_state": max(0.0, snap.mission_time - snap.state_entry_mission_time),
        "transition_reason": snap.state_transition_reason,
        "health": {
            "gps": worker_status("GPS", snap.gps_ok),
            "imu": worker_status("IMU", snap.imu_ok),
            "barometer": worker_status("Barometer", snap.barometer_ok),
            "camera": worker_status("Camera", snap.camera_ok),
            "gimbal": worker_status("Gimbal", snap.gimbal_ok),
            "navigation": worker_status("Navigation", snap.navigation_valid),
            "telemetry": worker_status("Telemetry", snap.telemetry_ok),
            "logging": worker_status("DataLogger", bool(data_logger)),
            "system": worker_status("System", True),
        },
        "raw": {
            "gyro": [snap.raw_gyro_x, snap.raw_gyro_y, snap.raw_gyro_z],
            "accel": [snap.raw_accel_x, snap.raw_accel_y, snap.raw_accel_z],
            "mag": [snap.raw_mag_x, snap.raw_mag_y, snap.raw_mag_z],
        },
        "gps": {
            "fix": snap.gps_ok,
            "fix_type": snap.gps_fix_type,
            "satellites": snap.gps_satellites,
            "hdop": snap.gps_hdop,
            "speed_mps": snap.gps_ground_speed_mps,
            "course_deg": snap.gps_course_deg,
            "timestamp_ns": snap.gps_timestamp_ns,
        },
        "navigation": {
            "mode": snap.navigation_mode,
            "position_quality": snap.position_quality,
            "heading_quality": snap.heading_quality,
            "altitude_quality": snap.altitude_quality,
            "position_source": snap.position_source,
            "latitude": snap.estimated_latitude,
            "longitude": snap.estimated_longitude,
            "north_m": snap.estimated_north_m,
            "east_m": snap.estimated_east_m,
            "altitude_m": snap.estimated_altitude_m,
            "agl_m": snap.estimated_agl_m,
            "vn_mps": snap.estimated_velocity_north_mps,
            "ve_mps": snap.estimated_velocity_east_mps,
            "ground_speed_mps": snap.estimated_ground_speed_mps,
            "course_deg": snap.estimated_course_deg,
            "heading_deg": snap.estimated_heading_deg,
            "gps_valid": snap.nav_gps_valid,
            "gps_rejected": snap.nav_gps_rejected,
            "gps_rejection_reason": snap.nav_gps_rejection_reason,
            "gps_age_ms": snap.nav_gps_age_ms,
            "gps_position_error_m": snap.nav_gps_position_error_m,
            "dead_reckoning_active": snap.dead_reckoning_active,
            "dead_reckoning_age_s": snap.dead_reckoning_age_s,
            "recovery_active": snap.recovery_active,
            "navigation_valid": snap.navigation_valid,
            "safe_for_guidance": snap.safe_for_guidance,
        },
        "gimbal": {
            "x": snap.gimbal_x_deflection_deg,
            "y": snap.gimbal_y_deflection_deg,
            "stepper": snap.gimbal_stepper_angle_deg,
            "servo": snap.gimbal_servo_angle_deg,
            "steps": snap.gimbal_stepper_steps,
        },
        "camera": {
            "sequence": snap.camera_capture_sequence,
            "total": snap.camera_total_captures,
            "successful": snap.camera_successful_captures,
            "failed": snap.camera_failed_captures,
            "dropped": snap.camera_dropped_captures,
            "file_size_bytes": snap.camera_last_file_size_bytes,
            "write_latency_ms": snap.camera_last_write_latency_ms,
            "sync_imu_delta_ms": snap.image_sync_imu_delta_ms,
            "sync_gps_delta_ms": snap.image_sync_gps_delta_ms,
            "sync_baro_delta_ms": snap.image_sync_baro_delta_ms,
            "quality_sharpness": snap.image_quality_sharpness,
            "quality_brightness": snap.image_quality_brightness,
            "quality_underexposed_fraction": snap.image_quality_underexposed_fraction,
            "quality_overexposed_fraction": snap.image_quality_overexposed_fraction,
            "quality_status": snap.image_quality_status,
        },
        "logger": {
            "rows_written": snap.logger_rows_written,
            "errors": snap.logger_errors,
            "last_write_timestamp": snap.logger_last_write_timestamp,
        },
        "storage": {
            "images_referenced": snap.images_referenced,
            "images_present": snap.images_present,
            "images_missing": snap.images_missing,
            "images_orphan": snap.images_orphan,
        },
        "power": {
            "bus_voltage_v": snap.bus_voltage_v,
            "current_a": snap.current_a,
            "power_w": snap.power_w,
            "min_voltage_v": snap.min_voltage_v,
            "max_current_a": snap.max_current_a,
            "undervoltage_events": snap.undervoltage_events,
        },
        "detectors": detector,
        "verification": verification,
        "diagnostics": diagnostics,
        "events": {
            "launch_detected": snap.launch_detected,
            "apogee_detected": snap.apogee_detected,
            "payload_ejected": snap.payload_ejected,
            "glider_deployed": snap.glider_deployed,
            "actuation_enabled": snap.actuation_enabled,
        },
        "telemetry": build_telemetry_packet(snap),
        "telemetry_sequence": snap.telemetry_sequence,
        "telemetry_tx_count": snap.telemetry_tx_count,
    }


def parse_json_body(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get("Content-Length", "0") or 0)
    if length <= 0:
        return {}
    return json.loads(handler.rfile.read(length).decode("utf-8"))


def config_snapshot() -> dict[str, Any]:
    keys = [
        "USE_MOCK_HARDWARE",
        "IMAGE_CAPTURE_INTERVAL_SEC",
        "SENSOR_LOG_INTERVAL_SEC",
        "TELEMETRY_INTERVAL_SEC",
        "GPS_EXPECTED_HZ",
        "IMU_EXPECTED_HZ",
        "BAROMETER_EXPECTED_HZ",
        "CAMERA_EXPECTED_HZ",
        "GIMBAL_EXPECTED_HZ",
        "TELEMETRY_EXPECTED_HZ",
        "LOGGER_EXPECTED_HZ",
        "GPS_HDOP_DEGRADED",
        "ENABLE_NAVIGATION_ESTIMATOR",
        "NAVIGATION_RATE_HZ",
        "NAV_MIN_SATELLITES",
        "NAV_MAX_HDOP",
        "NAV_MAX_GPS_AGE_MS",
        "NAV_MAX_PLAUSIBLE_SPEED_MPS",
        "NAV_MAX_ABSOLUTE_GPS_JUMP_M",
        "NAV_DEAD_RECKON_MAX_SEC",
        "NAV_GPS_GOOD_COUNT_TO_RECOVER",
        "IMAGE_SYNC_WARN_MS",
        "POWER_UNDERVOLTAGE_WARN_V",
    ]
    return {key: getattr(config, key, None) for key in keys}


def write_test_report(report: dict[str, Any]) -> dict[str, str]:
    report.setdefault("verification", build_report_verification_summary(report))
    report_dir = config.LOG_SAVE_PATH / "test_reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    test_id = report.get("test_id") or datetime.utcnow().strftime("garuda-test-%Y%m%d-%H%M%S")
    json_path = report_dir / f"{test_id}.json"
    csv_path = report_dir / f"{test_id}_events.csv"
    html_path = report_dir / f"{test_id}.html"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["mission_time", "severity", "source", "event_type", "message"])
        writer.writeheader()
        for event in report.get("events", []):
            writer.writerow({key: event.get(key, "") for key in writer.fieldnames})
    rows = []
    for name, worker in report.get("workers", {}).items():
        rows.append(
            f"<tr><td>{name}</td><td>{worker.get('status')}</td><td>{worker.get('actual_hz'):.2f}</td>"
            f"<td>{worker.get('expected_hz'):.2f}</td><td>{worker.get('error_count')}</td><td>{worker.get('reason')}</td></tr>"
        )
    summary_rows = []
    for name, item in report.get("verification", {}).get("categories", {}).items():
        summary_rows.append(
            f"<tr><td>{name}</td><td>{item.get('status')}</td><td>{'; '.join(item.get('reasons', []))}</td></tr>"
        )
    html_path.write_text(
        "<!doctype html><meta charset='utf-8'><title>GARUDA Test Report</title>"
        "<style>body{font-family:Segoe UI,Arial;background:#111827;color:#e5e7eb;padding:20px}"
        "table{border-collapse:collapse;width:100%}td,th{border:1px solid #374151;padding:6px;text-align:left}</style>"
        f"<h1>{test_id}</h1><p>Mode: {report.get('mode')} | Samples: {report.get('sample_count')} | Overall: {report.get('verification', {}).get('overall')}</p>"
        "<h2>Verification Summary</h2><table><tr><th>Category</th><th>Status</th><th>Reasons</th></tr>"
        + "".join(summary_rows)
        + "</table><h2>Worker Summary</h2><table><tr><th>Worker</th><th>Status</th><th>Actual Hz</th><th>Expected Hz</th><th>Errors</th><th>Reason</th></tr>"
        + "".join(rows)
        + "</table><h2>Min/Max</h2><pre>"
        + json.dumps(report.get("minmax", {}), indent=2)
        + "</pre><h2>Events</h2><pre>"
        + json.dumps(report.get("events", []), indent=2)
        + "</pre>",
        encoding="utf-8",
    )
    return {"json": str(json_path), "csv": str(csv_path), "html": str(html_path)}


def make_handler(shared: SharedData, control: DashboardControl, data_logger: DataLogger | None):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:
            return

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/":
                self.send_bytes(HTML.encode("utf-8"), "text/html; charset=utf-8")
            elif parsed.path == "/api/state":
                data = dashboard_snapshot(shared, control, data_logger)
                self.send_bytes(json.dumps(data).encode("utf-8"), "application/json")
            elif parsed.path == "/frame":
                self.send_frame(parsed)
            else:
                self.send_error(HTTPStatus.NOT_FOUND)

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            try:
                body = parse_json_body(self)
                if parsed.path == "/api/state":
                    if not control.can_mutate_state():
                        self.send_json({"ok": False, "error": "Manual state control disabled in this mode."}, HTTPStatus.FORBIDDEN)
                        return
                    force_state(shared, MissionState(str(body["state"]).upper()))
                    self.send_json({"ok": True})
                elif parsed.path == "/api/next":
                    if not control.can_mutate_state():
                        self.send_json({"ok": False, "error": "Manual state control disabled in this mode."}, HTTPStatus.FORBIDDEN)
                        return
                    current = MissionState(shared.get_snapshot().state)
                    target = next_state(current)
                    if target is None:
                        self.send_json({"ok": False, "error": f"No next state after {current.value}"}, HTTPStatus.BAD_REQUEST)
                    else:
                        force_state(shared, target)
                        self.send_json({"ok": True})
                elif parsed.path == "/api/auto":
                    control.set_auto(bool(body.get("enabled")))
                    self.send_json({"ok": True, "auto_transitions": control.is_auto()})
                elif parsed.path == "/api/fault":
                    if not config.USE_MOCK_HARDWARE:
                        self.send_json({"ok": False, "error": "Fault injection is only enabled in mock mode."}, HTTPStatus.FORBIDDEN)
                        return
                    shared.set_fault(str(body["name"]), bool(body.get("enabled")))
                    self.send_json({"ok": True, "faults": shared.get_faults()})
                elif parsed.path == "/api/test/start":
                    test_id = shared.start_test_session(shared.get_snapshot().test_mode, config_snapshot())
                    self.send_json({"ok": True, "test_id": test_id})
                elif parsed.path == "/api/test/stop":
                    report = shared.stop_test_session()
                    if report.get("test_id"):
                        report["verification"] = build_report_verification_summary(report)
                    paths = write_test_report(report) if report.get("test_id") else {}
                    self.send_json({"ok": True, "report_paths": paths, "report": report})
                elif parsed.path == "/api/test/reset":
                    shared.reset_test_session()
                    self.send_json({"ok": True})
                else:
                    self.send_error(HTTPStatus.NOT_FOUND)
            except Exception as exc:
                self.send_json({"ok": False, "error": str(exc)}, HTTPStatus.BAD_REQUEST)

        def send_frame(self, parsed) -> None:
            query = parse_qs(parsed.query)
            name = Path(query.get("name", [""])[0]).name
            image_path = config.IMAGE_SAVE_PATH / name
            if not name or not image_path.exists():
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            content_type = mimetypes.guess_type(str(image_path))[0] or "image/jpeg"
            self.send_bytes(image_path.read_bytes(), content_type)

        def send_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
            self.send_bytes(json.dumps(payload).encode("utf-8"), "application/json", status)

        def send_bytes(
            self,
            data: bytes,
            content_type: str,
            status: HTTPStatus = HTTPStatus.OK,
        ) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

    return Handler


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Temporary GARUDA browser ground station.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--mock", action="store_true", help="Use mock hardware for a dry run.")
    parser.add_argument("--real-hardware", action="store_true", help="Force real hardware mode.")
    parser.add_argument("--bench", action="store_true", help="Real-hardware engineering bench mode; enables manual state controls.")
    parser.add_argument("--allow-manual-state", action="store_true", help="Allow browser state mutation outside mock mode.")
    parser.add_argument("--auto-transitions", action="store_true", help="Start with live sensor-driven transitions enabled.")
    parser.add_argument("--duration", type=float, default=0.0, help="Optional run duration in seconds; 0 runs until Ctrl+C.")
    for name in ("gps", "imu", "barometer", "camera", "gimbal", "telemetry", "logging", "navigation_estimator"):
        flag = name.replace("_", "-")
        parser.add_argument(f"--enable-{flag}", action="store_true")
        parser.add_argument(f"--disable-{flag}", action="store_true")
    return parser


def apply_overrides(args: argparse.Namespace) -> None:
    if args.mock and (args.real_hardware or args.bench):
        raise SystemExit("--mock cannot be combined with --real-hardware or --bench.")
    if args.mock:
        config.USE_MOCK_HARDWARE = True
    if args.real_hardware or args.bench:
        config.USE_MOCK_HARDWARE = False
    config.PAUSE_STATE_TRANSITIONS = True
    for name in ("gps", "imu", "barometer", "camera", "gimbal", "telemetry", "logging", "navigation_estimator"):
        enable = getattr(args, f"enable_{name}")
        disable = getattr(args, f"disable_{name}")
        if enable and disable:
            flag = name.replace("_", "-")
            raise SystemExit(f"--enable-{flag} and --disable-{flag} cannot be used together.")
        if enable or disable:
            setattr(config, f"ENABLE_{name.upper()}", enable)


def create_server(host: str, port: int, handler) -> ThreadingHTTPServer:
    """Bind the dashboard server, falling back when a local test port is blocked."""
    try:
        return ThreadingHTTPServer((host, port), handler)
    except PermissionError:
        if port != 8080:
            raise
        logger.warning("Port 8080 is blocked by the OS; trying an available fallback port.")
    except OSError as exc:
        if port != 8080:
            raise
        logger.warning("Port 8080 is unavailable (%s); trying an available fallback port.", exc)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind((host, 0))
        fallback_port = int(probe.getsockname()[1])
    return ThreadingHTTPServer((host, fallback_port), handler)


def main() -> int:
    args = build_parser().parse_args()
    apply_overrides(args)
    setup_logging()
    ensure_directories()

    shared = SharedData()
    shared.start_mission_clock()
    mode = "MOCK" if config.USE_MOCK_HARDWARE else "BENCH" if args.bench else "FLIGHT"
    shared.update(test_mode=mode)
    manual_allowed = config.USE_MOCK_HARDWARE or args.bench or args.allow_manual_state
    force_state(shared, MissionState.DISARMED)
    control = DashboardControl(
        auto_transitions=args.auto_transitions,
        manual_state_allowed=manual_allowed,
    )
    stop_event = threading.Event()
    thread_mgr = ThreadManager()
    data_logger = DataLogger(shared, filename="ground_station_test.csv") if config.ENABLE_LOGGING else None
    server = create_server(args.host, args.port, make_handler(shared, control, data_logger))
    server.timeout = 0.5

    if data_logger:
        data_logger.open()

    start_workers(shared, thread_mgr, data_logger)
    auto_thread = threading.Thread(
        target=auto_transition_loop,
        args=(shared, control, stop_event),
        name="DashboardAutoTransitions",
        daemon=True,
    )
    auto_thread.start()
    recording_thread = threading.Thread(
        target=test_recording_loop,
        args=(shared, stop_event),
        name="DashboardTestRecording",
        daemon=True,
    )
    recording_thread.start()

    shown_host = "localhost" if args.host in {"0.0.0.0", "127.0.0.1"} else args.host
    shown_port = int(server.server_address[1])
    logger.info("GARUDA ground station running at http://%s:%d", shown_host, shown_port)
    logger.info("Use Ctrl+C to stop and close the test log cleanly.")
    deadline = None if args.duration <= 0 else time.monotonic() + args.duration
    try:
        while deadline is None or time.monotonic() < deadline:
            server.handle_request()
    except KeyboardInterrupt:
        logger.info("Stopping ground station.")
    finally:
        stop_event.set()
        server.server_close()
        thread_mgr.stop_all()
        if data_logger:
            data_logger.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
