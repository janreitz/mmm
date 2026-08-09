"""The music library: every filesystem interaction with the audio directory
lives here (tag -> albums -> songs scanning/validation, album rotation and
its on-disk marker, .songstate persistence, the unknown-tag scratch file).
No player/LED/hardware dependencies - unit-testable against a real temp
directory alone. Absorbs the former tag_to_dir.py.
"""

import os
from logging import getLogger
from dataclasses import dataclass
from os import listdir, remove
from os.path import exists, isdir
from re import compile as re_compile, match as re_match

from marta.config import Config
from marta.util import sorted_aphanumeric

debug = getLogger("  Library").debug

ALBUM_INDICATOR_FILE = ".albumindicator"
SONG_STATE_FILE = ".songstate"

_TAG_NAME_RE = re_compile("^.*([0-9A-F]{12})$")


@dataclass(frozen=True)
class AlbumContents:
    songs: list[str]  # full paths, sorted, reserved files excluded
    song_index: int  # 0 if no/invalid saved state
    position_millis: int  # 0 if no/invalid saved state


class Library:
    def __init__(self, config: Config):
        self._unknown_tag_file = config.unknown_tag_file

        # Must run before _scan(): a leftover unknown_tag_file lives directly
        # in audio_dir, and _scan() rejects any top-level entry that isn't a
        # tag directory (or "system") - a stale file left over from a
        # previous run would otherwise make the scan itself fail.
        if exists(self._unknown_tag_file):
            debug("unknown tag file exists. removing")
            remove(self._unknown_tag_file)

        self._tag_to_albums: dict[str, list[str]] = _scan(config.audio_dir)

    def has_tag(self, tag: str) -> bool:
        return tag in self._tag_to_albums

    def has_multiple_albums(self, tag: str) -> bool:
        return len(self._tag_to_albums[tag]) > 1

    def current_album_dir(self, tag: str) -> str:
        return self._tag_to_albums[tag][0]

    def rotate_album(self, tag: str, forward: bool, previous_album_dir: str) -> None:
        """Rotate tag's album order and move the on-disk "current album"
        marker from previous_album_dir to the new head album."""
        previous_indicator = previous_album_dir + "/" + ALBUM_INDICATOR_FILE
        if exists(previous_indicator):
            debug("removing album indicator: " + previous_indicator)
            remove(previous_indicator)

        albums = self._tag_to_albums[tag]
        # we have to shift and cannot simply insert in place at index 0
        # because that doesn't rotate the other entries
        off = 1 if forward else -1
        self._tag_to_albums[tag] = albums[off:] + albums[:off]
        debug("changed album order: " + tag + "=" + str(self._tag_to_albums[tag]))

        open(self.current_album_dir(tag) + "/" + ALBUM_INDICATOR_FILE, "w").close()

    def load_album(self, album_dir: str) -> AlbumContents:
        debug("Loading album: " + album_dir)
        songs = sorted_aphanumeric(listdir(album_dir))

        if ALBUM_INDICATOR_FILE in songs:
            songs.remove(ALBUM_INDICATOR_FILE)

        song_index = 0
        position_millis = 0
        if SONG_STATE_FILE in songs:
            songs.remove(SONG_STATE_FILE)
            state_path = album_dir + "/" + SONG_STATE_FILE
            with open(state_path) as state_file:
                debug("reading from file: " + state_path)
                lines = [line.strip() for line in state_file.readlines()]
                song_index = int(lines[0])
                position_millis = int(lines[1])
                debug(f"current song index: {song_index}, position: {position_millis}")

        all_songs = [album_dir + "/" + song for song in songs]
        debug("all songs: " + str(all_songs))
        return AlbumContents(songs=all_songs, song_index=song_index, position_millis=position_millis)

    def save_songstate(self, album_dir: str, song_index: int, position_millis: int) -> None:
        state_path = album_dir + "/" + SONG_STATE_FILE
        debug("writing to file: " + state_path)
        with open(state_path, "w") as state_file:
            state_file.write(f"{song_index}\n{position_millis}\n")

    def write_unknown_tag(self, tag: str) -> None:
        debug("writing to unknown tag file")
        with open(self._unknown_tag_file, "w") as unknown_tag_file:
            unknown_tag_file.write(tag)

    def clear_unknown_tag_marker(self) -> None:
        if exists(self._unknown_tag_file):
            debug("unknown tag file exists. removing")
            remove(self._unknown_tag_file)


def _scan_albums(tag_path: str) -> list[str]:
    possible_albums = sorted_aphanumeric(listdir(tag_path))
    if len(possible_albums) == 0:
        raise Exception("empty tag directory: " + tag_path)

    albums = []

    current_album_dir = None
    at_least_one_file = False
    for album_dir in possible_albums:
        current = os.path.join(tag_path, album_dir)

        if isdir(current):
            files = listdir(current)
            if len(files) == 0:
                raise Exception("empty album directory: " + current)

            if ALBUM_INDICATOR_FILE in files:
                current_album_dir = current

            albums.append(current)

        else:
            at_least_one_file = True

    # we have to shift and cannot simply insert in place at index 0 because that doesn't rotate the other entries
    if current_album_dir is not None:
        i = albums.index(current_album_dir)
        albums = albums[i:] + albums[:i]

    if len(albums) == 0:
        albums.append(tag_path)
    elif at_least_one_file:
        raise Exception("directory and files mixed: " + tag_path)

    return albums


def _scan(audio_path: str) -> dict[str, list[str]]:
    debug("Preparing audio directory: " + audio_path)

    if not isdir(audio_path):
        raise Exception("not a directory: " + audio_path)

    if not isdir(audio_path + "/system"):
        raise Exception("missing system directory, expected at: " + os.path.join(audio_path, "system"))

    tag_to_albums: dict[str, list[str]] = {}
    dirs = listdir(audio_path)

    for d in dirs:
        current = os.path.join(audio_path, d)

        if not isdir(audio_path + "/" + d):
            raise Exception("not a directory: " + current)

        if d == "system":
            continue

        if not re_match(_TAG_NAME_RE, d):
            raise Exception("naming convention error: " + current)

        tag = d[-12:]

        if tag in tag_to_albums:
            raise Exception("tag found twice: " + d + ", " + tag_to_albums[tag][0])

        tag_to_albums[tag] = _scan_albums(current)
        debug(tag + "=" + str(tag_to_albums[tag]))

    return tag_to_albums


if __name__ == "__main__":
    from sys import argv

    from marta.logging_setup import setup_stdout_logging

    setup_stdout_logging()

    if len(argv) != 2:
        debug("Error: Missing path argument.")
        exit(1)

    try:
        _scan(argv[1])
    except Exception as e:
        debug("Error: " + str(e))
        exit(1)

    debug("Everything seems fine.")
    exit(0)
