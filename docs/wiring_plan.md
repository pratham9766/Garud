# Wiring Plan

Raspberry Pi 4 and GARUDA HAT connections for the Ground Mapping Payload.

## Power

- Raspberry Pi 4: 5 V / 3 A USB-C supply during development.
- HAT power input: 5 V through the protected HAT power path and connector J4.
- Servos: use the HAT servo power rail or an external 5 V servo supply sized for stall current.
- Common ground between Pi, HAT, servo supply, telemetry, and all sensors.

## I2C Bus

| Signal | Pi GPIO | Physical Pin | HAT Net |
|--------|---------|--------------|---------|
| SDA | GPIO2 | Pin 3 | `SDA_Servo`, `SDA_INA` |
| SCL | GPIO3 | Pin 5 | `SCL_Servo`, `SCL_INA` |
| 3.3 V | - | Pin 1 | Logic power |
| GND | - | Pin 6 | Common ground |

- PCA9685 servo controller and INA219 current sensor share the I2C bus.
- Verify addresses with `i2cdetect -y 1`.
- Check address jumpers if the PCA9685 and INA219 both appear at `0x40`.

## SPI Sensors

| Signal | Pi GPIO | Physical Pin | HAT Nets |
|--------|---------|--------------|----------|
| MOSI | GPIO10 | Pin 19 | `MOSI_BMP`, `MOSI_BNO` |
| MISO | GPIO9 | Pin 21 | `MISO_BMP`, `MISO_BNO` |
| SCLK | GPIO11 | Pin 23 | `SCK_BMP`, `SCK_BNO` |
| BMP388 CS | GPIO22 | Pin 15 | `CS_BMP` |
| BMP388 INT | GPIO17 | Pin 11 | `INT_BMP` |
| BNO085 CS | GPIO5 | Pin 29 | `CS_BNO` |
| BNO085 RST | GPIO6 | Pin 31 | `RST_BNO` |
| BNO085 INT | GPIO27 | Pin 13 | `INT_BNO` |

- Enable SPI in `raspi-config`.
- The schema labels BNO085 and BMP388 as SPI devices; do not wire them to the old I2C-only sensor plan.

## Servo Gimbal

| Function | Connection |
|----------|------------|
| Servo controller | PCA9685 on I2C |
| Output enable | GPIO4 / physical pin 7 (`OE_Servo`) |
| Pan channel | `config.GIMBAL_PAN_CHANNEL` |
| Tilt channel | `config.GIMBAL_TILT_CHANNEL` |
| Servo power | HAT servo power rail / external 5 V |
| Ground | Common GND |

Use `hardware_tests/test_servo_real.py` for one channel and `hardware_tests/test_gimbal_real.py` for the 2-axis sweep.

## LoRa Telemetry

| Signal | Pi GPIO | Physical Pin | HAT Net |
|--------|---------|--------------|---------|
| Pi TXD | GPIO14 | Pin 8 | `RX_Lora` |
| Pi RXD | GPIO15 | Pin 10 | `TX_Lora` |
| AUX | GPIO25 | Pin 22 | `AUX_Lora` |
| M0 | GPIO23 | Pin 16 | `M0` |
| M1 | GPIO24 | Pin 18 | `M1` |
| 5 V | - | Pin 2/4 rail | LoRa power as designed |
| GND | - | Ground rail | Common ground |

Disable the Raspberry Pi serial console before using GPIO14/GPIO15 for LoRa.

## GPS

- The HAT schema uses the primary UART pins for LoRa telemetry.
- Keep GPS on USB-UART (`GPS_PORT`, default `/dev/ttyUSB0`) unless you add a separate UART path.

## Camera

- Raspberry Pi HQ Camera or Arducam HQ Camera via CSI ribbon cable.
- Connector: `CAMERA` port on Pi board.
- Enable camera support and verify with `hardware_tests/test_camera_real.py`.

## Buzzer And Status LED

| Function | GPIO | Physical Pin | Notes |
|----------|------|--------------|-------|
| Buzzer | GPIO16 | Pin 36 | Drives Q1 buzzer transistor |
| Status LED | GPIO26 | Pin 37 | HAT LED through resistor |

## Wiring Checklist

- [ ] Pi powered and booting
- [ ] HAT 5 V and 3.3 V rails present
- [ ] I2C devices visible (`i2cdetect -y 1`)
- [ ] SPI enabled and BNO085/BMP388 chip-select lines connected
- [ ] LoRa UART data visible after serial console is disabled
- [ ] Camera preview working
- [ ] Servos powered from HAT/external 5 V rail, not Pi logic power
- [ ] All grounds tied together
