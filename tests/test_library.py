"""Library tests against a real temp directory - no hardware, no fakes.
Mirrors the audio/ layout convention: <name>_<12-hex-tag> directories,
optionally containing album subdirectories, one of which may hold a
.albumindicator file marking the "current" album.
"""

import os

import pytest

from marta.config import Config
from marta.library import ALBUM_INDICATOR_FILE, SONG_STATE_FILE, Library


def make_config(audio_dir, **overrides):
    base = dict(
        base_dir=str(audio_dir.parent),
        audio_dir=str(audio_dir),
        start_sound_path=str(audio_dir / "system" / "startup.mp3"),
        shutdown_sound_path=str(audio_dir / "system" / "shutdown.mp3"),
        unknown_tag_file=str(audio_dir / "unknown_tag.txt"),
        log_file=str(audio_dir.parent / "logs" / "mmm.log"),
    )
    base.update(overrides)
    return Config(**base)


def touch(path, content=""):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(content)


def make_audio_dir(tmp_path, tags=None):
    tags = tags or {}
    """tags: dict of tag -> either a list of song filenames (single-album,
    files directly in the tag dir) or a dict of album_name -> song filenames
    (multi-album)."""
    audio_dir = tmp_path / "audio"
    touch(str(audio_dir / "system" / ".keep"))

    for tag, contents in tags.items():
        tag_dir = audio_dir / f"somebody_{tag}"
        if isinstance(contents, dict):
            for album, songs in contents.items():
                for song in songs:
                    touch(str(tag_dir / album / song))
        else:
            for song in contents:
                touch(str(tag_dir / song))

    return audio_dir


def test_scans_single_and_multi_album_tags(tmp_path):
    audio_dir = make_audio_dir(
        tmp_path,
        tags={
            "AABBCCDDEEFF": ["b.mp3", "a.mp3"],
            "112233445566": {"album1": ["1.mp3"], "album2": ["1.mp3"]},
        },
    )
    library = Library(make_config(audio_dir))

    assert library.has_tag("AABBCCDDEEFF")
    assert not library.has_multiple_albums("AABBCCDDEEFF")
    assert library.current_album_dir("AABBCCDDEEFF") == str(audio_dir / "somebody_AABBCCDDEEFF")

    assert library.has_tag("112233445566")
    assert library.has_multiple_albums("112233445566")
    assert not library.has_tag("000000000000")


def test_load_album_sorts_and_filters_reserved_files(tmp_path):
    audio_dir = make_audio_dir(tmp_path, tags={"AABBCCDDEEFF": ["track10.mp3", "track2.mp3", "track1.mp3"]})
    library = Library(make_config(audio_dir))
    album_dir = library.current_album_dir("AABBCCDDEEFF")

    contents = library.load_album(album_dir)

    assert contents.songs == [
        os.path.join(album_dir, "track1.mp3"),
        os.path.join(album_dir, "track2.mp3"),
        os.path.join(album_dir, "track10.mp3"),
    ]
    assert contents.song_index == 0
    assert contents.position_millis == 0


def test_songstate_round_trip(tmp_path):
    audio_dir = make_audio_dir(tmp_path, tags={"AABBCCDDEEFF": ["a.mp3", "b.mp3"]})
    library = Library(make_config(audio_dir))
    album_dir = library.current_album_dir("AABBCCDDEEFF")

    library.save_songstate(album_dir, song_index=1, position_millis=42000)
    contents = library.load_album(album_dir)

    assert contents.song_index == 1
    assert contents.position_millis == 42000
    # the state file itself must not show up as a song
    assert all(not song.endswith(SONG_STATE_FILE) for song in contents.songs)


def test_rotate_album_reorders_and_moves_indicator(tmp_path):
    audio_dir = make_audio_dir(
        tmp_path,
        tags={"112233445566": {"album1": ["1.mp3"], "album2": ["1.mp3"], "album3": ["1.mp3"]}},
    )
    library = Library(make_config(audio_dir))
    tag = "112233445566"
    first = library.current_album_dir(tag)
    assert first.endswith("album1")

    library.rotate_album(tag, forward=True, previous_album_dir=first)
    second = library.current_album_dir(tag)
    assert second.endswith("album2")
    assert not os.path.exists(os.path.join(first, ALBUM_INDICATOR_FILE))
    assert os.path.exists(os.path.join(second, ALBUM_INDICATOR_FILE))

    library.rotate_album(tag, forward=False, previous_album_dir=second)
    assert library.current_album_dir(tag) == first
    assert os.path.exists(os.path.join(first, ALBUM_INDICATOR_FILE))
    assert not os.path.exists(os.path.join(second, ALBUM_INDICATOR_FILE))


def test_album_indicator_at_scan_time_picks_that_album_as_current(tmp_path):
    audio_dir = make_audio_dir(
        tmp_path,
        tags={"112233445566": {"album1": ["1.mp3"], "album2": ["1.mp3"]}},
    )
    touch(str(audio_dir / "somebody_112233445566" / "album2" / ALBUM_INDICATOR_FILE))

    library = Library(make_config(audio_dir))

    assert library.current_album_dir("112233445566").endswith("album2")


def test_unknown_tag_file_written_and_cleared(tmp_path):
    audio_dir = make_audio_dir(tmp_path, tags={"AABBCCDDEEFF": ["a.mp3"]})
    library = Library(make_config(audio_dir))

    library.write_unknown_tag("FF00FF00FF00")
    assert os.path.exists(str(audio_dir / "unknown_tag.txt"))

    library.clear_unknown_tag_marker()
    assert not os.path.exists(str(audio_dir / "unknown_tag.txt"))

    # clearing again (nothing to clear) must not raise
    library.clear_unknown_tag_marker()


def test_stale_unknown_tag_file_cleared_on_startup(tmp_path):
    audio_dir = make_audio_dir(tmp_path, tags={"AABBCCDDEEFF": ["a.mp3"]})
    touch(str(audio_dir / "unknown_tag.txt"), "leftover from a previous run")

    Library(make_config(audio_dir))

    assert not os.path.exists(str(audio_dir / "unknown_tag.txt"))


def test_missing_system_directory_raises(tmp_path):
    audio_dir = make_audio_dir(tmp_path, tags={"AABBCCDDEEFF": ["a.mp3"]})
    (audio_dir / "system" / ".keep").unlink()
    (audio_dir / "system").rmdir()

    with pytest.raises(Exception, match="missing system directory"):
        Library(make_config(audio_dir))


def test_bad_tag_name_raises(tmp_path):
    audio_dir = make_audio_dir(tmp_path)
    touch(str(audio_dir / "somebody_notahextag" / "a.mp3"))

    with pytest.raises(Exception, match="naming convention error"):
        Library(make_config(audio_dir))


def test_empty_tag_directory_raises(tmp_path):
    audio_dir = make_audio_dir(tmp_path)
    os.makedirs(str(audio_dir / "somebody_AABBCCDDEEFF"))

    with pytest.raises(Exception, match="empty tag directory"):
        Library(make_config(audio_dir))


def test_mixed_files_and_directories_raises(tmp_path):
    audio_dir = make_audio_dir(tmp_path, tags={"AABBCCDDEEFF": {"album1": ["1.mp3"]}})
    touch(str(audio_dir / "somebody_AABBCCDDEEFF" / "loose_file.mp3"))

    with pytest.raises(Exception, match="directory and files mixed"):
        Library(make_config(audio_dir))


if __name__ == "__main__":
    import sys

    sys.exit(pytest.main([__file__, "-v"]))
