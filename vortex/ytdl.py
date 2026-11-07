"""The one place that imports yt-dlp.

Everything else uses `from .ytdl import yt_dlp`, so the updater can decide
once, at startup, whether the built-in or a downloaded yt-dlp is used.
"""
from .config import log
from . import updater

try:
    yt_dlp = updater.load_ytdlp()
    YT_DLP_OK = True
    YT_DLP_VERSION = yt_dlp.version.__version__
except ImportError:
    yt_dlp = None
    YT_DLP_OK = False
    YT_DLP_VERSION = "missing"


def using_downloaded() -> bool:
    """True when the yt-dlp in use is one the updater downloaded."""
    return bool(YT_DLP_OK and str(updater.YTDLP_ZIP) in (yt_dlp.__file__ or ""))


class YtdlpLogger:
    """Routes yt-dlp's output to our log file instead of stdout/stderr."""
    def debug(self, msg):   pass
    def info(self, msg):    pass
    def warning(self, msg): log.warning("yt-dlp: %s", msg)
    def error(self, msg):   log.error("yt-dlp: %s", msg)
