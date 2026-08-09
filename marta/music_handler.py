from logging import getLogger
from os import listdir, remove
from os.path import exists

from marta.util import sorted_aphanumeric
from marta.ledstrip import LEDStrip
from marta.handler import Handler, Never
from marta.events import Button
from marta.config import Config
from marta.player import MPG123Player
from marta.tag_to_dir import TAG_TO_DIR, prepare, ALBUM_INDICATOR_FILE

debug = getLogger("MscHandler").debug


class MusicHandler(Handler):
    LONG_CLICK_THRESHOLD = 1500

    SONG_STATE_FILE = ".songstate"

    CONTROL_PITCH = 0
    CONTROL_VOLUME = 1
    CONTROL_BRIGHTNESS = 2

    def __init__(self, player: MPG123Player, leds: LEDStrip, config: Config):
        self.player = player
        self.leds = leds
        self.config = config

        self.currently_controlling = MusicHandler.CONTROL_VOLUME
        self.all_songs: list[str] | None = None
        self.current_song_index = 0
        self.current_song_dir: str | None = None
        self.current_tag: str | None = None
        self.expected_stop = False

        if exists(config.unknown_tag_file):
            debug("unknown tag file exists. removing")
            remove(config.unknown_tag_file)

        prepare(config.audio_dir)

    def initialize(self):
        debug("init")
        # breathing ring = powered but idle, as a reminder to turn the box off
        self.leds.breathe()
        return Never()

    def save_state_and_stop(self):
        # The track may already have stopped on its own (song end racing with
        # tag removal). Don't toggle pause then, it would start playback again.
        if not self.player.is_track_stopped():
            self.player.pause_track()

        debug("Saving state.")
        with open(self.current_song_dir + "/" + MusicHandler.SONG_STATE_FILE, "w") as state_file:
            debug("writing to file: " + self.current_song_dir + "/" + MusicHandler.SONG_STATE_FILE)
            state_file.write(str(self.current_song_index) + "\n" + str(self.player.get_position_in_millis()) + "\n")
        self.current_song_dir = None
        self.current_tag = None
        self.all_songs = None
        self.current_song_index = 0

        # Only expect a stop event if a stop command was actually sent,
        # otherwise the flag would swallow the next real song-end event.
        self.expected_stop = self.player.stop_track()

    def load_state(self, tag):
        debug("Loading state.")
        self.current_tag = tag
        self.current_song_dir = TAG_TO_DIR[self.current_tag][0]
        debug("tag name: " + self.current_song_dir)
        songs = sorted_aphanumeric(listdir(self.current_song_dir))

        current_pos = 0

        if ALBUM_INDICATOR_FILE in songs:
            songs.remove(ALBUM_INDICATOR_FILE)

        if MusicHandler.SONG_STATE_FILE in songs:
            songs.remove(MusicHandler.SONG_STATE_FILE)
            with open(self.current_song_dir + "/" + MusicHandler.SONG_STATE_FILE) as state_file:
                debug("reading from file: " + self.current_song_dir + "/" + MusicHandler.SONG_STATE_FILE)
                lines = state_file.readlines()
                lines = [line.strip() for line in lines]
                self.current_song_index = int(lines[0])
                debug("current song index: " + str(self.current_song_index))
                current_pos = int(lines[1])
                debug("current song position: " + str(current_pos))

        self.all_songs = [self.current_song_dir + "/" + song for song in songs]
        debug("all songs: " + str(self.all_songs))

        return current_pos

    def rfid_removed_event(self):
        debug("tag removed.")
        self.leds.fade_up_and_down(LEDStrip.RED)
        self.save_state_and_stop()
        self.leds.breathe()
        return Never()

    def rfid_music_tag_event(self, tag):
        current_position = self.load_state(tag)
        self.player.load_track_from_file(self.all_songs[self.current_song_index])
        if current_position != 0:
            self.player.set_position_in_millis(current_position)

        # end the sticky idle breathing: the ring stays dark during playback
        self.leds.clear()

        if len(self.all_songs) == 1:
            self.leds.fade_up_and_down(LEDStrip.GREEN)
        else:
            self.leds.song(self.current_song_index, len(self.all_songs))
        self.player.play_track()
        return Never()

    def rfid_tag_event(self, tag):
        debug("tag=%s", tag)

        if tag is None:
            if self.current_tag is None:
                debug("probably removed unknown tag")

                if exists(self.config.unknown_tag_file):
                    debug("unknown tag file exists. removing")
                    remove(self.config.unknown_tag_file)

                self.leds.fade_up_and_down(LEDStrip.RED)
                self.leds.breathe()
                return Never()

            return self.rfid_removed_event()

        if tag not in TAG_TO_DIR:
            self.current_song_dir = None
            debug("unknown tag")

            with open(self.config.unknown_tag_file, "w") as unknown_tag_file:
                debug("writing to unknown tag file")
                unknown_tag_file.write(tag)

            self.leds.fade_up_and_down(LEDStrip.ORANGE)
            # still waiting for a usable tag
            self.leds.breathe()
            return Never()

        return self.rfid_music_tag_event(tag)

    def rotation_event(self, x, y):
        debug("rotation event!")
        if x < -45:
            if self.currently_controlling == MusicHandler.CONTROL_BRIGHTNESS:
                return None

            self.currently_controlling = MusicHandler.CONTROL_BRIGHTNESS
            self.leds.fade_up_and_down(LEDStrip.PURPLE)
            debug("now controlling brightness")
            return None

        if x > 45:
            if self.currently_controlling == MusicHandler.CONTROL_PITCH:
                return None

            self.currently_controlling = MusicHandler.CONTROL_PITCH
            self.leds.fade_up_and_down(LEDStrip.YELLOW)
            debug("now controlling pitch")
            return None

        if self.currently_controlling == MusicHandler.CONTROL_VOLUME:
            return None

        self.currently_controlling = MusicHandler.CONTROL_VOLUME
        self.leds.fade_up_and_down(LEDStrip.BLUE)
        debug("now controlling volume")
        return None

    def player_stop_event(self):
        if self.expected_stop:
            self.expected_stop = False
            debug("ignoring this event because stopping is expected")
            return None

        if self.all_songs is None:
            debug("stop event without an active tag. ignoring")
            return None

        self.current_song_index = (self.current_song_index + 1) % len(self.all_songs)
        if len(self.all_songs) == 1:
            self.leds.fade_up_and_down(LEDStrip.GREEN)
        else:
            self.leds.song(self.current_song_index, len(self.all_songs))
        self.player.load_track_from_file(self.all_songs[self.current_song_index])
        self.player.play_track()
        return None

    def button_red_green_event(self, button: Button, millis):
        if self.currently_controlling == MusicHandler.CONTROL_VOLUME:
            debug("change volume")
            arr = self.config.volumes
            current = self.player.get_volume()
        elif self.currently_controlling == MusicHandler.CONTROL_PITCH:
            debug("change pitch")
            arr = self.config.pitches
            current = self.player.get_pitch()
        else:
            debug("change brightness")
            arr = self.config.brightnesses
            current = self.leds.get_brightness()

        debug("current value: " + str(current))

        if current in arr:
            current = arr.index(current)
        else:
            # e.g. a volume that is no longer part of the scale: snap to the
            # nearest step instead of crashing the message loop
            current = min(range(len(arr)), key=lambda i: abs(arr[i] - current))
            debug("current value not on the scale, snapping to index " + str(current))

        if button == Button.GREEN:
            new = current + 1
        else:
            new = current - 1

        if new < 0 or new >= len(arr):
            debug("would be out of bounds")
            self.leds.volume(current)
            return

        self.leds.volume(new)

        new = arr[new]
        debug("new value: " + str(new))

        if self.currently_controlling == MusicHandler.CONTROL_VOLUME:
            self.player.set_volume(new)
        elif self.currently_controlling == MusicHandler.CONTROL_PITCH:
            self.player.set_pitch(new)
        else:
            self.leds.set_brightness(new)

    def button_next_previous_album(self, button: Button):
        album_indicator = self.current_song_dir + "/" + ALBUM_INDICATOR_FILE
        if exists(album_indicator):
            debug("removing album indicator: " + album_indicator)
            remove(album_indicator)

        tag = self.current_tag

        off = 1 if button == Button.YELLOW else -1
        TAG_TO_DIR[self.current_tag] = TAG_TO_DIR[self.current_tag][off:] + TAG_TO_DIR[self.current_tag][:off]
        debug("changed album order: " + self.current_tag + "=" + str(TAG_TO_DIR[self.current_tag]))

        self.rfid_removed_event()
        self.rfid_tag_event(tag)

        album_indicator = self.current_song_dir + "/" + ALBUM_INDICATOR_FILE
        open(album_indicator, "w").close()

    def button_next_previous_song(self, button: Button):
        if button == Button.BLUE:
            pos = self.player.get_position_in_millis()
            debug("pos=" + str(pos))

            # if we are at the beginning of a song, skip to the beginning
            if pos > 2000:
                self.player.set_position_in_millis(0)
                off = 0
            else:
                off = -1
        else:
            off = 1

        if off != 0:
            self.expected_stop = self.player.stop_track()
            self.current_song_index = (self.current_song_index + off) % len(self.all_songs)
            self.player.load_track_from_file(self.all_songs[self.current_song_index])
            self.player.play_track()

        if len(self.all_songs) == 1:
            self.leds.fade_up_and_down(LEDStrip.GREEN)
            return

        self.leds.song(self.current_song_index, len(self.all_songs), forward=button == Button.YELLOW)

    def button_event(self, button: Button, millis):
        debug("button: %s", button.name)

        if button == Button.YELLOW or button == Button.BLUE:
            if self.current_tag is None:
                debug("no tag. ignore")
                return Never()

            if millis > MusicHandler.LONG_CLICK_THRESHOLD and len(TAG_TO_DIR[self.current_tag]) > 1:
                self.button_next_previous_album(button)
            else:
                self.button_next_previous_song(button)
        elif button == Button.GREEN or button == Button.RED:
            self.button_red_green_event(button, millis)

        if self.current_tag is None:
            # make sure breathing is on: it resumes by itself once the
            # volume/pitch/brightness animation has finished
            self.leds.breathe()
        return Never()

    def uninitialize(self):
        debug("uninitialize")
        self.leds.clear()
        if self.current_tag is not None:
            self.save_state_and_stop()
