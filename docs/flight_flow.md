# Flight Flow

Mission state machine for the Ground Mapping Payload.

## State Diagram

```
┌──────┐     ┌──────┐     ┌─────────┐     ┌────────┐
│ BOOT │ ──► │ IDLE │ ──► │ DESCENT │ ──► │ LANDED │
└──────┘     └──────┘     └─────────┘     └────────┘
    │            │              │
    └────────────┴──────────────┴──► ERROR
```

## States

### BOOT

- System powers on.
- All subsystems initialize (or mock equivalents start).
- Shared data defaults set; health monitor begins polling.
- Duration: ~2 seconds (simulation).

### IDLE

- Payload is armed and waiting for release / descent trigger.
- Sensors actively logging; camera may capture periodically.
- Telemetry transmitting status packets.
- Duration: ~3 seconds (simulation) or until release detected.

### DESCENT

- Primary mapping phase.
- Camera captures images at `IMAGE_CAPTURE_INTERVAL_SEC`.
- GPS, AHRS/IMU, and barometer logged at `SENSOR_LOG_INTERVAL_SEC`.
- Gimbal stabilizer active (if enabled).
- Telemetry sent at `TELEMETRY_INTERVAL_SEC`.
- Mission clock (`mission_time`) running.
- Transitions to LANDED when barometric altitude ≤ 5 m (simulation) or landing detected.

### LANDED

- Mapping complete.
- Logging may continue briefly; threads stop on shutdown.
- Final CSV log used to generate HTML map and KML.

### ERROR

- Entered on unrecoverable subsystem failure.
- `status` field in shared data describes the fault (e.g. `GPS_ERROR`).
- Can transition back to BOOT after manual reset.

## Transitions (Simulation)

| From | To | Trigger |
|------|-----|---------|
| BOOT | IDLE | ~2 s elapsed |
| IDLE | DESCENT | ~3 s elapsed (or release signal) |
| DESCENT | LANDED | Altitude ≤ 5 m and mission_time > 10 s |
| Any | ERROR | Critical subsystem failure |

## Future Enhancements

- Release detection via accelerometer threshold
- Parachute/glider steering during DESCENT (`ENABLE_STEERING`)
- Auto-shutdown after LANDED to preserve battery
