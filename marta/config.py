"""Deployment configuration, consolidated from what used to be scattered as
module-level constants (several read from `$MARTA` at *import* time, in more
than one module) across Marta.py, MusicHandler.py, RFIDReader.py, MPG123.py
and TagToHandler.py.

Deliberately NOT here: button/LED-strip GPIO pins and hardware wiring
parameters (frequency, DMA channel, ...) - those are fixed by the PCB, not
meaningfully "configuration", and stay next to the code that uses them
(events.Button, ledstrip.py) as originally sketched in docs/redesign.md.
Filename/format conventions (.songstate, .albumindicator) stay in the
modules that own that format, for the same reason.
"""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    base_dir: str
    audio_dir: str
    start_sound_path: str
    shutdown_sound_path: str
    unknown_tag_file: str
    log_file: str

    system_sound_volume: int = 2

    # music control scales: (allowed values..., default)
    volumes: tuple[int, ...] = (2, 3, 4, 5, 7, 9, 12, 15, 18, 22)
    default_volume: int = 2
    pitches: tuple[int, ...] = (55, 70, 85, 100, 115, 130, 145, 160, 175, 190)
    default_pitch: int = 100
    brightnesses: tuple[int, ...] = (0, 28, 56, 84, 112, 140, 168, 196, 224, 255)
    default_brightness: int = 255

    # LED ring idle breathing (see ledstrip.py for why these specific values)
    breathe_min_level: int = 4
    breathe_max_level: int = 32
    breathe_period_seconds: float = 5.0
    breathe_fps: int = 25

    # special tags: mode switches and the debug interrupt tag
    interrupt_tag: str = "5600C7AC4B76"
    button_light_tag: str = "5A00834F9204"
    rainbow_tag: str = "5500ACB96121"

    mpg123_binary: str = "mpg123"

    rfid_port: str = "/dev/serial0"
    rfid_baud_rate: int = 9600
    rfid_timeout: float = 0.5

    @staticmethod
    def from_env() -> "Config":
        """Build the config from $MARTA, resolved here (at call time, in
        main()) rather than at module import time like the legacy code did."""
        base_dir = os.environ["MARTA"]
        audio_dir = os.path.join(base_dir, "audio")
        return Config(
            base_dir=base_dir,
            audio_dir=audio_dir,
            start_sound_path=os.path.join(audio_dir, "system", "startup.mp3"),
            shutdown_sound_path=os.path.join(audio_dir, "system", "shutdown.mp3"),
            unknown_tag_file=os.path.join(audio_dir, "unknown_tag.txt"),
            log_file=os.path.join(base_dir, "logs", "mmm.log"),
        )
