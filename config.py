"""
Configuration for the Ground Mapping Payload.

Toggle hardware modules ON/OFF here. Set USE_MOCK_HARDWARE = False when real
sensors and actuators are connected on the Raspberry Pi.
"""

from pathlib import Path

# ---------------------------------------------------------------------------
# Module enable flags
# ---------------------------------------------------------------------------
ENABLE_CAMERA = True
ENABLE_GPS = True
ENABLE_IMU = True
ENABLE_BAROMETER = True
ENABLE_GIMBAL = True
ENABLE_TELEMETRY = True
ENABLE_MAPPING = True
ENABLE_LOGGING = True
ENABLE_STEERING = False  # Future: parachute/glider steering

# ---------------------------------------------------------------------------
# Simulation mode (default until hardware arrives)
# ---------------------------------------------------------------------------
USE_MOCK_HARDWARE = True

# ---------------------------------------------------------------------------
# Timing intervals (seconds)
# ---------------------------------------------------------------------------
IMAGE_CAPTURE_INTERVAL_SEC = 2.0
SENSOR_LOG_INTERVAL_SEC = 1.0
TELEMETRY_INTERVAL_SEC = 1.0

# ---------------------------------------------------------------------------
# Serial / I2C hardware settings (used when USE_MOCK_HARDWARE = False)
# ---------------------------------------------------------------------------
GPS_PORT = "/dev/ttyUSB0"
XBEE_PORT = "/dev/ttyUSB1"
GPS_BAUDRATE = 9600
XBEE_BAUDRATE = 9600
BAROMETER_ADDRESS = 0x76
IMU_ADDRESS = 0x68

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

# ---------------------------------------------------------------------------
# Mapping / camera footprint model
# ---------------------------------------------------------------------------
# Approximate camera field of view. Tune these values for the actual lens.
CAMERA_HORIZONTAL_FOV_DEG = 62.2
CAMERA_VERTICAL_FOV_DEG = 48.8

# Altitudes lower than this are ignored for footprint sizing to avoid zero-area
# polygons when the payload has landed.
MAPPING_MIN_FOOTPRINT_ALTITUDE_M = 2.0

# Cell size for approximate unique coverage estimation.
MAPPING_COVERAGE_GRID_M = 5.0

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_LEVEL = "INFO"
