# Raspberry Pi Hardware Test Toolkit

A reusable Raspberry Pi 5 hardware validation framework for checking peripherals before they are integrated into larger robotics or payload software.

The toolkit is organized as small, independently reusable Python modules. Each hardware device has its own controller class, all pin numbers and addresses live in `settings.yaml`, and the interactive menu keeps missing hardware from crashing the whole validation run.

## Target Platform

- Raspberry Pi 5
- Raspberry Pi OS Bookworm 64-bit
- Python 3.11 or newer
- I2C enabled
- Camera enabled through the modern libcamera stack
- `pigpiod` running for servo PWM

## Project Layout

```text
raspi_hardware_test/
|-- README.md
|-- requirements.txt
|-- config.py
|-- settings.yaml
|-- main.py
|-- menu.py
|-- utils/
|   |-- logger.py
|   |-- colors.py
|   `-- helpers.py
|-- hardware/
|   |-- camera.py
|   |-- servo.py
|   |-- bno055.py
|   `-- bmp388.py
|-- tests/
|   |-- test_camera.py
|   |-- test_servo.py
|   |-- test_bno055.py
|   |-- test_bmp388.py
|   `-- test_all.py
`-- logs/
```

## Installation

Update the Pi first:

```bash
sudo apt update
sudo apt full-upgrade -y
sudo reboot
```

Install system packages:

```bash
sudo apt install -y python3-pip python3-venv python3-picamera2 pigpio i2c-tools
```

Create and activate a virtual environment:

```bash
cd raspi_hardware_test
python3 -m venv .venv --system-site-packages
source .venv/bin/activate
pip install -r requirements.txt
```

`--system-site-packages` is recommended because Raspberry Pi OS provides Picamera2 through apt.

## Enable I2C

Run:

```bash
sudo raspi-config
```

Then select:

```text
Interface Options -> I2C -> Enable
```

Reboot after enabling:

```bash
sudo reboot
```

Optional bus check:

```bash
i2cdetect -y 1
```

Expected defaults:

- BNO055: `0x28`
- BMP388: `0x76`

## Enable Camera

Raspberry Pi OS Bookworm uses libcamera. Confirm the camera is detected:

```bash
rpicam-hello --list-cameras
```

If no camera is listed, power down and check the CSI cable orientation and connector seating.

## Install And Start pigpio

The servo controller uses the `pigpio` daemon:

```bash
sudo systemctl enable pigpiod
sudo systemctl start pigpiod
sudo systemctl status pigpiod
```

## Configuration

Edit `settings.yaml`:

```yaml
camera:
  resolution: [1920, 1080]
  preview: true
  image_dir: captures/images
  video_dir: captures/videos
  video_seconds: 10
  continuous_interval_seconds: 2.0

servo:
  gpio: 18
  min_pulse: 500
  max_pulse: 2500
  min_angle: 0
  max_angle: 180
  settle_seconds: 0.5

bno055:
  address: 0x28
  refresh_hz: 10

bmp388:
  address: 0x76
  sea_level_pressure_hpa: 1013.25
  refresh_hz: 5

logging:
  save_logs: true
  level: INFO
  directory: logs
```

No GPIO number is hardcoded in the hardware modules; change servo wiring by editing `settings.yaml`.

## Run

From the project directory:

```bash
python3 main.py
```

Menu:

```text
===========================
 Raspberry Pi Test Utility
===========================
1 Test Camera
2 Test Servo
3 Test BNO055
4 Test BMP388
5 Scan I2C Bus
6 Test Everything
7 Show System Info
0 Exit
```

## Hardware Wiring

Always power down the Pi before changing wiring.

### Servo Motor

| Servo wire | Raspberry Pi 5 |
| --- | --- |
| Signal | GPIO18, physical pin 12 |
| VCC | External 5 V supply |
| GND | External supply GND and Pi GND |

Use a separate 5 V supply for most servos. Connect the external supply ground to a Pi ground pin so the PWM signal has a shared reference.

### BNO055 IMU

| BNO055 pin | Raspberry Pi 5 |
| --- | --- |
| VIN | 3.3 V, physical pin 1 |
| GND | GND, physical pin 6 |
| SDA | GPIO2/SDA, physical pin 3 |
| SCL | GPIO3/SCL, physical pin 5 |

Default address: `0x28`.

### BMP388

| BMP388 pin | Raspberry Pi 5 |
| --- | --- |
| VIN | 3.3 V, physical pin 1 |
| GND | GND, physical pin 6 |
| SDA | GPIO2/SDA, physical pin 3 |
| SCL | GPIO3/SCL, physical pin 5 |

Default address: `0x76`.

### Camera Module

Connect the camera to the Pi 5 camera connector using the correct Pi 5 camera cable. After boot, verify with:

```bash
rpicam-hello --list-cameras
```

## Logging

The logger prints colored terminal messages for:

- `INFO`
- `WARNING`
- `ERROR`
- `SUCCESS`

When `logging.save_logs` is `true`, logs are also written to:

```text
logs/YYYYMMDD.log
```

## Reusing Hardware Classes

Each device can be imported independently:

```python
from config import load_config
from hardware.servo import ServoController

config = load_config()

with ServoController(config.servo) as servo:
    servo.move_to_angle(90)
```

The same pattern works with:

- `CameraController`
- `BNO055Sensor`
- `BMP388Sensor`

## Troubleshooting

### I2C scan fails

- Confirm I2C is enabled with `sudo raspi-config`.
- Confirm wiring uses GPIO2/SDA and GPIO3/SCL.
- Run `i2cdetect -y 1`.
- Check that sensors are powered from 3.3 V unless the breakout explicitly supports 5 V logic.

### BNO055 not detected at 0x28

- Check the address jumper on the breakout board.
- Some boards can use `0x29`; update `settings.yaml` if needed.
- Keep I2C wires short and secure.

### BMP388 not detected at 0x76

- Check whether the breakout uses `0x77`.
- Update `settings.yaml` if your board address differs.
- Confirm the sensor appears in `i2cdetect -y 1`.

### Camera initialization failed

- Run `rpicam-hello --list-cameras`.
- Confirm the ribbon cable orientation.
- Install Picamera2 with `sudo apt install python3-picamera2`.
- Use a virtual environment created with `--system-site-packages`.

### pigpio daemon is not running

Start it:

```bash
sudo systemctl start pigpiod
```

Enable it on boot:

```bash
sudo systemctl enable pigpiod
```

### Servo moves erratically

- Use an external 5 V power supply.
- Share ground between the Pi and servo supply.
- Tune `min_pulse` and `max_pulse` in `settings.yaml`.
- Avoid powering larger servos from the Pi 5 header.

## Design Notes

- Configuration is centralized in `settings.yaml`.
- Hardware failures raise `HardwareError` and are handled by the menu/test layer.
- Test modules return `True` or `False` so they can be reused by automation later.
- The framework avoids crashing the full test run when one device is missing.
