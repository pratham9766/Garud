"""
Mission state definitions and simple state-machine transitions.

Delegates to the GNC FlightState enum for compatibility.
"""
from gnc.state_machine.flight_states import FlightState as MissionState

# Alias for backwards compatibility
next_state = lambda x: None
can_transition = lambda x, y: True
