# GARUDA Ground Mapping Payload User Manual

This manual explains how to set up, run, test, and operate the GARUDA ground
mapping payload software.

## 1. System Overview

The payload software runs a set of background workers:

- GPS worker updates latitude, longitude, and GPS altitude.
- Barometer worker updates pressure-derived altitude.
- IMU worker preserves raw BNO085 data and publishes final AHRS attitude.
- Camera worker captures images at a fixed interval.
- Gimbal worker stabilizes camera orientation.
- Telemetry worker sends compact payload packets.
- Logger worker writes shared mission state to CSV.
- Health monitor reports subsystem health.

The main thread runs the mission state machine:

```text
BOOT -> IDLE -> DESCENT -> LANDED
```

After shutdown, the CSV log is used to create:

- `data/maps/flight_path.html`
- `data/maps/flight_path.kml`

The mapping output includes the GPS path, image capture markers, estimated
camera footprints, and an approximate unique coverage area.

## 2. Installation

Open a terminal in the project folder:

```bash
cd ground_mapping_payload
```

Create and activate a virtual environment.

Windows:

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Linux / Raspberry Pi:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 3. Configuration

All main runtime settings are in `config.py`.

For hardware mode:

```python
USE_MOCK_HARDWARE = False
GPS_TRANSPORT = "SC16IS750_SPI"
GPS_PORT = "SC16IS750@SPI0.CE1"
XBEE_PORT = "/dev/ttyAMA0"
GPS_BAUDRATE = 9600
XBEE_BAUDRATE = 9600
BNO085_TRANSPORT = "I2C"
BNO085_I2C_ADDRESS = 0x4A
BMP388_CS_PIN = 8
CAMERA_BACKEND = "AUTO"
SERVO_CONTROLLER_ADDRESS = 0x40
```

Module flags can disable subsystems during debugging:

```python
ENABLE_CAMERA = True
ENABLE_GPS = True
ENABLE_IMU = True
ENABLE_BAROMETER = True
ENABLE_GIMBAL = True
ENABLE_TELEMETRY = True
ENABLE_MAPPING = True
ENABLE_LOGGING = True
```

AHRS defaults:

```python
ENABLE_AHRS = True
AHRS_MODE = "BNO085"
AHRS_RATE_HZ = 100
AHRS_USE_MAGNETOMETER = True
AHRS_ACCEL_REJECTION_ENABLED = True
AHRS_MAG_REJECTION_ENABLED = True
AHRS_MAX_SAMPLE_AGE_MS = 250.0
AHRS_FAIL_COUNT_THRESHOLD = 5
AHRS_RECOVERY_COUNT_THRESHOLD = 20
AHRS_MADGWICK_BETA = 0.08
AHRS_MAHONY_KP = 0.6
AHRS_MAHONY_KI = 0.02
```

AHRS modes are `OFF`, `BNO085`, `MADGWICK`, `MAHONY`, and `AUTO`. `BNO085`
uses the sensor's fused rotation-vector quaternion and is the operational
default. `OFF` preserves the legacy raw roll/pitch/yaw path while marking AHRS
invalid.

Camera footprint settings:

```python
CAMERA_HORIZONTAL_FOV_DEG = 62.2
CAMERA_VERTICAL_FOV_DEG = 48.8
MAPPING_MIN_FOOTPRINT_ALTITUDE_M = 2.0
MAPPING_COVERAGE_GRID_M = 5.0
```

Tune field-of-view values after the final camera and lens are selected.

## 4. Simulation Workflow

Simulation tests are retained for desktop development and CI. The payload
runtime and hardware dashboards default to real sensors.

Run a fake mapping test:

```bash
python tests/test_fake_mapping.py
```

Expected result:

- Synthetic CSV log is written under `data/logs/`.
- HTML map is written to `data/maps/flight_path.html`.
- KML file is written to `data/maps/flight_path.kml`.
- Image footprint polygons and coverage estimates are included in the outputs.

Run the full simulation:

```bash
python tests/test_full_simulation.py
```

Expected result:

- Simulated sensors update shared state.
- Generated images are saved under `data/images/`.
- Telemetry packets print to console.
- Mission data is logged to CSV.
- HTML and KML maps are generated.

## 5. Main Program Operation

Start the main payload program:

```bash
python main.py
```

The software will:

1. Create required data folders.
2. Start enabled workers.
3. Enter `BOOT`.
4. Transition to `IDLE`.
5. Transition to `DESCENT`.
6. Continue until landing is detected or the operator stops the program.

Stop the program:

```text
Ctrl+C
```

Always stop cleanly so the logger closes the CSV file and mapping output is
generated.

## 5A. Ground Test Mode

Ground test mode runs the same live runtime workers as the flight program, but
keeps state transitions under operator control. Use it for on-ground checks of
sensor reading, gimbal stabilization, actuation flags, telemetry packets, camera
capture, and CSV logging.

Start a real-hardware ground test:

```bash
python main.py --test-mode --real-hardware
```

Start a dry run with mock devices:

```bash
python main.py --test-mode --mock
```

Enable or disable subsystems without editing `config.py`:

```bash
python main.py --test-mode --real-hardware --enable-gps --enable-camera --enable-telemetry
python main.py --test-mode --real-hardware --disable-camera --disable-telemetry
```

In the `garuda-test>` console:

```text
help              show commands
auto on           enable sensor-driven state transitions
auto off          pause sensor-driven state transitions
state <name>      force a state, for example state GUIDED_DESCENT
next              force the next nominal state
arm / disarm      switch pad arming state
abort / landed    force abort or landed
snap              print one live sensor/gimbal snapshot
quit              stop cleanly, close logs, and generate map outputs if enabled
```

Typical on-ground sequence:

```text
state DISARMED
arm
state DESCENT_DROGUE
state GLIDER_DEPLOY
state GUIDED_DESCENT
snap
auto off
landed
quit
```

Use `auto on` only when you intentionally want the normal sensor-driven flight
state controller to advance states from live barometer and IMU readings.

## 6. Output Files

| Output | Purpose |
| --- | --- |
| `data/images/` | Captured image files |
| `data/logs/flight_log_*.csv` | Mission log |
| `data/maps/flight_path.html` | Interactive browser map |
| `data/maps/flight_path.kml` | Google Earth path |
| `data/logs/hardware_tests/` | Hardware test logs |

CSV columns:

```text
timestamp,mission_time,state,latitude,longitude,gps_altitude,baro_altitude,roll,pitch,yaw,gyro_x,gyro_y,gyro_z,image_name,image_timestamp,battery,status,...
```

The original columns remain first. AHRS fields are appended, including source,
validity, confidence, quaternion `(w,x,y,z)`, AHRS Euler outputs, sample age,
correction flags, and preserved raw accel/mag/native quaternion values.

## 7. Hardware Bring-Up Procedure

Do not connect and test every subsystem at once. Bring up one subsystem at a
time.

Recommended order:

1. Boot Raspberry Pi and confirm SSH access.
2. Install Python dependencies.
3. Confirm I2C devices for BNO085/PCA9685/INA219.
4. Test camera.
5. Test GPS.
6. Test barometer.
7. Test IMU.
8. Test servos.
9. Test gimbal.
10. Test XBee telemetry.
11. Run the live terminal dashboard and visually check the readings.
12. Run the browser dashboard and visually check the camera frame.
13. Run the integrated ground station and save a test report.
14. Run a short real-hardware field walk.

Commands:

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

## 8. Raspberry Pi Package Notes

Install optional packages on the Pi when real hardware is connected:

```bash
sudo apt install -y i2c-tools python3-picamera2 python3-gpiozero pigpio
pip install -r requirements.txt
```

Enable interfaces with `raspi-config`:

- Camera
- I2C for BNO085/PCA9685/INA219
- SPI for BMP388/SC16IS750
- Serial as needed for GPS/XBee

## 9. Pre-Flight Checklist

- Battery charged and secured.
- SD card has enough free space.
- Camera focus and exposure checked.
- GPS has outdoor fix.
- Barometer altitude is plausible.
- IMU roll/pitch/yaw values respond to motion.
- Gimbal moves without binding.
- Telemetry packets received on ground station.
- `config.py` ports and addresses match connected hardware.
- `USE_MOCK_HARDWARE = False`.
- A short field walk produces a usable map.

## 10. Troubleshooting

No map generated:

- Confirm `ENABLE_MAPPING = True`.
- Confirm a CSV exists in `data/logs/`.
- Confirm CSV has `latitude` and `longitude` columns.

GPS values are zero:

- Confirm GPS transport, chip-select wiring, and baud rate.
- Check whether the GPS has a valid outdoor fix.

Camera errors:

- Confirm camera is enabled and detected.
- On Raspberry Pi, verify camera packages and cable orientation.
- Run `hardware_tests/test_camera_real.py`.

No telemetry:

- Confirm `XBEE_PORT` and `XBEE_BAUDRATE`.
- Check XBee pairing/configuration and ground-station receiver.
- Run `hardware_tests/test_xbee_real.py`.

## 11. Development Notes

- Keep generated data out of Git.
- Add new hardware drivers behind existing factory functions.
- Use simulation tests for desktop-only changes; use hardware dashboards before flight.
- Keep CSV column names stable because mapping and telemetry depend on them.
- Treat AHRS attitude as a prior. Visual geometry checks may reject bad pose
  assumptions after flight.
- Extend mapping carefully; current mapping is GPS path visualization, not image
  stitching or orthomosaic generation.

## 13. AHRS Coordinate Convention

- Body axes: existing payload/camera convention; roll about X, pitch about Y,
  yaw about Z. Mounting rotation is centralized in `IMU_TO_BODY_QUATERNION`.
- Navigation/world axes: unchanged from existing mapping code.
- Quaternion order: `(w, x, y, z)` internally and in logs.
- BNO085 native order: `(x, y, z, w)` and converted explicitly.
- Euler convention: degrees, `R = Rz(yaw) * Ry(pitch) * Rx(roll)`.
- Gyro units: raw software filters use rad/s; shared/logged gyro fields are
  deg/s.

## 14. Live Sensor Dashboard

For visual hardware bring-up:

```bash
python hardware_tests/live_sensor_dashboard.py --mode bno085
```

The dashboard displays GPS, barometer, raw BNO085 values, calculated
roll/pitch/yaw, AHRS quaternion, source, health,
sample age, correction flags, diagnostics counters, and a compact telemetry
packet preview. It reads sensors only and does not command the gimbal.

For a browser dashboard with the latest camera frame:

```bash
python hardware_tests/web_sensor_dashboard.py --mode bno085 --host 0.0.0.0
```

Open `http://<raspberry-pi-ip>:8080` from a laptop or the Pi browser. The page
shows live GPS, barometer, raw IMU, AHRS, telemetry preview, and latest captured
camera frame.

For an integrated temporary ground-station dashboard with graphs and state
controls:

```bash
python hardware_tests/ground_station_dashboard.py --host 0.0.0.0 --bench
```

Open `http://<raspberry-pi-ip>:8080`. The page shows mission state, subsystem
health, GPS/barometer altitude, vertical rate, attitude graphs, raw gyro rates,
gimbal command graphs, telemetry preview, and the latest camera frame when the
camera worker is enabled. Use the page controls to force a state, step to the
next nominal state, or toggle automatic sensor-driven transitions.

Modes:

```text
--mock           dry run with synthetic devices and fault injection enabled
--bench          real hardware engineering mode with manual state controls
--real-hardware  flight-style mode; manual state controls disabled by default
```

For a safe dry run:

```bash
python hardware_tests/ground_station_dashboard.py --mock --disable-camera --disable-telemetry
```

The dashboard includes Mission, Sensors, Payload, System, Telemetry, and Test
tabs. It includes event markers on plots, detector condition readouts, live
lightweight image quality, image-sensor synchronization deltas, power values,
worker health, storage validation, and a PASS/WARN/FAIL verification summary.
The Test tab can start/stop/reset a recording session. Stopped test reports are
written as JSON, event CSV, and HTML summary files to:

```text
data/logs/test_reports/
```

In mock mode only, the Test tab can inject faults into the normal worker path:

```text
gps_loss
gps_high_hdop
freeze_gps
freeze_imu
imu_drift
freeze_barometer
barometer_drift
camera_timeout
camera_dropped_frame
telemetry_drop
logger_write_failure
gimbal_saturation
low_voltage
high_cpu_temperature
```

In real hardware mode, unsupported metrics are shown as unavailable or disabled
instead of being invented.

Gimbal safety limits:

```text
Stepper travel: -180 deg to +180 deg from home, one full revolution total.
Servo command:  -180 deg to +180 deg logical command.
```

The stepper limit is a hard wire-wrap protection; commands beyond this range
are clamped and reported as gimbal saturation. The servo command is converted
inside `RealGimbal` to the PCA9685 physical angle range before actuation.

## 12. Mapping Algorithm

For every row with valid latitude, longitude, and `image_name`, the mapper:

1. Reads altitude from `baro_altitude`, falling back to `gps_altitude`.
2. Estimates image ground width and height using:

```text
ground_size = 2 * altitude * tan(field_of_view / 2)
```

3. Creates a rectangle centered on the GPS coordinate.
4. Rotates that rectangle by the logged yaw angle.
5. Converts local meter offsets back to latitude/longitude.
6. Draws the rectangle on the HTML map and KML export.
7. Rasterizes all rectangles onto a metric grid to estimate unique covered
   area and overlap.

Assumptions:

- Camera is nadir-facing due to gimbal stabilization.
- Terrain is locally flat.
- GPS coordinate is the center of the image.
- Roll and pitch are small enough to ignore for this first coverage model.
