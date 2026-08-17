"""
actuators/servo_driver.py
---------------------------
PCA9685 16-channel PWM driver wrapper, feeding the Servo_control
connector (J2). Shares I2C1 with the BNO085.

GPIO4 drives the PCA9685's chip-level /OE pin (active-LOW): pull it
LOW to let the PWM outputs drive the servos, HIGH to force every
channel off (used here as a safety default at startup / shutdown).

Requires: adafruit-circuitpython-pca9685, adafruit-circuitpython-motor
"""
import digitalio
from adafruit_pca9685 import PCA9685
from adafruit_motor import servo

import config


class PCA9685Driver:
    def __init__(self, i2c_bus, address=config.PCA9685_I2C_ADDRESS,
                 frequency=config.PCA9685_PWM_FREQ):
        self.pca = PCA9685(i2c_bus, address=address)
        self.pca.frequency = frequency

        self._oe = digitalio.DigitalInOut(config.PCA9685_OE_PIN)
        self._oe.direction = digitalio.Direction.OUTPUT
        self.disable_outputs()  # safe default until explicitly enabled

        self._servos = {}   # channel -> servo.Servo instance

    def enable_outputs(self):
        """Pull /OE LOW - PWM outputs become active."""
        self._oe.value = False

    def disable_outputs(self):
        """Pull /OE HIGH - all PWM outputs forced off (safety state)."""
        self._oe.value = True

    def attach_servo(self, channel, min_pulse=500, max_pulse=2500):
        """Register a standard servo on a PCA9685 channel (0-15)."""
        s = servo.Servo(self.pca.channels[channel], min_pulse=min_pulse, max_pulse=max_pulse)
        self._servos[channel] = s
        return s

    def set_angle(self, channel, angle):
        """Drive a positional servo to `angle` degrees (0-180)."""
        if channel not in self._servos:
            self.attach_servo(channel)
        self._servos[channel].angle = angle

    def set_throttle(self, channel, throttle):
        """Drive a continuous-rotation servo / ESC, throttle in [-1.0, 1.0]."""
        if channel not in self._servos:
            self.attach_servo(channel)
        self._servos[channel].throttle = throttle

    def deinit(self):
        self.disable_outputs()
        self.pca.deinit()
