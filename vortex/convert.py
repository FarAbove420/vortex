"""Converting local files with FFmpeg, without any UI.

The Convert tab reads its choices on the main thread, hands them to
run_convert() on a worker thread, and polls the ConvertJob for progress.
The worker never touches Tk: on Windows, Tk calls from another thread wait
for the main thread, which stalls while the window is dragged or switched,
and that froze conversions.
"""
import re
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from .config import SUBPROCESS_FLAGS, log

# ── Choices, in plain words ───────────────────────────────────────────────────
# Output formats: key -> (label shown in the dropdown, kind, explanation)
# For video the format is only the container: the file size comes from the
# codec and the Quality setting, which the explanations say.
FORMATS = {
    "MP4":  ("MP4 video · plays everywhere · normal size", "video",
             "The format plays on any phone, TV or computer. For video, the format barely "
             "changes the size: the Quality setting below decides it."),
    "MOV":  ("MOV video · Apple, iMovie · same size as MP4", "video",
             "Apple's format, handy for iMovie and Final Cut. About the same size as MP4: "
             "the Quality setting below decides it."),
    "MKV":  ("MKV video · subtitles, extra audio · same size as MP4", "video",
             "Holds anything, including several audio tracks and subtitles. About the same "
             "size as MP4. Not every TV or phone plays it."),
    "WEBM": ("WEBM video · for websites · smaller than MP4", "video",
             "Made for websites. It uses VP9 or AV1, which give smaller files than MP4's "
             "usual H.264 at the same quality, but take longer to make."),
    "AVI":  ("AVI video · very old players · same size as MP4", "video",
             "Only for very old players. Uses H.264 and is about the same size as MP4."),
    "MP3":  ("MP3 audio · plays everywhere · about 1.4 MB per minute", "audio",
             "Music that plays everywhere. About 1 to 2.4 MB per minute, depending on the "
             "quality below."),
    "M4A":  ("M4A audio · Apple · same size as MP3", "audio",
             "Apple's music format. The same size as MP3 at the same quality, and sounds a "
             "little better."),
    "FLAC": ("FLAC audio · perfect quality · about 4× an MP3", "audio",
             "Perfect quality without any loss. Roughly 5 MB per minute, about 4 times an "
             "MP3."),
    "WAV":  ("WAV audio · uncompressed · about 7× an MP3", "audio",
             "Uncompressed, for editing programs. About 10 MB per minute, about 7 times an "
             "MP3."),
}

# Video quality: key -> (label, explanation shown under the dropdown)
VIDEO_QUALITY = {
    "keep":     ("Keep original · fastest",
                 "Copies the video as it is: no quality loss, the same size, done in seconds. "
                 "If the new format can't hold the original video, it's re-encoded at Balanced."),
    "high":     ("High quality · big file",
                 "Looks like the original. The file often stays as big as the original. "
                 "Re-encoding takes a while."),
    "balanced": ("Balanced · good quality, medium size",
                 "Hard to tell apart from the original, usually a lot smaller. A good default."),
    "small":    ("Small file · for sharing",
                 "Visibly softer, and limited to 720p. Good for WhatsApp, email or a phone."),
    "smallest": ("Smallest · lowest quality",
                 "Limited to 480p and clearly lower quality. Tiny files for slow connections."),
}

# Audio quality for MP3 and M4A: key -> (label, explanation, bitrate)
AUDIO_QUALITY = {
    "high":     ("High · 320 kbps, about 2.4 MB per minute",
                 "As good as MP3 gets. Use this for music you care about.", "320k"),
    "standard": ("Standard · 192 kbps, about 1.4 MB per minute",
                 "Sounds the same as High to most people. A good default.", "192k"),
    "small":    ("Small · 128 kbps, about 1 MB per minute",
                 "Fine for speech and podcasts, a bit flat for music.", "128k"),
}

LOSSLESS_NOTE = "Perfect quality: there's nothing to choose."

# Video codec in the "More options" part: key -> (label, explanation)
CODECS = {
    "h264": ("H.264 · plays everywhere", "The safe choice for any phone, TV or computer."),
    "h265": ("H.265 · up to half the size", "Same quality in a smaller file, but slower to make, "
                                            "and older devices may not play it."),
    "vp9":  ("VP9 · smaller, for websites", "Smaller than H.264 at the same quality. Plays in "
                                            "browsers and on Android, not on older Apple devices."),
    "av1":  ("AV1 · smallest, newest", "The smallest files, but slow to make, and only newer "
                                       "devices play it."),
}
# Which codecs each video format can hold; the first one is the automatic choice
FORMAT_CODECS = {
    "MP4":  ["h264", "h265", "av1"],
    "MOV":  ["h264", "h265"],
    "MKV":  ["h264", "h265", "vp9", "av1"],
    "WEBM": ["vp9", "av1"],
    "AVI":  ["h264"],
}

# Encoder settings per codec and quality: (encoder, constant-quality value, extra args)
_ENCODERS = {
    #          encoder        high balanced small smallest  extra
    "h264": ("libx264",     (18, 23, 27, 30), ["-preset", "veryfast"]),
    "h265": ("libx265",     (20, 26, 29, 32), ["-preset", "fast"]),
    "vp9":  ("libvpx-vp9",  (30, 37, 41, 45), ["-b:v", "0", "-deadline", "good", "-cpu-used", "4", "-row-mt", "1"]),
    "av1":  ("libsvtav1",   (24, 32, 38, 44), ["-preset", "8"]),
}
# The Windows FFmpeg (gyan.dev "essentials" build) has no SVT-AV1, only the
# slower libaom, which needs -b:v 0 for constant quality
_AV1_FALLBACK = ("libaom-av1", ["-b:v", "0", "-cpu-used", "6", "-row-mt", "1"])
_QUALITY_INDEX = {"high": 0, "balanced": 1, "small": 2, "smallest": 3}
_MAX_HEIGHT = {"small": 720, "smallest": 480}

_AUDIO_ENCODER = {"MP3": "libmp3lame", "M4A": "aac", "FLAC": "flac", "WAV": "pcm_s16le"}

# Which original streams each video format can hold as they are
_COPY_OK = {
    "MP4":  ({"h264", "hevc", "av1", "mpeg4"}, {"aac", "mp3", "alac", "ac3", "eac3", "opus"}),
    "MOV":  ({"h264", "hevc", "mpeg4", "prores"}, {"aac", "mp3", "alac", "ac3", "pcm_s16le"}),
    "MKV":  (None, None),   # anything
    "WEBM": ({"vp8", "vp9", "av1"}, {"opus", "vorbis"}),
    "AVI":  ({"mpeg4", "h264", "mjpeg"}, {"mp3", "ac3", "pcm_s16le"}),
}


# ── Reading the input ─────────────────────────────────────────────────────────
@dataclass
class MediaInfo:
    duration: float = 0.0
    vcodec: str = ""
    acodec: str = ""
    height: int = 0


def probe(ffmpeg: str, path: str) -> MediaInfo:
    """Duration and codecs, parsed from `ffmpeg -i` (no separate ffprobe)."""
    info = MediaInfo()
    try:
        # ffmpeg writes UTF-8; without an explicit encoding Windows decodes it
        # as cp1252 and fails on accented file names and tags
        r = subprocess.run([ffmpeg, "-hide_banner", "-i", path], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=30, **SUBPROCESS_FLAGS)
    except Exception as e:
        log.warning("Probe failed: %s", e)
        return info
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", r.stderr)
    if m:
        info.duration = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    m = re.search(r"Stream #\S+.*?: Video: (\w+).*?, (\d+)x(\d+)", r.stderr)
    if m:
        info.vcodec, info.height = m.group(1), int(m.group(3))
    m = re.search(r"Stream #\S+.*?: Audio: (\w+)", r.stderr)
    if m:
        info.acodec = m.group(1)
    return info


_encoders_cache: dict[str, set[str]] = {}


def encoders(ffmpeg: str) -> set[str]:
    """Names of the encoders this FFmpeg build has, from `ffmpeg -encoders`."""
    if ffmpeg not in _encoders_cache:
        try:
            r = subprocess.run([ffmpeg, "-hide_banner", "-encoders"], capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=30, **SUBPROCESS_FLAGS)
            # lines look like " V....D libx264   libx264 H.264 / AVC ..."
            _encoders_cache[ffmpeg] = set(re.findall(r"^ [VAS][.A-Z]{5} (\S+)", r.stdout, re.MULTILINE))
        except Exception as e:
            log.warning("Could not list FFmpeg encoders: %s", e)
            _encoders_cache[ffmpeg] = set()
    return _encoders_cache[ffmpeg]


def parse_time(text: str) -> str | None:
    """'90', '1:30' or '00:01:30' -> '90.0' seconds for ffmpeg. None if empty.
    Raises ValueError for anything else."""
    text = text.strip()
    if not text:
        return None
    parts = text.split(":")
    if len(parts) > 3 or not all(re.fullmatch(r"\d+(\.\d+)?", p) for p in parts):
        raise ValueError(f"\u201c{text}\u201d isn't a time. Use seconds, minutes:seconds or h:mm:ss.")
    secs = 0.0
    for p in parts:
        secs = secs * 60 + float(p)
    return str(secs)


# ── Building the command ──────────────────────────────────────────────────────
@dataclass
class ConvertChoices:
    fmt: str = "MP4"
    video_quality: str = "keep"
    audio_quality: str = "standard"
    codec: str = "auto"
    start: str | None = None   # seconds, from parse_time
    end: str | None = None


def build_command(ffmpeg: str, inp: str, out: str, c: ConvertChoices, info: MediaInfo,
                  available: set[str] | None = None) -> tuple[list[str], str]:
    """The ffmpeg command, and a plain sentence about what it will do.
    available: the FFmpeg build's encoders (see encoders()); None assumes
    every encoder is there."""
    cmd = [ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin"]
    if c.start:
        cmd += ["-ss", c.start]       # before -i: jumps straight there, fast
    cmd += ["-i", inp]
    if c.end:
        # -to counts from the start of the input; with -ss before -i the
        # timestamps restart at 0, so use the length instead
        length = float(c.end) - float(c.start or 0)
        if length <= 0:
            raise ValueError("The end time has to be after the start time.")
        cmd += ["-t", str(length)]

    if FORMATS[c.fmt][1] == "audio":
        cmd += ["-vn", "-c:a", _AUDIO_ENCODER[c.fmt]]
        if c.fmt == "FLAC":
            cmd += ["-sample_fmt", "s16"]   # CD quality; otherwise 24-bit and twice the size
        if c.fmt in ("MP3", "M4A"):
            cmd += ["-b:a", AUDIO_QUALITY[c.audio_quality][2]]
        what = f"Converting the audio to {c.fmt}"
    else:
        vok, aok = _COPY_OK[c.fmt]
        quality = c.video_quality
        can_copy_video = vok is None or info.vcodec in vok
        if quality == "keep" and can_copy_video:
            cmd += ["-c:v", "copy"]
            what = "Copying the video as it is (fast, no quality loss)"
        else:
            if quality == "keep":
                quality = "balanced"   # the format can't hold the original video
            codec = c.codec if c.codec in FORMAT_CODECS[c.fmt] else FORMAT_CODECS[c.fmt][0]
            encoder, values, extra = _ENCODERS[codec]
            if available is not None and encoder not in available:
                if codec == "av1" and _AV1_FALLBACK[0] in available:
                    encoder, extra = _AV1_FALLBACK
                else:
                    raise ValueError(f"The FFmpeg in Vortex can't make {CODECS[codec][0].split(' ·')[0]} "
                                     "video. Pick another video codec under More options.")
            cmd += ["-c:v", encoder, "-crf", str(values[_QUALITY_INDEX[quality]])] + extra
            if quality in _MAX_HEIGHT and info.height > _MAX_HEIGHT[quality]:
                cmd += ["-vf", f"scale=-2:{_MAX_HEIGHT[quality]}"]
            if codec == "h264":
                cmd += ["-pix_fmt", "yuv420p"]   # what phones and TVs can play
            if c.fmt in ("MP4", "MOV"):
                cmd += ["-movflags", "+faststart"]
                if codec == "h265":
                    cmd += ["-tag:v", "hvc1"]    # so Apple devices play it
            names = {"h264": "H.264", "h265": "H.265", "vp9": "VP9", "av1": "AV1"}
            what = (f"Re-encoding the video ({names[codec]}, "
                    f"{VIDEO_QUALITY[quality][0].split(' ·')[0]}). This uses the processor "
                    "and is the slow part")
        if aok is None or info.acodec in aok or not info.acodec:
            cmd += ["-c:a", "copy"]
        else:
            cmd += ["-c:a", "libopus" if c.fmt == "WEBM" else "aac", "-b:a", "192k"]
    cmd += ["-progress", "pipe:1", "-nostats", "-y", out]
    return cmd, what


# ── Expected size ─────────────────────────────────────────────────────────────
# Only where it can be known: audio (bitrate x length) and video that's copied
# as it is. A re-encoded video's size depends on what's in it, so no guess.
_AUDIO_KBPS = {"WAV": 1411}


def estimate_size(info: MediaInfo, original_bytes: int, c: ConvertChoices) -> int | None:
    """Expected output size in bytes, or None when it can't be known."""
    length = info.duration
    if c.end:
        length = float(c.end) - float(c.start or 0)
    elif c.start and length:
        length -= float(c.start)
    if length <= 0:
        return None
    if FORMATS[c.fmt][1] == "audio":
        if c.fmt in ("MP3", "M4A"):
            kbps = int(AUDIO_QUALITY[c.audio_quality][2].rstrip("k"))
        elif c.fmt in _AUDIO_KBPS:
            kbps = _AUDIO_KBPS[c.fmt]
        else:
            return None   # FLAC depends on the music
        return int(kbps * 1000 / 8 * length)
    vok, _aok = _COPY_OK[c.fmt]
    if c.video_quality == "keep" and (vok is None or info.vcodec in vok) and info.duration:
        return int(original_bytes * min(length / info.duration, 1.0))
    return None


# ── Running it ────────────────────────────────────────────────────────────────
@dataclass
class ConvertJob:
    inp: str
    out: str
    choices: ConvertChoices
    ffmpeg: str = "ffmpeg"
    status: str = "starting"    # starting, running, done, error, cancelled
    what: str = "Reading the file..."
    progress: float = 0.0       # 0..1
    speed: float = 0.0          # 1.0 = as fast as playing the video
    eta: float = 0.0            # seconds left
    elapsed: float = 0.0
    error: str = ""
    cancel_requested: bool = False
    _proc: subprocess.Popen | None = field(default=None, repr=False)

    def cancel(self):
        self.cancel_requested = True
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()


def run_convert(job: ConvertJob) -> None:
    """Runs on a worker thread and only updates job."""
    started = time.monotonic()
    try:
        info = probe(job.ffmpeg, job.inp)
        cmd, job.what = build_command(job.ffmpeg, job.inp, job.out, job.choices, info,
                                      encoders(job.ffmpeg))
        total = info.duration
        if job.choices.end:
            total = float(job.choices.end) - float(job.choices.start or 0)
        elif job.choices.start and total:
            total -= float(job.choices.start)
        log.info("Convert: %s", subprocess.list2cmdline(cmd))
        if job.cancel_requested:
            job.status = "cancelled"
            return

        job._proc = proc = subprocess.Popen(
            cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace", **SUBPROCESS_FLAGS)
        job.status = "running"
        stderr_buf: list[str] = []
        drain = threading.Thread(target=lambda: stderr_buf.extend(proc.stderr), daemon=True)
        drain.start()

        for line in proc.stdout:
            key, _, value = line.strip().partition("=")
            if key == "out_time_us" and total:      # microseconds, despite ffmpeg's other names
                try:
                    job.progress = min(int(value) / (total * 1_000_000), 1.0)
                except ValueError:
                    pass
            elif key == "speed" and value.endswith("x"):
                try:
                    job.speed = float(value[:-1])
                except ValueError:
                    pass
            job.elapsed = time.monotonic() - started
            if job.progress > 0.01:
                job.eta = job.elapsed / job.progress - job.elapsed

        proc.wait()
        drain.join(timeout=5)
        job.elapsed = time.monotonic() - started
        if job.cancel_requested:
            Path(job.out).unlink(missing_ok=True)   # half a file is no use
            job.status = "cancelled"
        elif proc.returncode == 0:
            job.progress = 1.0
            job.status = "done"
            log.info("Convert finished in %.0fs: %s", job.elapsed, job.out)
        else:
            lines = [l.strip() for l in stderr_buf if l.strip()]
            log.error("ffmpeg exited with %s:\n%s", proc.returncode, "\n".join(lines))
            job.error = lines[-1] if lines else f"ffmpeg exited with code {proc.returncode}"
            job.status = "error"
    except FileNotFoundError:
        job.error = "FFmpeg not found. Check the FFmpeg path in Settings."
        job.status = "error"
    except Exception as e:
        log.exception("Convert failed")
        job.error = str(e)
        job.status = "error"
