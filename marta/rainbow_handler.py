from logging import getLogger

from marta.ledstrip import LEDStrip
from marta.handler import Handler, Timeout, Done

debug = getLogger("RnbwHndler").debug


class RainbowHandler(Handler):
    TIMEOUT = 60

    def __init__(self, leds: LEDStrip):
        self.leds = leds

    def rfid_tag_event(self, tag: str | None):
        debug("tag: " + str(tag))
        if tag is None:
            return Done()
        return None

    def initialize(self):
        debug("init!!!")
        self.leds.rainbow_demo()
        return Timeout(RainbowHandler.TIMEOUT)

    def uninitialize(self):
        self.leds.clear()
        debug("uninit!!!")
