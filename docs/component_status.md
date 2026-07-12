# Component Status

Track hardware arrival, assembly, and software integration status.

| Component | Ordered | Received | Bench Tested | Integrated | Software Driver | Notes |
|-----------|---------|----------|--------------|------------|-----------------|-------|
| Raspberry Pi 4 8GB | ☐ | ☐ | ☐ | ☐ | N/A | |
| microSD card (32 GB+) | ☐ | ☐ | ☐ | ☐ | N/A | High endurance recommended |
| Pi HQ / Arducam HQ Camera | ☐ | ☐ | ☐ | ☐ | `RealCamera` stub | CSI cable included? |
| GPS module | ☐ | ☐ | ☐ | ☐ | `RealGPS` stub | USB adapter for dev |
| Barometer (BMP280) | ☐ | ☐ | ☐ | ☐ | `RealBarometer` stub | I2C 0x76 |
| IMU (MPU6050) | ☐ | ☐ | ☐ | ☐ | `RealIMU` stub | I2C 0x68 |
| 2-axis servo gimbal | ☐ | ☐ | ☐ | ☐ | `RealGimbal` stub | External 5 V supply |
| XBee module + adapter | ☐ | ☐ | ☐ | ☐ | `RealTelemetry` stub | USB first |
| Servo BEC (5 V) | ☐ | ☐ | ☐ | ☐ | N/A | |
| Jumper wires / breadboard | ☐ | ☐ | ☐ | ☐ | N/A | |
| Payload enclosure | ☐ | ☐ | ☐ | ☐ | N/A | |

## Software Status

| Module | Mock Working | Real Driver | Test Script |
|--------|--------------|-------------|-------------|
| GPS | ✅ | ☐ | `tests/test_gps.py` |
| IMU | ✅ | ☐ | `tests/test_imu.py` |
| Barometer | ✅ | ☐ | `tests/test_barometer.py` |
| Camera | ✅ | ☐ | `tests/test_camera.py` |
| Gimbal | ✅ | ☐ | — |
| Telemetry | ✅ | ☐ | `tests/test_telemetry.py` |
| CSV Logger | ✅ | N/A | full simulation |
| Map / KML | ✅ | N/A | `tests/test_fake_mapping.py` |
| Full simulation | ✅ | ☐ | `tests/test_full_simulation.py` |

## Last Updated

_Date: ___________  
Updated by: ___________
