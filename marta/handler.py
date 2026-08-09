"""Base class for tag-triggered modes (music playback, button-light,
rainbow) and the small result vocabulary their event methods return to
control the main loop's deadline.

Replaces the old magic return values: `None` (leave the timeout alone),
`-1` == MartaHandler.EVENT_HANDLER_DONE, or a bare number of seconds -
including the ten-years-means-never hack that used to stand in for "no
timeout". `Never` now means what it says: the loop blocks on the queue with
no timeout at all.
"""

from dataclasses import dataclass

from marta.events import Button


@dataclass(frozen=True)
class Timeout:
    """Arm (or replace) the handler's deadline, this many seconds from now."""

    seconds: float


class Never:
    """No deadline: the loop blocks until the next event, forever."""


class Done:
    """The handler is finished; the loop switches back to the default
    handler and re-initializes it."""


# Returning plain None leaves the current deadline unchanged.
HandlerResult = Timeout | Never | Done | None


class Handler:
    def initialize(self) -> Timeout | Never:
        raise NotImplementedError

    def uninitialize(self) -> None:
        pass

    def rfid_tag_event(self, tag: str | None) -> HandlerResult:
        return None

    def rotation_event(self, x: float, y: float) -> HandlerResult:
        # Never fires today: the MPU is disabled (see mpu.py / events.py).
        # Kept for interface parity in case it is revived.
        return None

    def player_stop_event(self) -> HandlerResult:
        return None

    def button_event(self, button: Button, millis: int) -> HandlerResult:
        return None
