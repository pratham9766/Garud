# Pin Map

Raspberry Pi 4 GPIO assignment for the GARUDA HAT payload schema (`Schema_Draft_2.pdf`).

## GPIO Summary

| Function | GPIO (BCM) | Physical Pin | Direction | Notes |
|----------|------------|--------------|-----------|-------|
| I2C SDA | GPIO2 | 3 | Bidirectional | `SDA_Servo`, `SDA_INA` |
| I2C SCL | GPIO3 | 5 | Output | `SCL_Servo`, `SCL_INA` |
| Servo OE | GPIO4 | 7 | Output | PCA9685 output enable, `OE_Servo` |
| LoRa TXD | GPIO14 | 8 | Output | Pi TX to LoRa `RX_Lora` |
| LoRa RXD | GPIO15 | 10 | Input | Pi RX from LoRa `TX_Lora` |
| BMP388 INT | GPIO17 | 11 | Input | `INT_BMP` |
| BMP388 CS | GPIO22 | 15 | Output | `CS_BMP` |
| LoRa M0 | GPIO23 | 16 | Output | LoRa mode select `M0` |
| LoRa M1 | GPIO24 | 18 | Output | LoRa mode select `M1` |
| SPI MOSI | GPIO10 | 19 | Output | `MOSI_BMP`, `MOSI_BNO` |
| SPI MISO | GPIO9 | 21 | Input | `MISO_BMP`, `MISO_BNO` |
| SPI SCLK | GPIO11 | 23 | Output | `SCK_BMP`, `SCK_BNO` |
| LoRa AUX | GPIO25 | 22 | Input | `AUX_Lora` |
| BNO085 CS | GPIO5 | 29 | Output | `CS_BNO` |
| BNO085 RST | GPIO6 | 31 | Output | `RST_BNO` |
| BNO085 INT | GPIO27 | 13 | Input | `INT_BNO` |
| Buzzer | GPIO16 | 36 | Output | Drives buzzer transistor |
| Status LED | GPIO26 | 37 | Output | HAT status LED |
| 3.3 V | - | 1, 17 | Power | Logic and sensors |
| 5 V | - | 2, 4 | Power | HAT input and servo rail as designed |
| GND | - | 6, 9, 14, 20, 25, 30, 34, 39 | Ground | Common ground rail |

## Not Used By Current Schema

| GPIO (BCM) | Physical Pin | Notes |
|------------|--------------|-------|
| GPIO18 | 12 | Not used for direct servo PWM in this HAT schema |
| GPIO8 | 24 | Unconnected in schematic |
| GPIO12 | 32 | Unconnected in schematic |
| GPIO13 | 33 | Unconnected in schematic |
| GPIO19 | 35 | Unconnected in schematic |
| GPIO20 | 38 | Unconnected in schematic |
| GPIO21 | 40 | Unconnected in schematic |

## Connector Summary

| Connector / Module | Signals |
|--------------------|---------|
| J2 Servo Control | 3.3 V, GND, `OE_Servo`, `SCL_Servo`, `SDA_Servo` |
| J3 Telemetry | 5 V, GND, `M0`, `M1`, `RX_Lora`, `TX_Lora`, `AUX_Lora` |
| J4 Power | 5 V input and GND through protected HAT power path |
| BNO085 | SPI: `SCK_BNO`, `MOSI_BNO`, `MISO_BNO`, plus `CS_BNO`, `RST_BNO`, `INT_BNO` |
| BMP388 | SPI: `SCK_BMP`, `MOSI_BMP`, `MISO_BMP`, plus `CS_BMP`, `INT_BMP` |
| INA219 | I2C: `SCL_INA`, `SDA_INA`; current sense on 5 V rail |

## I2C Devices

| Device | Default Address |
|--------|-----------------|
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
   BMP388 INT (11)(12) NC
   BNO085 INT (13)(14) GND
    BMP388 CS (15)(16) LoRa M0
        3.3V (17)(18) LoRa M1
     SPI MOSI (19)(20) GND
     SPI MISO (21)(22) LoRa AUX
     SPI SCLK (23)(24) NC
         GND (25)(26) NC
       ID SDA (27)(28) ID SCL
    BNO085 CS (29)(30) GND
   BNO085 RST (31)(32) NC
          NC (33)(34) GND
          NC (35)(36) Buzzer (GPIO16)
  Status LED (37)(38) NC
         GND (39)(40) NC
```

Always verify pin numbers against the official Raspberry Pi pinout before wiring.
