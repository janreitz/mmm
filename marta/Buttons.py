from logging import getLogger
from time import monotonic as mtime
from gpiozero import Button, LED

debug = getLogger('   Buttons').debug

POWER_BUTTON = 17
RUN_LED = 20

YELLOW_BUTTON = 5
BLUE_BUTTON = 6
RED_BUTTON = 13
GREEN_BUTTON = 26

COLOR_BUTTONS = [YELLOW_BUTTON, BLUE_BUTTON, RED_BUTTON, GREEN_BUTTON]

BUTTONS_HUMAN_READABLE = {
    YELLOW_BUTTON: "YELLOW",
    BLUE_BUTTON: "BLUE",
    RED_BUTTON: "RED",
    GREEN_BUTTON: "GREEN",
    POWER_BUTTON: "POWER"
}

# Global variables for gpiozero objects
_buttons = {}
_status_led = None
_button_callback = None
_buttons_last_pushed_time = {}

def setup_gpio(button_callback):
    global _buttons, _status_led, _button_callback, _buttons_last_pushed_time
    
    debug("setting up gpio with gpiozero")
    
    _button_callback = button_callback
    
    # Initialize button tracking
    for pin in COLOR_BUTTONS + [POWER_BUTTON]:
        _buttons_last_pushed_time[pin] = 0
    
    # Setup status LED
    _status_led = LED(RUN_LED)
    
    # Setup buttons with pull-up resistors and debouncing
    for pin in COLOR_BUTTONS + [POWER_BUTTON]:
        # bounce_time handles debouncing automatically
        btn = Button(pin, pull_up=True, bounce_time=0.05)
        btn.when_pressed = lambda btn_obj, pin=pin: _on_button_press(pin)
        btn.when_released = lambda btn_obj, pin=pin: _on_button_release(pin)
        _buttons[pin] = btn
        debug(f"Setup button on pin {pin}")

def _on_button_press(pin):
    """Called when button is pressed down"""
    now = int(mtime() * 1000)
    _buttons_last_pushed_time[pin] = now
    debug(f"Button {BUTTONS_HUMAN_READABLE.get(pin, pin)} pressed")

def _on_button_release(pin):
    """Called when button is released - this is where we trigger the callback"""
    now = int(mtime() * 1000)
    press_time = _buttons_last_pushed_time[pin]
    
    if press_time == 0:
        debug(f"Button {pin} released but no press time recorded")
        return
    
    diff = now - press_time
    _buttons_last_pushed_time[pin] = 0
    
    if diff < 50:  # Debounce - ignore very short presses
        debug(f"Button {pin} press too short ({diff}ms), ignoring")
        return
    
    debug("push event on pin " + str(pin) + ": " + str(diff))
    if _button_callback:
        _button_callback(pin, diff)

def set_status_led(value):
    """Set the status LED on (True/1) or off (False/0)"""
    global _status_led
    if _status_led:
        if value:
            _status_led.on()
        else:
            _status_led.off()

def is_pushed(pin):
    """Check if a button is currently being pressed"""
    global _buttons
    if pin in _buttons:
        # With pull_up=True, the button reads False when pressed
        return not _buttons[pin].is_pressed
    debug(f"Button {pin} not found in setup buttons")
    return False

def terminate():
    """Clean up GPIO resources"""
    global _buttons, _status_led
    debug("terminating")
    
    if _status_led:
        _status_led.close()
        _status_led = None
    
    for pin, btn in _buttons.items():
        debug(f"Closing button {pin}")
        btn.close()
    _buttons.clear()

################################################################

def main():
    from SetupLogging import setup_stdout_logging
    setup_stdout_logging()

    debug("push the buttons!")
    debug("ENTER or CTRL + C to quit")

    setup_gpio(lambda pin, millis: debug(BUTTONS_HUMAN_READABLE[pin] + ": " + str(millis) + " ms"))

    try:
        input()
    except:
        pass

    terminate()

if __name__ == "__main__":
    main()