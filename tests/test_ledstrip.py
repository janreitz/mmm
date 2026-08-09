import sys
import time

import fake_rpi_ws281x

sys.modules["_rpi_ws281x"] = fake_rpi_ws281x

from marta.ledstrip import LEDStrip


def is_breathing_frame(frame):
    """All LEDs (nearly) the same dim white value: r == g == b > 0, and at
    most two adjacent levels present (spatial dithering)."""
    values = set(frame)
    if not values or values == {0}:
        return False
    for v in values:
        r, g, b = (v >> 16) & 255, (v >> 8) & 255, v & 255
        if not (r == g == b > 0):
            return False
    return max(values) - min(values) <= (1 << 16) + (1 << 8) + 1


def frames_between(t_from, t_to):
    return [f for ts, f in fake_rpi_ws281x.RENDERS if t_from <= ts <= t_to]


def test_breathing_yields_to_animations_and_resumes():
    strip = LEDStrip()

    t0 = time.monotonic()
    strip.breathe()
    time.sleep(1.0)
    assert any(is_breathing_frame(f) for f in frames_between(t0, time.monotonic())), (
        "no breathing frames after breathe()"
    )

    # a volume press while idle, exactly like MusicHandler does it: the volume
    # animation must play out fully, then breathing must resume by itself
    t1 = time.monotonic()
    strip.volume(3)
    strip.breathe()
    time.sleep(3.5)

    during_animation = frames_between(t1 + 0.1, t1 + 1.3)
    assert during_animation, "volume animation rendered nothing"
    assert not any(is_breathing_frame(f) for f in during_animation), "breathing interrupted the volume animation"
    assert any(len(set(f)) > 2 for f in during_animation), "no volume bar frames seen"

    after_animation = frames_between(t1 + 2.0, time.monotonic())
    assert any(is_breathing_frame(f) for f in after_animation), "breathing did not resume after the volume animation"

    # clear() must end the idle state for good
    t2 = time.monotonic()
    strip.clear()
    time.sleep(1.0)
    late = frames_between(t2 + 0.5, time.monotonic())
    assert not any(is_breathing_frame(f) for f in late), "breathing kept running after clear()"

    strip.terminate()


if __name__ == "__main__":
    test_breathing_yields_to_animations_and_resumes()
    print("ALL ASSERTIONS PASSED")
