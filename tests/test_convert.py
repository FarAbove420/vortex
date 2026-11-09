"""Convert: command building and real conversions with the bundled FFmpeg."""
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from vortex.convert import (ConvertChoices, ConvertJob, MediaInfo, build_command, encoders,
                            parse_time, probe, run_convert)
from vortex.media import find_ffmpeg

FFMPEG = find_ffmpeg()


@pytest.fixture(scope="module")
def clip(tmp_path_factory):
    """A 6-second 1280x720 H.264 + AAC test video."""
    path = tmp_path_factory.mktemp("media") / "clip.mp4"
    subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error",
                    "-f", "lavfi", "-i", "testsrc=d=6:s=1280x720:r=25",
                    "-f", "lavfi", "-i", "sine=d=6", "-shortest",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-y", str(path)], check=True)
    return path


def test_parse_time():
    assert parse_time("") is None
    assert parse_time("90") == "90.0"
    assert parse_time("1:30") == "90.0"
    assert parse_time("0:01:30.5") == "90.5"
    with pytest.raises(ValueError):
        parse_time("1m30")


def test_probe(clip):
    info = probe(FFMPEG, str(clip))
    assert round(info.duration) == 6
    assert (info.vcodec, info.acodec, info.height) == ("h264", "aac", 720)


H264 = MediaInfo(duration=6, vcodec="h264", acodec="aac", height=1080)


def test_keep_original_copies_when_possible():
    cmd, what = build_command("ffmpeg", "in.mp4", "out.mkv", ConvertChoices(fmt="MKV", video_quality="keep"), H264)
    assert cmd[cmd.index("-c:v") + 1] == "copy" and cmd[cmd.index("-c:a") + 1] == "copy"
    assert "fast" in what


def test_keep_original_reencodes_when_format_cant_hold_it():
    # WEBM can't hold H.264 or AAC
    cmd, what = build_command("ffmpeg", "in.mp4", "out.webm", ConvertChoices(fmt="WEBM", video_quality="keep"), H264)
    assert cmd[cmd.index("-c:v") + 1] == "libvpx-vp9"
    assert cmd[cmd.index("-c:a") + 1] == "libopus"
    assert "Re-encoding" in what


def test_small_file_limits_to_720p():
    cmd, _ = build_command("ffmpeg", "in.mp4", "out.mp4", ConvertChoices(fmt="MP4", video_quality="small"), H264)
    assert cmd[cmd.index("-vf") + 1] == "scale=-2:720"
    assert cmd[cmd.index("-preset") + 1] == "veryfast"


def test_audio_quality_sets_bitrate():
    cmd, _ = build_command("ffmpeg", "in.mp4", "out.mp3", ConvertChoices(fmt="MP3", audio_quality="high"), H264)
    assert "-vn" in cmd and cmd[cmd.index("-b:a") + 1] == "320k"


def test_trim_uses_length():
    c = ConvertChoices(fmt="MKV", start=parse_time("1:00"), end=parse_time("1:30"))
    cmd, _ = build_command("ffmpeg", "in.mp4", "out.mkv", c, H264)
    assert cmd[cmd.index("-ss") + 1] == "60.0" and cmd[cmd.index("-t") + 1] == "30.0"
    with pytest.raises(ValueError):
        build_command("ffmpeg", "in", "out", ConvertChoices(start="30", end="10"), H264)


def test_av1_uses_libaom_when_svt_is_missing():
    # The Windows FFmpeg build has libaom-av1 but no libsvtav1
    c = ConvertChoices(fmt="MKV", video_quality="balanced", codec="av1")
    cmd, _ = build_command("ffmpeg", "in.mp4", "out.mkv", c, H264, {"libx264", "libaom-av1"})
    assert cmd[cmd.index("-c:v") + 1] == "libaom-av1" and cmd[cmd.index("-b:v") + 1] == "0"
    cmd, _ = build_command("ffmpeg", "in.mp4", "out.mkv", c, H264, {"libsvtav1", "libaom-av1"})
    assert cmd[cmd.index("-c:v") + 1] == "libsvtav1"


def test_missing_encoder_says_so():
    c = ConvertChoices(fmt="MKV", video_quality="balanced", codec="av1")
    with pytest.raises(ValueError, match="AV1"):
        build_command("ffmpeg", "in.mp4", "out.mkv", c, H264, {"libx264"})


def test_bundled_ffmpeg_has_the_encoders_vortex_uses():
    have = encoders(FFMPEG)
    for name in ("libx264", "libx265", "libvpx-vp9", "libmp3lame", "aac", "flac", "pcm_s16le", "libopus"):
        assert name in have, name
    assert have & {"libsvtav1", "libaom-av1"}, "no AV1 encoder"


def test_real_av1_conversion(clip, tmp_path):
    out = tmp_path / "av1.mkv"
    c = ConvertChoices(fmt="MKV", video_quality="smallest", codec="av1", end="1")
    job = ConvertJob(str(clip), str(out), c, ffmpeg=FFMPEG)
    run_convert(job)
    assert job.status == "done", job.error
    assert probe(FFMPEG, str(out)).vcodec == "av1"


@pytest.mark.parametrize("fmt,quality", [("MP4", "balanced"), ("MP3", "keep"), ("MKV", "keep")])
def test_real_conversion(clip, tmp_path, fmt, quality):
    out = tmp_path / f"out.{fmt.lower()}"
    job = ConvertJob(str(clip), str(out), ConvertChoices(fmt=fmt, video_quality=quality), ffmpeg=FFMPEG)
    run_convert(job)
    assert job.status == "done", job.error
    assert job.progress == 1.0 and out.stat().st_size > 0


def test_small_file_is_smaller(clip, tmp_path):
    out = tmp_path / "small.mp4"
    job = ConvertJob(str(clip), str(out), ConvertChoices(fmt="MP4", video_quality="smallest"), ffmpeg=FFMPEG)
    run_convert(job)
    assert job.status == "done", job.error
    assert probe(FFMPEG, str(out)).height == 480


def test_progress_and_cancel(clip, tmp_path):
    out = tmp_path / "slow.webm"
    job = ConvertJob(str(clip), str(out), ConvertChoices(fmt="WEBM", video_quality="high"), ffmpeg=FFMPEG)
    t = threading.Thread(target=run_convert, args=(job,))
    t.start()
    deadline = time.time() + 20
    while job.status != "running" and time.time() < deadline:
        time.sleep(0.05)
    job.cancel()
    t.join(30)
    assert job.status == "cancelled"
    assert not out.exists()


def test_convert_module_does_not_use_tk():
    # The worker must never touch Tk (that froze the window on Windows)
    code = "import sys; import vortex.convert; print('tkinter' in sys.modules)"
    root = Path(__file__).resolve().parent.parent
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=root)
    assert r.stdout.strip() == "False", r.stderr


def test_accented_file_name(clip, tmp_path):
    # Windows used to decode ffmpeg's UTF-8 output as cp1252 and lose the duration
    accented = tmp_path / "Café für Ångström.mp4"
    accented.write_bytes(clip.read_bytes())
    assert round(probe(FFMPEG, str(accented)).duration) == 6
    out = tmp_path / "Café.mp3"
    job = ConvertJob(str(accented), str(out), ConvertChoices(fmt="MP3"), ffmpeg=FFMPEG)
    run_convert(job)
    assert job.status == "done", job.error
