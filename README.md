# Raspberry Pi Hardware Test Toolkit

A reusable Raspberry Pi 5 hardware validation framework for checking peripherals before they are integrated into larger robotics or payload software.

The toolkit is organized as small, independently reusable Python modules. Each hardware device has its own controller class, all pin numbers and addresses live in `settings.yaml`, and the interactive menu keeps missing hardware from crashing the whole validation run.

## Target Platform

- Raspberry Pi 5
- Raspberry Pi OS Bookworm 64-bit
- Python 3.11 or newer
- I2C enabled for I2C sensors
- SPI enabled for the uploaded BMP388 schematic wiring
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
- BMP388 I2C mode only: `0x76`

## Enable SPI

The uploaded schematic connects the BMP388 through SPI0.

Run:

```bash
sudo raspi-config
```

Then select:

```text
Interface Options -> SPI -> Enable
```

Reboot after enabling:

```bash
sudo reboot
```

Optional SPI check:

```bash
ls /dev/spidev*
```

You should see devices such as `/dev/spidev0.0` and `/dev/spidev0.1`.

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
board:
  pin_numbering: BCM
  i2c_sda_gpio: 2
  i2c_scl_gpio: 3
  spi0_mosi_gpio: 10
  spi0_miso_gpio: 9
  spi0_sclk_gpio: 11

camera:
  resolution: [1920, 1080]
  preview: true
  image_dir: captures/images
  video_dir: captures/videos
  video_seconds: 10
  continuous_interval_seconds: 2.0

servo:
  gpio: 4
  min_pulse: 500
  max_pulse: 2500
  min_angle: 0
  max_angle: 180
  settle_seconds: 0.5

bno055:
  interface: i2c
  address: 0x28
  sda_gpio: 2
  scl_gpio: 3
  schematic_reset_gpio: 5
  schematic_cs_gpio: 8
  schematic_int_gpio: 27
  refresh_hz: 10

bmp388:
  interface: spi
  address: 0x76
  sck_gpio: 11
  mosi_gpio: 10
  miso_gpio: 9
  cs_gpio: 22
  int_gpio: 27
  sea_level_pressure_hpa: 1013.25
  refresh_hz: 5

logging:
  save_logs: true
  level: INFO
  directory: logs
```

No GPIO number is hardcoded in the hardware modules; change wiring by editing `settings.yaml`.

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

## Pin Map From Uploaded Schematic

The schematic uses BCM GPIO numbering on the Raspberry Pi HAT header.

| Net name in schematic | BCM GPIO | Physical pin | Purpose |
| --- | ---: | ---: | --- |
| `OE_Servo` | GPIO4 | 7 | Servo PWM/control signal |
| `SCL_Servo` / I2C SCL | GPIO3 | 5 | I2C clock |
| `SDA_Servo` / I2C SDA | GPIO2 | 3 | I2C data |
| `SCK_BMP` | GPIO11 | 23 | BMP388 SPI0 SCLK |
| `MISO_BMP` | GPIO9 | 21 | BMP388 SPI0 MISO |
| `MOSI_BMP` | GPIO10 | 19 | BMP388 SPI0 MOSI |
| `CS_BMP` | GPIO22 | 15 | BMP388 chip select |
| `INT_BMP` | GPIO27 | 13 | BMP388 interrupt |
| `RST_BNO` | GPIO5 | 29 | BNO reset net shown in schematic |
| `CS_BNO` | GPIO8 | 24 | BNO chip-select net shown in schematic |
| `INT_BNO` | GPIO27 | 13 | BNO interrupt net shown in schematic |
| `GPIO16` | GPIO16 | 36 | Buzzer driver input |

Important: the schematic page labels the BNO module image as a BNO08x-style breakout and shows SPI-style nets such as `CS_BNO`, `SCK_BNO`, `MOSI_BNO`, and `MISO_BNO`. This project is written for a Bosch BNO055 using the Adafruit BNO055 I2C driver. If your actual fitted module is BNO08x/BNO085 on SPI, replace the BNO055 driver with the matching BNO08x library before expecting IMU readings.

### Servo Motor

| Servo wire | Raspberry Pi 5 |
| --- | --- |
| Signal | GPIO4, physical pin 7, schematic net `OE_Servo` |
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

The uploaded schematic wires BMP388 through SPI.

| BMP388 pin/net | Raspberry Pi 5 |
| --- | --- |
| VIN | 3.3 V, physical pin 1 |
| GND | GND, physical pin 6 |
| SCK / `SCK_BMP` | GPIO11/SPI0 SCLK, physical pin 23 |
| SDO / `MISO_BMP` | GPIO9/SPI0 MISO, physical pin 21 |
| SDI / `MOSI_BMP` | GPIO10/SPI0 MOSI, physical pin 19 |
| CS / `CS_BMP` | GPIO22, physical pin 15 |
| INT / `INT_BMP` | GPIO27, physical pin 13 |

The `address: 0x76` setting is kept for I2C mode. In the uploaded schematic's SPI mode, chip select GPIO22 is the important selection pin.

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

## How To Confirm Sensors Are Working

Start the menu:

```bash
python3 main.py
```

Use these options:

| Menu option | What you should see |
| --- | --- |
| `5 Scan I2C Bus` | BNO055 should appear as `0x28` if wired as I2C. BMP388 will not appear here when using the uploaded SPI wiring. |
| `1 Test Camera` | Capture/preview/video options and saved file paths under `captures/`. |
| `2 Test Servo` | Servo moves to selected angles or performs a sweep. |
| `3 Test BNO055` | Live acceleration, gyro, magnetometer, Euler, quaternion, calibration, and temperature at 10 Hz. Press `CTRL+C` to stop. |
| `4 Test BMP388` | Live temperature, pressure, and altitude at 5 Hz. Press `CTRL+C` to stop. |
| `6 Test Everything` | One combined pass/fail summary for camera, servo, BNO055, and BMP388. |

Quick command-line checks before running Python:

```bash
i2cdetect -y 1
ls /dev/spidev*
rpicam-hello --list-cameras
systemctl status pigpiod
```

Expected confirmations:

- BNO055 over I2C: `i2cdetect -y 1` shows `28`.
- BMP388 using this schematic: `/dev/spidev0.0` or `/dev/spidev0.1` exists, and menu option `4` prints changing pressure/temperature values.
- Servo: menu option `2` moves the servo and option `8` stops PWM.
- Camera: menu option `1` saves an image path, and `rpicam-hello --list-cameras` lists the camera.

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
