"""
config.py
---------
Central pin & bus configuration for the MRIC CanSat "Garud HAT".

Pin mapping taken directly from Garud_HAT.kicad_sch /
Sensor_Connector_Sections_HAT.kicad_sch:

    BNO085 (IMU)        - I2C1   : SDA=GPIO2, SCL=GPIO3
    PCA9685 (Servo drv) - I2C1   : SDA=GPIO2, SCL=GPIO3, OE=GPIO4
    BMP388 (Baro)       - SPI0   : MISO=GPIO9, MOSI=GPIO10, SCK=GPIO11, CS=GPIO8
    ULN2003 (Stepper)   - GPIO   : IN1=GPIO25, IN2=GPIO24, IN3=GPIO23, IN4=GPIO18
    Buzzer              - GPIO16 (via Q2 2N2222A)

Only edit values here -- every other module imports from this file so the
whole project stays in sync with the schematic.
"""
import board

# ---------------------------------------------------------------- #
# I2C bus (shared by BNO085 and PCA9685 - both hang off GPIO2/3)
# ---------------------------------------------------------------- #
I2C_SDA = board.SDA    # GPIO2 / SDA1
I2C_SCL = board.SCL    # GPIO3 / SCL1

# ---------------------------------------------------------------- #
# SPI0 bus (BMP388)
# ---------------------------------------------------------------- #
SPI_SCK = board.SCK    # GPIO11 - SPI0.SCLK
SPI_MOSI = board.MOSI  # GPIO10 - SPI0.MOSI
SPI_MISO = board.MISO  # GPIO9  - SPI0.MISO
BMP388_CS_PIN = board.D8   # GPIO8  - SPI0.CE0

# ---------------------------------------------------------------- #
# BNO085 9-DOF IMU
# ---------------------------------------------------------------- #
BNO085_I2C_ADDRESS = 0x4A   # default; use 0x4B if ADR pin strapped high

# ---------------------------------------------------------------- #
# PCA9685 16-ch PWM / servo driver
# ---------------------------------------------------------------- #
PCA9685_I2C_ADDRESS = 0x40      # default (confirm with i2cdetect -y 1)
PCA9685_OE_PIN = board.D4       # GPIO4, active-LOW output enable
PCA9685_PWM_FREQ = 50           # Hz - standard analog servo rate

# ---------------------------------------------------------------- #
# ULN2003 unipolar stepper driver (e.g. 28BYJ-48)
# ---------------------------------------------------------------- #
ULN2003_IN1_PIN = board.D25
ULN2003_IN2_PIN = board.D24
ULN2003_IN3_PIN = board.D23
ULN2003_IN4_PIN = board.D18
STEPPER_STEP_DELAY = 0.002      # seconds between individual steps

# ---------------------------------------------------------------- #
# Buzzer (status / recovery beacon)
# ---------------------------------------------------------------- #
BUZZER_PIN = board.D16
