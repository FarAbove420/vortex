"""Keeps yt-dlp and Deno up to date without reinstalling Vortex, and tells
the user when a new Vortex release is out.

YouTube changes often, and an old yt-dlp stops working. The packaged app has
yt-dlp built in, so without this a fix means a new Vortex build.

yt-dlp: every release has a file called `yt-dlp`, which is a zip that Python
can import directly (it includes yt-dlp-ejs). We download it to
~/.vortex/yt-dlp/, check it against the release's SHA2-256SUMS, and use it
on the next start when it's newer than the built-in copy. The previous
download is kept, so a bad release can be undone. This is the same check
`yt-dlp -U` itself does (hash, no signature).

Deno: since yt-dlp 2025.11.12, YouTube needs a JavaScript runtime. We
download Deno from its GitHub releases to ~/.vortex/bin/, checked against its
.sha256sum file, and pass its path to yt-dlp.

Versions are read from where github.com/<repo>/releases/latest redirects to,
not from the GitHub API, which only allows 60 requests per hour per IP
address (easily used up behind a shared school or office connection).

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
import threading
import time
import urllib.request
import zipfile
from pathlib import Path

from .config import APP_DIR

log = logging.getLogger("vortex.updater")

YTDLP_DIR      = APP_DIR / "yt-dlp"
YTDLP_ZIP      = YTDLP_DIR / "yt-dlp.zip"
YTDLP_PREVIOUS = YTDLP_DIR / "yt-dlp.previous.zip"
BIN_DIR        = APP_DIR / "bin"
STATE_PATH     = APP_DIR / "updates.json"

YTDLP_REPO  = "yt-dlp/yt-dlp"
DENO_REPO   = "denoland/deno"
VORTEX_REPO = "FarAbove420/vortex"

YTDLP_CHECK_EVERY  = 6 * 3600
DENO_CHECK_EVERY   = 7 * 24 * 3600
VORTEX_CHECK_EVERY = 24 * 3600

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


_state_lock = threading.Lock()


def write_state(**changes):
    with _state_lock:
        state = read_state()
        state.update(changes)
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = STATE_PATH.with_suffix(f".{os.getpid()}.tmp")
        tmp.write_text(json.dumps(state, indent=2))
        os.replace(tmp, STATE_PATH)


def _ssl_context():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def _open(url: str, timeout: int, method: str = "GET"):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT}, method=method)
    return urllib.request.urlopen(req, timeout=timeout, context=_ssl_context())


def _get(url: str, timeout: int = 20) -> bytes:
    with _open(url, timeout) as r:
        return r.read()


def _download(url: str, dest: Path, timeout: int = 60):
    with _open(url, timeout) as r, open(dest, "wb") as f:
        shutil.copyfileobj(r, f, length=1024 * 1024)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def latest_tag(repo: str) -> str:
    """Tag of a repo's latest release, from the releases/latest redirect."""
    with _open(f"https://github.com/{repo}/releases/latest", 20, method="HEAD") as r:
        final = r.geturl()
    m = re.search(r"/releases/tag/([^/?#]+)$", final)
    if not m:
        raise ValueError(f"no release tag in {final}")
    return urllib.request.unquote(m.group(1))


def _release_file(repo: str, tag: str, name: str) -> str:
    return f"https://github.com/{repo}/releases/download/{tag}/{name}"


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


def _discard_ytdlp_download(version: str | None):
    """Forget the downloaded yt-dlp and never try that version again. The
    previous download, if any, becomes the current one."""
    state = read_state()
    previous = state.get("yt_dlp_previous") if YTDLP_PREVIOUS.exists() else None
    try:
        if previous:
            os.replace(YTDLP_PREVIOUS, YTDLP_ZIP)
        else:
            YTDLP_ZIP.unlink(missing_ok=True)
    except OSError as e:
        log.warning("Could not remove downloaded yt-dlp: %s", e)
    bad = set(state.get("yt_dlp_bad_list") or [])
    if version:
        bad.add(version)
    write_state(yt_dlp=previous, yt_dlp_previous=None, yt_dlp_bad_list=sorted(bad))


def load_ytdlp():
    """Import yt-dlp, preferring the downloaded copy when it's newer.

    Returns the yt_dlp module. Raises ImportError if no yt-dlp is available.
    """
    state   = read_state()
    cached  = state.get("yt_dlp")
    bundled = bundled_ytdlp_version()
    use_downloaded = (cached and YTDLP_ZIP.exists() and not state.get("use_builtin")
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
            _discard_ytdlp_download(cached)

    import yt_dlp
    return yt_dlp


def revert_ytdlp():
    """Stop using the downloaded yt-dlp that's running now (from the next
    start): go back to the previous download, or the built-in copy."""
    current = read_state().get("yt_dlp")
    log.warning("Reverting downloaded yt-dlp %s", current)
    _discard_ytdlp_download(current)


def set_use_builtin(value: bool):
    """Settings switch: always use the yt-dlp built into the app."""
    write_state(use_builtin=bool(value))


def update_ytdlp(running_version: str) -> str | None:
    """Download a newer yt-dlp if there is one. Returns its version, or None."""
    state = read_state()
    if state.get("use_builtin"):
        return None
    if time.time() - state.get("yt_dlp_checked", 0) < YTDLP_CHECK_EVERY:
        return None
    tag = latest_tag(YTDLP_REPO)
    write_state(yt_dlp_checked=time.time())
    if version_tuple(tag) <= version_tuple(running_version):
        return None
    if tag == state.get("yt_dlp") or tag in (state.get("yt_dlp_bad_list") or []):
        return None  # already downloaded, or known not to work

    sums = _get(_release_file(YTDLP_REPO, tag, "SHA2-256SUMS")).decode()
    m = re.search(r"^([0-9a-f]{64})\s+yt-dlp$", sums, re.MULTILINE)
    if not m:
        raise ValueError("yt-dlp checksum not found in SHA2-256SUMS")

    YTDLP_DIR.mkdir(parents=True, exist_ok=True)
    tmp = YTDLP_DIR / f"yt-dlp.{os.getpid()}.download"
    try:
        _download(_release_file(YTDLP_REPO, tag, "yt-dlp"), tmp)
        if _sha256(tmp) != m.group(1):
            raise ValueError("yt-dlp download doesn't match its checksum")
        with zipfile.ZipFile(tmp) as z:
            if "yt_dlp/__init__.py" not in z.namelist():
                raise ValueError("yt-dlp download is not the expected zip")
        # Keep the current download as the fallback for a bad release. Not
        # while it's in use on Windows, where an open file can't be renamed.
        previous = read_state().get("yt_dlp")
        if previous and YTDLP_ZIP.exists():
            try:
                os.replace(YTDLP_ZIP, YTDLP_PREVIOUS)
            except OSError:
                previous = None
        os.replace(tmp, YTDLP_ZIP)
    finally:
        tmp.unlink(missing_ok=True)
    write_state(yt_dlp=tag, yt_dlp_previous=previous)
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
    tag = latest_tag(DENO_REPO)
    write_state(deno_checked=time.time())
    if have and state.get("deno") == tag:
        return None

    name = f"deno-{target}.zip"
    sums = _get(_release_file(DENO_REPO, tag, name + ".sha256sum")).decode()
    # macOS/Linux use `hash  file`, Windows uses PowerShell's Get-FileHash output
    m = re.search(r"\b([0-9a-fA-F]{64})\b", sums)
    if not m:
        raise ValueError("Deno checksum not found")

    BIN_DIR.mkdir(parents=True, exist_ok=True)
    exe = "deno.exe" if sys.platform == "win32" else "deno"
    with tempfile.TemporaryDirectory(dir=APP_DIR) as tmp:
        zpath = Path(tmp) / name
        _download(_release_file(DENO_REPO, tag, name), zpath, timeout=120)
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


# ── Vortex itself ─────────────────────────────────────────────────────────────
def check_vortex(running_version: str) -> str | None:
    """Newer Vortex release tag, or None. Fails quietly while the repo is
    private (GitHub answers 404)."""
    state = read_state()
    if time.time() - state.get("vortex_checked", 0) < VORTEX_CHECK_EVERY:
        tag = state.get("vortex_latest")
    else:
        tag = latest_tag(VORTEX_REPO)
        write_state(vortex_checked=time.time(), vortex_latest=tag)
    if tag and version_tuple(tag) > version_tuple(running_version):
        return tag
    return None


def vortex_release_url(tag: str) -> str:
    return f"https://github.com/{VORTEX_REPO}/releases/tag/{tag}"


# ── Background check ──────────────────────────────────────────────────────────
def check_in_background(running_ytdlp: str, running_vortex: str, notify):
    """Run all checks on a thread. notify(kind, text, data) is called from
    that thread; kind is "ytdlp", "deno" or "vortex"."""

    def run():
        try:
            tag = update_ytdlp(running_ytdlp)
            if tag:
                notify("ytdlp", f"yt-dlp {tag} ready, restart Vortex to use it", tag)
        except Exception as e:
            log.warning("yt-dlp update check failed: %s", e)
        try:
            tag = update_deno()
            if tag:
                notify("deno", f"Deno {tag} installed for YouTube", tag)
        except Exception as e:
            log.warning("Deno update check failed: %s", e)
        try:
            tag = check_vortex(running_vortex)
            if tag:
                notify("vortex", f"Vortex {tag.lstrip('v')} is available, click to download", tag)
        except Exception as e:
            log.info("Vortex update check skipped: %s", e)

    threading.Thread(target=run, daemon=True, name="updater").start()
