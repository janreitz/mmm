"""Package entry point: python -m marta

Composition root: builds Config, the hardware adapters, and the handlers,
plays the startup jingle, then hands everything to loop.Marta. This used to
be split between Marta.py's module-level main() and its __init__ (which mixed
adapter construction with the jingle choreography) - now cleanly separated.
"""

import traceback
from logging import DEBUG, Formatter, StreamHandler, getLogger, handlers
from queue import Queue
from signal import SIGINT, signal
from sys import argv, stdout
from time import sleep, strftime

from marta.button_light_handler import ButtonLightHandler
from marta.buttons import ButtonInput
from marta.config import Config
from marta.events import Event
from marta.ledstrip import LEDStrip
from marta.loop import Marta
from marta.music_handler import MusicHandler
from marta.player import MPG123Player
from marta.rainbow_handler import RainbowHandler
from marta.rfid import RFIDReader

debug = getLogger("     Marta").debug


def setup_logging(config: Config) -> None:
    logger = getLogger("")
    logger.setLevel(DEBUG)
    formatter = Formatter("%(asctime)s.%(msecs)03d | %(name)s |    %(message)s", "%H:%M:%S")

    if "log2stdout" in argv:
        ch = StreamHandler(stdout)
        ch.setFormatter(formatter)
        logger.addHandler(ch)

    fh = handlers.RotatingFileHandler(config.log_file, maxBytes=(1024 * 1024 * 10), backupCount=10)
    fh.setFormatter(formatter)
    logger.addHandler(fh)


def play_startup_jingle(
    player: MPG123Player,
    leds: LEDStrip,
    button_input: ButtonInput,
    config: Config,
    message_queue: "Queue[Event]",
) -> None:
    debug(f"Loading startup sound from: {config.start_sound_path}")
    player.load_track_from_file(config.start_sound_path)
    leds.startup()
    player.play_track()

    # hacky because MPG123Player is async. Bounded wait: if playback never
    # starts (e.g. the audio device is not usable yet), fail so systemd
    # restarts us instead of hanging here forever with the RFID reader
    # never coming up.
    for _ in range(200):
        if player.is_track_playing():
            break
        sleep(0.05)
    else:
        raise Exception("startup sound did not start playing within 10s")

    blink = True
    while player.is_track_playing():
        button_input.set_status_led(blink)
        sleep(0.2)
        blink = not blink

    button_input.set_status_led(False)

    # Empty q after short period of time (player stop event and button pushes)
    sleep(0.1)
    while not message_queue.empty():
        message_queue.get(block=False)


def build_marta(config: Config, message_queue: "Queue[Event]") -> Marta:
    button_input = ButtonInput(post=message_queue.put)
    player = MPG123Player(config.mpg123_binary, post=message_queue.put, volume=config.system_sound_volume)
    leds = LEDStrip()

    play_startup_jingle(player, leds, button_input, config, message_queue)

    rfid_reader = RFIDReader(
        post=message_queue.put,
        port=config.rfid_port,
        baud_rate=config.rfid_baud_rate,
        timeout=config.rfid_timeout,
    )

    music_handler = MusicHandler(player, leds, config)
    rainbow_handler = RainbowHandler(leds)
    button_light_handler = ButtonLightHandler(leds)
    handlers_by_tag = {
        config.button_light_tag: button_light_handler,
        config.rainbow_tag: rainbow_handler,
    }

    return Marta(
        message_queue=message_queue,
        config=config,
        player=player,
        leds=leds,
        button_input=button_input,
        rfid_reader=rfid_reader,
        default_handler=music_handler,
        handlers_by_tag=handlers_by_tag,
    )


def main():
    config = Config.from_env()
    setup_logging(config)

    debug("#################################################")
    debug("#                  INITIALIZED                  #")
    debug("#              " + strftime("%Y-%m-%d %H:%M:%S") + "              #")
    debug("#################################################")

    debug(r"""

                            _    _        _                                _
                           | |  | |      | |                              | |
                           | |  | |  ___ | |  ___  ___   _ __ ___    ___  | |_  ___
                           | |/\| | / _ \| | / __|/ _ \ | '_ ` _ \  / _ \ | __|/ _ \
                           \  /\  /|  __/| || (__| (_) || | | | | ||  __/ | |_| (_) |
                            \/  \/  \___||_| \___|\___/ |_| |_| |_| \___|  \__|\___/


    MMMMMMMM               MMMMMMMM     MMMMMMMM               MMMMMMMM     MMMMMMMM               MMMMMMMM
    M:::::::M             M:::::::M     M:::::::M             M:::::::M     M:::::::M             M:::::::M
    M::::::::M           M::::::::M     M::::::::M           M::::::::M     M::::::::M           M::::::::M
    M:::::::::M         M:::::::::M     M:::::::::M         M:::::::::M     M:::::::::M         M:::::::::M
    M::::::::::M       M::::::::::M     M::::::::::M       M::::::::::M     M::::::::::M       M::::::::::M
    M:::::::::::M     M:::::::::::M     M:::::::::::M     M:::::::::::M     M:::::::::::M     M:::::::::::M
    M:::::::M::::M   M::::M:::::::M     M:::::::M::::M   M::::M:::::::M     M:::::::M::::M   M::::M:::::::M
    M::::::M M::::M M::::M M::::::M     M::::::M M::::M M::::M M::::::M     M::::::M M::::M M::::M M::::::M
    M::::::M  M::::M::::M  M::::::M     M::::::M  M::::M::::M  M::::::M     M::::::M  M::::M::::M  M::::::M
    M::::::M   M:::::::M   M::::::M     M::::::M   M:::::::M   M::::::M     M::::::M   M:::::::M   M::::::M
    M::::::M    M:::::M    M::::::M     M::::::M    M:::::M    M::::::M     M::::::M    M:::::M    M::::::M
    M::::::M     MMMMM     M::::::M     M::::::M     MMMMM     M::::::M     M::::::M     MMMMM     M::::::M
    M::::::M               M::::::M     M::::::M               M::::::M     M::::::M               M::::::M
    M::::::M               M::::::M     M::::::M               M::::::M     M::::::M               M::::::M
    M::::::M               M::::::M     M::::::M               M::::::M     M::::::M               M::::::M
    MMMMMMMM               MMMMMMMM     MMMMMMMM               MMMMMMMM     MMMMMMMM               MMMMMMMM

    """)

    debug("initializing")

    message_queue: "Queue[Event]" = Queue()
    marta = build_marta(config, message_queue)
    signal(SIGINT, lambda s, f: marta.interrupt())

    debug("looping")
    try:
        exit_val = marta.message_loop()
    except Exception as e:
        debug("excepted: " + str(e))
        debug(traceback.format_exc())
        exit_val = 1

    marta.terminate()

    debug("exiting")
    exit(exit_val)


if __name__ == "__main__":
    main()
