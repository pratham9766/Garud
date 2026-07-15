# GARUDA TARSR Ground Mapping Payload

Onboard software for the GARUDA CanSat terrain and ground mapping payload. The
payload runs on a Raspberry Pi, collects GPS, barometer, IMU, camera, gimbal,
and telemetry data during descent, logs the mission to CSV, and generates
HTML/KML flight-path maps after shutdown.

The project currently defaults to simulation mode, so it can be developed and
tested without connected flight hardware.

## Project Status

The simulation path is the primary working flow. It can generate a fake descent,
capture mock images, log telemetry, and export map products without hardware.
Real hardware bring-up scripts and configuration hooks are included for Raspberry
Pi testing, but the flight hardware path should be verified end-to-end before
mission use.

## Features

- Simulated GPS track near Pune, India.
- Simulated descent from roughly 700 m altitude.
- Mock camera image capture with GPS text overlays.
- Mock IMU, barometer, gimbal, and telemetry workers.
- Threaded mission runtime with shared payload state.
- CSV mission logging.
- Interactive Folium HTML map export.
- Google Earth compatible KML export.
- Estimated camera ground footprints and unique coverage area.
- Standalone hardware bring-up scripts for Raspberry Pi testing.

## Tech Stack

- Python 3.9+
- Raspberry Pi target platform
- Folium for interactive HTML maps
- SimpleKML for Google Earth exports
- Pillow/OpenCV for image handling
- Adafruit CircuitPython libraries for supported hardware modules

## Mapping Scope

The implemented mapping is GPS flight-path mapping plus an estimated camera
coverage model. It plots the payload path, geotagged image capture points, and
estimated ground rectangles for each image based on altitude, yaw, and camera
field-of-view.

This repository does not implement orthomosaic generation, image stitching,
SLAM, feature matching, or camera-to-ground projection.

## Repository Layout

```text
ground_mapping_payload/
|-- camera/             Camera factory and mock/real camera classes
|-- core/               Shared state, mission states, thread manager, health
|-- data/               Runtime output folders for logs, images, and maps
|-- docs/               Wiring, pin map, checklist, and user manual
|-- gimbal/             Gimbal stabilizer and servo control
|-- hardware_tests/     Real hardware bring-up scripts
|-- logging_system/     CSV logger
|-- mapping/            Fake flight data, HTML map, KML, geotag helpers
|-- sensors/            GPS, IMU, and barometer interfaces
|-- telemetry/          LoRa/XBee telemetry packet generation/sending
|-- tests/              Simulation and module tests
|-- config.py           Runtime configuration
|-- main.py             Main mission entry point
|-- requirements.txt    Python dependencies
`-- README.md
```

## Hardware Target

- Python 3.9 or newer
- Raspberry Pi 4 recommended for hardware mode
- Optional hardware: GPS, camera, BMP388 barometer, BNO085 IMU, PCA9685 gimbal, LoRa radio

Python packages are listed in `requirements.txt`.

## Quick Start

Clone the repository:

```bash
git clone https://github.com/pratham9766/Garuda_TARSR.git
cd Garuda_TARSR
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
python hardware_tests/test_servo_real.py
python hardware_tests/test_gimbal_real.py
python hardware_tests/test_xbee_real.py
python hardware_tests/test_all_sensors_status.py
```

## Generated Outputs

| Path | Description |
| --- | --- |
| `data/images/` | Captured mock or real images |
| `data/logs/` | Mission CSV logs |
| `data/maps/flight_path.html` | Interactive flight-path map |
| `data/maps/flight_path.kml` | Google Earth KML export |
| `data/logs/hardware_tests/` | Hardware test logs |

Runtime output folders are kept in the repository with `.gitkeep` files, while
generated logs, images, and maps are ignored by Git.

## CSV Format

```text
timestamp,mission_time,state,latitude,longitude,gps_altitude,baro_altitude,roll,pitch,yaw,image_name,battery,status
```

## Configuration

Edit `config.py` to enable/disable modules, switch between mock and real
hardware, adjust capture/logging intervals, and set serial/I2C/SPI device values.

Important settings:

```python
USE_MOCK_HARDWARE = True
ENABLE_CAMERA = True
ENABLE_GPS = True
ENABLE_MAPPING = True
GPS_PORT = "/dev/ttyUSB0"
XBEE_PORT = "/dev/ttyUSB1"
```

Set `USE_MOCK_HARDWARE = False` only after real hardware drivers and device
ports are ready.

Mapping footprint settings:

```python
CAMERA_HORIZONTAL_FOV_DEG = 62.2
CAMERA_VERTICAL_FOV_DEG = 48.8
MAPPING_COVERAGE_GRID_M = 5.0
```

## Documentation

- `docs/USER_MANUAL.md` - operator manual and workflow
- `docs/flight_flow.md` - mission state sequence
- `docs/wiring_plan.md` - wiring notes
- `docs/pin_map.md` - Raspberry Pi pin assignments
- `docs/test_checklist.md` - bring-up and field checklist
- `docs/component_status.md` - subsystem readiness status

## Hardware Mode Notes

The real hardware path is scaffolded, but several real device classes are still
placeholders. Before flight use, implement and verify:

| File | Class / area |
| --- | --- |
| `sensors/gps.py` | `RealGPS` NMEA serial reader |
| `sensors/imu.py` | Real BNO085 SPI reader |
| `sensors/barometer.py` | Real BMP388 SPI reader |
| `camera/mock_camera.py` | Real Raspberry Pi camera capture |
| `telemetry/xbee_sender.py` | Real LoRa/XBee serial transmitter |
| `gimbal/servo_control.py` | Real PCA9685 servo control |

## License

Internal project for the GARUDA CanSat / TARSR team.
