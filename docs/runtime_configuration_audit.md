# GARUDA Runtime Configuration Audit

Date: 2026-09-01

## Authoritative Runtime

The active onboard entry point is `main.py`. It starts enabled workers, shares
live data through `core.shared_data.SharedData`, and uses
`core.flight_state_machine.FlightStateController` when automatic transitions
are enabled.

The authoritative mission states are defined in `core/mission_state.py`:

```text
BOOT
DISARMED
IDLE
ARMED_PAD
BOOST
COAST
APOGEE
DESCENT
DESCENT_DROGUE
GLIDER_DEPLOY
GUIDED_DESCENT
LANDED
ABORT
ERROR
```

`FlightStateController` is the current authoritative sensor-driven state
machine. Older documents and tests that describe only `BOOT -> IDLE ->
DESCENT -> LANDED` are stale or simplified simulation references.

## Configured Hardware Interfaces

Current `config.py` settings describe this implementation:

| Subsystem | Current interface |
| --- | --- |
| BNO085 IMU/AHRS | I2C1, address `0x4A` |
| BMP388 barometer | SPI0, chip select GPIO8 |
| NEO-M8N GPS | SC16IS750 UART bridge on SPI0 CE1/GPIO7 |
| PCA9685 servo controller | I2C1, address `0x40`, OE GPIO4 |
| Gimbal stepper | ULN2003 on GPIO25/GPIO24/GPIO23/GPIO18 |
| XBee telemetry | `/dev/ttyAMA0`, 9600 baud |
| Camera | `AUTO`, Picamera2 first, OpenCV fallback |

## Ground Station State Authority

The browser ground station now reads `SharedData.state` and state history from
`SharedData.get_diagnostics_snapshot()`. Manual dashboard state changes use
`SharedData.transition_state()` so the runtime state, previous state,
transition reason, event log, telemetry packet, and dashboard selector all come
from one source.

Manual state mutation is enabled in mock mode and explicit bench mode. It is
disabled by default in real flight mode.

## Stale Or Inconsistent References Found

| Area | Finding | Suggested cleanup |
| --- | --- | --- |
| Mission states | Some docs/tests still reference only `BOOT`, `IDLE`, `DESCENT`, `LANDED`. | Update after final flight-state acceptance. |
| Telemetry naming | Runtime and primary docs now use XBee naming. | Keep future ground receiver docs consistent with XBee unless hardware changes. |
| Dashboard maturity | Integrated ground station now includes worker diagnostics, plots, event markers, fault injection, reports, and verification summaries. | Continue only with field-specific polish after bench use. |
| GPS quality | NMEA parser exposes GGA/RMC basics; many advanced metrics depend on receiver sentences not yet parsed. | Add GSA/GSV/VTG parsing if needed. |
| Power monitoring | Power worker exists with mock values and optional INA219 adapter. | Confirm INA219 address, library, and wiring on hardware. |
| Pi health | `vcgencmd` throttling is Raspberry Pi specific and unavailable on Windows. | Keep graceful fallback. |

## Notes

No post-flight photogrammetry code was wired into the live dashboard. SIFT,
SfM, bundle adjustment, dense MVS, DSM, and orthomosaic generation remain
offline under `processing/`, `vision/`, and `mapping/`.

## Engineering Console Additions

The ground station now exposes:

- SharedData-backed worker timing, age, errors, recovery counts, and reasons.
- Debounced mission events.
- State transition history with source and reason.
- Mock-only fault injection flags.
- Test recording sessions with JSON reports.
- Event CSV and HTML test summary export.
- PASS/WARN/FAIL verification summaries for sensors, payload, logging, power,
  telemetry, system health, and state flow.
- Lightweight live image-quality diagnostics for the latest stored frame.
- Log/image storage validation for missing or orphan image files.
- Detector condition readouts for launch, apogee, glider deploy, and landing.
- Event markers on dashboard plots.
- Power metrics from INA219 when available, or mock synthetic power values in
  mock mode.
- Raspberry Pi/system metrics where supported, with graceful unavailable
  values on development machines.

## Unsupported Or Partial Metrics

| Metric | Current status |
| --- | --- |
| INA219 real power | Worker exists, but real support depends on `adafruit_ina219` and confirmed non-conflicting address/wiring. |
| RSSI/SNR | Not reported because the XBee sender does not expose those values. |
| Bidirectional packet loss | TX sequence exists; RX-side ground radio ingestion is not implemented. |
| Full GPS constellation | GGA/RMC basics are parsed; GSA/GSV satellite detail is not implemented. |
| Live image quality | Lightweight latest-frame sharpness/exposure checks are implemented; full photogrammetry quality analysis remains offline. |
| Full report styling | JSON, event CSV, compact HTML, and verification summary exist; richer printable report styling is pending. |
