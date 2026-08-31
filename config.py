"""
Central pin, bus, sensor, and runtime configuration for the GARUDA payload.

Pin mapping follows the working Garud HAT setup:

    BNO085 (IMU)         - I2C1 : SDA=GPIO2, SCL=GPIO3
    PCA9685 (Servo drv)  - I2C1 : SDA=GPIO2, SCL=GPIO3, OE=GPIO4
    BMP388 (Baro)        - SPI0 : MISO=GPIO9, MOSI=GPIO10, SCK=GPIO11, CS=GPIO8
    SC16IS750 GPS bridge - SPI0 : shared SPI0, CS=GPIO7
    ULN2003 (Stepper)    - GPIO : IN1=GPIO25, IN2=GPIO24, IN3=GPIO23, IN4=GPIO18
    Buzzer               - GPIO16

Only edit values here; runtime modules import this file so the project stays
in sync with the tested sensor setup.
"""

from pathlib import Path

try:
    import board
except (ImportError, NotImplementedError):
    board = None


def _board_pin(name: str, bcm: int):
    """Return a Blinka board pin on hardware, or the BCM number off-target."""
    if board is None:
        return bcm
    return getattr(board, name)

# ---------------------------------------------------------------------------
# Module enable flags
# ---------------------------------------------------------------------------
ENABLE_CAMERA = False
ENABLE_GPS = False
ENABLE_IMU = True
ENABLE_BAROMETER = True
ENABLE_GIMBAL = True
ENABLE_TELEMETRY = False
ENABLE_MAPPING = True
ENABLE_LOGGING = True
ENABLE_STEERING = False  # Future: parachute/glider steering
ENABLE_POST_FLIGHT_PROCESSING = True
PAUSE_STATE_TRANSITIONS = True

# ---------------------------------------------------------------------------
# AHRS attitude estimation
# ---------------------------------------------------------------------------
ENABLE_AHRS = True
AHRS_MODE = "BNO085"  # OFF, BNO085, MADGWICK, MAHONY, AUTO
AHRS_RATE_HZ = 100
AHRS_USE_MAGNETOMETER = True
AHRS_ACCEL_REJECTION_ENABLED = True
AHRS_MAG_REJECTION_ENABLED = True
AHRS_MAX_SAMPLE_AGE_MS = 250.0
AHRS_MIN_DT_SEC = 0.001
AHRS_MAX_DT_SEC = 0.25
AHRS_FAIL_COUNT_THRESHOLD = 5
AHRS_RECOVERY_COUNT_THRESHOLD = 20
AHRS_MADGWICK_BETA = 0.08
AHRS_MAHONY_KP = 0.6
AHRS_MAHONY_KI = 0.02
AHRS_MAHONY_BIAS_LIMIT_RADS = 0.2
AHRS_ACCEL_NORM_MIN_G = 0.70
AHRS_ACCEL_NORM_MAX_G = 1.30
AHRS_MAG_NORM_MIN_UT = 15.0
AHRS_MAG_NORM_MAX_UT = 85.0
AHRS_MAX_ANGULAR_JUMP_DEG = 120.0
AHRS_BNO085_DEGRADED_ACCURACY_RAD = 0.6
AHRS_AUTO_SOFTWARE_FALLBACK = "MADGWICK"
AHRS_INIT_TIMEOUT_SEC = 2.0
IMU_TO_BODY_QUATERNION = (1.0, 0.0, 0.0, 0.0)

# ---------------------------------------------------------------------------
# Runtime hardware mode
# ---------------------------------------------------------------------------
USE_MOCK_HARDWARE = False

# ---------------------------------------------------------------------------
# Timing intervals (seconds)
# ---------------------------------------------------------------------------
IMAGE_CAPTURE_INTERVAL_SEC = 2.0
SENSOR_LOG_INTERVAL_SEC = 1.0
TELEMETRY_INTERVAL_SEC = 1.0

# ---------------------------------------------------------------------------
# Serial / I2C / SPI hardware settings (used when USE_MOCK_HARDWARE = False)
# ---------------------------------------------------------------------------
# Tested GARUDA HAT connections:
#   BNO085 + PCA9685 + INA219: I2C1 on GPIO2/GPIO3
#   BMP388: SPI0 on GPIO9/GPIO10/GPIO11 with CS=GPIO8
#   GPS M8N: SC16IS750 UART bridge on SPI0 CE1/GPIO7
#   XBee3: Pi primary UART on GPIO14/GPIO15
GPS_TRANSPORT = "SC16IS750_SPI"
GPS_PORT = "SC16IS750@SPI0.CE1"
XBEE_SERIAL_PORT = "/dev/ttyAMA0"
XBEE_PORT = XBEE_SERIAL_PORT
GPS_BAUDRATE = 9600
XBEE_BAUDRATE = 9600
XBEE_TX_INTERVAL = TELEMETRY_INTERVAL_SEC

BNO085_TRANSPORT = "I2C"
BNO085_I2C_ADDRESS = 0x4A
IMU_ADDRESS = BNO085_I2C_ADDRESS
BAROMETER_ADDRESS = None

# GARUDA HAT schema pin map (Raspberry Pi BCM numbering)
I2C_SDA_PIN = 2
I2C_SCL_PIN = 3
I2C_SDA = _board_pin("SDA", I2C_SDA_PIN)
I2C_SCL = _board_pin("SCL", I2C_SCL_PIN)

SPI_MOSI_PIN = 10
SPI_MISO_PIN = 9
SPI_SCLK_PIN = 11
SPI_MOSI = _board_pin("MOSI", SPI_MOSI_PIN)
SPI_MISO = _board_pin("MISO", SPI_MISO_PIN)
SPI_SCK = _board_pin("SCK", SPI_SCLK_PIN)

SERVO_OE_PIN = 4
PCA9685_OE_PIN = _board_pin("D4", SERVO_OE_PIN)
PCA9685_I2C_ADDRESS = 0x40
PCA9685_PWM_FREQ = 50
SERVO_CONTROLLER_ADDRESS = PCA9685_I2C_ADDRESS
GIMBAL_PAN_CHANNEL = 0
GIMBAL_TILT_CHANNEL = 1

BMP388_CS_PIN = 8
BMP388_CS = _board_pin("D8", BMP388_CS_PIN)
BMP388_INT_PIN = 17

GPS_SC16IS750_CS_PIN = 7
GPS_SC16IS750_CS = _board_pin("D7", GPS_SC16IS750_CS_PIN)
GPS_SC16IS750_I2C_ADDRESS = 0x4D
GPS_SC16IS750_CRYSTAL_HZ = 14_745_600
GPS_NMEA_TIMEOUT_S = 60
GPS_PPS_PIN = 17

# Retained for SPI bench experiments only. Payload runtime defaults to BNO085
# on I2C1 (GPIO2/GPIO3) at BNO085_I2C_ADDRESS.
BNO085_CS_PIN = None
BNO085_RST_PIN = None
BNO085_INT_PIN = None
BNO085_CS = None
BNO085_RST = None
BNO085_INT = None
BNO085_ROTATION_MODE = "ROTATION_VECTOR"  # or "GAME_ROTATION_VECTOR" if supported cleanly

ULN2003_IN1_PIN = 25
ULN2003_IN2_PIN = 24
ULN2003_IN3_PIN = 23
ULN2003_IN4_PIN = 18
ULN2003_IN1 = _board_pin("D25", ULN2003_IN1_PIN)
ULN2003_IN2 = _board_pin("D24", ULN2003_IN2_PIN)
ULN2003_IN3 = _board_pin("D23", ULN2003_IN3_PIN)
ULN2003_IN4 = _board_pin("D18", ULN2003_IN4_PIN)
STEPPER_STEP_DELAY = 0.002

LORA_TX_PIN = 14
LORA_RX_PIN = 15
LORA_AUX_PIN = 25
LORA_M0_PIN = 23
LORA_M1_PIN = 24

BUZZER_PIN = 16
STATUS_LED_PIN = 26

# ---------------------------------------------------------------------------
# Storage paths (relative to project root)
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent
IMAGE_SAVE_PATH = PROJECT_ROOT / "data" / "images"
LOG_SAVE_PATH = PROJECT_ROOT / "data" / "logs"
MAP_SAVE_PATH = PROJECT_ROOT / "data" / "maps"

# ---------------------------------------------------------------------------
# Mission simulation (pre-hardware)
# ---------------------------------------------------------------------------
SIMULATION_DURATION_SEC = 30.0
SIMULATION_DESCENT_START_SEC = 5.0

# Pune reference coordinates for mock GPS
MOCK_GPS_LAT = 18.5204
MOCK_GPS_LON = 73.8567
MOCK_START_ALTITUDE_M = 700.0

# Gimbal servo limits (degrees)
GIMBAL_PITCH_MIN = -45
GIMBAL_PITCH_MAX = 45
GIMBAL_ROLL_MIN = -45
GIMBAL_ROLL_MAX = 45
GIMBAL_SERVO_MIN = 0.0
GIMBAL_SERVO_MAX = 180.0
GIMBAL_SERVO_CENTER = 90.0

# The gimbal now damps large swings and keeps the camera roughly nadir-facing.
# It is not expected to remove all roll/yaw from images.
GIMBAL_POSE_DAMPING_GAIN = 0.35
GIMBAL_MAX_COMMAND_STEP_DEG = 8.0

# ---------------------------------------------------------------------------
# Mapping / camera footprint model
# ---------------------------------------------------------------------------
# Approximate camera field of view. Tune these values for the actual lens.
CAMERA_HORIZONTAL_FOV_DEG = 62.2
CAMERA_VERTICAL_FOV_DEG = 48.8
CAMERA_SENSOR_WIDTH_PX = 4056
CAMERA_SENSOR_HEIGHT_PX = 3040
CAMERA_FOCAL_LENGTH_PX = 3100.0
CAMERA_CENTER_X_PX = CAMERA_SENSOR_WIDTH_PX / 2.0
CAMERA_CENTER_Y_PX = CAMERA_SENSOR_HEIGHT_PX / 2.0
CAMERA_DISTORTION_COEFFS = [0.0, 0.0, 0.0, 0.0, 0.0]
CAMERA_BACKEND = "AUTO"  # AUTO, PICAMERA2, or OPENCV
CAMERA_DEVICE_INDEX = 0
CAMERA_FRAME_WIDTH = 1280
CAMERA_FRAME_HEIGHT = 720

# Altitudes lower than this are ignored for footprint sizing to avoid zero-area
# polygons when the payload has landed.
MAPPING_MIN_FOOTPRINT_ALTITUDE_M = 2.0

# Cell size for approximate unique coverage estimation.
MAPPING_COVERAGE_GRID_M = 5.0

# Post-flight reconstruction profiles and resource limits. These settings are
# only used by processing/*, vision/*, mapping/*, and storage/* modules.
MAPPING_DEFAULT_PROFILE = "BALANCED"
MAPPING_MAX_WORKERS = 2
MAPPING_MAX_NEIGHBORS_PER_IMAGE = 8
MAPPING_TEMPORAL_NEIGHBORS = 2
MAPPING_MAX_ALTITUDE_RATIO = 2.5
MAPPING_MAX_GPS_DISTANCE_M = 250.0
MAPPING_MAX_TIME_SEPARATION_SEC = 20.0
MAPPING_MAX_YAW_DIFF_DEG = 80.0
MAPPING_MAX_ROLL_PITCH_DIFF_DEG = 45.0
MAPPING_MIN_PREDICTED_OVERLAP = 0.03
MAPPING_SPATIAL_GRID_M = 120.0
MAPPING_FEATURE_BACKEND = "SIFT"
MAPPING_FEATURE_MAX_DIM = 2048
MAPPING_PREVIEW_MAX_DIM = 640
MAPPING_FEATURE_MAX_FEATURES = 4000
MAPPING_MATCH_RATIO = 0.75
MAPPING_MIN_FILTERED_MATCHES = 12
MAPPING_MIN_GEOMETRIC_INLIERS = 10
MAPPING_MIN_INLIER_RATIO = 0.18
MAPPING_ENABLE_DENSE_RECONSTRUCTION = False
MAPPING_ENABLE_ORTHOMOSAIC = False
MAPPING_REFINE_FOCAL_LENGTH = False
MAPPING_REFINE_PRINCIPAL_POINT = False
MAPPING_REFINE_DISTORTION = False
MAPPING_INTERPOLATE_SENSOR_TIMELINE = False
MAPPING_CACHE_VERSION = "v1"
POSTFLIGHT_SAVE_PATH = PROJECT_ROOT / "data" / "postflight"

# Post-flight image quality thresholds.
QUALITY_BLUR_MIN_VARIANCE = 80.0
QUALITY_EXPOSURE_LOW = 35.0
QUALITY_EXPOSURE_HIGH = 220.0
QUALITY_MAX_TILT_DEG = 35.0
QUALITY_MAX_ANGULAR_RATE_DPS = 120.0
QUALITY_CLIPPED_SHADOW_FRACTION = 0.15
QUALITY_CLIPPED_HIGHLIGHT_FRACTION = 0.15
QUALITY_GOOD_MIN_SCORE = 0.70
QUALITY_MARGINAL_MIN_SCORE = 0.40

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_LEVEL = "INFO"
