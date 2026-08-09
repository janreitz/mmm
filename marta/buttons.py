from logging import getLogger
from time import monotonic as mtime
from typing import Callable

from gpiozero import LED
from gpiozero import Button as GpioButton

from marta.events import Button, ButtonPressed, Event

debug = getLogger("   Buttons").debug

RUN_LED = 20


class ButtonInput:
    def __init__(self, post: Callable[[Event], None]):
        debug("setting up gpio with gpiozero")

        self._post = post
        self._last_pushed_time: dict[Button, int] = dict.fromkeys(Button, 0)

        self._status_led: LED | None = LED(RUN_LED)

        # bounce_time handles debouncing automatically
        self._buttons: dict[Button, GpioButton] = {}
        for button in Button:
            gpio_button = GpioButton(button.value, pull_up=True, bounce_time=0.05)
            gpio_button.when_pressed = lambda _b, button=button: self._on_press(button)
            gpio_button.when_released = lambda _b, button=button: self._on_release(button)
            self._buttons[button] = gpio_button
            debug(f"Setup button {button.name} on pin {button.value}")

    def _on_press(self, button: Button) -> None:
        """Called when button is pressed down"""
        now = int(mtime() * 1000)
        self._last_pushed_time[button] = now
        debug(f"Button {button.name} pressed")

    def _on_release(self, button: Button) -> None:
        """Called when button is released - this is where we trigger the callback"""
        now = int(mtime() * 1000)
        press_time = self._last_pushed_time[button]

        if press_time == 0:
            debug(f"Button {button.name} released but no press time recorded")
            return

        diff = now - press_time
        self._last_pushed_time[button] = 0

        if diff < 50:  # Debounce - ignore very short presses
            debug(f"Button {button.name} press too short ({diff}ms), ignoring")
            return

        debug(f"push event on {button.name}: {diff}")
        self._post(ButtonPressed(button, diff))

    def set_status_led(self, value: bool) -> None:
        """Set the status LED on (True) or off (False)"""
        if self._status_led:
            if value:
                self._status_led.on()
            else:
                self._status_led.off()

    def is_pushed(self, button: Button) -> bool:
        """Check if a button is currently being pressed"""
        if button in self._buttons:
            return self._buttons[button].is_pressed
        debug(f"Button {button} not found in setup buttons")
        return False

    def terminate(self) -> None:
        """Clean up GPIO resources"""
        debug("terminating")

        if self._status_led:
            self._status_led.close()
            self._status_led = None

        for button, gpio_button in self._buttons.items():
            debug(f"Closing button {button.name}")
            gpio_button.close()
        self._buttons.clear()


################################################################


def main():
    from marta.logging_setup import setup_stdout_logging

    setup_stdout_logging()

    debug("push the buttons!")
    debug("ENTER or CTRL + C to quit")

    button_input = ButtonInput(post=lambda event: debug("%r", event))

    try:
        input()
    except:
        pass

    button_input.terminate()


if __name__ == "__main__":
    main()
