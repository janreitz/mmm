from logging import getLogger

from marta.ledstrip import LEDStrip
from marta.handler import Handler, Timeout, Done
from marta.events import Button

debug = getLogger("BtnLgtHdlr").debug


class ButtonLightHandler(Handler):
    TIMEOUT = 60

    def __init__(self, leds: LEDStrip):
        self.leds = leds

    def button_event(self, button: Button, millis: int):
        if button == Button.BLUE:
            self.leds.fade_up_and_down(LEDStrip.BLUE)
        elif button == Button.RED:
            self.leds.fade_up_and_down(LEDStrip.RED)
        elif button == Button.GREEN:
            self.leds.fade_up_and_down(LEDStrip.GREEN)
        elif button == Button.YELLOW:
            self.leds.fade_up_and_down(LEDStrip.YELLOW)

        return Timeout(ButtonLightHandler.TIMEOUT)

    def rfid_tag_event(self, tag: str | None):
        debug("tag: " + str(tag))
        if tag is None:
            return Done()
        return None

    def initialize(self):
        self.leds.fade_up_and_down(LEDStrip.WHITE)
        debug("init!!!")
        return Timeout(ButtonLightHandler.TIMEOUT)

    def uninitialize(self):
        self.leds.fade_up_and_down(LEDStrip.WHITE)
        debug("uninit!!!")
