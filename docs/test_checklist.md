# Test Checklist

Pre-flight and bring-up checklist for the Ground Mapping Payload.

## Raspberry Pi Setup

- [ ] Pi boots from SD card
- [ ] SSH access working (`ssh pi@<ip>`)
- [ ] Python 3.9+ installed
- [ ] Virtual environment created and dependencies installed
- [ ] `data/` folders exist (images, logs, maps)
- [ ] I2C, SPI, camera, and serial interfaces enabled as needed

## GARUDA HAT Hardware Tests

- [ ] **Camera test** - `libcamera-hello` or `python hardware_tests/test_camera_real.py`
- [ ] **GPS test** - NMEA output on USB-UART; `python hardware_tests/test_gps_real.py`
- [ ] **I2C scan** - PCA9685/INA219 visible; `python hardware_tests/test_i2c_scan.py`
- [ ] **SPI sensor wiring** - BNO085 and BMP388 CS/INT/RST lines match `docs/pin_map.md`
- [ ] **IMU test** - BNO085 readings respond to motion after real driver is added
- [ ] **Barometer test** - BMP388 altitude reading plausible after real driver is added
- [ ] **Servo test** - PCA9685 sweep without load; `python hardware_tests/test_servo_real.py`
- [ ] **Gimbal test** - 2-axis PCA9685 sweep; `python hardware_tests/test_gimbal_real.py`
- [ ] **LoRa telemetry test** - packet received on ground station; `python hardware_tests/test_xbee_real.py`
- [ ] **Buzzer/LED test** - GPIO16 buzzer and GPIO26 LED verified after test script is added

## Software Integration Tests

- [ ] **Integrated logging** - CSV rows append with correct header
- [ ] **Fake mapping** - `python tests/test_fake_mapping.py` produces HTML + KML
- [ ] **Full simulation** - `python tests/test_full_simulation.py` completes 30 s
- [ ] **Main program** - `python main.py` runs all enabled modules; Ctrl+C clean shutdown
- [ ] Maps open in browser (`data/maps/flight_path.html`)
- [ ] KML opens in Google Earth (`data/maps/flight_path.kml`)

## Field Tests

- [ ] **Field walk test** - carry payload outdoors; verify GPS track and image geotags
- [ ] LoRa telemetry received at expected rate on ground station
- [ ] SD card has free space after 10-minute run
- [ ] Gimbal stabilizes during gentle motion
- [ ] Battery/current telemetry logged and within safe range

## Sign-off

| Test | Date | Tester | Pass/Fail | Notes |
|------|------|--------|-----------|-------|
| Pi boot | | | | |
| HAT power rails | | | | |
| Full simulation | | | | |
| Field walk | | | | |
