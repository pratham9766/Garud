# GARUDA TARSR Ground Mapping Payload

Onboard and post-flight software for the GARUDA CanSat terrain and ground
mapping payload. The payload runs on a Raspberry Pi 5, collects synchronized
GPS, barometer, AHRS/IMU, camera, gimbal, and telemetry data during descent, logs the
mission to CSV, and processes recovered mission data after flight.

The project now defaults to real hardware mode for Raspberry Pi payload tests.
Simulation helpers remain for CI and desktop development, but operator bring-up
commands read the connected sensors directly.

## Project Status

Real hardware adapters are wired for the tested Garud HAT reference
configuration. Run the hardware checks and live dashboards on the Raspberry Pi
before mission use so BNO085, BMP388, GPS, camera, telemetry, and gimbal status
are visible with live readings.

Post-flight terrain reconstruction has a tested V2 path for external aerial
datasets such as the Wietrznia OpenDroneMap DJI image set. The V2 path now
executes GARUDA quality filtering, graph-based matching, multi-view track
diagnostics, PyCOLMAP sparse SfM, and global bundle adjustment. Dense COLMAP
PatchMatch is wired as a post-flight-only backend, but it requires CUDA; on the
current Windows test machine dense MVS failed at that CUDA requirement, so DSM
and true terrain orthorectification were skipped honestly.

## Features

- Real BNO085, BMP388, GPS, camera, telemetry, and PCA9685 gimbal hardware paths.
- Terminal test mode and browser ground station for manual state, sensor,
  payload, telemetry, logging, and gimbal verification.
- Threaded mission runtime with shared payload state.
- CSV mission logging with image timestamps, angular velocity, raw IMU, and AHRS metadata.
- AHRS-assisted pose priors for post-flight image normalization.
- Post-flight image quality scoring for blur, exposure, tilt, and motion.
- Graph-based image relationship candidates for non-sequential matching.
- Dataset-mode post-flight runner for DJI aerial image folders.
- PyCOLMAP sparse SfM import from GARUDA verified features and matches.
- Bundle-adjusted camera pose export and sparse reconstruction diagnostics.
- Optional COLMAP dense MVS adapter isolated from flight runtime.
- DSM rasterization from dense PLY point clouds when dense MVS succeeds.
- Interactive Folium HTML map export.
- Google Earth compatible KML export.
- Estimated camera ground footprints and unique coverage area.
- Garud HAT hardware adapters for BNO085 on I2C1, BMP388 on SPI0 CS GPIO8, GPS-over-SC16IS750, XBee, and PCA9685 gimbal control.
- Standalone hardware bring-up scripts for Raspberry Pi testing.

## Tech Stack

- Python 3.9+
- Raspberry Pi target platform
- Folium for interactive HTML maps
- SimpleKML for Google Earth exports
- Pillow/OpenCV for image handling
- Adafruit CircuitPython libraries for supported hardware modules

## Mapping Scope

The mapping stack is split into flight-safe capture/logging code and expensive
post-flight reconstruction code. Flight runtime still records images and
metadata only. Heavy work stays under `processing/`, `mapping/`, `vision/`,
`sensor_fusion/`, and `storage/`.

The current V2 post-flight pipeline can run on a folder of DJI images:

```text
image dataset
-> quality scoring
-> temporal/GPS candidate graph
-> SIFT feature extraction and cache
-> FLANN/BF matching
-> Essential/Fundamental/Homography verification
-> multi-view track diagnostics
-> PyCOLMAP database import
-> incremental sparse SfM
-> global bundle adjustment
-> camera pose and sparse model export
-> optional dense PatchMatch and DSM if CUDA is available
```

The preview JPEGs are diagnostic products. A true orthomosaic is only claimed
when dense MVS, DSM generation, and terrain-based orthorectification complete.
On the latest Wietrznia test, sparse SfM succeeded and dense MVS was blocked by
missing CUDA.

## Repository Layout

```text
ground_mapping_payload/
|-- camera/             Camera factory and camera implementations
|-- core/               Shared state, mission states, thread manager, health
|-- data/               Runtime output folders for logs, images, and maps
|-- docs/               Wiring, pin map, checklist, and user manual
|-- gimbal/             Gimbal stabilizer and servo control
|-- hardware_tests/     Real hardware bring-up scripts
|-- logging_system/     CSV logger
|-- mapping/            Fake flight data, HTML map, KML, geotag helpers
|-- processing/         Offline mission validation and preprocessing
|-- sensor_fusion/      AHRS estimators, quaternion helpers, and pose priors
|-- storage/            Mission manifest and metadata records
|-- sensors/            GPS, IMU, and barometer interfaces
|-- telemetry/          XBee telemetry packet generation/sending
|-- vision/             Undistortion, pose normalization, features, matching
|-- tests/              Simulation and module tests
|-- config.py           Runtime configuration
|-- main.py             Main mission entry point
|-- requirements.txt    Python dependencies
`-- README.md
```

## Hardware Target

- Python 3.9 or newer
- Raspberry Pi 5 target for hardware mode
- Garud HAT with BNO085 IMU on I2C1, BMP388 barometer on SPI0 CS GPIO8, NEO-M8N GPS through SC16IS750, PCA9685 gimbal, XBee telemetry, and camera

Python packages are listed in `requirements.txt`.

## Quick Start

Clone the repository:

```bash
git clone https://github.com/TARSR/GARUD.git
cd GARUD
```

Create a virtual environment:

```bash
python -m venv venv
```

Windows:

```bash
venv\Scripts\activate
pip install -r requirements.txt
```

Linux / Raspberry Pi:

```bash
source venv/bin/activate
pip install -r requirements.txt
```

Run the full simulated mission:

```bash
python tests/test_full_simulation.py
```

Run the main payload program:

```bash
python main.py
```

Press `Ctrl+C` to stop the main program cleanly. When logging and mapping are
enabled, the program generates output maps during shutdown.

Run operator-controlled ground test mode:

```bash
python main.py --test-mode --real-hardware
python main.py --test-mode --mock
```

Run the temporary browser ground station only when needed:

```bash
python hardware_tests/ground_station_dashboard.py --bench --real-hardware --host 0.0.0.0
python hardware_tests/ground_station_dashboard.py --mock
```

## Testing

Generate a fake flight log and maps:

```bash
python tests/test_fake_mapping.py
```

Run the main simulation/module checks:

```bash
python tests/test_gps.py
python tests/test_imu.py
python tests/test_barometer.py
python tests/test_camera.py
python tests/test_telemetry.py
python tests/test_ahrs.py
```

Run all pytest-style tests if `pytest` is installed:

```bash
python -m pytest tests
```

Run hardware checks on Raspberry Pi:

```bash
python hardware_tests/test_i2c_scan.py
python hardware_tests/test_camera_real.py
python hardware_tests/test_gps_real.py
python hardware_tests/test_barometer_real.py
python hardware_tests/test_imu_real.py
python hardware_tests/test_ahrs_real.py --mode bno085
python hardware_tests/live_sensor_dashboard.py --mode bno085
python hardware_tests/web_sensor_dashboard.py --mode bno085 --host 0.0.0.0
python hardware_tests/ground_station_dashboard.py --bench --real-hardware --host 0.0.0.0
python hardware_tests/test_servo_real.py
python hardware_tests/test_gimbal_real.py
python hardware_tests/test_xbee_real.py
python hardware_tests/test_all_sensors_status.py
```

## Generated Outputs

| Path | Description |
| --- | --- |
| `data/images/` | Captured payload images |
| `data/logs/` | Mission CSV logs |
| `data/maps/flight_path.html` | Interactive flight-path map |
| `data/maps/flight_path.kml` | Google Earth KML export |
| `data/logs/hardware_tests/` | Hardware test logs |
| `data/logs/test_reports/` | Ground-station JSON, event CSV, and HTML verification reports |
| `mapping_output/terrain_mapping_test_v2/` | Checked-in Wietrznia V2 result images and diagnostics |

Runtime output folders are kept in the repository with `.gitkeep` files, while
generated logs, images, and maps are ignored by Git.

## Post-Flight Dataset Reconstruction

Install normal flight/runtime dependencies first:

```bash
pip install -r requirements.txt
```

Install heavy post-flight dependencies only on the development/reconstruction
machine:

```bash
pip install -r requirements-postflight.txt
```

Run a small Wietrznia-style dataset test:

```bash
python -m processing.run_dataset_test ^
    --images "D:\RESOURCES\Terrain dataset\images" ^
    --output "output\terrain_mapping_test_v2\small_25" ^
    --profile fast ^
    --max-images 25 ^
    --neighbors 4 ^
    --feature-max-dim 1024 ^
    --enable-dense ^
    --dense-max-image-size 900
```

Latest checked-in V2 test summary:

```text
Images selected: 25
Good images: 25
Candidate edges: 53
Verified edges: 53
Sparse SfM: SUCCESS
Registered images: 25 / 25
Sparse points: 9,329
Mean reprojection error after BA: 1.163 px
Dense MVS: FAILED - CUDA unavailable
DSM / true orthomosaic: SKIPPED
Overall: PARTIAL
```

Important outputs:

| Path | Description |
| --- | --- |
| `mapping_output/terrain_mapping_test_v2/final/global_pose_preview.jpg` | Sparse reconstruction and camera trajectory preview |
| `mapping_output/terrain_mapping_test_v2/final/before_after_comparison.jpg` | Baseline vs V2 diagnostic comparison |
| `mapping_output/terrain_mapping_test_v2/diagnostics/reconstruction_report.json` | Full run report |
| `mapping_output/terrain_mapping_test_v2/diagnostics/dense_metrics.json` | Dense MVS status and CUDA blocker |
| `mapping_output/terrain_mapping_test_v2/diagnostics/camera_poses.csv` | Bundle-adjusted camera pose export |

## CSV Format

```text
timestamp,mission_time,state,latitude,longitude,gps_altitude,baro_altitude,vertical_velocity,max_altitude,roll,pitch,yaw,gyro_x,gyro_y,gyro_z,image_name,image_timestamp,battery,status,ahrs_enabled,ahrs_source,ahrs_valid,ahrs_healthy,ahrs_confidence,quat_w,quat_x,quat_y,quat_z,ahrs_roll,ahrs_pitch,ahrs_yaw,attitude_accuracy_rad,imu_sample_age_ms,accel_correction_active,mag_correction_active,ahrs_timestamp_ns,raw_gyro_x,raw_gyro_y,raw_gyro_z,raw_accel_x,raw_accel_y,raw_accel_z,raw_mag_x,raw_mag_y,raw_mag_z,raw_quat_w,raw_quat_x,raw_quat_y,raw_quat_z,raw_imu_timestamp_ns,raw_imu_accuracy_rad,raw_imu_calibration_status,raw_baro_pressure_hpa,raw_baro_temperature_c,gimbal_x_deflection_deg,gimbal_y_deflection_deg,gimbal_stepper_angle_deg,gimbal_servo_angle_deg,gimbal_stepper_steps,gimbal_ok,launch_detected,apogee_detected,payload_ejected,glider_deployed,actuation_enabled,previous_state,state_transition_reason,telemetry_sequence,telemetry_tx_count,bus_voltage_v,current_a,power_w,min_voltage_v,max_current_a,undervoltage_events,logger_rows_written,logger_errors,camera_capture_sequence,camera_total_captures,camera_successful_captures,camera_failed_captures,camera_dropped_captures,camera_last_file_size_bytes,camera_last_write_latency_ms,image_sync_imu_delta_ms,image_sync_gps_delta_ms,image_sync_baro_delta_ms,image_quality_sharpness,image_quality_brightness,image_quality_underexposed_fraction,image_quality_overexposed_fraction,image_quality_status,images_referenced,images_present,images_missing,images_orphan
```

## Configuration

Edit `config.py` to enable/disable modules, adjust capture/logging intervals,
and set Garud HAT bus/pin values.

Important settings:

```python
USE_MOCK_HARDWARE = False
ENABLE_CAMERA = True
ENABLE_GPS = True
ENABLE_MAPPING = True
CAMERA_BACKEND = "AUTO"
CAMERA_DEVICE_INDEX = 0
GPS_TRANSPORT = "SC16IS750_SPI"
XBEE_SERIAL_PORT = "/dev/ttyAMA0"
BNO085_TRANSPORT = "I2C"
BNO085_I2C_ADDRESS = 0x4A
BMP388_CS_PIN = 8
GPS_SC16IS750_CS_PIN = 7
PCA9685_I2C_ADDRESS = 0x40
ULN2003_IN1_PIN = 25
ULN2003_IN2_PIN = 24
ULN2003_IN3_PIN = 23
ULN2003_IN4_PIN = 18
ENABLE_AHRS = True
AHRS_MODE = "BNO085"
AHRS_RATE_HZ = 100
```

Keep `USE_MOCK_HARDWARE = False` on the Raspberry Pi for real sensor testing.

Flight state transition settings:

```python
TARGET_APOGEE_AGL_M = 1000.0
GLIDER_DEPLOY_ALTITUDE_AGL_M = 600.0
STATE_CONFIRMATION_COUNT = 5

LAUNCH_DETECT_ACCEL_G = 1.5
LAUNCH_DETECT_ALTITUDE_AGL_M = 30.0

BOOST_BURNOUT_ACCEL_G = 1.5
BOOST_MAX_DURATION_SEC = 10.0

APOGEE_DESCENT_VELOCITY_MPS = -1.0
APOGEE_ALTITUDE_DROP_M = 2.0
APOGEE_MIN_ALTITUDE_AGL_M = 50.0
APOGEE_BACKUP_TIME_SEC = 30.0

GLIDER_DEPLOY_CONFIRMATION_COUNT = 5
GLIDER_DEPLOY_SETTLE_SEC = 1.0

LANDING_DETECT_ALTITUDE_AGL_M = 20.0
LANDING_DETECT_VELOCITY_MPS = 1.0
LANDING_DETECT_TIME_SEC = 5.0

MAX_FLIGHT_TIME_SEC = 600.0
```

State transition summary:

| Transition | Constraint |
| --- | --- |
| `ARMED_PAD -> BOOST` | 3 confirmed readings of acceleration `> 1.5 g` or altitude `> 30.0 m AGL` |
| `BOOST -> COAST` | 5 confirmed readings of acceleration `< 1.5 g`, or boost duration `> 10.0 s` |
| `COAST -> APOGEE` | 5 confirmed readings of descent: velocity `< -1.0 m/s`, altitude drop `> 2.0 m` from max altitude, and altitude `> 50.0 m AGL`; backup after `30.0 s` from launch |
| `APOGEE -> DESCENT_DROGUE` | `1.0 s` settle after apogee/payload ejection |
| `DESCENT_DROGUE -> GLIDER_DEPLOY` | 5 confirmed readings of altitude `<= 600.0 m AGL` while descending |
| `GLIDER_DEPLOY -> GUIDED_DESCENT` | `1.0 s` settle, then `actuation_enabled=True` |
| `GUIDED_DESCENT -> LANDED` | Landing conditions persist for `5.0 s`: altitude `< 20.0 m AGL`, vertical speed `< 1.0 m/s`, acceleration near `1 g` |

See `docs/flight_flow.md` for the full state diagram and abort behavior.

Mapping footprint settings:

```python
CAMERA_HORIZONTAL_FOV_DEG = 62.2
CAMERA_VERTICAL_FOV_DEG = 48.8
MAPPING_COVERAGE_GRID_M = 5.0
```

## Documentation

- `docs/USER_MANUAL.md` - operator manual and workflow
- `docs/architecture_pose_normalization.md` - V1 pose-assisted mapping design
- `docs/postflight_terrain_mapping.md` - V2 dataset reconstruction workflow and current limitations
- `docs/flight_flow.md` - mission state sequence
- `docs/wiring_plan.md` - wiring notes
- `docs/pin_map.md` - Raspberry Pi pin assignments
- `docs/test_checklist.md` - bring-up and field checklist
- `docs/component_status.md` - subsystem readiness status

## Hardware Mode Notes

| File | Class / area |
| --- | --- |
| `bus_manager.py` | Shared I2C1/SPI0 bus initialization |
| `sensors/gps.py` | `RealGPS` using NEO-M8N through SC16IS750 on SPI0 CE1 |
| `sensors/imu.py` | `RealIMU` using BNO085 on I2C1 address `0x4A` |
| `sensors/barometer.py` | `RealBarometer` using BMP388 on SPI0 with `CS_BMP` GPIO8 |
| `camera/mock_camera.py` | `RealCamera` via Picamera2 or OpenCV |
| `telemetry/xbee_sender.py` | `RealTelemetry` using XBee on `/dev/ttyAMA0` |
| `gimbal/servo_control.py` | `RealGimbal` using PCA9685 servo control |

For visual manual bring-up, run:

```bash
python hardware_tests/live_sensor_dashboard.py --mode bno085
```

Use `--duration <seconds>` for a timed run. The dashboard shows GPS,
barometer, raw BNO085 readings, native quaternion,
calculated Euler angles, AHRS source/health, quaternion `(w,x,y,z)`, correction
flags, diagnostics counters, and a telemetry packet preview. It reads sensors
only and does not move servos.

For a browser display with the latest camera frame:

```bash
python hardware_tests/web_sensor_dashboard.py --mode bno085 --host 0.0.0.0
```

Open `http://<raspberry-pi-ip>:8080`. The page refreshes live readings and the
latest captured camera frame.

For integrated state-transition and payload verification:

```bash
python hardware_tests/ground_station_dashboard.py --bench --real-hardware --host 0.0.0.0
```

The ground station is separate from `main.py`, so it opens only when this script
is run. It shows state controls, event-marked graphs, worker health,
PASS/WARN/FAIL verification, mock-only fault injection, and saved test reports
under `data/logs/test_reports/`.

The mapping, logging, telemetry, and post-flight processing pipelines are kept
independent of the hardware adapters. Mock classes remain only for local
development tests and CI-style checks.

## License

Internal project for the GARUDA CanSat / TARSR team.
