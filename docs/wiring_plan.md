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
| SDA | GPIO2 | Pin 3 | `SDA_BNO`, `SDA_Servo`, `SDA_INA` |
| SCL | GPIO3 | Pin 5 | `SCL_BNO`, `SCL_Servo`, `SCL_INA` |
| 3.3 V | - | Pin 1 | Logic power |
| GND | - | Pin 6 | Common ground |

- BNO085 IMU, PCA9685 servo controller, and INA219 current sensor share the I2C bus.
- BNO085 default address is `0x4A`.
- Verify addresses with `i2cdetect -y 1`.
- Check address jumpers if the PCA9685 and INA219 both appear at `0x40`.

## SPI Sensors

| Signal | Pi GPIO | Physical Pin | HAT Nets |
|--------|---------|--------------|----------|
| MOSI | GPIO10 | Pin 19 | `MOSI_BMP`, `MOSI_GPS` |
| MISO | GPIO9 | Pin 21 | `MISO_BMP`, `MISO_GPS` |
| SCLK | GPIO11 | Pin 23 | `SCK_BMP`, `SCK_GPS` |
| BMP388 CS | GPIO8 | Pin 24 | `CS_BMP` |
| BMP388 INT | GPIO17 | Pin 11 | `INT_BMP` |

- Enable SPI in `raspi-config`.
- BMP388 and the SC16IS750 GPS bridge use SPI. BNO085 remains on I2C1 in the
  current payload runtime config.

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

## ULN2003 Stepper

| Function | GPIO | Physical Pin |
|----------|------|--------------|
| IN1 | GPIO25 | Pin 22 |
| IN2 | GPIO24 | Pin 18 |
| IN3 | GPIO23 | Pin 16 |
| IN4 | GPIO18 | Pin 12 |

## XBee Telemetry

| Signal | Pi GPIO | Physical Pin | HAT Net |
|--------|---------|--------------|---------|
| Pi TXD | GPIO14 | Pin 8 | telemetry radio RX |
| Pi RXD | GPIO15 | Pin 10 | telemetry radio TX |
| 5 V | - | Pin 2/4 rail | XBee/telemetry radio power as designed |
| GND | - | Ground rail | Common ground |

Disable the Raspberry Pi serial console before using GPIO14/GPIO15 for XBee
telemetry.

## GPS

- The HAT schema uses the primary UART pins for XBee telemetry.
- Keep GPS on the SC16IS750 UART-over-SPI bridge at SPI0 CE1/GPIO7 unless
  `GPS_TRANSPORT` is deliberately changed for bench debugging.

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
- [ ] SPI enabled and BMP388 CS on GPIO8 plus SC16IS750 CS on GPIO7 connected
- [ ] XBee UART data visible after serial console is disabled
- [ ] Camera preview working
- [ ] Servos powered from HAT/external 5 V rail, not Pi logic power
- [ ] All grounds tied together
