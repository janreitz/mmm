"""The Marta class: the message loop and its handler-switching/deadline
rules, unchanged in behavior from the legacy Marta.py. Construction of the
hardware adapters and handlers - previously mixed into this class's
constructor alongside the startup jingle - now happens in __main__.py's
composition root; this class receives everything already built.
"""

from logging import getLogger
from queue import Queue, Empty
from time import monotonic as mtime, sleep

from marta.buttons import ButtonInput
from marta.config import Config
from marta.events import Event, Interrupted, PlayerDied, TagPlaced, TagRemoved, ButtonPressed, PlaybackStopped
from marta.handler import Handler, Timeout, Never, Done
from marta.ledstrip import LEDStrip
from marta.player import MPG123Player
from marta.rfid import RFIDReader

debug = getLogger("     Marta").debug

# The debug/interrupt-tag exit code: must match systemd/marta.service's
# SuccessExitStatus=2, which tells the unit not to restart on this exit.
EXIT_CODE_DEBUG = 2


class Marta:
    def __init__(
        self,
        message_queue: "Queue[Event]",
        config: Config,
        player: MPG123Player,
        leds: LEDStrip,
        button_input: ButtonInput,
        rfid_reader: RFIDReader,
        default_handler: Handler,
        handlers_by_tag: dict[str, Handler],
    ):
        self._message_queue = message_queue
        self._config = config
        self._player = player
        self._leds = leds
        self._button_input = button_input
        self._rfid_reader = rfid_reader
        self._default_handler = default_handler
        self._handlers_by_tag = handlers_by_tag

    def interrupt(self):
        self._message_queue.put(Interrupted())

    @staticmethod
    def _deadline_from(result: Timeout | Never) -> float | None:
        if isinstance(result, Never):
            return None
        if isinstance(result, Timeout):
            return mtime() + result.seconds
        raise TypeError(f"handler must return Timeout or Never here, got {result!r}")

    def message_loop(self) -> int:
        exit_val = 0

        current_handler = self._default_handler
        deadline = self._deadline_from(current_handler.initialize())

        while True:
            now = mtime()
            debug("now = " + str(now))

            if deadline is not None and now >= deadline:
                debug("timeout occurred")
                break

            timeout = None if deadline is None else deadline - now
            debug("waiting for " + str(timeout))
            try:
                event = self._message_queue.get(block=True, timeout=timeout)
            except Empty:
                # If a time change (due to network time availability) occurs while waiting for an event,
                # Queue.get will return Empty early:

                # 14:46:31.368 | main | now = 54.502526
                # 14:46:31.380 | main | waiting for 299.955775
                # -- NOW THE TIME CHANGE OCCURS --
                # 19:29:13.403 | main | timeout @ 67.323505
                # 19:29:13.410 | main | Terminating!

                # Instead of breaking here, we just continue, because we have another check on top of this function
                #  which checks the timeout again but using a monotonic timer
                debug("possible timeout @ " + str(mtime()))
                continue

            debug("%r", event)

            # Phase 1: interrupts and handler switches. A tag switch does not
            # skip phase 2 below - the newly-switched handler still receives
            # the same event afterwards (matches the legacy if/elif exactly).
            match event:
                case Interrupted():
                    debug("Critical: Interrupt event!")
                    break

                case PlayerDied():
                    debug("Critical: MPG123 error event!")
                    break

                case TagPlaced(tag) if tag == self._config.interrupt_tag:
                    debug("Critical: Interrupt tag event!")
                    exit_val = EXIT_CODE_DEBUG
                    break

                case TagPlaced(tag) if tag in self._handlers_by_tag:
                    current_handler.uninitialize()
                    current_handler = self._handlers_by_tag[tag]
                    deadline = self._deadline_from(current_handler.initialize())

                case _:
                    pass

            # Phase 2: unconditional dispatch to whatever the current handler
            # is now (freshly switched, above, or unchanged).
            match event:
                case ButtonPressed(button, millis):
                    result = current_handler.button_event(button, millis)
                case PlaybackStopped():
                    result = current_handler.player_stop_event()
                case TagPlaced(tag):
                    result = current_handler.rfid_tag_event(tag)
                case TagRemoved():
                    result = current_handler.rfid_tag_event(None)
                case _:
                    # Interrupted/PlayerDied already broke out of the loop
                    # above and never reach here.
                    raise AssertionError(f"unreachable: {event!r}")

            if result is None:
                debug("not changing the timeout")
            else:
                if isinstance(result, Done):
                    debug("This event handler is done.")
                    current_handler.uninitialize()
                    current_handler = self._default_handler
                    result = current_handler.initialize()
                deadline = self._deadline_from(result)

        current_handler.uninitialize()
        return exit_val

    def terminate(self):
        debug("Terminating!")

        try:
            self._player.set_volume(self._config.system_sound_volume)
            self._player.set_pitch(self._config.default_pitch)
            self._player.load_track_from_file(self._config.shutdown_sound_path)
            self._player.play_track()
        except:
            pass

        try:
            self._leds.shutdown()
        except:
            pass

        try:
            for i in range(20):
                self._button_input.set_status_led(bool(i % 2))
                sleep(0.2)
        except:
            pass

        try:
            self._player.terminate()
        except:
            pass

        try:
            self._rfid_reader.terminate()
        except:
            pass

        try:
            self._leds.terminate()
        except:
            pass

        try:
            for i in range(10):
                self._button_input.set_status_led(bool(i % 2))
                sleep(0.2)
        except:
            pass

        try:
            self._button_input.terminate()
        except:
            pass
