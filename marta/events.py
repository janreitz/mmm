"""Typed events flowing through the single message queue.

Replaces the old `[int, *params]` lists dispatched by if/elif chains keyed
on integer constants: adapters construct these directly and post them, the
main loop dispatches on them with `match`, and a dataclass's repr doubles as
the log line (the old EVENT_HUMAN_READABLE lookup tables are gone).
"""

from dataclasses import dataclass
from enum import Enum


class Button(Enum):
    """BCM pin numbers double as the enum values - the wiring is fixed by
    the PCB, not something that varies at runtime."""

    YELLOW = 5
    BLUE = 6
    RED = 13
    GREEN = 26


@dataclass(frozen=True)
class ButtonPressed:
    button: Button
    millis: int


@dataclass(frozen=True)
class TagPlaced:
    tag: str


@dataclass(frozen=True)
class TagRemoved:
    pass


@dataclass(frozen=True)
class PlaybackStopped:
    pass


@dataclass(frozen=True)
class PlayerDied:
    """mpg123 exited unexpectedly."""


@dataclass(frozen=True)
class Interrupted:
    """SIGINT: Ctrl+C, or the power button daemon's graceful-shutdown signal.

    Not the interrupt RFID tag - that is still a TagPlaced like any other
    tag, checked against config.interrupt_tag where the loop handles it, to
    keep tag-triggered behavior in one place.
    """


# No Rotation event: the MPU is disabled (see mpu.py) and nothing produces
# one today. Handler.rotation_event() is kept for parity in case it is
# revived; reviving it means adding a variant here and a match arm in
# loop.py's dispatch.
Event = ButtonPressed | TagPlaced | TagRemoved | PlaybackStopped | PlayerDied | Interrupted
