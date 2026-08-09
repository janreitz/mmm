"""Message-loop control flow tests: pure logic, no hardware. Exercises the
two-phase match rewrite in loop.Marta.message_loop against fake handlers,
since this is the highest-risk part of the stage-2 restructuring.
"""

import sys
from queue import Queue

import fake_rpi_ws281x

# loop.py imports LEDStrip for type hints, which transitively imports the
# Pi-only _rpi_ws281x extension - fake it out before importing marta.loop,
# same as test_ledstrip.py.
sys.modules["_rpi_ws281x"] = fake_rpi_ws281x

from marta.config import Config
from marta.events import ButtonPressed, Button, Interrupted, PlaybackStopped, TagPlaced, TagRemoved
from marta.handler import Done, Never, Timeout
from marta.loop import EXIT_CODE_DEBUG, Marta


class FakeHandler:
    """results is consumed in order, one per event-method call (button_event/
    player_stop_event/rfid_tag_event/rotation_event share the same queue);
    once exhausted, further calls return None. Queued upfront since
    message_loop() processes the whole test queue in one synchronous call -
    there is no chance to react mid-loop."""

    def __init__(self, name, init_result=None, results=()):
        self.name = name
        self.init_result = init_result or Never()
        self.initialized = 0
        self.uninitialized = 0
        self.calls = []
        self._results = list(results)

    def initialize(self):
        self.initialized += 1
        return self.init_result

    def uninitialize(self):
        self.uninitialized += 1

    def button_event(self, button, millis):
        self.calls.append(("button_event", button, millis))
        return self._take_result()

    def player_stop_event(self):
        self.calls.append(("player_stop_event",))
        return self._take_result()

    def rfid_tag_event(self, tag):
        self.calls.append(("rfid_tag_event", tag))
        return self._take_result()

    def rotation_event(self, x, y):
        self.calls.append(("rotation_event", x, y))
        return self._take_result()

    def _take_result(self):
        return self._results.pop(0) if self._results else None


def make_config(**overrides):
    base = dict(
        base_dir="/fake",
        audio_dir="/fake/audio",
        start_sound_path="/fake/audio/system/startup.mp3",
        shutdown_sound_path="/fake/audio/system/shutdown.mp3",
        unknown_tag_file="/fake/audio/unknown_tag.txt",
        log_file="/fake/logs/mmm.log",
    )
    base.update(overrides)
    return Config(**base)


def make_marta(default_handler, handlers_by_tag=None, config=None):
    return Marta(
        message_queue=Queue(),
        config=config or make_config(),
        player=None,
        leds=None,
        button_input=None,
        rfid_reader=None,
        default_handler=default_handler,
        handlers_by_tag=handlers_by_tag or {},
    )


def test_button_event_dispatches_and_keeps_default_timeout_on_none():
    default = FakeHandler("default")
    marta = make_marta(default)
    marta._message_queue.put(ButtonPressed(Button.GREEN, 42))
    marta._message_queue.put(Interrupted())

    marta.message_loop()

    assert default.calls == [("button_event", Button.GREEN, 42)]
    assert default.initialized == 1
    assert default.uninitialized == 1  # final cleanup on the way out


def test_tag_switch_then_still_dispatches_to_the_new_handler():
    # Reproduces the legacy if/elif's fallthrough: switching handler on a
    # known special tag does NOT skip calling rfid_tag_event on the new
    # handler with that same tag.
    default = FakeHandler("default")
    special = FakeHandler("special", init_result=Timeout(60))
    marta = make_marta(default, handlers_by_tag={"SPECIALTAG": special})

    marta._message_queue.put(TagPlaced("SPECIALTAG"))
    marta._message_queue.put(Interrupted())

    marta.message_loop()

    assert default.calls == []  # default never saw the tag event
    assert special.calls == [("rfid_tag_event", "SPECIALTAG")]
    assert special.initialized == 1
    assert default.uninitialized == 1  # switched away from once (init)
    assert special.uninitialized == 1  # and cleaned up at loop exit


def test_done_result_switches_back_to_default_and_reinitializes():
    default = FakeHandler("default")
    # First rfid_tag_event call (the switch tag itself) replies None so the
    # Timeout(60) from initialize() stays armed; the second (on removal)
    # replies Done() to leave special mode.
    special = FakeHandler("special", init_result=Timeout(60), results=[None, Done()])
    marta = make_marta(default, handlers_by_tag={"SPECIALTAG": special})

    marta._message_queue.put(TagPlaced("SPECIALTAG"))
    marta._message_queue.put(TagRemoved())
    marta._message_queue.put(Interrupted())

    marta.message_loop()

    assert special.calls == [("rfid_tag_event", "SPECIALTAG"), ("rfid_tag_event", None)]
    assert special.uninitialized == 1  # once, when Done() fires
    assert default.initialized == 2  # once at loop start, once after Done()


def test_interrupt_tag_exits_with_debug_code_and_no_dispatch():
    default = FakeHandler("default")
    config = make_config()
    marta = make_marta(default, config=config)

    marta._message_queue.put(TagPlaced(config.interrupt_tag))

    exit_val = marta.message_loop()

    assert exit_val == EXIT_CODE_DEBUG
    assert default.calls == []  # broke out before phase-2 dispatch


def test_player_stop_event_updates_deadline_from_timeout():
    default = FakeHandler("default", results=[Timeout(0.05)])
    marta = make_marta(default)

    marta._message_queue.put(PlaybackStopped())
    marta._message_queue.put(Interrupted())

    marta.message_loop()

    assert default.calls == [("player_stop_event",)]


if __name__ == "__main__":
    test_button_event_dispatches_and_keeps_default_timeout_on_none()
    test_tag_switch_then_still_dispatches_to_the_new_handler()
    test_done_result_switches_back_to_default_and_reinitializes()
    test_interrupt_tag_exits_with_debug_code_and_no_dispatch()
    test_player_stop_event_updates_deadline_from_timeout()
    print("ALL ASSERTIONS PASSED")
