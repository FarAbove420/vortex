"""Small OS helpers: formatting, opening files, notifications, one instance."""
import os
import subprocess
import sys
from pathlib import Path

from .config import APP_DIR, SUBPROCESS_FLAGS, log


# ── Formatting ────────────────────────────────────────────────────────────────
def fmt_bytes(b: float) -> str:
    if b < 1024:      return f"{b:.0f} B"
    if b < 1024**2:   return f"{b/1024:.1f} KB"
    if b < 1024**3:   return f"{b/1024**2:.1f} MB"
    return                    f"{b/1024**3:.2f} GB"


def fmt_speed(bps: float) -> str:
    return fmt_bytes(bps) + "/s"


def fmt_eta(sec: int) -> str:
    sec = int(sec)
    if sec < 60:   return f"{sec}s"
    if sec < 3600: return f"{sec//60}m {sec%60:02d}s"
    return                f"{sec//3600}h {(sec%3600)//60}m"


def fmt_duration(sec) -> str:
    if not sec:
        return ""
    sec = int(sec)
    h, m, s = sec // 3600, (sec % 3600) // 60, sec % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


# ── Files and URLs ────────────────────────────────────────────────────────────
def open_path(path: str):
    p = Path(path)
    if not p.exists():
        return
    try:
        if sys.platform == "win32":
            os.startfile(str(p))
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(p)], **SUBPROCESS_FLAGS)
        else:
            subprocess.Popen(["xdg-open", str(p)], **SUBPROCESS_FLAGS)
    except Exception as e:
        log.warning("Could not open %s: %s", p, e)


def reveal_in_folder(path: str):
    p = Path(path)
    try:
        if sys.platform == "win32" and p.exists():
            subprocess.Popen(["explorer", "/select,", str(p)])
        elif sys.platform == "darwin" and p.exists():
            subprocess.Popen(["open", "-R", str(p)])
        elif p.parent.exists():
            open_path(str(p.parent))
    except Exception as e:
        log.warning("Could not show %s: %s", p, e)


def open_url(url: str):
    import webbrowser
    webbrowser.open(url)


def get_default_browser() -> str:
    if sys.platform == "win32":
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\Shell\Associations\UrlAssociations\https\UserChoice"
            )
            prog_id = winreg.QueryValueEx(key, "ProgId")[0].lower()
            winreg.CloseKey(key)
            for name in ("firefox", "chrome", "edge", "brave", "opera", "vivaldi"):
                if name in prog_id:
                    return name
        except Exception:
            pass
        return "chrome"
    elif sys.platform == "darwin":
        try:
            import plistlib
            plist_path = Path.home() / "Library/Preferences/com.apple.LaunchServices/com.apple.launchservices.secure.plist"
            with open(plist_path, "rb") as f:
                data = plistlib.load(f)
            for handler in data.get("LSHandlers", []):
                if handler.get("LSHandlerURLScheme") in ("https", "http"):
                    bundle = handler.get("LSHandlerRoleAll", "").lower()
                    for name in ("firefox", "chrome", "edge", "brave", "opera", "vivaldi", "safari"):
                        if name in bundle:
                            return name
        except Exception:
            pass
        return "safari"
    return "chrome"


def cookie_browser() -> str:
    """Browser to read cookies from for "Retry with browser cookies".

    On Windows, Chrome 127+ (and other Chromium browsers) encrypt cookies so
    that other programs can't read them, so Firefox is used when it's
    installed, even if it isn't the default browser.
    """
    browser = get_default_browser()
    if sys.platform == "win32" and browser != "firefox":
        profiles = Path(os.environ.get("APPDATA", "")) / "Mozilla" / "Firefox" / "Profiles"
        if profiles.is_dir() and any(profiles.iterdir()):
            return "firefox"
    return browser


# ── Notifications ─────────────────────────────────────────────────────────────
def notify(window, title: str, message: str):
    """Tell the user a download finished while Vortex is in the background.

    macOS: a Notification Center banner via osascript.
    Windows: flash the taskbar button (FlashWindowEx), no extra libraries.
    """
    try:
        if sys.platform == "darwin":
            def q(s):  # AppleScript string literal
                return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'
            subprocess.Popen(["osascript", "-e",
                              f"display notification {q(message)} with title {q(title)}"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif sys.platform == "win32":
            import ctypes
            from ctypes import wintypes

            class FLASHWINFO(ctypes.Structure):
                _fields_ = [("cbSize", wintypes.UINT), ("hwnd", wintypes.HWND),
                            ("dwFlags", wintypes.DWORD), ("uCount", wintypes.UINT),
                            ("dwTimeout", wintypes.DWORD)]
            FLASHW_ALL, FLASHW_TIMERNOFG = 0x3, 0xC
            hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
            info = FLASHWINFO(ctypes.sizeof(FLASHWINFO), hwnd, FLASHW_ALL | FLASHW_TIMERNOFG, 0, 0)
            ctypes.windll.user32.FlashWindowEx(ctypes.byref(info))
    except Exception as e:
        log.warning("Notification failed: %s", e)


# ── One Vortex at a time ──────────────────────────────────────────────────────
_lock_file = None


def acquire_single_instance() -> bool:
    """Lock ~/.vortex/vortex.lock for as long as this process runs.

    Returns False when another Vortex already holds the lock. The OS drops
    the lock when the process ends, even after a crash.
    """
    global _lock_file
    APP_DIR.mkdir(parents=True, exist_ok=True)
    f = open(APP_DIR / "vortex.lock", "a+")
    try:
        if sys.platform == "win32":
            import msvcrt
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        f.close()
        return False
    _lock_file = f
    return True
