"""
actuators/stepper_driver.py
------------------------------
ULN2003 unipolar stepper driver wrapper for a 28BYJ-48, driven straight
off 4 RPi GPIOs through the Darlington array on the external ULN2003
module, connected via CON_ULN2003 (J3) on the HAT:
    IN1=GPIO25, IN2=GPIO24, IN3=GPIO23, IN4=GPIO18, J3 pin5=GND,
    motor VCC from a separate 5V supply.

Pins are driven directly with the standard 28BYJ-48 phase tables
(wave / double-coil full step / half step). NOTE: adafruit_motor's
step sequences are laid out for bipolar drivers and energize these
pins as B->C->A->D, so a unipolar 28BYJ-48 only vibrates in place -
hence the direct tables here.
"""
import time
import digitalio

import config

# 28BYJ-48 phase tables (bit N = GPIO for IN(N+1) of J3)
WAVE = [
    0b0001,  # IN1
    0b0010,  # IN2
    0b0100,  # IN3
    0b1000,  # IN4
]
DOUBLE = [
    0b0011,  # IN1+IN2
    0b0110,  # IN2+IN3
    0b1100,  # IN3+IN4
    0b1001,  # IN4+IN1
]
HALF = [
    0b0001, 0b0011,
    0b0010, 0b0110,
    0b0100, 0b1100,
    0b1000, 0b1001,
]

# Style aliases matching the old adafruit_motor API
SINGLE = WAVE
FULL = DOUBLE


class ULN2003Stepper:
    def __init__(self,
                 in1_pin=config.ULN2003_IN1_PIN,
                 in2_pin=config.ULN2003_IN2_PIN,
                 in3_pin=config.ULN2003_IN3_PIN,
                 in4_pin=config.ULN2003_IN4_PIN,
                 step_delay=config.STEPPER_STEP_DELAY):
        self._pins = []
        for pin in (in1_pin, in2_pin, in3_pin, in4_pin):
            d = digitalio.DigitalInOut(pin)
            d.direction = digitalio.Direction.OUTPUT
            d.value = False
            self._pins.append(d)
        self._step_delay = step_delay
        self._phase = 0

    @property
    def step_delay(self):
        return self._step_delay

    def _set_phase(self, bits):
        for i, pin in enumerate(self._pins):
            pin.value = bool(bits & (1 << i))

    def step(self, steps, style=DOUBLE):
        """Move `steps` steps. Positive = FORWARD, negative = BACKWARD."""
        direction = 1 if steps >= 0 else -1
        for _ in range(abs(steps)):
            self._phase = (self._phase + direction) % len(style)
            self._set_phase(style[self._phase])
            time.sleep(self._step_delay)

    def release(self):
        """De-energize all coils - prevents overheating / saves power when idle."""
        self._set_phase(0)
