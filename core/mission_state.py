"""
Mission state definitions and simple state-machine transitions.

States: BOOT -> IDLE -> DESCENT -> LANDED (or ERROR).
"""

from enum import Enum


class MissionState(str, Enum):
    """Enumeration of mission lifecycle states."""

    BOOT = "BOOT"
    IDLE = "IDLE"
    DESCENT = "DESCENT"
    LANDED = "LANDED"
    ERROR = "ERROR"

    def __str__(self) -> str:
        return self.value


# Valid forward transitions for the pre-hardware simulation
TRANSITIONS: dict[MissionState, list[MissionState]] = {
    MissionState.BOOT: [MissionState.IDLE, MissionState.ERROR],
    MissionState.IDLE: [MissionState.DESCENT, MissionState.ERROR],
    MissionState.DESCENT: [MissionState.LANDED, MissionState.ERROR],
    MissionState.LANDED: [],
    MissionState.ERROR: [MissionState.BOOT],
}


def can_transition(current: MissionState, target: MissionState) -> bool:
    """Return True if transitioning from *current* to *target* is allowed."""
    return target in TRANSITIONS.get(current, [])


def next_state(current: MissionState) -> MissionState | None:
    """
    Return the next state in the nominal mission flow, or None if terminal.

    BOOT -> IDLE -> DESCENT -> LANDED
    """
    flow = [
        MissionState.BOOT,
        MissionState.IDLE,
        MissionState.DESCENT,
        MissionState.LANDED,
    ]
    try:
        idx = flow.index(current)
        if idx + 1 < len(flow):
            return flow[idx + 1]
    except ValueError:
        pass
    return None
