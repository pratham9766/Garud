# Pin Map

Raspberry Pi 4 GPIO assignment for the Ground Mapping Payload.

## GPIO Summary

| Function | GPIO (BCM) | Physical Pin | Direction | Notes |
|----------|------------|--------------|-----------|-------|
| I2C SDA | GPIO2 | 3 | Bidirectional | Barometer + IMU |
| I2C SCL | GPIO3 | 5 | Output | Barometer + IMU |
| UART TX | GPIO14 | 8 | Output | GPS RX (phase 2) |
| UART RX | GPIO15 | 10 | Input | GPS TX (phase 2) |
| Gimbal Pitch | GPIO18 | 12 | Output (PWM) | Pitch servo signal |
| Gimbal Roll | GPIO19 | 35 | Output (PWM) | Roll servo signal |
| 3.3 V | — | 1, 17 | Power | I2C sensors |
| 5 V | — | 2, 4 | Power | Pi only (not servos) |
| GND | — | 6, 9, 14, 20, 25, 30, 34, 39 | Ground | Common ground rail |

## Reserved (Future Steering)

| Function | GPIO (BCM) | Physical Pin | Notes |
|----------|------------|--------------|-------|
| Steer Left | GPIO23 | 16 | `ENABLE_STEERING` |
| Steer Right | GPIO24 | 18 | `ENABLE_STEERING` |

## Non-GPIO Connections

| Component | Connection |
|-----------|------------|
| HQ Camera | CSI ribbon → CAMERA port |
| GPS (dev) | USB → `/dev/ttyUSB0` |
| XBee (dev) | USB → `/dev/ttyUSB1` |
| Servo power | External 5 V BEC |
| microSD | Internal slot |

## I2C Addresses (config.py)

| Device | Default Address |
|--------|-----------------|
| Barometer | `0x76` |
| IMU | `0x68` |

Verify with: `i2cdetect -y 1`

## Pinout Reference

```
        3.3V  (1) (2)  5V
      I2C SDA (3) (4)  5V
      I2C SCL (5) (6)  GND
             (7) (8)  UART TX
         GND (9) (10) UART RX
             (11)(12) Gimbal Pitch (GPIO18)
             (13)(14) GND
             (15)(16) Steer L (GPIO23) [future]
         3.3V (17)(18) Steer R (GPIO24) [future]
Gimbal Roll (19)(20) GND
             ...
```

Always verify pin numbers against the official Raspberry Pi pinout before wiring.
