# Pin Map

Raspberry Pi 4 GPIO assignment for the GARUDA HAT payload schema (`Schema_Draft_2.pdf`).

## GPIO Summary

| Function | GPIO (BCM) | Physical Pin | Direction | Notes |
|----------|------------|--------------|-----------|-------|
| I2C SDA | GPIO2 | 3 | Bidirectional | `SDA_BNO`, `SDA_Servo`, `SDA_INA` |
| I2C SCL | GPIO3 | 5 | Output | `SCL_BNO`, `SCL_Servo`, `SCL_INA` |
| Servo OE | GPIO4 | 7 | Output | PCA9685 output enable, `OE_Servo` |
| XBee/LoRa TXD | GPIO14 | 8 | Output | Pi TX to telemetry radio RX |
| XBee/LoRa RXD | GPIO15 | 10 | Input | Pi RX from telemetry radio TX |
| BMP388 INT | GPIO17 | 11 | Input | `INT_BMP` |
| ULN2003 IN4 | GPIO18 | 12 | Output | Stepper driver input 4 |
| ULN2003 IN3 | GPIO23 | 16 | Output | Stepper driver input 3 |
| ULN2003 IN2 | GPIO24 | 18 | Output | Stepper driver input 2 |
| SPI MOSI | GPIO10 | 19 | Output | `MOSI_BMP` |
| SPI MISO | GPIO9 | 21 | Input | `MISO_BMP` |
| SPI SCLK | GPIO11 | 23 | Output | `SCK_BMP` |
| ULN2003 IN1 | GPIO25 | 22 | Output | Stepper driver input 1 |
| BMP388 CS | GPIO8 | 24 | Output | `CS_BMP` |
| Buzzer | GPIO16 | 36 | Output | Drives buzzer transistor |
| Status LED | GPIO26 | 37 | Output | HAT status LED |
| 3.3 V | - | 1, 17 | Power | Logic and sensors |
| 5 V | - | 2, 4 | Power | HAT input and servo rail as designed |
| GND | - | 6, 9, 14, 20, 25, 30, 34, 39 | Ground | Common ground rail |

## Not Used By Current Schema

| GPIO (BCM) | Physical Pin | Notes |
|------------|--------------|-------|
| GPIO12 | 32 | Unconnected in schematic |
| GPIO13 | 33 | Unconnected in schematic |
| GPIO19 | 35 | Unconnected in schematic |
| GPIO20 | 38 | Unconnected in schematic |
| GPIO21 | 40 | Unconnected in schematic |
| GPIO22 | 15 | Not used by the pasted HAT pin configuration |

## Connector Summary

| Connector / Module | Signals |
|--------------------|---------|
| J2 Servo Control | 3.3 V, GND, `OE_Servo`, `SCL_Servo`, `SDA_Servo` |
| Telemetry radio | 5 V, GND, Pi UART TX/RX on GPIO14/GPIO15 |
| J4 Power | 5 V input and GND through protected HAT power path |
| BNO085 | I2C1: `SCL_BNO`, `SDA_BNO`, default address `0x4A` |
| BMP388 | SPI: `SCK_BMP`, `MOSI_BMP`, `MISO_BMP`, plus `CS_BMP`, `INT_BMP` |
| INA219 | I2C: `SCL_INA`, `SDA_INA`; current sense on 5 V rail |
| ULN2003 | GPIO: IN1=GPIO25, IN2=GPIO24, IN3=GPIO23, IN4=GPIO18 |

## I2C Devices

| Device | Default Address |
|--------|-----------------|
| BNO085 IMU | `0x4A` |
| PCA9685 servo controller | `0x40` |
| INA219 current sensor | commonly `0x40`/`0x41` depending module address jumpers |

Verify with: `i2cdetect -y 1`

Note: if both PCA9685 and INA219 are on the same default I2C address, change one module's address jumpers before running the full payload.

## Pinout Reference

```
        3.3V  (1) (2)  5V
      I2C SDA (3) (4)  5V
      I2C SCL (5) (6)  GND
     Servo OE (7) (8)  LoRa RX input from Pi TX (GPIO14)
         GND (9) (10) LoRa TX output to Pi RX (GPIO15)
   BMP388 INT (11)(12) ULN2003 IN4
          NC (13)(14) GND
          NC (15)(16) ULN2003 IN3
        3.3V (17)(18) ULN2003 IN2
     SPI MOSI (19)(20) GND
     SPI MISO (21)(22) ULN2003 IN1
     SPI SCLK (23)(24) BMP388 CS
         GND (25)(26) NC
       ID SDA (27)(28) ID SCL
          NC (29)(30) GND
          NC (31)(32) NC
          NC (33)(34) GND
          NC (35)(36) Buzzer (GPIO16)
  Status LED (37)(38) NC
         GND (39)(40) NC
```

Always verify pin numbers against the official Raspberry Pi pinout before wiring.
