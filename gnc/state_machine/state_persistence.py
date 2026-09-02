"""
state_machine/state_persistence.py
====================================
Payload reset recovery mechanism for GARUD GNC (Python / Raspberry Pi 5).

Ported from the GARUD payload flight computer (Teensy 4.1, Arduino C++) —
specifically the dual-slot A/B recovery pattern in saveRecoveryState() /
attemptRecovery().

How the dual-slot A/B pattern works (same as Arduino)
------------------------------------------------------
Two files are kept: flight.state.A and flight.state.B.
Writes alternate between A and B (toggled by `_slot_is_a`).
Each write increments a `version` counter.
On boot, BOTH files are read; the one with the higher version number and a
valid magic number is used.

If power is cut during a write, the OTHER slot still has the previous valid
state — exactly as in the Arduino `recoveryA` / `recoveryB` pattern.

Key constants matching Arduino payload code
-------------------------------------------
  RECOVERY_MAGIC         = 0xDEAD1234   (same as Arduino)
  RECOVERY_THRESHOLD_SEC = 300          (same as Arduino RECOVERY_THRESHOLD_SEC)
  STATE_WRITE_INTERVAL_S = 5            (equivalent to Arduino RECOVERY_LOG_HZ=10)

State file format (JSON, not binary — Pi has plenty of CPU for JSON parsing)
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants — matched to Arduino payload code
# ---------------------------------------------------------------------------

RECOVERY_MAGIC          = 0xDEAD1234   # same magic as Arduino
RECOVERY_THRESHOLD_SEC  = 300          # 5 minutes — same as Arduino
STATE_WRITE_INTERVAL_S  = 5.0          # write every 5 s (equivalent to Arduino 10 Hz)
SCHEMA_VERSION          = 2            # bump if struct layout changes

# A/B slot file paths
_SLOT_A = Path("flight.state.A")
_SLOT_B = Path("flight.state.B")

# Module-level slot tracker (toggled on every write, same as Arduino recoverySlotA)
_slot_is_a: bool = True
_version:   int  = 0


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class StateSnapshot:
    """All variables needed to resume flight after a reboot.

    Mirrors the Arduino RecoveryState struct fields that are relevant to
    the Python GNC system.
    """
    # Core state (FlightState enum name as string, same as Arduino stateName())
    flight_state:      str
    ground_altitude_m: float   # MSL ground reference (same as Arduino base pressure ref)

    # Safety locks — NEVER allow re-fire if True
    # Equivalent to Arduino `mainDeployed` flag
    drogue_fired: bool

    # Last known kinematics (same as Arduino currentAltitude, currentVelocity)
    last_altitude_m:  float
    last_velocity_ms: float

    # Mission target coordinates
    target_lat: float
    target_lon: float

    # Controller state
    rl_active: bool

    # Recovery bookkeeping (filled by write_state)
    magic:          int   = RECOVERY_MAGIC
    version:        int   = 0
    schema_version: int   = SCHEMA_VERSION
    timestamp_utc:  str   = ""
    timestamp_mono: float = 0.0


# ---------------------------------------------------------------------------
# Write — dual A/B slot
# ---------------------------------------------------------------------------

def write_state(snapshot: StateSnapshot,
                slot_a: Path = _SLOT_A,
                slot_b: Path = _SLOT_B) -> None:
    """
    Write snapshot to the INACTIVE slot, then toggle the active slot.

    Pattern mirrors Arduino saveRecoveryState():
        File& f = recoverySlotA ? recoveryA : recoveryB;
        f.seek(0);
        f.write(...);
        recoverySlotA = !recoverySlotA;
    """
    global _slot_is_a, _version

    _version        += 1
    snapshot.version = _version
    snapshot.timestamp_utc  = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    snapshot.timestamp_mono = time.monotonic()
    snapshot.magic          = RECOVERY_MAGIC
    snapshot.schema_version = SCHEMA_VERSION

    # Write to the current slot (same as Arduino writing to recoverySlotA ? A : B)
    target = slot_a if _slot_is_a else slot_b
    tmp    = target.with_suffix(".tmp")

    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(asdict(snapshot), f, indent=2)
        os.replace(tmp, target)   # atomic rename (POSIX)
        logger.debug("State v%d written to slot %s  drogue=%s  alt=%.1f m",
                     _version, "A" if _slot_is_a else "B",
                     snapshot.drogue_fired, snapshot.last_altitude_m)
    except Exception as e:
        logger.warning("Failed to write .state slot %s: %s",
                       "A" if _slot_is_a else "B", e)
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass

    # Toggle slot — same as `recoverySlotA = !recoverySlotA`
    _slot_is_a = not _slot_is_a


# ---------------------------------------------------------------------------
# Load — reads both slots, picks highest valid version (same as Arduino)
# ---------------------------------------------------------------------------

def load_state(slot_a: Path = _SLOT_A,
               slot_b: Path = _SLOT_B) -> Optional[StateSnapshot]:
    """
    Read both A and B slots. Return the snapshot with the higher version
    number that passes all validation checks.

    Mirrors Arduino attemptRecovery():
        if (validA && validB)   chosen = (rsA.version >= rsB.version) ? &rsA : &rsB;
        else if (validA)        chosen = &rsA;
        else if (validB)        chosen = &rsB;
        else                    return false;
    """
    snap_a = _load_slot(slot_a, "A")
    snap_b = _load_slot(slot_b, "B")

    # Pick highest valid version (same as Arduino logic)
    if snap_a is not None and snap_b is not None:
        chosen = snap_a if snap_a.version >= snap_b.version else snap_b
        slot_label = "A" if chosen is snap_a else "B"
    elif snap_a is not None:
        chosen, slot_label = snap_a, "A"
    elif snap_b is not None:
        chosen, slot_label = snap_b, "B"
    else:
        logger.info("No valid .state slots found — cold start.")
        return None

    # Age check — matches Arduino `elapsed > RECOVERY_THRESHOLD_SEC`
    try:
        saved_at = datetime.strptime(
            chosen.timestamp_utc, "%Y-%m-%dT%H:%M:%SZ"
        ).replace(tzinfo=timezone.utc)
        age_s = (datetime.now(timezone.utc) - saved_at).total_seconds()
    except Exception:
        logger.warning(".state has bad timestamp — cold start.")
        return None

    if age_s > RECOVERY_THRESHOLD_SEC:
        logger.info(".state slot %s is %.0f s old (max %d s) — stale, cold start.",
                    slot_label, age_s, RECOVERY_THRESHOLD_SEC)
        return None

    logger.info(
        "[RECOVERY] Slot %s v%d: state=%s  drogue=%s  alt=%.1f m  age=%.0f s",
        slot_label, chosen.version, chosen.flight_state,
        chosen.drogue_fired, chosen.last_altitude_m, age_s,
    )
    return chosen


def _load_slot(path: Path, label: str) -> Optional[StateSnapshot]:
    """Load and validate one slot file. Returns None on any failure."""
    if not path.exists():
        return None

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(".state slot %s corrupt (%s)", label, e)
        _archive_bad(path, label)
        return None

    # Magic number check — same as Arduino `rs.magic != RECOVERY_MAGIC`
    if data.get("magic") != RECOVERY_MAGIC:
        logger.warning(".state slot %s bad magic (got %s)", label, data.get("magic"))
        _archive_bad(path, label)
        return None

    # Schema version check
    if data.get("schema_version") != SCHEMA_VERSION:
        logger.warning(".state slot %s schema mismatch (got %s, want %s)",
                       label, data.get("schema_version"), SCHEMA_VERSION)
        _archive_bad(path, label)
        return None

    try:
        return StateSnapshot(
            flight_state      = str(data["flight_state"]),
            ground_altitude_m = float(data["ground_altitude_m"]),
            drogue_fired      = bool(data["drogue_fired"]),
            last_altitude_m   = float(data["last_altitude_m"]),
            last_velocity_ms  = float(data["last_velocity_ms"]),
            target_lat        = float(data["target_lat"]),
            target_lon        = float(data["target_lon"]),
            rl_active         = bool(data["rl_active"]),
            magic             = int(data["magic"]),
            version           = int(data["version"]),
            schema_version    = int(data["schema_version"]),
            timestamp_utc     = str(data["timestamp_utc"]),
            timestamp_mono    = float(data["timestamp_mono"]),
        )
    except (KeyError, TypeError, ValueError) as e:
        logger.warning(".state slot %s missing field: %s", label, e)
        _archive_bad(path, label)
        return None


# ---------------------------------------------------------------------------
# Delete / Archive
# ---------------------------------------------------------------------------

def delete_state(slot_a: Path = _SLOT_A, slot_b: Path = _SLOT_B) -> None:
    """Delete both slots on clean landing — no stale recovery on next boot.

    Mirrors Arduino clearing the recovery files after normal LANDED state.
    """
    for p, label in [(slot_a, "A"), (slot_b, "B")]:
        try:
            p.unlink(missing_ok=True)
            logger.info(".state slot %s deleted (clean landing).", label)
        except Exception as e:
            logger.warning("Could not delete .state slot %s: %s", label, e)


def _archive_bad(path: Path, label: str) -> None:
    """Rename bad slot to .bad for post-flight inspection."""
    bad = path.with_suffix(f".{label}.bad")
    try:
        os.replace(path, bad)
        logger.info("Bad slot %s archived to %s", label, bad)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Standalone viewer — `python -m state_machine.state_persistence`
# ---------------------------------------------------------------------------

def print_state_files() -> None:
    """Pretty-print both A/B slots for ground crew inspection."""
    print("=" * 50)
    print("  GARUD FLIGHT STATE RECOVERY FILES")
    print("=" * 50)
    for path, label in [(_SLOT_A, "A"), (_SLOT_B, "B")]:
        snap = _load_slot(path, label)
        if snap is None:
            print(f"  Slot {label}: NOT FOUND or INVALID")
            continue
        print(f"  Slot {label} — version {snap.version}")
        print(f"    Saved at     : {snap.timestamp_utc}")
        print(f"    Flight state : {snap.flight_state}")
        print(f"    Ground alt   : {snap.ground_altitude_m:.1f} m MSL")
        print(f"    Last alt AGL : {snap.last_altitude_m:.1f} m")
        print(f"    Last velocity: {snap.last_velocity_ms:.2f} m/s")
        print(f"    Drogue fired : {'YES — LOCKED OUT' if snap.drogue_fired else 'No'}")
        print(f"    Target       : {snap.target_lat:.6f}, {snap.target_lon:.6f}")
        print(f"    RL active    : {snap.rl_active}")
    print("=" * 50)

    # Show which would be chosen on recovery
    chosen = load_state()
    if chosen:
        print(f"  → Would recover to: {chosen.flight_state} (v{chosen.version})")
    else:
        print("  → Would cold start (no valid/fresh slot)")


if __name__ == "__main__":
    print_state_files()
