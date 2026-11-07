"""Real downloads from YouTube and GitHub. Run with: pytest --network"""
import subprocess

import pytest

from vortex import updater
from vortex.media import (Item, cli_to_opts, download_args, final_exts, fetch_preview,
                          find_ffmpeg, run_download, search, thumbnail_png_b64, best_thumbnail_url)

pytestmark = pytest.mark.network

URL = "https://www.youtube.com/watch?v=jNQXAC9IVRw"   # "Me at the zoo", 19 seconds


def song_item(folder, info=None, fmt="mp3"):
    opts = cli_to_opts(download_args(kind="Audio Only", audio_format=fmt, folder=str(folder)))
    return Item(URL, opts, exts=final_exts("Audio Only", fmt, True), info=info)


def test_song_download_and_no_overwrite(tmp_path):
    first = song_item(tmp_path)
    run_download(first)
    assert first.status == "done", first.error
    assert first.filepath.endswith("Me at the zoo.mp3")

    second = song_item(tmp_path)
    run_download(second)
    assert second.status == "done", second.error
    assert second.filepath.endswith("Me at the zoo (2).mp3")
    assert sorted(p.name for p in tmp_path.iterdir()) == ["Me at the zoo (2).mp3", "Me at the zoo.mp3"]


def test_song_has_cover_art(tmp_path):
    item = song_item(tmp_path)
    run_download(item)
    probe = subprocess.run([find_ffmpeg(), "-hide_banner", "-i", item.filepath],
                           capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
    assert "attached pic" in probe


def test_preview_info_is_reused(tmp_path):
    info, reusable = fetch_preview(URL)
    assert info["title"] == "Me at the zoo" and reusable
    item = song_item(tmp_path, info=info)
    run_download(item)
    assert item.status == "done", item.error


def test_video_is_mp4(tmp_path):
    opts = cli_to_opts(download_args(kind="Video + Audio", quality="360p", folder=str(tmp_path)))
    item = Item(URL, opts, exts={"mp4"})
    run_download(item)
    assert item.status == "done", item.error
    assert item.filepath.endswith(".mp4")


def test_cancel(tmp_path):
    item = song_item(tmp_path)
    item.cancel_requested = True
    run_download(item)
    assert item.status == "cancelled"


def test_search_and_thumbnail():
    results = search("me at the zoo", n=3)
    assert results and all(r["url"].startswith("http") for r in results)
    png = thumbnail_png_b64(best_thumbnail_url(fetch_preview(URL)[0]), 160)
    assert png and png.startswith("iVBOR")   # base64 of the PNG signature


def test_latest_tag_without_api():
    assert updater.version_tuple(updater.latest_tag("yt-dlp/yt-dlp")) >= (2026,)
