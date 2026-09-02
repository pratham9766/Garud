# Flight Flow

Mission state machine for the GARUDA payload.

The payload is expected to ascend with the rocket to roughly 1 km AGL. At
apogee the payload/CanSat is considered ejected. The glider parachute deploys
at 600 m AGL, and guidance actuations are enabled only after that deployment
state is confirmed.

## State Diagram

```text
BOOT
  -> DISARMED
  -> ARMED_PAD
  -> BOOST
  -> COAST
  -> APOGEE
  -> DESCENT_DROGUE
  -> GLIDER_DEPLOY
  -> GUIDED_DESCENT
  -> LANDED

ARMED_PAD/BOOST/COAST/APOGEE/DESCENT_* may enter ABORT.
```

## States

### BOOT

- Process starts and subsystems initialize.
- Runtime then enters `DISARMED`.

### DISARMED

- System is powered but not flight-ready.
- Real hardware should remain here until explicit arming is added from ground
  command handling.
- In mock mode, `AUTO_ARM_IN_MOCK_MODE` can move directly to `ARMED_PAD` for
  repeatable simulation.

### ARMED_PAD

- Payload is armed and waiting on the pad.
- Launch is detected by acceleration magnitude or altitude rise.

### BOOST

- Motor burn / high-acceleration phase.
- Barometric readings may be disturbed, so transition logic primarily waits for
  acceleration to fall below burnout threshold or a boost timeout.

### COAST

- Rocket coasts toward apogee.
- The controller tracks maximum altitude and watches for sustained descent.

### APOGEE

- Apogee has been detected.
- Payload/CanSat ejection is marked with `payload_ejected=True`.
- The system then enters descent after a short settle interval.

### DESCENT_DROGUE

- Payload is descending after apogee/ejection.
- Camera capture is allowed.
- The controller waits for confirmed descent below `GLIDER_DEPLOY_ALTITUDE_AGL_M`
  which defaults to 600 m AGL.

### GLIDER_DEPLOY

- Glider parachute deployment is marked with `glider_deployed=True`.
- This is represented as a state/event flag in software. Real deployment
  hardware should be connected through a dedicated actuator driver before use.

### GUIDED_DESCENT

- Guidance actuations are enabled with `actuation_enabled=True`.
- Mapping capture continues during descent.
- The state transitions to `LANDED` after sustained low altitude, low vertical
  velocity, and near-1g acceleration.

### LANDED

- Flight is complete.
- Actuation is disabled.
- Logs can be used for post-flight mapping outputs.

### ABORT

- Emergency state.
- The current Python implementation does not directly fire deployment hardware.
  It records the abort state and may transition to `LANDED` when landing is
  detected.

## Key Thresholds

| Setting | Value | Default Meaning |
| --- | --- |
| `TARGET_APOGEE_AGL_M` | `1000.0` | Expected apogee, about 1 km AGL |
| `GLIDER_DEPLOY_ALTITUDE_AGL_M` | `600.0` | Glider parachute deploy altitude |
| `STATE_CONFIRMATION_COUNT` | `5` | Default consecutive readings for confirmed transitions |
| `LAUNCH_DETECT_ACCEL_G` | `1.5` | Acceleration launch trigger |
| `LAUNCH_DETECT_ALTITUDE_AGL_M` | `30.0` | Backup altitude launch trigger |
| `BOOST_BURNOUT_ACCEL_G` | `1.5` | Burnout trigger when acceleration falls below this |
| `BOOST_MAX_DURATION_SEC` | `10.0` | Backup forced transition from boost to coast |
| `APOGEE_DESCENT_VELOCITY_MPS` | `-1.0` | Sustained downward velocity for apogee |
| `APOGEE_ALTITUDE_DROP_M` | `2.0` | Altitude drop below max altitude for apogee |
| `APOGEE_MIN_ALTITUDE_AGL_M` | `50.0` | Minimum altitude before apogee detection is accepted |
| `APOGEE_BACKUP_TIME_SEC` | `30.0` | Backup apogee trigger after launch |
| `GLIDER_DEPLOY_CONFIRMATION_COUNT` | `5` | Consecutive readings needed before glider deploy state |
| `GLIDER_DEPLOY_SETTLE_SEC` | `1.0` | Time to wait before guided descent begins |
| `LANDING_DETECT_ALTITUDE_AGL_M` | `20.0` | Low-altitude landing gate |
| `LANDING_DETECT_VELOCITY_MPS` | `1.0` | Maximum absolute vertical speed for landing |
| `LANDING_DETECT_TIME_SEC` | `5.0` | Time landing conditions must persist |
| `MAX_FLIGHT_TIME_SEC` | `600.0` | Maximum flight time before abort |

## Transition Constraints

| Transition | Constraint |
| --- | --- |
| `BOOT -> DISARMED` | No numeric sensor constraint. Happens when the controller starts. |
| `DISARMED -> ARMED_PAD` | Requires arming. In mock mode, `AUTO_ARM_IN_MOCK_MODE=True` can arm automatically. |
| `ARMED_PAD -> BOOST` | Confirmed 3 readings: acceleration `> 1.5 g` or altitude `> 30.0 m AGL`. |
| `BOOST -> COAST` | Confirmed 5 readings: acceleration `< 1.5 g`, or boost duration `> 10.0 s`. |
| `COAST -> APOGEE` | Confirmed 5 readings: vertical velocity `< -1.0 m/s`, altitude `< max_altitude - 2.0 m`, and altitude `> 50.0 m AGL`. Backup: time since launch `> 30.0 s`. |
| `APOGEE -> DESCENT_DROGUE` | Time in `APOGEE` is at least `1.0 s`. Marks payload ejection at apogee. |
| `DESCENT_DROGUE -> GLIDER_DEPLOY` | Confirmed 5 readings: altitude `<= 600.0 m AGL` and vertical velocity `< 0.0 m/s`. |
| `GLIDER_DEPLOY -> GUIDED_DESCENT` | Time in `GLIDER_DEPLOY` is at least `1.0 s`. Enables guidance actuations. |
| `GUIDED_DESCENT -> LANDED` | Conditions persist for `5.0 s`: altitude `< 20.0 m AGL`, absolute vertical velocity `< 1.0 m/s`, and acceleration between `0.8 g` and `1.2 g`. |
| `Active flight -> ABORT` | Manual/emergency abort, or time since launch `> 600.0 s`. |
| `ABORT -> LANDED` | Same landing detector as guided descent. |

## Bench Mode

`PAUSE_STATE_TRANSITIONS=True` keeps the automatic state machine paused during
hardware setup checks. Set it to `False` only when you want the runtime to use
live sensor values for flight-state transitions.

For operator-controlled on-ground testing, prefer:

```bash
python main.py --test-mode --real-hardware
```

This starts the normal sensor, gimbal, telemetry, logging, camera, and health
threads according to the enabled module flags, then opens a `garuda-test>`
console. Use `state <name>` or `next` to force states manually, `auto on` to
temporarily resume sensor-driven state transitions, `auto off` to pause them
again, and `quit` for a clean shutdown.

For a browser-based engineering console, run:

```bash
python hardware_tests/ground_station_dashboard.py --bench --real-hardware --host 0.0.0.0
```

This dashboard is started separately from `main.py`. It reads the same
`SharedData` state, records transition history and events, overlays event
markers on live plots, and shows a PASS/WARN/FAIL verification summary. Manual
state mutation is available in `--bench` and `--mock` modes; real flight-style
mode keeps manual mutation disabled unless explicitly allowed.
