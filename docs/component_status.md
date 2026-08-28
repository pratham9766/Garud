# Component Status

Track hardware arrival, assembly, and software integration status.

| Component | Ordered | Received | Bench Tested | Integrated | Software Driver | Notes |
|-----------|---------|----------|--------------|------------|-----------------|-------|
| Raspberry Pi 4 8GB | [ ] | [ ] | [ ] | [ ] | N/A | |
| microSD card (32 GB+) | [ ] | [ ] | [ ] | [ ] | N/A | High endurance recommended |
| Pi HQ / Arducam HQ Camera | [ ] | [ ] | [ ] | [ ] | `RealCamera` stub | CSI cable |
| GPS module | [ ] | [ ] | [ ] | [ ] | `RealGPS` stub | USB-UART because HAT UART is LoRa |
| BMP388 barometer | [ ] | [ ] | [ ] | [ ] | `RealBarometer` stub | SPI: `CS_BMP` on GPIO8 |
| BNO085 IMU/AHRS | [ ] | [ ] | [ ] | [ ] | `RealIMU` I2C driver path plus AHRS manager | I2C1: GPIO2/GPIO3, address `0x4A` |
| PCA9685 servo controller | [ ] | [ ] | [ ] | [ ] | `adafruit_servokit` hardware tests | I2C, `OE_Servo` on GPIO4 |
| 2-axis servo gimbal | [ ] | [ ] | [ ] | [ ] | `RealGimbal` stub | PCA9685 channels in `config.py` |
| ULN2003 stepper | [ ] | [ ] | [ ] | [ ] | legacy bench driver | GPIO25/24/23/18 |
| LoRa telemetry module | [ ] | [ ] | [ ] | [ ] | `RealTelemetry` stub | UART GPIO14/GPIO15, M0/M1/AUX |
| INA219 current sensor | [ ] | [ ] | [ ] | [ ] | Planned | I2C |
| HAT 5 V power path | [ ] | [ ] | [ ] | [ ] | N/A | XT30/J4 and protection path |
| Payload enclosure | [ ] | [ ] | [ ] | [ ] | N/A | |

## Software Status

| Module | Mock Working | Real Driver | Test Script |
|--------|--------------|-------------|-------------|
| GPS | yes | stub | `tests/test_gps.py`, `hardware_tests/test_gps_real.py` |
| IMU | yes | stub | `tests/test_imu.py` |
| Barometer | yes | stub | `tests/test_barometer.py` |
| Camera | yes | stub | `tests/test_camera.py`, `hardware_tests/test_camera_real.py` |
| Gimbal | yes | partial PCA9685 hardware test | `hardware_tests/test_gimbal_real.py` |
| Telemetry | yes | serial stub | `tests/test_telemetry.py`, `hardware_tests/test_xbee_real.py` |
| CSV Logger | yes | N/A | full simulation |
| Map / KML | yes | N/A | `tests/test_fake_mapping.py` |
| Full simulation | yes | stubbed hardware | `tests/test_full_simulation.py` |

## Last Updated

Date: ___________
Updated by: ___________
