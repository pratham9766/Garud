"""
PCA9685 Servo Controller for Garuda_TARSR.

Utilizes the shared I2C bus from bus_manager.py.
Handles Glider (Left, Right, Drogue) and Gimbal (Pan, Tilt) servos.
"""
import logging
from adafruit_servokit import ServoKit

import config
import bus_manager

logger = logging.getLogger(__name__)


class ServoController:
    """Controls PCA9685 servos over the shared I2C bus."""

    def __init__(self) -> None:
        try:
            i2c_bus = bus_manager.get_i2c()
            self._kit = ServoKit(
                channels=16, 
                i2c=i2c_bus, 
                address=config.PCA9685_I2C_ADDRESS
            )
            logger.info("PCA9685 ServoKit initialised at I2C 0x%02X", config.PCA9685_I2C_ADDRESS)
            
            # Initialise neutral positions
            self.set_glider_neutral()
            self.set_gimbal_neutral()
            # Drogue default should be locked
            self._kit.servo[config.GLIDER_DROGUE_CHANNEL].angle = 60
            logger.info("Servos initialised to neutral/safe positions.")
            
        except Exception as e:
            logger.error(f"Failed to initialise PCA9685: {e}")
            self._kit = None

    def set_glider_neutral(self) -> None:
        if self._kit:
            self._kit.servo[config.GLIDER_LEFT_CHANNEL].angle = 90
            self._kit.servo[config.GLIDER_RIGHT_CHANNEL].angle = 90

    def set_gimbal_neutral(self) -> None:
        if self._kit:
            self._kit.servo[config.GIMBAL_PAN_CHANNEL].angle = 90
            self._kit.servo[config.GIMBAL_TILT_CHANNEL].angle = 90

    def write_glider_servos(self, left_deg: float, right_deg: float) -> None:
        """Command left and right brake servos [60, 120] degrees."""
        if not self._kit: return
        left_deg  = max(60.0, min(120.0, left_deg))
        right_deg = max(60.0, min(120.0, right_deg))
        
        self._kit.servo[config.GLIDER_LEFT_CHANNEL].angle = left_deg
        self._kit.servo[config.GLIDER_RIGHT_CHANNEL].angle = right_deg

    def trigger_drogue(self) -> None:
        """Fire drogue release servo."""
        if not self._kit: return
        self._kit.servo[config.GLIDER_DROGUE_CHANNEL].angle = 120
        logger.warning("[HW] DROGUE RELEASE commanded!")

    def write_gimbal(self, pan_deg: float, tilt_deg: float) -> None:
        """Command gimbal servos [-45, +45] offset to [45, 135]."""
        if not self._kit: return
        pan_deg  = max(-45.0, min(45.0, pan_deg))
        tilt_deg = max(-45.0, min(45.0, tilt_deg))
        
        self._kit.servo[config.GIMBAL_PAN_CHANNEL].angle = pan_deg + 90.0
        self._kit.servo[config.GIMBAL_TILT_CHANNEL].angle = tilt_deg + 90.0
