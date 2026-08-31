"""ULN2003 stepper driver for the active GARUDA gimbal."""

from __future__ import annotations

import time

import config

HALF_STEP = [
    0b0001,
    0b0011,
    0b0010,
    0b0110,
    0b0100,
    0b1100,
    0b1000,
    0b1001,
]


class ULN2003Stepper:
    """Direct GPIO driver for a 28BYJ-48 through a ULN2003 board."""

    def __init__(
        self,
        pins: tuple[object, object, object, object] | None = None,
        step_delay: float | None = None,
    ) -> None:
        import digitalio

        self._digitalio = digitalio
        self._pins = []
        self._phase = 0
        self._step_delay = config.STEPPER_STEP_DELAY if step_delay is None else step_delay
        for pin in pins or (
            config.ULN2003_IN1,
            config.ULN2003_IN2,
            config.ULN2003_IN3,
            config.ULN2003_IN4,
        ):
            out = digitalio.DigitalInOut(pin)
            out.direction = digitalio.Direction.OUTPUT
            out.value = False
            self._pins.append(out)

    def _set_phase(self, bits: int) -> None:
        for index, pin in enumerate(self._pins):
            pin.value = bool(bits & (1 << index))

    def step(self, steps: int) -> None:
        """Move signed half-steps."""
        direction = 1 if steps >= 0 else -1
        for _ in range(abs(steps)):
            self._phase = (self._phase + direction) % len(HALF_STEP)
            self._set_phase(HALF_STEP[self._phase])
            time.sleep(self._step_delay)

    def release(self) -> None:
        """De-energize coils."""
        self._set_phase(0)
