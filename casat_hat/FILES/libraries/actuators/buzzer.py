"""
actuators/buzzer.py
----------------------
Status / recovery buzzer wrapper. GPIO16 -> R3 -> Q2 (2N2222A) -> BZ1,
per the Buzzer_CKT sub-sheet in Garud_HAT.kicad_sch.
"""
import time
import digitalio

import config


class Buzzer:
    def __init__(self, pin=config.BUZZER_PIN):
        self._pin = digitalio.DigitalInOut(pin)
        self._pin.direction = digitalio.Direction.OUTPUT
        self._pin.value = False

    def on(self):
        self._pin.value = True

    def off(self):
        self._pin.value = False

    def beep(self, duration=0.2):
        self.on()
        time.sleep(duration)
        self.off()

    def beep_pattern(self, count=3, on_time=0.15, off_time=0.15):
        """Useful as a post-landing recovery beacon."""
        for _ in range(count):
            self.beep(on_time)
            time.sleep(off_time)
