"""Minimal stand-in for the _rpi_ws281x SWIG module, for offline tests.

Records every rendered frame (timestamp + tuple of packed color values) in
RENDERS so tests can assert on the animation output over time.
"""

from time import monotonic

WS2811_SUCCESS = 0
WS2811_STRIP_RGB = 0x100800
WS2811_STRIP_GRB = 0x081000

RENDERS = []


class _Channel(object):
    def __init__(self):
        self.count = 0
        self.gpionum = 0
        self.invert = 0
        self.brightness = 0
        self.strip_type = 0
        self.leds = []


class _Leds(object):
    def __init__(self):
        self.channels = [_Channel(), _Channel()]
        self.freq = 0
        self.dmanum = 0


def new_ws2811_t():
    return _Leds()


def delete_ws2811_t(leds):
    pass


def ws2811_channel_get(leds, channum):
    return leds.channels[channum]


def ws2811_channel_t_count_set(chan, n):
    chan.count = n
    chan.leds = [0] * n


def ws2811_channel_t_count_get(chan):
    return chan.count


def ws2811_channel_t_gpionum_set(chan, n):
    chan.gpionum = n


def ws2811_channel_t_invert_set(chan, n):
    chan.invert = n


def ws2811_channel_t_brightness_set(chan, n):
    chan.brightness = n


def ws2811_channel_t_brightness_get(chan):
    return chan.brightness


def ws2811_channel_t_strip_type_set(chan, n):
    chan.strip_type = n


def ws2811_t_freq_set(leds, n):
    leds.freq = n


def ws2811_t_dmanum_set(leds, n):
    leds.dmanum = n


def ws2811_init(leds):
    return WS2811_SUCCESS


def ws2811_render(leds):
    for chan in leds.channels:
        if chan.count:
            RENDERS.append((monotonic(), tuple(chan.leds)))
    return WS2811_SUCCESS


def ws2811_led_set(chan, n, value):
    chan.leds[n] = value


def ws2811_led_get(chan, n):
    return chan.leds[n]


def ws2811_get_return_t_str(resp):
    return "fake error %d" % resp
