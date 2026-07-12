# Wiring Plan

Raspberry Pi 4 GPIO and peripheral connections for the Ground Mapping Payload.

## Power

- Raspberry Pi 4: 5 V / 3 A USB-C supply (official adapter recommended).
- Servos: **External 5 V BEC** — do NOT power servos from the Pi 5 V pin.
- Common ground between Pi, servo supply, and all peripherals.

## I2C Bus (Barometer + IMU)

| Signal | Pi GPIO | Physical Pin |
|--------|---------|--------------|
| SDA | GPIO2 | Pin 3 |
| SCL | GPIO3 | Pin 5 |
| 3.3 V | — | Pin 1 |
| GND | — | Pin 6 |

- Connect barometer and IMU in parallel on the same I2C bus.
- Use distinct I2C addresses (configure in `config.py`).
- Add 2.2 kΩ–4.7 kΩ pull-ups if not on breakout boards.

## UART (GPS)

| Signal | Pi GPIO | Physical Pin |
|--------|---------|--------------|
| TX | GPIO14 | Pin 8 |
| RX | GPIO15 | Pin 10 |
| GND | — | Pin 6 |

**Phase 1 (development):** GPS via USB-UART adapter → `/dev/ttyUSB0`  
**Phase 2 (flight):** Direct UART wiring; disable serial console in `raspi-config`.

## Camera

- Raspberry Pi HQ Camera or Arducam HQ Camera via **CSI ribbon cable**.
- Connector: `CAMERA` port on Pi board (label facing Ethernet port).
- Enable camera in `raspi-config` → Interface Options → Camera.

## Servo Gimbal (2-axis)

| Servo | Signal GPIO | Notes |
|-------|-------------|-------|
| Pitch | GPIO18 (Pin 12) | PWM-capable |
| Roll | GPIO19 (Pin 35) | PWM-capable |
| VCC | External 5 V | From BEC |
| GND | Common GND | Shared with Pi |

Use hardware PWM (pigpio) for stable servo timing.

## XBee Telemetry

**Phase 1:** XBee USB adapter → `/dev/ttyUSB1`  
**Phase 2:** XBee Explorer wired to spare UART or USB adapter.

| XBee Pin | Connection |
|----------|------------|
| DOUT | Pi RX (or USB RX) |
| DIN | Pi TX (or USB TX) |
| GND | Common GND |
| VCC | 3.3 V (check module spec) |

## SD Card / Storage

- High-endurance microSD (32 GB+ recommended).
- Logs: `data/logs/`
- Images: `data/images/`
- Maps: `data/maps/`

## Future: Steering (Parachute / Glider)

`ENABLE_STEERING = False` in `config.py` until hardware is ready.  
Reserve GPIO pins for steering servos (document in `pin_map.md` before wiring).

## Wiring Checklist

- [ ] Pi powered and booting
- [ ] I2C devices visible (`i2cdetect -y 1`)
- [ ] GPS NMEA sentences on serial port
- [ ] Camera preview working
- [ ] Servos on external 5 V, signal on GPIO
- [ ] XBee loopback / ground station receive
- [ ] All grounds tied together
