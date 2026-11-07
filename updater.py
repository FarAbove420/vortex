"""Keeps yt-dlp and Deno up to date without reinstalling Vortex.

YouTube changes often, and an old yt-dlp stops working. The packaged app has
yt-dlp built in, so without this a fix means a new Vortex build.

yt-dlp: every release has a file called `yt-dlp`, which is a zip that Python
can import directly (it includes yt-dlp-ejs). We download it to
~/.vortex/yt-dlp/, check it against the release's SHA2-256SUMS, and use it
on the next start when it's newer than the built-in copy.

Deno: since yt-dlp 2025.11.12, YouTube needs a JavaScript runtime. We
download Deno from its GitHub releases to ~/.vortex/bin/, checked against its
.sha256sum file, and pass its path to yt-dlp.

All network work runs on a background thread. Without internet, Vortex keeps
using what it already has.
"""
import hashlib
import json
import logging
import os
import platform
import re
import shutil
import ssl
import sys
import tempfile
import time
import urllib.request
import zipfile
from pathlib import Path

log = logging.getLogger("vortex.updater")

APP_DIR    = Path.home() / ".vortex"
YTDLP_ZIP  = APP_DIR / "yt-dlp" / "yt-dlp.zip"
BIN_DIR    = APP_DIR / "bin"
STATE_PATH = APP_DIR / "updates.json"

YTDLP_API  = "https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest"
YTDLP_DL   = "https://github.com/yt-dlp/yt-dlp/releases/download/{tag}/{name}"
DENO_API   = "https://api.github.com/repos/denoland/deno/releases/latest"
DENO_DL    = "https://github.com/denoland/deno/releases/download/{tag}/{name}"

YTDLP_CHECK_EVERY = 6 * 3600        # GitHub allows 60 API calls/hour per IP
DENO_CHECK_EVERY  = 7 * 24 * 3600

USER_AGENT = "Vortex-updater"


# ── Small helpers ─────────────────────────────────────────────────────────────
def version_tuple(v: str) -> tuple:
    """'2026.10.26' -> (2026, 10, 26). Non-numbers count as 0."""
    return tuple(int(p) if p.isdigit() else 0 for p in re.split(r"[.\-]", v.lstrip("v")))


def read_state() -> dict:
    try:
        return json.loads(STATE_PATH.read_text())
    except (OSError, ValueError):
        return {}


def write_state(**changes):
    state = read_state()
    state.update(changes)
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2))
    os.replace(tmp, STATE_PATH)


def _ssl_context():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def _get(url: str, timeout: int = 20) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout, context=_ssl_context()) as r:
        return r.read()


def _download(url: str, dest: Path, timeout: int = 60):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout, context=_ssl_context()) as r, open(dest, "wb") as f:
        shutil.copyfileobj(r, f, length=1024 * 1024)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _latest_tag(api_url: str) -> str:
    return json.loads(_get(api_url))["tag_name"]


# ── yt-dlp ────────────────────────────────────────────────────────────────────
def _is_ytdlp_module(name: str) -> bool:
    return name.split(".")[0] in ("yt_dlp", "yt_dlp_ejs")


def bundled_ytdlp_version() -> str | None:
    """Version of the yt-dlp built into the app, read from its package
    metadata so yt-dlp itself isn't imported. Only one copy of yt-dlp may be
    imported per run: yt-dlp patches urllib3 on import, and a second copy
    patching it again breaks the requests handler."""
    from importlib.metadata import PackageNotFoundError, version
    try:
        return version("yt-dlp")
    except PackageNotFoundError:
        return None


def load_ytdlp():
    """Import yt-dlp, preferring the downloaded copy when it's newer.

    Returns the yt_dlp module. Raises ImportError if no yt-dlp is available.
    """
    cached  = read_state().get("yt_dlp")
    bundled = bundled_ytdlp_version()
    use_downloaded = (cached and YTDLP_ZIP.exists()
                      and (bundled is None or version_tuple(cached) > version_tuple(bundled)))

    if use_downloaded:
        sys.path.insert(0, str(YTDLP_ZIP))
        try:
            import yt_dlp
            if yt_dlp.version.__version__ != cached:
                raise ImportError(f"expected {cached}, got {yt_dlp.version.__version__} from {yt_dlp.__file__}")
            return yt_dlp
        except Exception as e:
            # Most likely the new yt-dlp needs something the app doesn't
            # bundle. Use the built-in copy and don't try this version again.
            log.error("Downloaded yt-dlp %s doesn't load, using the built-in one: %s", cached, e)
            sys.path.remove(str(YTDLP_ZIP))
            for k in [k for k in sys.modules if _is_ytdlp_module(k)]:
                del sys.modules[k]
            write_state(yt_dlp=None, yt_dlp_bad=cached)
            try:
                YTDLP_ZIP.unlink()
            except OSError:
                pass

    import yt_dlp
    return yt_dlp


def update_ytdlp(running_version: str) -> str | None:
    """Download a newer yt-dlp if there is one. Returns its version, or None."""
    state = read_state()
    if time.time() - state.get("yt_dlp_checked", 0) < YTDLP_CHECK_EVERY:
        return None
    tag = _latest_tag(YTDLP_API)
    write_state(yt_dlp_checked=time.time())
    if version_tuple(tag) <= version_tuple(running_version):
        return None
    if tag in (state.get("yt_dlp"), state.get("yt_dlp_bad")):
        return None  # already downloaded, or known not to load

    sums = _get(YTDLP_DL.format(tag=tag, name="SHA2-256SUMS")).decode()
    m = re.search(r"^([0-9a-f]{64})\s+yt-dlp$", sums, re.MULTILINE)
    if not m:
        raise ValueError("yt-dlp checksum not found in SHA2-256SUMS")

    YTDLP_ZIP.parent.mkdir(parents=True, exist_ok=True)
    tmp = YTDLP_ZIP.with_suffix(".download")
    try:
        _download(YTDLP_DL.format(tag=tag, name="yt-dlp"), tmp)
        if _sha256(tmp) != m.group(1):
            raise ValueError("yt-dlp download doesn't match its checksum")
        with zipfile.ZipFile(tmp) as z:
            if "yt_dlp/__init__.py" not in z.namelist():
                raise ValueError("yt-dlp download is not the expected zip")
        os.replace(tmp, YTDLP_ZIP)
    finally:
        tmp.unlink(missing_ok=True)
    write_state(yt_dlp=tag)
    log.info("Downloaded yt-dlp %s", tag)
    return tag


# ── Deno ──────────────────────────────────────────────────────────────────────
def _deno_target() -> str | None:
    machine = platform.machine().lower()
    arch = "aarch64" if machine in ("arm64", "aarch64") else "x86_64" if machine in ("x86_64", "amd64") else None
    os_name = {"darwin": "apple-darwin", "win32": "pc-windows-msvc"}.get(sys.platform)
    if sys.platform.startswith("linux"):
        os_name = "unknown-linux-gnu"
    return f"{arch}-{os_name}" if arch and os_name else None


def deno_path() -> Path | None:
    """Our own Deno, if we have downloaded one."""
    p = BIN_DIR / ("deno.exe" if sys.platform == "win32" else "deno")
    return p if p.exists() else None


def update_deno() -> str | None:
    """Download Deno, or a newer one. Returns its version, or None."""
    state = read_state()
    have = deno_path()
    if have and time.time() - state.get("deno_checked", 0) < DENO_CHECK_EVERY:
        return None
    target = _deno_target()
    if not target:
        return None
    tag = _latest_tag(DENO_API)
    write_state(deno_checked=time.time())
    if have and state.get("deno") == tag:
        return None

    name = f"deno-{target}.zip"
    sums = _get(DENO_DL.format(tag=tag, name=name + ".sha256sum")).decode()
    # macOS/Linux use `hash  file`, Windows uses PowerShell's Get-FileHash output
    m = re.search(r"\b([0-9a-fA-F]{64})\b", sums)
    if not m:
        raise ValueError("Deno checksum not found")

    BIN_DIR.mkdir(parents=True, exist_ok=True)
    exe = "deno.exe" if sys.platform == "win32" else "deno"
    with tempfile.TemporaryDirectory(dir=APP_DIR) as tmp:
        zpath = Path(tmp) / name
        _download(DENO_DL.format(tag=tag, name=name), zpath, timeout=120)
        if _sha256(zpath) != m.group(1).lower():
            raise ValueError("Deno download doesn't match its checksum")
        with zipfile.ZipFile(zpath) as z:
            z.extract(exe, tmp)
        new = Path(tmp) / exe
        new.chmod(0o755)
        os.replace(new, BIN_DIR / exe)
    write_state(deno=tag)
    log.info("Downloaded Deno %s", tag)
    return tag


# ── Background check ──────────────────────────────────────────────────────────
def check_in_background(running_ytdlp: str, notify):
    """Run both updates on a thread. notify(text) is called from that thread."""
    import threading

    def run():
        try:
            tag = update_ytdlp(running_ytdlp)
            if tag:
                notify(f"yt-dlp {tag} ready, restart Vortex to use it")
        except Exception as e:
            log.warning("yt-dlp update check failed: %s", e)
        try:
            if update_deno():
                notify("Deno installed for YouTube")
        except Exception as e:
            log.warning("Deno update check failed: %s", e)

    threading.Thread(target=run, daemon=True, name="updater").start()
