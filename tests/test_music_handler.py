"""MusicHandler state-machine tests. Uses a real Library against a real temp
directory (fast, pure, already covered standalone by test_library.py) plus
hand-rolled recording fakes for the player and LED strip - no hardware.
"""

import os
import sys

import fake_rpi_ws281x

# music_handler.py imports LEDStrip for type hints, which transitively
# imports the Pi-only _rpi_ws281x extension - fake it out before importing
# marta.music_handler, same as test_ledstrip.py / test_loop.py.
sys.modules["_rpi_ws281x"] = fake_rpi_ws281x

from marta.events import Button
from marta.handler import Done, Never, Timeout
from marta.music_handler import Idle, MusicHandler, Playing

from test_library import make_audio_dir, make_config, touch


class FakePlayer:
    def __init__(self):
        self.calls = []
        self._playing = False
        self._stopped = True
        self._position = 0
        self._volume = 2
        self._pitch = 100
        self.current_file = None

    def load_track_from_file(self, path):
        self.calls.append(("load", path))
        self.current_file = path
        self._position = 0
        return True

    def play_track(self):
        self.calls.append(("play",))
        self._playing = True
        self._stopped = False
        return True

    def pause_track(self):
        self.calls.append(("pause",))
        self._playing = False
        return True

    def stop_track(self):
        self.calls.append(("stop",))
        was_stopped = self._stopped
        self._playing = False
        self._stopped = True
        return not was_stopped

    def is_track_stopped(self):
        return self._stopped

    def is_track_playing(self):
        return self._playing

    def get_position_in_millis(self):
        return self._position

    def set_position_in_millis(self, millis):
        self.calls.append(("seek", millis))
        self._position = millis
        return True

    def get_volume(self):
        return self._volume

    def set_volume(self, v):
        self.calls.append(("set_volume", v))
        self._volume = v

    def get_pitch(self):
        return self._pitch

    def set_pitch(self, p):
        self.calls.append(("set_pitch", p))
        self._pitch = p


class FakeLeds:
    def __init__(self):
        self.calls = []
        self._brightness = 255

    def breathe(self):
        self.calls.append(("breathe",))

    def clear(self):
        self.calls.append(("clear",))

    def fade_up_and_down(self, color):
        self.calls.append(("fade", color))

    def song(self, i, n, forward=True):
        self.calls.append(("song", i, n, forward))

    def volume(self, v):
        self.calls.append(("volume", v))

    def get_brightness(self):
        return self._brightness

    def set_brightness(self, v):
        self.calls.append(("set_brightness", v))
        self._brightness = v


def make_handler(tmp_path, tags, player=None, leds=None):
    audio_dir = make_audio_dir(tmp_path, tags=tags)
    config = make_config(audio_dir)
    handler = MusicHandler(player or FakePlayer(), leds or FakeLeds(), config)
    return handler, config


def test_initialize_enters_idle_and_breathes(tmp_path):
    handler, _ = make_handler(tmp_path, {"AABBCCDDEEFF": ["a.mp3"]})
    result = handler.initialize()

    assert isinstance(handler.state, Idle)
    assert isinstance(result, Never)
    assert ("breathe",) in handler.leds.calls


def test_known_tag_enters_playing_and_loads_first_song(tmp_path):
    handler, _ = make_handler(tmp_path, {"AABBCCDDEEFF": ["b.mp3", "a.mp3"]})
    handler.initialize()

    handler.rfid_tag_event("AABBCCDDEEFF")

    assert isinstance(handler.state, Playing)
    assert handler.state.tag == "AABBCCDDEEFF"
    assert handler.state.song_index == 0
    assert handler.player.current_file.endswith("a.mp3")  # sorted first
    assert ("play",) in handler.player.calls


def test_known_tag_resumes_from_saved_songstate(tmp_path):
    audio_dir = make_audio_dir(tmp_path, tags={"AABBCCDDEEFF": ["a.mp3", "b.mp3"]})
    touch(str(audio_dir / "somebody_AABBCCDDEEFF" / ".songstate"), "1\n5000\n")
    config = make_config(audio_dir)
    handler = MusicHandler(FakePlayer(), FakeLeds(), config)
    handler.initialize()

    handler.rfid_tag_event("AABBCCDDEEFF")

    assert handler.state.song_index == 1
    assert handler.player.current_file.endswith("b.mp3")
    assert ("seek", 5000) in handler.player.calls


def test_unknown_tag_stays_idle_and_writes_marker(tmp_path):
    handler, config = make_handler(tmp_path, {"AABBCCDDEEFF": ["a.mp3"]})
    handler.initialize()

    handler.rfid_tag_event("FF00FF00FF00")

    assert isinstance(handler.state, Idle)
    assert os.path.exists(config.unknown_tag_file)
    with open(config.unknown_tag_file) as f:
        assert f.read() == "FF00FF00FF00"


def test_removing_unknown_tag_clears_marker(tmp_path):
    handler, config = make_handler(tmp_path, {"AABBCCDDEEFF": ["a.mp3"]})
    handler.initialize()
    handler.rfid_tag_event("FF00FF00FF00")

    handler.rfid_tag_event(None)

    assert not os.path.exists(config.unknown_tag_file)
    assert isinstance(handler.state, Idle)


def test_removing_tag_saves_state_and_returns_to_idle(tmp_path):
    handler, _ = make_handler(tmp_path, {"AABBCCDDEEFF": ["a.mp3", "b.mp3"]})
    handler.initialize()
    handler.rfid_tag_event("AABBCCDDEEFF")
    handler.player._position = 12345

    handler.rfid_tag_event(None)

    assert isinstance(handler.state, Idle)
    album_dir = handler.library.current_album_dir("AABBCCDDEEFF")
    with open(os.path.join(album_dir, ".songstate")) as f:
        assert f.read() == "0\n12345\n"


def test_player_stop_event_advances_to_next_song_and_wraps(tmp_path):
    handler, _ = make_handler(tmp_path, {"AABBCCDDEEFF": ["a.mp3", "b.mp3"]})
    handler.initialize()
    handler.rfid_tag_event("AABBCCDDEEFF")

    handler.player_stop_event()
    assert handler.state.song_index == 1
    assert handler.player.current_file.endswith("b.mp3")

    handler.player_stop_event()
    assert handler.state.song_index == 0
    assert handler.player.current_file.endswith("a.mp3")


def test_player_stop_event_ignored_while_idle(tmp_path):
    handler, _ = make_handler(tmp_path, {"AABBCCDDEEFF": ["a.mp3"]})
    handler.initialize()

    result = handler.player_stop_event()

    assert result is None
    assert isinstance(handler.state, Idle)


def test_expected_stop_swallows_one_stop_event(tmp_path):
    handler, _ = make_handler(tmp_path, {"AABBCCDDEEFF": ["a.mp3", "b.mp3", "c.mp3"]})
    handler.initialize()
    handler.rfid_tag_event("AABBCCDDEEFF")

    handler.button_event(Button.YELLOW, 100)  # short press -> next song, sets expected_stop
    assert handler.state.song_index == 1

    # the stray stop event from the skip's stop_track() call must be swallowed
    handler.player_stop_event()
    assert handler.state.song_index == 1  # not advanced again

    # a later real stop advances normally
    handler.player_stop_event()
    assert handler.state.song_index == 2


def test_album_switch_preserves_expected_stop_across_the_new_playing_state(tmp_path):
    # The tricky case: expected_stop must stay controller-level (not reset by
    # entering a fresh Playing state), or the old album's stray stop event
    # would be misread as the new album's song ending.
    handler, _ = make_handler(
        tmp_path,
        {"112233445566": {"album1": ["1.mp3"], "album2": ["1.mp3"]}},
    )
    handler.initialize()
    handler.rfid_tag_event("112233445566")
    assert handler.state.album_dir.endswith("album1")

    handler.button_event(Button.YELLOW, 2000)  # long press -> switch album

    assert handler.state.album_dir.endswith("album2")
    assert handler.expected_stop is True  # armed by the old album's stop_track()

    # the old album's stray @P 0 arrives now, after the new one is playing
    handler.player_stop_event()

    assert handler.state.song_index == 0  # swallowed, not advanced
    assert handler.state.album_dir.endswith("album2")  # still the new album


def test_long_press_with_single_album_does_next_song_not_album_switch(tmp_path):
    handler, _ = make_handler(tmp_path, {"AABBCCDDEEFF": ["a.mp3", "b.mp3"]})
    handler.initialize()
    handler.rfid_tag_event("AABBCCDDEEFF")

    handler.button_event(Button.YELLOW, 5000)  # long press, but only one album

    assert handler.state.tag == "AABBCCDDEEFF"
    assert handler.state.song_index == 1  # treated as a song skip


def test_yellow_blue_ignored_while_idle(tmp_path):
    handler, _ = make_handler(tmp_path, {"AABBCCDDEEFF": ["a.mp3"]})
    handler.initialize()

    result = handler.button_event(Button.YELLOW, 100)

    assert isinstance(handler.state, Idle)
    assert isinstance(result, Never)


def test_green_red_adjusts_volume_via_config_scale(tmp_path):
    handler, config = make_handler(tmp_path, {"AABBCCDDEEFF": ["a.mp3"]})
    handler.initialize()
    assert handler.player.get_volume() == config.default_volume

    handler.button_event(Button.GREEN, 100)

    idx = config.volumes.index(config.default_volume)
    assert handler.player.get_volume() == config.volumes[idx + 1]


def test_uninitialize_saves_state_when_playing(tmp_path):
    handler, _ = make_handler(tmp_path, {"AABBCCDDEEFF": ["a.mp3"]})
    handler.initialize()
    handler.rfid_tag_event("AABBCCDDEEFF")
    handler.player._position = 7000

    handler.uninitialize()

    album_dir = handler.library.current_album_dir("AABBCCDDEEFF")
    with open(os.path.join(album_dir, ".songstate")) as f:
        assert f.read() == "0\n7000\n"
    assert isinstance(handler.state, Idle)


def test_uninitialize_while_idle_is_a_noop_besides_clearing_leds(tmp_path):
    handler, _ = make_handler(tmp_path, {"AABBCCDDEEFF": ["a.mp3"]})
    handler.initialize()

    handler.uninitialize()

    assert ("clear",) in handler.leds.calls
    assert isinstance(handler.state, Idle)


def test_handler_result_types_used_correctly():
    # sanity check on the vocabulary these tests rely on
    assert not isinstance(Never(), Timeout)
    assert not isinstance(Done(), Never)


if __name__ == "__main__":
    import sys

    import pytest

    sys.exit(pytest.main([__file__, "-v"]))
