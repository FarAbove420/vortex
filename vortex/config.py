"""Paths, logging and settings. Imported first by everything else."""
import json
import logging
import os
import subprocess
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

# python.org's Python on macOS ships without a certificate store, so HTTPS
# fails out of the box. Point SSL at certifi's certificate list before any
# HTTPS-using module is imported.
try:
    import certifi
    os.environ.setdefault("SSL_CERT_FILE",      certifi.where())
    os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())
except ImportError:
    pass

APP_DIR       = Path.home() / ".vortex"
LOG_PATH      = APP_DIR / "vortex.log"
SETTINGS_PATH = APP_DIR / "settings.json"
HISTORY_PATH  = APP_DIR / "history.json"

# ── Logging ───────────────────────────────────────────────────────────────────
# The packaged app has no console, so everything worth keeping goes to a
# small rotating log file.
log = logging.getLogger("vortex")


def setup_logging():
    if log.handlers:
        return
    log.setLevel(logging.INFO)
    try:
        APP_DIR.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(LOG_PATH, maxBytes=1_000_000, backupCount=2, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        log.addHandler(handler)
    except OSError:
        log.addHandler(logging.NullHandler())


setup_logging()

# On Windows, our own subprocess calls would briefly flash a console window.
if sys.platform == "win32":
    SUBPROCESS_FLAGS = {"creationflags": subprocess.CREATE_NO_WINDOW}
else:
    SUBPROCESS_FLAGS = {}


def resource_path(rel: str) -> Path:
    """Path to a bundled file, both from source and in the PyInstaller build."""
    base = getattr(sys, "_MEIPASS", None)
    return (Path(base) if base else Path(__file__).resolve().parent.parent) / rel


# ── Settings ──────────────────────────────────────────────────────────────────
DEFAULTS = {
    "download_dir":         str(Path.home() / "Downloads"),
    "default_audio_format": "mp3",
    "ffmpeg_path":          "ffmpeg",
    "embed_subs":           False,
    "embed_thumbnail":      True,    # cover art in songs, thumbnail in videos
    "prefer_mp4":           True,    # videos that play on any device
    "auto_update":          True,
    "show_advanced":        False,   # the Advanced download tab
    "text_size":            "Normal",
    "notify":               True,
}

TEXT_SIZES = {"Normal": 1.0, "Large": 1.15, "Larger": 1.3}


def load_settings() -> dict:
    s = DEFAULTS.copy()
    try:
        s.update(json.loads(SETTINGS_PATH.read_text()))
    except FileNotFoundError:
        pass
    except (OSError, ValueError) as e:
        log.warning("Settings file unreadable, using defaults: %s", e)
    return s


def save_settings(s: dict):
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = SETTINGS_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(s, indent=2))
    os.replace(tmp, SETTINGS_PATH)
