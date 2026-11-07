"""Everything that talks to yt-dlp and FFmpeg, without any UI."""
import base64
import re
import shlex
import subprocess
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

from .config import SUBPROCESS_FLAGS, log
from . import updater
from .ytdl import yt_dlp, YtdlpLogger, using_downloaded


# ── FFmpeg ────────────────────────────────────────────────────────────────────
def find_ffmpeg(configured: str = "") -> str:
    """Return the best available ffmpeg binary path.

    1. User-configured absolute path from Settings (if it exists)
    2. Static ffmpeg bundled via imageio-ffmpeg (also in the packaged app)
    3. Bare 'ffmpeg', relying on PATH
    """
    if configured and configured != "ffmpeg" and Path(configured).exists():
        return configured
    try:
        import imageio_ffmpeg
        bundled = imageio_ffmpeg.get_ffmpeg_exe()
        if Path(bundled).exists():
            return bundled
    except Exception:
        pass
    return "ffmpeg"


# ── Turning choices into yt-dlp options ───────────────────────────────────────
AUDIO_FORMATS = ["MP3", "M4A", "FLAC", "WAV", "OPUS", "AAC"]
# File extension yt-dlp's FFmpegExtractAudio produces per --audio-format
AUDIO_EXT = {"mp3": "mp3", "m4a": "m4a", "flac": "flac", "wav": "wav", "opus": "opus", "aac": "m4a"}
# Formats yt-dlp can embed cover art in (EmbedThumbnailPP)
THUMB_AUDIO = {"mp3", "m4a", "flac", "opus"}
VIDEO_EXTS = {"mp4", "mkv", "webm", "mov"}


def build_format(kind: str, quality: str) -> str:
    """yt-dlp format selector for the Type and Quality dropdowns."""
    if kind == "Audio Only":
        return "bestaudio/best"
    limit = ""
    if quality == "4K":
        limit = "[height<=2160]"
    elif quality not in ("Best", ""):
        limit = f"[height<={quality.rstrip('p')}]"
    if kind == "Video Only":
        return f"bestvideo{limit}/best{limit}"
    return f"bestvideo{limit}+bestaudio/best{limit}"


_DEFAULT_OPTS = None


def cli_to_opts(args: list[str]) -> dict:
    """Turn yt-dlp command line flags into YoutubeDL options.

    Letting yt-dlp parse real CLI flags keeps us in step with how yt-dlp
    itself combines options (postprocessor order, presets like -t mp4).
    parse_options() returns every option including defaults, so only the
    ones that differ from yt-dlp's defaults are returned; applying all of
    them would reset things like the output folder.
    Raises ValueError when yt-dlp doesn't accept the flags.
    """
    import optparse
    global _DEFAULT_OPTS
    from yt_dlp import parse_options
    try:
        given = parse_options(args).ydl_opts
        if _DEFAULT_OPTS is None:
            _DEFAULT_OPTS = parse_options([]).ydl_opts
    except (optparse.OptParseError, SystemExit, ValueError) as e:
        reason = str(e).strip().splitlines()[-1] if str(e).strip() else ""
        raise ValueError(f"yt-dlp doesn't accept these options.\n\n{reason}") from e

    default = _DEFAULT_OPTS
    diff = {k: v for k, v in given.items() if default.get(k) != v}
    if "postprocessors" in diff:
        diff["postprocessors"] = [p for p in given["postprocessors"]
                                  if p not in default["postprocessors"]]
    return diff


def split_args(text: str) -> list[str]:
    """Split typed yt-dlp flags like a shell does, quotes included.

    On Windows a backslash is a path separator, not an escape character, so
    C:\\Music\\archive.txt stays as typed instead of becoming C:Musicarchive.txt.
    """
    lex = shlex.shlex(text, posix=True)
    lex.whitespace_split = True
    lex.commenters = ""
    if sys.platform == "win32":
        lex.escape = ""
    return list(lex)


def extra_args_to_opts(text: str) -> dict:
    return cli_to_opts(split_args(text))


def download_args(*, kind: str, quality: str = "Best", audio_format: str = "mp3",
                  folder: str, embed_thumbnail: bool = True, embed_subs: bool = False,
                  prefer_mp4: bool = True, playlist: bool = False,
                  sponsorblock: bool = False, extra: str = "") -> list[str]:
    """yt-dlp command line flags for one download."""
    afmt = audio_format.lower()
    args = ["-f", build_format(kind, quality),
            "-o", str(Path(folder) / "%(title)s.%(ext)s"),
            "--yes-playlist" if playlist else "--no-playlist",
            "--embed-metadata"]
    if kind == "Audio Only":
        args += ["-x", "--audio-format", afmt, "--audio-quality", "192K"]
        if embed_thumbnail and afmt in THUMB_AUDIO:
            args += ["--embed-thumbnail"]
    else:
        if prefer_mp4:
            args += ["-t", "mp4"]          # yt-dlp's own "plays everywhere" preset
            if embed_thumbnail:
                args += ["--embed-thumbnail"]   # webm can't hold one, mp4 can
        if embed_subs:
            args += ["--write-subs", "--embed-subs"]
    if sponsorblock:
        args += ["--sponsorblock-remove", "sponsor"]
    if extra.strip():
        args += split_args(extra)
    return args


def final_exts(kind: str, audio_format: str, prefer_mp4: bool) -> set[str]:
    if kind == "Audio Only":
        return {AUDIO_EXT.get(audio_format.lower(), audio_format.lower())}
    return {"mp4"} if prefer_mp4 else VIDEO_EXTS


# ── Queue items ───────────────────────────────────────────────────────────────
class Item:
    def __init__(self, url: str, opts: dict, title: str = "", *,
                 exts: set[str] | None = None, info: dict | None = None):
        self.url     = url
        self.opts    = opts
        self.exts    = exts or set()   # final extensions, to avoid overwriting
        self.info    = info            # info from the preview, saves a request
        self.title   = title or url[:60]
        self.title_known = bool(title)
        self.cancel_requested = False
        self.status  = "queued"         # queued, downloading, done, error, cancelled
        self.stage   = ""               # "", "processing" (converting after download)
        self.progress = 0.0
        self.speed   = 0.0
        self.eta     = 0
        self.total   = 0
        self.playlist_pos   = 0
        self.playlist_total = 0
        self.error   = ""
        self.filepath = ""
        self.added   = datetime.now().strftime("%H:%M:%S")


def unique_template(ydl, info: dict, exts: set[str]) -> str | None:
    """A new output template when the file this download would create exists.

    yt-dlp overwrites a converted file (e.g. the .mp3) if one with the same
    title is already there, so two different songs called "Intro" would end
    up as one. Returns e.g. '/Downloads/Intro (2).%(ext)s', or None.
    """
    if not exts or not info.get("title"):
        return None
    name = Path(ydl.prepare_filename({**info, "ext": "tmp"}))
    folder, stem = name.parent, name.stem

    def taken(s):
        return any((folder / f"{s}.{e}").exists() for e in exts)

    if not taken(stem):
        return None
    n = 2
    while taken(f"{stem} ({n})"):
        n += 1
    return str(folder / f"{stem} ({n})").replace("%", "%%") + ".%(ext)s"


def run_download(item: Item, ffmpeg_path: str = "") -> None:
    """Download one queue item. Runs on a worker thread and only updates item."""
    def hook(d):
        if item.cancel_requested:
            raise yt_dlp.utils.DownloadCancelled("Cancelled by user")
        info = d.get("info_dict") or {}
        item.playlist_pos   = info.get("playlist_index") or 0
        item.playlist_total = info.get("n_entries") or info.get("playlist_count") or 0
        if d["status"] == "downloading":
            item.stage = ""
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            dl    = d.get("downloaded_bytes", 0)
            item.progress = min(dl / total, 1.0) if total else 0.0
            item.speed    = d.get("speed") or 0
            item.eta      = d.get("eta") or 0
            item.total    = total or dl
            if info.get("title"):
                item.title = info["title"][:60]
                item.title_known = True
        elif d["status"] == "finished":
            item.progress = 1.0
            if d.get("filename"):
                item.filepath = d["filename"]

    def pp_hook(d):
        if d.get("status") == "started":
            item.stage = "processing"
        elif d.get("status") == "finished":
            info = d.get("info_dict", {}) or {}
            path = (info.get("filepath") or info.get("_filename")
                    or (info.get("requested_downloads") or [{}])[0].get("filepath"))
            if path:
                item.filepath = path

    try:
        opts = dict(item.opts)
        opts["progress_hooks"]      = [hook]
        opts["postprocessor_hooks"] = [pp_hook]
        opts["logger"]              = YtdlpLogger()
        opts.setdefault("quiet", True)
        opts.setdefault("noprogress", True)
        opts.setdefault("ffmpeg_location", find_ffmpeg(ffmpeg_path))
        deno = updater.deno_path()
        if deno:
            opts.setdefault("js_runtimes", {"deno": {"path": str(deno)}})
        log.info("Download started: %s", item.url)
        with yt_dlp.YoutubeDL(opts) as ydl:
            # Fetch the info once (or reuse the preview's), pick a free file
            # name, then download.
            ie = item.info or ydl.extract_info(item.url, download=False, process=False)
            if ie.get("_type", "video") == "video":
                tmpl = unique_template(ydl, ie, item.exts)
                if tmpl:
                    log.info("File exists, saving as %s", tmpl)
                    ydl.params["outtmpl"]["default"] = tmpl
            info = ydl.process_ie_result(ie, download=True)
        if info and info.get("title"):
            item.title = info["title"][:60]
            item.title_known = True
        item.progress = 1.0
        item.stage    = ""
        item.status   = "done"
        log.info("Download finished: %s -> %s", item.url, item.filepath)
    except yt_dlp.utils.DownloadCancelled:
        item.status = "cancelled"
        log.info("Download cancelled: %s", item.url)
    except Exception as e:
        msg = re.sub(r"^ERROR:\s*", "", str(e))
        if using_downloaded() and ("No module named" in msg or isinstance(e, ImportError)):
            # The downloaded yt-dlp needs something the app doesn't bundle
            updater.revert_ytdlp()
            msg += "\n\nVortex switched back to its built-in yt-dlp. Restart Vortex and try again."
        item.error  = msg
        item.stage  = ""
        item.status = "error"
        log.error("Download failed: %s: %s", item.url, msg)


# ── Preview and search ────────────────────────────────────────────────────────
def _quick_ydl(**extra):
    opts = {"quiet": True, "noprogress": True, "logger": YtdlpLogger(),
            "extract_flat": "in_playlist", "noplaylist": True}
    deno = updater.deno_path()
    if deno:
        opts["js_runtimes"] = {"deno": {"path": str(deno)}}
    opts.update(extra)
    return yt_dlp.YoutubeDL(opts)


def looks_like_url(text: str) -> bool:
    return bool(re.match(r"^(https?://|www\.)\S+$", text.strip(), re.I))


def fetch_preview(url: str) -> tuple[dict, bool]:
    """Info for one URL, and whether the download may reuse it.

    For a single video this is yt-dlp's raw extractor result (process=False),
    the same thing run_download would fetch, so the download skips a second
    request to YouTube. A processed result can't be reused: it already has
    formats picked for the preview, and YouTube refuses those (HTTP 403).
    Playlists and redirects are resolved for display only.
    """
    with _quick_ydl() as ydl:
        ie = ydl.extract_info(url, download=False, process=False)
        if ie.get("_type", "video") == "video":
            return ie, True
        return ydl.process_ie_result(ie, download=False), False


def search(query: str, n: int = 6) -> list[dict]:
    """YouTube search. Returns flat entries: id, url, title, channel, duration."""
    with _quick_ydl() as ydl:
        res = ydl.extract_info(f"ytsearch{n}:{query}", download=False)
    out = []
    for e in (res or {}).get("entries") or []:
        out.append({
            "url": e.get("url") or f"https://www.youtube.com/watch?v={e.get('id')}",
            "title": e.get("title") or "",
            "channel": e.get("channel") or e.get("uploader") or "",
            "duration": e.get("duration"),
        })
    return out


def best_thumbnail_url(info: dict) -> str | None:
    if info.get("thumbnail"):
        return info["thumbnail"]
    thumbs = [t for t in info.get("thumbnails") or [] if t.get("url")]
    if not thumbs:
        return None
    # pick one close to 480 px wide, preferring jpg over webp
    def score(t):
        return (abs((t.get("width") or 480) - 480), ".webp" in t["url"])
    return sorted(thumbs, key=score)[0]["url"]


def thumbnail_png_b64(url: str, width: int = 320, ffmpeg_path: str = "") -> str | None:
    """Fetch a thumbnail and turn it into base64 PNG with FFmpeg.

    Tk can only show PNG/GIF, and thumbnails are JPEG or WebP. FFmpeg is
    already bundled, so this avoids adding Pillow to the app.
    """
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = r.read(5_000_000)
        p = subprocess.run(
            [find_ffmpeg(ffmpeg_path), "-hide_banner", "-loglevel", "error", "-i", "pipe:0",
             "-vf", f"scale={width}:-2", "-frames:v", "1", "-f", "image2pipe", "-c:v", "png", "pipe:1"],
            input=data, capture_output=True, timeout=20, **SUBPROCESS_FLAGS)
        if p.returncode == 0 and p.stdout:
            return base64.b64encode(p.stdout).decode()
        log.warning("Thumbnail conversion failed: %s", p.stderr.decode(errors="replace")[-200:])
    except Exception as e:
        log.warning("Thumbnail failed: %s", e)
    return None
