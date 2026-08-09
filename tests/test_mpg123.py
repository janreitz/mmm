import os
import time

from marta.logging_setup import setup_stdout_logging
from marta.player import MPG123Player
from marta.events import PlaybackStopped, PlayerDied


def test_mpg123_player():
    setup_stdout_logging()
    fake_binary = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fake_mpg123.py")

    events = []

    player = MPG123Player(fake_binary, post=events.append, volume=2)

    assert player.load_track_from_file("/fake/track.mp3") is True, "load failed"
    assert player._track_length_in_millis == 10000, player._track_length_in_millis

    player.play_track()
    time.sleep(0.2)

    player.set_volume(5)
    player.set_pitch(115)
    assert player.get_pitch() == 115

    assert player.set_position_in_millis(5000) is True
    pos = player.get_position_in_millis()
    assert pos == 5000, pos

    # reject out-of-range without raising
    assert player.set_position_in_millis(-5) is False

    sent = player.stop_track()
    assert sent is True
    time.sleep(0.2)
    assert player.is_track_stopped()
    assert player.stop_track() is False, "second stop should be a no-op"

    stops = [e for e in events if isinstance(e, PlaybackStopped)]
    errors = [e for e in events if isinstance(e, PlayerDied)]
    assert stops, "stop event did not fire"
    assert not errors, "unexpected error event"

    player.terminate()


if __name__ == "__main__":
    test_mpg123_player()
    print("ALL ASSERTIONS PASSED")
