# GARUDA Lightweight Navigation Estimator

## A. Existing Architecture Audit

- GPS driver: `sensors/gps.py` exposes `MockGPS` and `RealGPS`. `RealGPS` reads NEO-M8N NMEA through the SC16IS750 SPI UART bridge in `sensors/gps_m8n.py`.
- GPS update rate: `gps_worker()` polls every `0.5 s`; expected rate is `GPS_EXPECTED_HZ = 2.0`.
- GPS fields found: latitude, longitude, altitude, fix status/type, satellites, HDOP, native ground speed, native course over ground, and monotonic timestamp after this update.
- BMP388 driver: `sensors/barometer.py` uses `BMP388Sensor` on SPI0 CS GPIO8 and publishes altitude, pressure, temperature, health, and monotonic timestamp.
- AHRS: `sensors/imu.py` reads BNO085 on I2C1, SDA GPIO2 and SCL GPIO3, then publishes raw accel/gyro/mag/native quaternion plus final AHRS quaternion, yaw, source, health, and timestamp.
- SharedData: `core/shared_data.py` is the central locked snapshot store used by workers, logger, telemetry, dashboards, mapping, health, and state machine.
- ThreadManager: `core/thread_manager.py` registers one daemon worker per subsystem with stop events.
- Mission state machine: `core/flight_state_machine.py` uses baro altitude, vertical velocity, accel magnitude, and state confirmation counts; it does not own navigation.
- Logger: `logging_system/data_logger.py` writes `SharedData.CSV_HEADER` and `SharedData.to_csv_row()`.
- Telemetry: `telemetry/telemetry_packet.py` builds compact JSON from the payload snapshot.
- Dashboards: `hardware_tests/live_sensor_dashboard.py`, `hardware_tests/web_sensor_dashboard.py`, and `hardware_tests/ground_station_dashboard.py` display raw sensor/health data.
- Gimbal: `gimbal/gimbal_stabilizer.py` consumes AHRS attitude only and commands the gimbal; navigation does not command actuators.
- Guidance/path code: no dedicated glider path-planning/controller module was found. The estimator exposes `safe_for_guidance` for that future layer.
- Geo helpers: mapping code had local conversions for image footprints/graphs, but not a reusable flight navigation frame.
- Health monitoring: worker health and rate-limited events already exist in `SharedData`.
- Test architecture: mostly direct Python scripts in `tests/`, with hardware tests under `hardware_tests/`.

## B. New Architecture

Before:

```text
GPS / BMP388 / BNO085 -> SharedData -> Logger / Telemetry / Dashboard
```

After:

```text
GPS raw fields ─────────┐
BMP388 altitude ────────┼──> SharedData snapshot -> Navigation Worker -> NavigationState -> SharedData
BNO085 AHRS heading ────┘

SharedData raw + estimated nav -> Guidance / Logger / Telemetry / Dashboard
```

Raw GPS, barometer, and AHRS fields are never overwritten by estimated fields.

## C. Algorithm

- State vector: `[north_m, east_m, north_velocity_mps, east_velocity_mps]`.
- Prediction: constant velocity using actual monotonic `dt`; invalid tiny/large dt is skipped or bounded.
- GPS position update: valid lat/lon is converted into a local tangent-plane north/east frame.
- GPS velocity update: native GPS ground speed/course is preferred. Velocity is derived from position differences only when native speed/course is unavailable.
- Heading: AHRS yaw is the primary vehicle heading. GPS course is used only as a fallback heading when speed exceeds `NAV_MIN_SPEED_FOR_GPS_HEADING_MPS`.
- Course vs heading: course is movement direction; heading is vehicle orientation.
- Altitude: BMP388 barometric altitude is primary. `estimated_agl_m` is relative to the first healthy barometer altitude seen by the estimator; it is not terrain-clearance AGL.
- GPS validation: fix, age, satellites, HDOP, finite/legal lat/lon, finite altitude, reported speed, timestamp order, implied speed, and catastrophic jump guard.
- Dead reckoning: GPS loss predicts only from last known ground velocity. It does not integrate accelerometers and does not rotate velocity to AHRS yaw.
- Timeout: after `NAV_DEAD_RECKON_MAX_SEC`, position becomes `UNRELIABLE` and `safe_for_guidance=False`.
- Recovery: valid GPS must pass hysteresis before returning to `GOOD`; correction toward GPS is rate-limited by `NAV_GPS_RECOVERY_MAX_CORRECTION_RATE_MPS`.

## D. Configuration

Defaults in `config.py`:

```python
ENABLE_NAVIGATION_ESTIMATOR = True
NAVIGATION_RATE_HZ = 20.0
NAV_MIN_SATELLITES = 5
NAV_MAX_HDOP = 4.0
NAV_MAX_GPS_AGE_MS = 1500.0
NAV_MAX_BARO_AGE_MS = 1000.0
NAV_MAX_AHRS_AGE_MS = 500.0
NAV_MAX_PLAUSIBLE_SPEED_MPS = 120.0
NAV_MAX_ABSOLUTE_GPS_JUMP_M = 250.0
NAV_GPS_REJECT_COUNT_TO_LOST = 4
NAV_GPS_GOOD_COUNT_TO_RECOVER = 3
NAV_DEAD_RECKON_MAX_SEC = 5.0
NAV_MIN_SPEED_FOR_GPS_HEADING_MPS = 2.0
NAV_MIN_DT_SEC = 0.001
NAV_MAX_DT_SEC = 0.25
NAV_PROCESS_NOISE_POSITION = 1.0
NAV_PROCESS_NOISE_VELOCITY = 4.0
NAV_GPS_POSITION_NOISE_M2 = 16.0
NAV_GPS_VELOCITY_NOISE_M2PS2 = 4.0
NAV_GPS_RECOVERY_ENABLED = True
NAV_GPS_RECOVERY_MAX_CORRECTION_RATE_MPS = 8.0
NAV_GPS_RECOVERY_MIN_STEP_M = 0.5
NAV_GPS_RECOVERY_POSITION_TOLERANCE_M = 8.0
NAV_SAFE_IN_DEGRADED = False
NAV_SAFE_IN_SHORT_DEAD_RECKONING = False
```

These are conservative software defaults and require bench testing, field walking, vehicle tests, and flight validation.

## E. Failsafe Matrix

| Failure | Behavior |
| --- | --- |
| GPS good + AHRS good + baro good | `GOOD`, GPS-corrected horizontal state, baro altitude, AHRS heading |
| GPS bad + AHRS good + baro good | `DEGRADED`, then `GPS_LOST`; bounded prediction from last VN/VE, baro and AHRS continue |
| GPS outage longer than timeout | `UNRELIABLE`, `navigation_valid=False`, `safe_for_guidance=False` |
| GPS recovery | `RECOVERING` until multiple valid samples and bounded convergence |
| AHRS bad + GPS good | Position remains usable; heading falls back to GPS course only above minimum speed |
| Barometer bad + GPS/AHRS good | Horizontal navigation continues; altitude quality becomes `DEGRADED` |
| GPS + AHRS bad + baro good | Brief bounded horizontal prediction, altitude continues, heading invalid |
| All navigation sensors bad | `UNRELIABLE`, guidance marked unsafe, payload workers remain alive |

## F. Test Results

Software tests run on 2026-09-02 with the bundled Python runtime:

```text
python -B tests/test_navigation_estimator.py
python -B tests/test_gps.py
python -B tests/test_imu.py
python -B tests/test_barometer.py
python -B tests/test_camera.py
python -B tests/test_telemetry.py
python -B tests/test_ahrs.py
python -B tests/test_diagnostics.py
python -B tests/test_flight_state_machine.py
python -B tests/test_fake_mapping.py
python -B tests/test_full_simulation.py
```

Result: passed.

`tests/test_full_simulation.py` now starts the Navigation worker and asserts that the estimator publishes a nonzero estimated position. It passed using the built-in HTML/KML mapping fallbacks because the bundled runtime does not include `folium` or `simplekml`.

Hardware tests were not run because the Pi/HAT sensors were not attached to this machine.

## G. Benchmark

`tests/test_navigation_estimator.py` ran 10,000 synthetic updates:

```text
mean = 0.1756 ms
p95  = 0.2185 ms
p99  = 1.6218 ms
max  = 67.3330 ms
```

At 20 Hz, the available period is 50 ms. Mean and p95 are still far below the period; the maximum result included a Windows scheduling spike on the development laptop and should be remeasured on the Raspberry Pi flight computer.

## H. Remaining Risks

- GPS multipath
- GPS antenna orientation
- Crosswind causing heading/course separation
- Barometric drift
- Pressure disturbances around the airframe
- AHRS magnetic error
- Temporary I2C/UART errors
- Scheduler jitter
- Dead-reckoning drift
- Threshold tuning

## I. Flight Recommendation

Status: `BENCH_ONLY`.

The estimator is implemented and software-tested, but it is not `FIELD_TEST_READY` until Raspberry Pi sensor bring-up and outdoor static/walking tests are run. It is not `FLIGHT_READY` until field results and vehicle/flight validation prove the thresholds and recovery behavior.

## J. Field Test Command

```bash
python hardware_tests/navigation_field_test.py --seconds 60
python hardware_tests/navigation_field_test.py --seconds 90 --simulate-gps-loss-after 30 --simulate-gps-loss-seconds 5
```
