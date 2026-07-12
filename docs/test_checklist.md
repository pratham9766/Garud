# Test Checklist

Pre-flight and bring-up checklist for the Ground Mapping Payload.

## Raspberry Pi Setup

- [ ] Pi boots from SD card
- [ ] SSH access working (`ssh pi@<ip>`)
- [ ] Python 3.9+ installed
- [ ] Virtual environment created and dependencies installed
- [ ] `data/` folders exist (images, logs, maps)

## Individual Hardware Tests

- [ ] **Camera test** — `libcamera-hello` or `python tests/test_camera.py`
- [ ] **GPS test** — NMEA output on serial port; `python tests/test_gps.py` (mock first)
- [ ] **IMU test** — I2C detect + read angles; `python tests/test_imu.py`
- [ ] **Barometer test** — altitude reading plausible; `python tests/test_barometer.py`
- [ ] **Servo test** — manual angle sweep without load; gimbal prints/commands verified
- [ ] **XBee test** — packet received on ground station; `python tests/test_telemetry.py`

## Software Integration Tests

- [ ] **Integrated logging** — CSV rows append with correct header
- [ ] **Fake mapping** — `python tests/test_fake_mapping.py` produces HTML + KML
- [ ] **Full simulation** — `python tests/test_full_simulation.py` completes 30 s
- [ ] **Main program** — `python main.py` runs all enabled modules; Ctrl+C clean shutdown
- [ ] Maps open in browser (`data/maps/flight_path.html`)
- [ ] KML opens in Google Earth (`data/maps/flight_path.kml`)

## Field Tests

- [ ] **Field walk test** — carry payload outdoors; verify GPS track and image geotags
- [ ] Telemetry received at expected rate on ground station
- [ ] SD card has free space after 10-minute run
- [ ] Gimbal stabilizes during gentle motion
- [ ] Battery voltage logged and within safe range

## Sign-off

| Test | Date | Tester | Pass/Fail | Notes |
|------|------|--------|-----------|-------|
| Pi boot | | | | |
| Full simulation | | | | |
| Field walk | | | | |
