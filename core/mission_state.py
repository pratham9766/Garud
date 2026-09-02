"""Mission state definitions and allowed flight transitions."""

from enum import Enum


class MissionState(str, Enum):
    """Enumeration of mission lifecycle states."""

    BOOT = "BOOT"
    DISARMED = "DISARMED"
    IDLE = "IDLE"
    ARMED_PAD = "ARMED_PAD"
    BOOST = "BOOST"
    COAST = "COAST"
    APOGEE = "APOGEE"
    DESCENT = "DESCENT"
    DESCENT_DROGUE = "DESCENT_DROGUE"
    GLIDER_DEPLOY = "GLIDER_DEPLOY"
    GUIDED_DESCENT = "GUIDED_DESCENT"
    LANDED = "LANDED"
    ABORT = "ABORT"
    ERROR = "ERROR"

    def __str__(self) -> str:
        return self.value


# Valid forward transitions for the flight state machine.
TRANSITIONS: dict[MissionState, list[MissionState]] = {
    MissionState.BOOT: [MissionState.DISARMED, MissionState.IDLE, MissionState.ERROR],
    MissionState.DISARMED: [MissionState.ARMED_PAD, MissionState.ERROR],
    MissionState.IDLE: [MissionState.ARMED_PAD, MissionState.ERROR],
    MissionState.ARMED_PAD: [MissionState.DISARMED, MissionState.BOOST, MissionState.ABORT],
    MissionState.BOOST: [MissionState.COAST, MissionState.ABORT],
    MissionState.COAST: [MissionState.APOGEE, MissionState.ABORT],
    MissionState.APOGEE: [MissionState.DESCENT_DROGUE, MissionState.ABORT],
    MissionState.DESCENT: [MissionState.GLIDER_DEPLOY, MissionState.LANDED, MissionState.ABORT],
    MissionState.DESCENT_DROGUE: [MissionState.GLIDER_DEPLOY, MissionState.ABORT],
    MissionState.GLIDER_DEPLOY: [MissionState.GUIDED_DESCENT, MissionState.ABORT],
    MissionState.GUIDED_DESCENT: [MissionState.LANDED, MissionState.ABORT],
    MissionState.LANDED: [],
    MissionState.ABORT: [MissionState.LANDED],
    MissionState.ERROR: [MissionState.BOOT, MissionState.DISARMED],
}


def can_transition(current: MissionState, target: MissionState) -> bool:
    """Return True if transitioning from *current* to *target* is allowed."""
    return target in TRANSITIONS.get(current, [])


def next_state(current: MissionState) -> MissionState | None:
    """
    Return the next state in the nominal mission flow, or None if terminal.

    BOOT -> DISARMED -> ARMED_PAD -> BOOST -> COAST -> APOGEE ->
    DESCENT_DROGUE -> GLIDER_DEPLOY -> GUIDED_DESCENT -> LANDED
    """
    flow = [
        MissionState.BOOT,
        MissionState.DISARMED,
        MissionState.ARMED_PAD,
        MissionState.BOOST,
        MissionState.COAST,
        MissionState.APOGEE,
        MissionState.DESCENT_DROGUE,
        MissionState.GLIDER_DEPLOY,
        MissionState.GUIDED_DESCENT,
        MissionState.LANDED,
    ]
    try:
        idx = flow.index(current)
        if idx + 1 < len(flow):
            return flow[idx + 1]
    except ValueError:
        pass
    return None
