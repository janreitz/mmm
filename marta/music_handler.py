from dataclasses import dataclass
from logging import getLogger

from marta.config import Config
from marta.events import Button
from marta.handler import Handler, HandlerResult, Never
from marta.ledstrip import LEDStrip
from marta.library import Library
from marta.player import MPG123Player

debug = getLogger("MscHandler").debug


@dataclass
class Idle:
    pass


@dataclass
class Playing:
    tag: str
    album_dir: str
    songs: list[str]
    song_index: int = 0


class MusicHandler(Handler):
    LONG_CLICK_THRESHOLD = 1500

    CONTROL_PITCH = 0
    CONTROL_VOLUME = 1
    CONTROL_BRIGHTNESS = 2

    def __init__(self, player: MPG123Player, leds: LEDStrip, config: Config):
        self.player = player
        self.leds = leds
        self.config = config
        self.library = Library(config)

        self.currently_controlling = MusicHandler.CONTROL_VOLUME
        # Deliberately controller-level, not part of Playing: set while
        # switching albums to swallow the *old* album's stray stop-event
        # after the *new* one is already loaded (see _next_previous_album).
        # Scoping it to a (fresh) Playing instance would silently break
        # that suppression.
        self.expected_stop = False

        self.state: Idle | Playing = Idle()

    def initialize(self) -> Never:
        debug("init")
        self.state = Idle()
        # breathing ring = powered but idle, as a reminder to turn the box off
        self.leds.breathe()
        return Never()

    def uninitialize(self) -> None:
        debug("uninitialize")
        self.leds.clear()
        match self.state:
            case Playing() as playing:
                self._save_and_stop(playing)
            case Idle():
                pass
        self.state = Idle()

    def _save_and_stop(self, playing: Playing) -> None:
        # The track may already have stopped on its own (song end racing
        # with tag removal). Don't toggle pause then, it would restart it.
        if not self.player.is_track_stopped():
            self.player.pause_track()

        self.library.save_songstate(playing.album_dir, playing.song_index, self.player.get_position_in_millis())

        # Only expect a stop event if a stop command was actually sent,
        # otherwise the flag would swallow the next real song-end event.
        self.expected_stop = self.player.stop_track()

    def _enter_idle_from_playing(self, playing: Playing) -> HandlerResult:
        debug("tag removed.")
        self.leds.fade_up_and_down(LEDStrip.RED)
        self._save_and_stop(playing)
        self.state = Idle()
        self.leds.breathe()
        return Never()

    def _enter_playing(self, tag: str) -> HandlerResult:
        album_dir = self.library.current_album_dir(tag)
        contents = self.library.load_album(album_dir)
        self.player.load_track_from_file(contents.songs[contents.song_index])
        if contents.position_millis != 0:
            self.player.set_position_in_millis(contents.position_millis)

        # end the sticky idle breathing: the ring stays dark during playback
        self.leds.clear()

        if len(contents.songs) == 1:
            self.leds.fade_up_and_down(LEDStrip.GREEN)
        else:
            self.leds.song(contents.song_index, len(contents.songs))
        self.player.play_track()

        self.state = Playing(tag=tag, album_dir=album_dir, songs=contents.songs, song_index=contents.song_index)
        return Never()

    def _unknown_tag(self, tag: str) -> HandlerResult:
        debug("unknown tag")
        self.library.write_unknown_tag(tag)
        self.leds.fade_up_and_down(LEDStrip.ORANGE)
        # still waiting for a usable tag
        self.leds.breathe()
        return Never()

    def rfid_tag_event(self, tag: str | None) -> HandlerResult:
        debug("tag=%s", tag)

        if tag is None:
            match self.state:
                case Idle():
                    debug("probably removed unknown tag")
                    self.library.clear_unknown_tag_marker()
                    self.leds.fade_up_and_down(LEDStrip.RED)
                    self.leds.breathe()
                    return Never()
                case Playing() as playing:
                    return self._enter_idle_from_playing(playing)

        if not self.library.has_tag(tag):
            return self._unknown_tag(tag)

        # Matches the legacy behavior: a known tag arriving without a prior
        # TagRemoved (shouldn't happen with real hardware, which always
        # alternates) switches straight to the new tag without saving or
        # stopping whatever was playing before.
        return self._enter_playing(tag)

    def rotation_event(self, x: float, y: float) -> HandlerResult:
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

    def player_stop_event(self) -> HandlerResult:
        if self.expected_stop:
            self.expected_stop = False
            debug("ignoring this event because stopping is expected")
            return None

        match self.state:
            case Idle():
                debug("stop event without an active tag. ignoring")
                return None
            case Playing() as playing:
                return self._advance_song(playing)
        return None

    def _advance_song(self, playing: Playing) -> HandlerResult:
        playing.song_index = (playing.song_index + 1) % len(playing.songs)
        if len(playing.songs) == 1:
            self.leds.fade_up_and_down(LEDStrip.GREEN)
        else:
            self.leds.song(playing.song_index, len(playing.songs))
        self.player.load_track_from_file(playing.songs[playing.song_index])
        self.player.play_track()
        return None

    def _adjust_control(self, button: Button) -> None:
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

        new = current + 1 if button == Button.GREEN else current - 1

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

    def _next_previous_album(self, button: Button, playing: Playing) -> None:
        tag = playing.tag
        self.library.rotate_album(tag, forward=button == Button.YELLOW, previous_album_dir=playing.album_dir)
        self._enter_idle_from_playing(playing)
        self._enter_playing(tag)

    def _next_previous_song(self, button: Button, playing: Playing) -> None:
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
            playing.song_index = (playing.song_index + off) % len(playing.songs)
            self.player.load_track_from_file(playing.songs[playing.song_index])
            self.player.play_track()

        if len(playing.songs) == 1:
            self.leds.fade_up_and_down(LEDStrip.GREEN)
            return

        self.leds.song(playing.song_index, len(playing.songs), forward=button == Button.YELLOW)

    def button_event(self, button: Button, millis: int) -> HandlerResult:
        debug("button: %s", button.name)

        if button == Button.YELLOW or button == Button.BLUE:
            match self.state:
                case Idle():
                    debug("no tag. ignore")
                case Playing() as playing:
                    if millis > MusicHandler.LONG_CLICK_THRESHOLD and self.library.has_multiple_albums(playing.tag):
                        self._next_previous_album(button, playing)
                    else:
                        self._next_previous_song(button, playing)
        elif button == Button.GREEN or button == Button.RED:
            self._adjust_control(button)

        if isinstance(self.state, Idle):
            # make sure breathing is on: it resumes by itself once the
            # volume/pitch/brightness animation has finished
            self.leds.breathe()
        return Never()
