# GARUDA Ground Mapping Payload User Manual

This manual explains how to set up, run, test, and operate the GARUDA ground
mapping payload software.

## 1. System Overview

The payload software runs a set of background workers:

- GPS worker updates latitude, longitude, and GPS altitude.
- Barometer worker updates pressure-derived altitude.
- IMU worker updates roll, pitch, and yaw.
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

For simulation:

```python
USE_MOCK_HARDWARE = True
```

For hardware mode:

```python
USE_MOCK_HARDWARE = False
GPS_PORT = "/dev/ttyUSB0"
XBEE_PORT = "/dev/ttyUSB1"
GPS_BAUDRATE = 9600
XBEE_BAUDRATE = 9600
BAROMETER_ADDRESS = 0x76
IMU_ADDRESS = 0x68
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

Camera footprint settings:

```python
CAMERA_HORIZONTAL_FOV_DEG = 62.2
CAMERA_VERTICAL_FOV_DEG = 48.8
MAPPING_MIN_FOOTPRINT_ALTITUDE_M = 2.0
MAPPING_COVERAGE_GRID_M = 5.0
```

Tune field-of-view values after the final camera and lens are selected.

## 4. Simulation Workflow

Use simulation mode before connecting hardware.

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

- Mock sensors update shared state.
- Mock images are saved under `data/images/`.
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
timestamp,mission_time,state,latitude,longitude,gps_altitude,baro_altitude,roll,pitch,yaw,image_name,battery,status
```

## 7. Hardware Bring-Up Procedure

Do not connect and test every subsystem at once. Bring up one subsystem at a
time.

Recommended order:

1. Boot Raspberry Pi and confirm SSH access.
2. Install Python dependencies.
3. Confirm I2C devices.
4. Test camera.
5. Test GPS.
6. Test barometer.
7. Test IMU.
8. Test servos.
9. Test gimbal.
10. Test XBee telemetry.
11. Run full integrated simulation.
12. Run a short real-hardware field walk.

Commands:

```bash
python hardware_tests/test_i2c_scan.py
python hardware_tests/test_camera_real.py
python hardware_tests/test_gps_real.py
python hardware_tests/test_barometer_real.py
python hardware_tests/test_imu_real.py
python hardware_tests/test_servo_real.py
python hardware_tests/test_gimbal_real.py
python hardware_tests/test_xbee_real.py
python hardware_tests/test_all_sensors_status.py
```

## 8. Raspberry Pi Package Notes

Install optional packages on the Pi when real hardware is connected:

```bash
sudo apt install -y i2c-tools python3-picamera2 python3-gpiozero pigpio
pip install adafruit-circuitpython-bmp280 adafruit-circuitpython-mpu6050 adafruit-blinka smbus2
```

Enable interfaces with `raspi-config`:

- Camera
- I2C
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
- `USE_MOCK_HARDWARE` is set correctly.
- A short field walk produces a usable map.

## 10. Troubleshooting

No map generated:

- Confirm `ENABLE_MAPPING = True`.
- Confirm a CSV exists in `data/logs/`.
- Confirm CSV has `latitude` and `longitude` columns.

GPS values are zero:

- In simulation, confirm `USE_MOCK_HARDWARE = True`.
- In hardware mode, confirm GPS serial port and baud rate.
- Check whether the GPS has a valid fix.

Camera errors:

- Confirm camera is enabled and detected.
- On Raspberry Pi, verify camera packages and cable orientation.
- Run `hardware_tests/test_camera_real.py`.

No telemetry:

- Confirm `XBEE_PORT` and `XBEE_BAUDRATE`.
- Check XBee pairing and ground-station receiver.
- Run `hardware_tests/test_xbee_real.py`.

## 11. Development Notes

- Keep generated data out of Git.
- Add new hardware drivers behind existing factory functions.
- Test in mock mode before switching to real hardware.
- Keep CSV column names stable because mapping and telemetry depend on them.
- Extend mapping carefully; current mapping is GPS path visualization, not image
  stitching or orthomosaic generation.

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
