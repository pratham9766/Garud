# Garud HAT - Sensor & Actuator Integration

Modular Python codebase for the MRIC CanSat, matching the pin-out in
`Garud_HAT.kicad_sch` / `Sensor_Connector_Sections_HAT.kicad_sch`.

## Wiring recap (as supplied)

| Device            | Bus  | Pins                                                        |
|-------------------|------|--------------------------------------------------------------|
| BNO085 (IMU)      | I2C1 | SDA=GPIO2, SCL=GPIO3                                          |
| BMP388 (Baro)     | SPI0 | MISO=GPIO9, MOSI=GPIO10, SCK=GPIO11, CS=GPIO8                 |
| PCA9685 (Servo)   | I2C1 | SDA=GPIO2, SCL=GPIO3, OE=GPIO4 (active-LOW)                   |
| ULN2003 (Stepper) | GPIO | IN1=GPIO25, IN2=GPIO24, IN3=GPIO23, IN4=GPIO18                |
| Buzzer            | GPIO | GPIO16 (through Q2 2N2222A)                                    |

I2C1 is shared between the BNO085 and PCA9685 - this is fine, they sit
at different addresses (`0x4A` and `0x40` by default).

## 1. Enable interfaces on the Pi

```bash
sudo raspi-config
# Interface Options -> I2C -> Enable
# Interface Options -> SPI -> Enable
sudo reboot
```

## 2. Install dependencies

```bash
cd cansat_hat
pip install -r requirements.txt --break-system-packages
```

## 3. Verify addresses (optional but recommended)

```bash
sudo i2cdetect -y 1
# Confirm BNO085 shows at 0x4A (or 0x4B) and PCA9685 at 0x40
```

If either address differs on your boards, update `config.py`.

## 4. Run

```bash
python3 test_codes/main.py
```

## Project layout

```
cansat_hat/
├── libraries/                # reusable driver / wrapper modules
│   ├── config.py             # all pin/address definitions (single source of truth)
│   ├── bus_manager.py        # shared I2C / SPI bus singletons
│   ├── xbee_link.py          # XBee UART link wrapper
│   ├── sensors/
│   │   ├── bno085_sensor.py  # IMU wrapper
│   │   └── bmp388_sensor.py  # barometer wrapper
│   └── actuators/
│       ├── servo_driver.py   # PCA9685 + OE control
│       ├── stepper_driver.py # ULN2003 stepper wrapper
│       ├── buzzer.py         # recovery beacon buzzer
│       └── gimbal.py         # orientation-hold gimbal controller
├── test_codes/               # all runnable scripts (tests + demos)
│   ├── main.py               # integration / telemetry loop
│   ├── test_all.py           # full integration test
│   ├── test_everything.py    # subsystem regression suite (PASS/FAIL)
│   ├── test_bno085_live.py   # live IMU stream
│   ├── test_bmp388_live.py   # live baro stream
│   ├── motor_emi_test.py     # motor EMI test (mag watch + CSV log)
│   ├── bno_calibrate.py      # guided BNO085 self-calibration
│   ├── gimbal_angle_test.py  # quaternion-accurate gimbal bench test
│   ├── gimbal_diag.py        # raw hardware + axis-mapping check
│   ├── gimbal_control.py     # standalone gimbal controller
│   └── transmit_telemetry.py # XBee telemetry transmitter
├── README.md
└── requirements.txt
```

Every script in `test_codes/` inserts `../libraries` on its own `sys.path`
at startup, so it runs from anywhere (no PYTHONPATH needed):

```bash
cd test_codes && python3 test_everything.py     # or from repo root:
python3 test_codes/test_everything.py
```

## Notes

- `PCA9685Driver` starts with outputs **disabled** (`/OE` HIGH) until
  `enable_outputs()` is called — a safety default so servos/ESCs don't
  twitch on power-up before your flight software is ready.
- `ULN2003Stepper.release()` de-energizes the stepper coils when idle
  to avoid unnecessary current draw / heat on battery power.
- Set `baro.set_sea_level_pressure(<local QNH>)` on the pad just
  before launch for accurate above-ground-level altitude readings.
- The BNO085 also supports UART-RVC and SPI modes if you ever need to
  move it off the shared I2C bus — the schematic breaks out `CS`/`INT`
  on `JP2` for that purpose.
