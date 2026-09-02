# Component Status

Track hardware arrival, assembly, and software integration status.

| Component | Ordered | Received | Bench Tested | Integrated | Software Driver | Notes |
|-----------|---------|----------|--------------|------------|-----------------|-------|
| Raspberry Pi 5 / Pi 4 8GB | [ ] | [ ] | [ ] | [ ] | N/A | Pi 5 is the primary target; Pi 4 can be used for compatible bench checks |
| microSD card (32 GB+) | [ ] | [ ] | [ ] | [ ] | N/A | High endurance recommended |
| Pi HQ / Arducam HQ Camera | [ ] | [ ] | [ ] | [ ] | `RealCamera` Picamera2/OpenCV path | CSI cable or OpenCV camera device |
| GPS module | [ ] | [ ] | [ ] | [ ] | `RealGPS` SC16IS750 path | GPS bridge on SPI0 CE1/GPIO7 |
| BMP388 barometer | [ ] | [ ] | [ ] | [ ] | `RealBarometer` BMP388 SPI path | SPI: `CS_BMP` on GPIO8 |
| BNO085 IMU/AHRS | [ ] | [ ] | [ ] | [ ] | `RealIMU` I2C driver path plus AHRS manager | I2C1: GPIO2/GPIO3, address `0x4A` |
| PCA9685 servo controller | [ ] | [ ] | [ ] | [ ] | `adafruit_servokit` hardware tests | I2C, `OE_Servo` on GPIO4 |
| 2-axis servo gimbal | [ ] | [ ] | [ ] | [ ] | `RealGimbal` command path | Stepper limited to one revolution; servo command range `-180..+180` |
| ULN2003 stepper | [ ] | [ ] | [ ] | [ ] | legacy bench driver | GPIO25/24/23/18 |
| XBee telemetry module | [ ] | [ ] | [ ] | [ ] | `RealTelemetry` serial path | `/dev/ttyAMA0` at 9600 baud |
| INA219 current sensor | [ ] | [ ] | [ ] | [ ] | `power_worker` adapter pending hardware address | I2C address must be confirmed in `config.py` |
| HAT 5 V power path | [ ] | [ ] | [ ] | [ ] | N/A | XT30/J4 and protection path |
| Payload enclosure | [ ] | [ ] | [ ] | [ ] | N/A | |

## Software Status

| Module | Mock Working | Real Driver | Test Script |
|--------|--------------|-------------|-------------|
| GPS | yes | SC16IS750 bridge path | `tests/test_gps.py`, `hardware_tests/test_gps_real.py` |
| IMU | yes | BNO085 I2C path | `tests/test_imu.py`, `hardware_tests/test_imu_real.py` |
| Barometer | yes | BMP388 SPI path | `tests/test_barometer.py`, `hardware_tests/test_barometer_real.py` |
| Navigation estimator | yes | consumes raw GPS/BMP388/AHRS from `SharedData` | `tests/test_navigation_estimator.py`, `hardware_tests/navigation_field_test.py` |
| Camera | yes | Picamera2/OpenCV path | `tests/test_camera.py`, `hardware_tests/test_camera_real.py` |
| Gimbal | yes | partial PCA9685 hardware test | `hardware_tests/test_gimbal_real.py` |
| Telemetry | yes | serial stub | `tests/test_telemetry.py`, `hardware_tests/test_xbee_real.py` |
| CSV Logger | yes | N/A | full simulation |
| Ground station dashboard | yes | reads enabled live workers | `hardware_tests/ground_station_dashboard.py --bench --real-hardware` |
| Runtime diagnostics | yes | worker timing, stale detection, system health, storage checks | `tests/test_diagnostics.py` |
| Power monitor | yes | INA219 path requires confirmed address/library | dashboard System tab |
| Map / KML | yes | N/A | `tests/test_fake_mapping.py` |
| Full simulation | yes | stubbed hardware | `tests/test_full_simulation.py` |

## Last Updated

Date: ___________
Updated by: ___________
