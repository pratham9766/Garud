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
# SPI0 bus (BMP388 + SC16IS750 GPS bridge, separate CE lines)
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
# Pin mapping from the HAT schematic:
#     IN1=GPIO25, IN2=GPIO24, IN3=GPIO23, IN4=GPIO18
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

# ---------------------------------------------------------------- #
# XBee (DigiXbee3), one-way UART link
# Wired to Pi primary UART: GPIO14/TXD0 (pin 8) -> XBee DIN,
# XBee DOUT -> GPIO15/RXD0 (pin 10). See Garud_HAT.kicad_sch (XRX/XTX).
# ---------------------------------------------------------------- #
XBEE_SERIAL_PORT = "/dev/ttyAMA0"   # wired GPIO14/15 -> verified via AT probe (NOT /dev/serial0 on this Pi 5 image)
XBEE_BAUDRATE = 9600                # matched to XBee device config (XCTU)
XBEE_TX_INTERVAL = 1.0              # seconds between telemetry frames (1 Hz)

# ---------------------------------------------------------------- #
# GPS - u-blox NEO-M8N via SC16IS750 UART-to-SPI bridge
# SC16IS750 hangs off SPI0.CE1 (GPIO7, header pin 26) sharing the
# bus with BMP388 (CE0/GPIO8). UART side:
#     SC16IS750.TXA -> M8N.RX, SC16IS750.RXA <- M8N.TX
#     3.3V logic only (M8N VCC 2.7-3.6V; never feed 5V to VCC).
# See libraries/sensors/sc16is750.py + gps_m8n.py.
# ---------------------------------------------------------------- #
GPS_SC16IS750_CS_PIN = board.D7        # GPIO7 - SPI0.CE1 (header pin 26)
GPS_SC16IS750_I2C_ADDRESS = 0x4D       # 7-bit I2C fallback addr (A1=A0=VSS strap,
                                       # scan-verified); requires mode strap HIGH
                                       # (I2C mode) + SDA/SCL on GPIO2/3
GPS_BAUDRATE = 9600                    # NEO-M8N default, 8N1
GPS_SC16IS750_CRYSTAL_HZ = 14_745_600  # module crystal; some modules use 1_843_200 / 3_072_000
GPS_PPS_PIN = board.D17                # optional 1PPS time pulse input (free GPIO)
GPS_NMEA_TIMEOUT_S = 60                # max wait for a checksum-valid GGA/RMC sentence

# ---------------------------------------------------------------- #
# Camera gimbal (orientation-hold stabilization)
# BNO085 gyro -> 28BYJ-48 roll stage (stepper) + positional servo
# on PCA9685 channel 0. Mounting (IMU frame): optical axis = Z
# (stepper roll axis s1 = Z), servo shaft = Y at zero roll (s2z).
# Servo axis is nested in the roll stage, so its body-frame direction
# rotates with the current roll - we project the gyro onto the
# current axes each tick (see actuators/gimbal.py).
# ---------------------------------------------------------------- #
GIMBAL_LOOP_HZ = 100                # control tick rate
GIMBAL_STEPS_PER_DEG = 2048.0 / 360.0   # 28BYJ-48: 2048 double-steps/rev
GIMBAL_MAX_STEPS_PER_TICK = 5       # caps speed at ~90 deg/s @ 2ms/step
GIMBAL_ROLL_AXIS = (0.0, 0.0, 1.0)  # s1: stepper roll axis in IMU frame
GIMBAL_SERVO_AXIS_ZERO = (0.0, 1.0, 0.0)  # s2 direction at theta1 = 0
GIMBAL_ROLL_SIGN = -1               # flip if gimbal amplifies roll
GIMBAL_ROLL_GAIN = 1.0              # 1.0 = exact counter-rotation; >1 stiffer
GIMBAL_TILT_SIGN = 1                # flip if leveling error drives AWAY from 0
GIMBAL_SERVO_CHANNEL = 0
GIMBAL_SERVO_CENTER = 90.0
GIMBAL_SERVO_MIN = 0.0
GIMBAL_SERVO_MAX = 180.0
GIMBAL_DEADBAND_DPS = 0.2           # ignore gyro rates below (deg/s)
GIMBAL_FILTER_ALPHA = 0.4           # 1st-order low-pass on gyro (0-1)
GIMBAL_UNWIND_LIMIT_DEG = 360.0     # reset roll stage past this to protect the CSI cable
GIMBAL_SERVO_P = 6.0                # leveling velocity gain (1/s, error decay)
GIMBAL_SERVO_RATE_LIMIT_DPS = 60.0  # max servo slew rate (deg/s)
GIMBAL_ACCEL_ALPHA = 0.2            # low-pass alpha on accelerometer (gravity vec)
