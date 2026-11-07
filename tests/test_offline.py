"""Fast tests, no network."""
from pathlib import Path

import pytest

from vortex import history, updater
from vortex.media import (build_format, cli_to_opts, download_args, extra_args_to_opts,
                          final_exts, unique_template, looks_like_url)
from vortex.ytdl import yt_dlp


def pp_keys(opts):
    return [p["key"] for p in opts.get("postprocessors", [])]


# ── Options ───────────────────────────────────────────────────────────────────
def test_extra_args_only_returns_what_was_given():
    assert extra_args_to_opts("--cookies-from-browser firefox") == {
        "cookiesfrombrowser": ("firefox", None, None, None)}


def test_bad_flag_raises_valueerror():
    with pytest.raises(ValueError):
        extra_args_to_opts("--this-flag-does-not-exist")


@pytest.mark.parametrize("kind,quality,expected", [
    ("Audio Only", "720p", "bestaudio/best"),
    ("Video Only", "720p", "bestvideo[height<=720]/best[height<=720]"),
    ("Video + Audio", "4K", "bestvideo[height<=2160]+bestaudio/best[height<=2160]"),
    ("Video + Audio", "Best", "bestvideo+bestaudio/best"),
])
def test_build_format(kind, quality, expected):
    assert build_format(kind, quality) == expected


def test_song_options(tmp_path):
    opts = cli_to_opts(download_args(kind="Audio Only", audio_format="mp3", folder=str(tmp_path)))
    assert opts["format"] == "bestaudio/best"
    assert opts["outtmpl"]["default"].startswith(str(tmp_path))
    assert opts["noplaylist"] is True
    keys = pp_keys(opts)
    assert keys.index("FFmpegExtractAudio") < keys.index("EmbedThumbnail")
    assert "FFmpegMetadata" in keys


def test_no_cover_art_for_wav(tmp_path):
    # yt-dlp can't embed a thumbnail in WAV and would fail the download
    opts = cli_to_opts(download_args(kind="Audio Only", audio_format="wav", folder=str(tmp_path)))
    assert "EmbedThumbnail" not in pp_keys(opts)


def test_video_prefers_mp4(tmp_path):
    opts = cli_to_opts(download_args(kind="Video + Audio", folder=str(tmp_path), prefer_mp4=True))
    assert opts["merge_output_format"] == "mp4"
    assert opts["format_sort"][0] == "vcodec:h264"


def test_sponsorblock_removes_segments(tmp_path):
    opts = cli_to_opts(download_args(kind="Video + Audio", folder=str(tmp_path), sponsorblock=True))
    assert "ModifyChapters" in pp_keys(opts)


def test_final_exts():
    assert final_exts("Audio Only", "AAC", True) == {"m4a"}
    assert final_exts("Video + Audio", "mp3", True) == {"mp4"}


def test_looks_like_url():
    assert looks_like_url("https://youtu.be/abc")
    assert not looks_like_url("never gonna give you up")


# ── File names ────────────────────────────────────────────────────────────────
def test_unique_template_adds_number(tmp_path):
    ydl = yt_dlp.YoutubeDL({"outtmpl": str(tmp_path / "%(title)s.%(ext)s"), "quiet": True})
    info = {"title": "Intro", "id": "x"}
    assert unique_template(ydl, info, {"mp3"}) is None
    (tmp_path / "Intro.mp3").write_bytes(b"")
    assert unique_template(ydl, info, {"mp3"}) == str(tmp_path / "Intro (2)") + ".%(ext)s"
    (tmp_path / "Intro (2).mp3").write_bytes(b"")
    assert unique_template(ydl, info, {"mp3"}).endswith("Intro (3).%(ext)s")
    # a video with the same title doesn't block a song
    assert unique_template(ydl, info, {"mp4"}) is None


def test_unique_template_escapes_percent(tmp_path):
    ydl = yt_dlp.YoutubeDL({"outtmpl": str(tmp_path / "%(title)s.%(ext)s"), "quiet": True})
    (tmp_path / "100% Hits.mp3").write_bytes(b"")
    assert "100%% Hits (2)" in unique_template(ydl, {"title": "100% Hits"}, {"mp3"})


# ── Updater and history ───────────────────────────────────────────────────────
def test_version_tuple():
    assert updater.version_tuple("2026.10.26") > updater.version_tuple("2026.03.17")
    assert updater.version_tuple("v0.10.0") > updater.version_tuple("0.9.9")


def test_revert_goes_back_to_previous(tmp_path):
    updater.YTDLP_DIR.mkdir(parents=True, exist_ok=True)
    updater.YTDLP_ZIP.write_bytes(b"new")
    updater.YTDLP_PREVIOUS.write_bytes(b"old")
    updater.write_state(yt_dlp="2099.2.2", yt_dlp_previous="2099.1.1")
    updater.revert_ytdlp()
    state = updater.read_state()
    assert state["yt_dlp"] == "2099.1.1"
    assert "2099.2.2" in state["yt_dlp_bad_list"]
    assert updater.YTDLP_ZIP.read_bytes() == b"old"
    assert not updater.YTDLP_PREVIOUS.exists()


def test_history_roundtrip():
    history.clear()
    history.add("Song", "https://x", "/tmp/Song.mp3", "done")
    entries = history.load()
    assert entries[0]["title"] == "Song" and entries[0]["status"] == "done"
    history.clear()
    assert history.load() == []


def test_tests_use_temp_home():
    assert "vortex-test-home-" in str(Path.home())
