#!/usr/bin/env python3
"""Vortex - yt-dlp + ffmpeg desktop UI"""

# ── SSL fix (must run before any HTTPS-using module is imported) ──────────────
# python.org's Python on macOS ships without a certificate store, so HTTPS
# fails out of the box. Point SSL at certifi's bundled cert list before
# anything else can pin to the (broken) default.
import os
try:
    import certifi
    os.environ.setdefault("SSL_CERT_FILE",      certifi.where())
    os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())
except ImportError:
    pass

import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
import threading
import subprocess
import json
import re
import sys
from pathlib import Path
from datetime import datetime

try:
    import yt_dlp
    YT_DLP_OK = True
except ImportError:
    YT_DLP_OK = False

# On Windows, our own subprocess calls (ffmpeg duration probe, ffmpeg
# convert) would briefly flash a black cmd window. CREATE_NO_WINDOW hides
# it. yt-dlp already handles its internal Popen calls this way, but ours
# need this flag explicitly. No-op on macOS / Linux.
if sys.platform == "win32":
    SUBPROCESS_FLAGS = {"creationflags": subprocess.CREATE_NO_WINDOW}
else:
    SUBPROCESS_FLAGS = {}


# ── ffmpeg locator ────────────────────────────────────────────────────────────
def find_ffmpeg(configured: str = "") -> str:
    """Return the best available ffmpeg binary path.

    Preference order:
      1. User-configured absolute path from Settings (if it exists)
      2. Static ffmpeg bundled via the imageio-ffmpeg package (works in frozen
         .app bundles too: PyInstaller includes the binaries folder)
      3. Bare 'ffmpeg' string, relying on the user's PATH
    """
    if configured and configured != "ffmpeg":
        if Path(configured).exists():
            return configured

    try:
        import imageio_ffmpeg
        bundled = imageio_ffmpeg.get_ffmpeg_exe()
        if Path(bundled).exists():
            return bundled
    except Exception:
        pass

    return "ffmpeg"

# ── Palette ───────────────────────────────────────────────────────────────────
BG         = "#0d0d1a"
SURFACE    = "#12122a"
CARD       = "#191932"
CARD_HOVER = "#20203d"
ACCENT     = "#7c3aed"
ACCENT_LT  = "#9d5cf5"
ACCENT_DK  = "#5b21b6"
TEXT       = "#f0f0ff"
TEXT_DIM   = "#7070a0"
TEXT_HINT  = "#383858"
SUCCESS    = "#22c55e"
ERROR      = "#ef4444"
WARNING    = "#f59e0b"
BORDER     = "#252550"
WHITE      = "#ffffff"

ctk.set_appearance_mode("dark")

# ── Settings ──────────────────────────────────────────────────────────────────
SETTINGS_PATH = Path.home() / ".vortex" / "settings.json"
DEFAULTS = {
    "download_dir":         str(Path.home() / "Downloads"),
    "default_audio_format": "mp3",
    "ffmpeg_path":          "ffmpeg",
    "embed_subs":           False,
    "embed_thumbnail":      False,
    "keep_video":           True,
}

def load_settings() -> dict:
    if SETTINGS_PATH.exists():
        try:
            s = DEFAULTS.copy()
            s.update(json.loads(SETTINGS_PATH.read_text()))
            return s
        except Exception:
            pass
    return DEFAULTS.copy()

def save_settings(s: dict):
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_PATH.write_text(json.dumps(s, indent=2))

# ── Utilities ─────────────────────────────────────────────────────────────────
def fmt_bytes(b: float) -> str:
    if b < 1024:      return f"{b:.0f} B"
    if b < 1024**2:   return f"{b/1024:.1f} KB"
    if b < 1024**3:   return f"{b/1024**2:.1f} MB"
    return                    f"{b/1024**3:.2f} GB"

def fmt_speed(bps: float) -> str:
    return fmt_bytes(bps) + "/s"

def fmt_eta(sec: int) -> str:
    if sec < 60:   return f"{sec}s"
    if sec < 3600: return f"{sec//60}m {sec%60:02d}s"
    return                f"{sec//3600}h {(sec%3600)//60}m"

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

# ── Widget helpers ────────────────────────────────────────────────────────────
def lbl(parent, text, size=13, weight="normal", color=TEXT, **kw):
    return ctk.CTkLabel(
        parent, text=text,
        font=ctk.CTkFont(size=size, weight=weight),
        text_color=color, **kw
    )

def card(parent, **kw):
    return ctk.CTkFrame(
        parent, fg_color=CARD, corner_radius=14,
        border_width=1, border_color=BORDER, **kw
    )

def fancy_entry(parent, placeholder="", height=44, **kw):
    return ctk.CTkEntry(
        parent, placeholder_text=placeholder,
        height=height, corner_radius=10,
        border_width=1, border_color=BORDER,
        fg_color=SURFACE, text_color=TEXT,
        placeholder_text_color=TEXT_HINT,
        font=ctk.CTkFont(size=13), **kw
    )

def dropdown(parent, values, width=140, variable=None, **kw):
    return ctk.CTkOptionMenu(
        parent, values=values, width=width,
        corner_radius=10,
        fg_color=SURFACE,
        button_color=ACCENT, button_hover_color=ACCENT_LT,
        text_color=TEXT,
        dropdown_fg_color=CARD,
        dropdown_hover_color=CARD_HOVER,
        dropdown_text_color=TEXT,
        font=ctk.CTkFont(size=13),
        dropdown_font=ctk.CTkFont(size=12),
        variable=variable, **kw
    )

def ghost_btn(parent, text, command, width=100, height=36, **kw):
    return ctk.CTkButton(
        parent, text=text, command=command,
        width=width, height=height, corner_radius=10,
        fg_color=CARD_HOVER, hover_color=BORDER,
        text_color=TEXT, font=ctk.CTkFont(size=13), **kw
    )

def accent_btn(parent, text, command, width=160, height=48, **kw):
    return ctk.CTkButton(
        parent, text=text, command=command,
        width=width, height=height, corner_radius=12,
        fg_color=ACCENT, hover_color=ACCENT_LT,
        text_color=WHITE,
        font=ctk.CTkFont(size=14, weight="bold"), **kw
    )

def progress_bar(parent, color=ACCENT, **kw):
    bar = ctk.CTkProgressBar(
        parent, height=8, corner_radius=5,
        fg_color=SURFACE, progress_color=color, **kw
    )
    bar.set(0)
    return bar

def checkbox(parent, text, variable, **kw):
    return ctk.CTkCheckBox(
        parent, text=text, variable=variable,
        font=ctk.CTkFont(size=12), text_color=TEXT_DIM,
        fg_color=ACCENT, hover_color=ACCENT_LT,
        checkmark_color=WHITE, border_color=BORDER, **kw
    )

# ── Download queue item ────────────────────────────────────────────────────────
class Item:
    def __init__(self, url: str, opts: dict, title: str = ""):
        self.url     = url
        self.opts    = opts
        self.title   = title or url[:60]
        self.status  = "queued"
        self.progress = 0.0
        self.speed   = 0.0
        self.eta     = 0
        self.total   = 0
        self.error   = ""
        self.added   = datetime.now().strftime("%H:%M:%S")

# ── Main window ────────────────────────────────────────────────────────────────
class Vortex(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Vortex")
        self.geometry("1240x780")
        self.minsize(1000, 640)
        self.configure(fg_color=BG)

        self.settings = load_settings()
        self.queue: list[Item] = []
        self.active: Item | None = None

        self._build()
        self._nav("download")

    # ── Layout ────────────────────────────────────────────────────────────────
    def _build(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._sidebar()
        self._content()

    def _sidebar(self):
        sb = ctk.CTkFrame(self, width=230, corner_radius=0, fg_color=SURFACE)
        sb.grid(row=0, column=0, sticky="nsew")
        sb.grid_propagate(False)
        sb.grid_columnconfigure(0, weight=1)
        sb.grid_rowconfigure(5, weight=1)
        self._sb = sb

        # Logo
        logo_wrap = ctk.CTkFrame(sb, fg_color="transparent", height=88)
        logo_wrap.grid(row=0, column=0, sticky="ew")
        logo_wrap.grid_propagate(False)

        ctk.CTkLabel(
            logo_wrap, text="⚡ Vortex",
            font=ctk.CTkFont(size=26, weight="bold"), text_color=TEXT
        ).place(relx=0.5, rely=0.56, anchor="center")

        ctk.CTkFrame(sb, height=1, fg_color=BORDER).grid(
            row=1, column=0, sticky="ew", padx=18, pady=(0, 10)
        )

        # Nav
        self._nav_btns: dict[str, ctk.CTkButton] = {}
        nav = [
            ("download", "  ↓   Download"),
            ("queue",    "  ☰   Queue"),
            ("convert",  "  ⇄   Convert"),
            ("settings", "  ⚙   Settings"),
        ]
        for i, (key, label) in enumerate(nav):
            btn = ctk.CTkButton(
                sb, text=label, anchor="w",
                height=46, corner_radius=10, border_spacing=10,
                font=ctk.CTkFont(size=13),
                fg_color="transparent", hover_color=CARD_HOVER,
                text_color=TEXT_DIM,
                command=lambda k=key: self._nav(k),
            )
            btn.grid(row=i+2, column=0, padx=12, pady=2, sticky="ew")
            self._nav_btns[key] = btn

        # Status dot
        self._status_lbl = ctk.CTkLabel(
            sb, text="● Ready",
            font=ctk.CTkFont(size=11), text_color=SUCCESS
        )
        self._status_lbl.grid(row=6, column=0, padx=20, pady=(0, 18), sticky="w")

    def _content(self):
        cf = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        cf.grid(row=0, column=1, sticky="nsew")
        cf.grid_columnconfigure(0, weight=1)
        cf.grid_rowconfigure(0, weight=1)

        self._tabs = {
            "download": DownloadTab(cf, self),
            "queue":    QueueTab(cf, self),
            "convert":  ConvertTab(cf, self),
            "settings": SettingsTab(cf, self),
        }
        for t in self._tabs.values():
            t.grid(row=0, column=0, sticky="nsew")

    def _nav(self, key: str):
        for k, btn in self._nav_btns.items():
            if k == key:
                btn.configure(
                    fg_color=ACCENT, text_color=WHITE, hover_color=ACCENT_LT,
                    font=ctk.CTkFont(size=13, weight="bold")
                )
            else:
                btn.configure(
                    fg_color="transparent", text_color=TEXT_DIM,
                    hover_color=CARD_HOVER, font=ctk.CTkFont(size=13)
                )
        self._tabs[key].tkraise()

    def set_status(self, text: str, color: str = SUCCESS):
        self._status_lbl.configure(text=f"● {text}", text_color=color)

    # ── Queue management ───────────────────────────────────────────────────────
    def enqueue(self, item: Item):
        self.queue.append(item)
        self._tabs["queue"].refresh()
        if self.active is None:
            self._next()

    def _next(self):
        pending = [i for i in self.queue if i.status == "queued"]
        if not pending:
            self.set_status("Ready", SUCCESS)
            return
        item = pending[0]
        item.status = "downloading"
        self.active = item
        self._tabs["queue"].refresh()
        self.set_status("Downloading...", WARNING)
        threading.Thread(target=self._worker, args=(item,), daemon=True).start()

    def _worker(self, item: Item):
        def hook(d):
            if d["status"] == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 1
                dl    = d.get("downloaded_bytes", 0)
                item.progress = dl / total
                item.speed    = d.get("speed") or 0
                item.eta      = d.get("eta") or 0
                item.total    = total
                fname = d.get("filename", "")
                if fname and item.title == item.url[:60]:
                    item.title = Path(fname).stem[:60]
                self.after(80, self._tabs["queue"].refresh)
            elif d["status"] == "finished":
                item.progress = 1.0

        try:
            opts = item.opts.copy()
            opts["progress_hooks"] = [hook]
            opts.setdefault("quiet", True)
            opts.setdefault("no_warnings", True)
            opts.setdefault("ffmpeg_location",
                            find_ffmpeg(self.settings.get("ffmpeg_path", "")))
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(item.url, download=False)
                if info and item.title == item.url[:60]:
                    item.title = (info.get("title") or item.title)[:60]
                ydl.download([item.url])
            item.status   = "done"
            item.progress = 1.0
        except Exception as e:
            item.status = "error"
            item.error  = str(e)

        self.active = None
        self.after(0, self._tabs["queue"].refresh)
        self.after(100, self._next)


# ── Download Tab ──────────────────────────────────────────────────────────────
class DownloadTab(ctk.CTkFrame):
    def __init__(self, parent, app: Vortex):
        super().__init__(parent, fg_color=BG, corner_radius=0)
        self.app = app
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        self._build()

    def _build(self):
        # ── Header
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=32, pady=(30, 0))
        lbl(hdr, "Download", size=28, weight="bold").pack(side="left")
        lbl(hdr, "Paste a URL and configure your download", size=13, color=TEXT_DIM).pack(
            side="left", padx=(14, 0), pady=(10, 0)
        )

        # ── URL card
        url_card = card(self)
        url_card.grid(row=1, column=0, padx=32, pady=(20, 0), sticky="ew")
        url_card.grid_columnconfigure(0, weight=1)

        # URL row
        url_section = ctk.CTkFrame(url_card, fg_color="transparent")
        url_section.grid(row=0, column=0, padx=22, pady=(22, 12), sticky="ew")
        url_section.grid_columnconfigure(0, weight=1)

        lbl(url_section, "URL", size=11, weight="bold", color=TEXT_DIM).grid(
            row=0, column=0, sticky="w", pady=(0, 6)
        )

        url_row = ctk.CTkFrame(url_section, fg_color="transparent")
        url_row.grid(row=1, column=0, sticky="ew")
        url_row.grid_columnconfigure(0, weight=1)

        self.url_entry = fancy_entry(url_row, "https://youtube.com/watch?v=...", height=50)
        self.url_entry.configure(font=ctk.CTkFont(size=14))
        self.url_entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))

        ghost_btn(url_row, "Paste", self._paste, width=86, height=50).grid(row=0, column=1)

        # Options row
        opts_frame = ctk.CTkFrame(url_card, fg_color="transparent")
        opts_frame.grid(row=1, column=0, padx=22, pady=(0, 14), sticky="ew")
        opts_frame.grid_columnconfigure(3, weight=1)

        self.type_var  = ctk.StringVar(value="Audio Only")
        self.qual_var  = ctk.StringVar(value="Best")
        self.afmt_var  = ctk.StringVar(value=self.app.settings.get("default_audio_format", "mp3").upper())

        def opt_col(parent, label_text, var, values, width, on_change=None):
            c = ctk.CTkFrame(parent, fg_color="transparent")
            lbl(c, label_text, size=11, weight="bold", color=TEXT_DIM).pack(anchor="w", pady=(0, 5))
            dropdown(c, values, width=width, variable=var, command=on_change).pack()
            return c

        type_col = opt_col(opts_frame, "Type", self.type_var,
                           ["Video + Audio", "Video Only", "Audio Only"], 148,
                           on_change=self._on_type_change)
        type_col.grid(row=0, column=0, padx=(0, 22), sticky="w")

        self.qual_col = opt_col(opts_frame, "Quality", self.qual_var,
                                ["Best", "4K", "1440p", "1080p", "720p", "480p", "360p"], 120)
        self.qual_col.grid(row=0, column=1, padx=(0, 22), sticky="w")

        self.afmt_col = opt_col(opts_frame, "Audio Format", self.afmt_var,
                                ["MP3", "M4A", "FLAC", "WAV", "OPUS", "AAC"], 110)
        self.afmt_col.grid(row=0, column=2, padx=(0, 22), sticky="w")

        # Save-to (always visible)
        save_col = ctk.CTkFrame(opts_frame, fg_color="transparent")
        save_col.grid(row=0, column=3, sticky="ew")
        lbl(save_col, "Save To", size=11, weight="bold", color=TEXT_DIM).pack(anchor="w", pady=(0, 5))

        dir_row = ctk.CTkFrame(save_col, fg_color="transparent")
        dir_row.pack(fill="x")
        dir_row.grid_columnconfigure(0, weight=1)

        self.dir_entry = fancy_entry(dir_row, height=36)
        self.dir_entry.insert(0, self.app.settings.get("download_dir", str(Path.home() / "Downloads")))
        self.dir_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))

        ghost_btn(dir_row, "...", self._browse_dir, width=36, height=36).grid(row=0, column=1)

        # Checkboxes
        cb_row = ctk.CTkFrame(url_card, fg_color="transparent")
        cb_row.grid(row=2, column=0, padx=22, pady=(0, 14), sticky="ew")

        self.subs_var     = ctk.BooleanVar(value=self.app.settings.get("embed_subs", False))
        self.thumb_var    = ctk.BooleanVar(value=self.app.settings.get("embed_thumbnail", False))
        self.playlist_var = ctk.BooleanVar(value=False)
        self.sb_var       = ctk.BooleanVar(value=False)

        self.subs_cb     = checkbox(cb_row, "Embed subtitles",   self.subs_var)
        self.thumb_cb    = checkbox(cb_row, "Embed thumbnail",   self.thumb_var)
        self.playlist_cb = checkbox(cb_row, "Download playlist", self.playlist_var)
        self.sb_cb       = checkbox(cb_row, "SponsorBlock",      self.sb_var)

        self.subs_cb.grid(    row=0, column=0, padx=(0, 22), sticky="w")
        self.thumb_cb.grid(   row=0, column=1, padx=(0, 22), sticky="w")
        self.playlist_cb.grid(row=0, column=2, padx=(0, 22), sticky="w")
        self.sb_cb.grid(      row=0, column=3,               sticky="w")

        # Extra args
        extra_row = ctk.CTkFrame(url_card, fg_color="transparent")
        extra_row.grid(row=3, column=0, padx=22, pady=(0, 10), sticky="ew")
        extra_row.grid_columnconfigure(1, weight=1)

        lbl(extra_row, "Extra args", size=11, weight="bold", color=TEXT_DIM).grid(
            row=0, column=0, padx=(0, 12), sticky="w"
        )
        self.extra_entry = fancy_entry(extra_row, "--cookies-from-browser firefox", height=36)
        self.extra_entry.grid(row=0, column=1, sticky="ew")

        # Buttons
        btn_row = ctk.CTkFrame(url_card, fg_color="transparent")
        btn_row.grid(row=4, column=0, padx=22, pady=(8, 22), sticky="ew")

        accent_btn(btn_row, "  ↓  Download", self._download, width=190, height=54).pack(side="left")
        ghost_btn(btn_row, "Add to Queue", lambda: self._download(to_queue=True), width=148, height=54).pack(
            side="left", padx=(12, 0)
        )

        # ── Progress card
        self.prog_card = card(self)
        self.prog_card.grid(row=2, column=0, padx=32, pady=(16, 24), sticky="nsew")
        self.prog_card.grid_columnconfigure(0, weight=1)

        prog_hdr = ctk.CTkFrame(self.prog_card, fg_color="transparent")
        prog_hdr.grid(row=0, column=0, padx=22, pady=(18, 10), sticky="ew")
        prog_hdr.grid_columnconfigure(1, weight=1)

        lbl(prog_hdr, "Progress", size=13, weight="bold").grid(row=0, column=0, sticky="w")
        self.prog_pct = lbl(prog_hdr, "Idle", size=12, color=TEXT_DIM)
        self.prog_pct.grid(row=0, column=1, sticky="e")

        self.prog_bar = progress_bar(self.prog_card)
        self.prog_bar.grid(row=1, column=0, padx=22, pady=(0, 10), sticky="ew")

        info_row = ctk.CTkFrame(self.prog_card, fg_color="transparent")
        info_row.grid(row=2, column=0, padx=22, pady=(0, 18), sticky="ew")
        info_row.grid_columnconfigure(0, weight=1)

        self.prog_title = lbl(info_row, "No active download", size=12, color=TEXT_DIM)
        self.prog_title.grid(row=0, column=0, sticky="w")

        self.prog_speed = lbl(info_row, "", size=12, color=ACCENT)
        self.prog_speed.grid(row=0, column=1, sticky="e")

        # Set initial visibility based on default type
        self._on_type_change(self.type_var.get())

    # ── Reactivity ────────────────────────────────────────────────────────────
    def _on_type_change(self, value: str):
        is_audio = value == "Audio Only"
        if is_audio:
            self.qual_col.grid_remove()
            self.afmt_col.grid()
            self.subs_cb.grid_remove()
        else:
            self.qual_col.grid()
            self.afmt_col.grid_remove()
            self.subs_cb.grid()

    # ── Actions ───────────────────────────────────────────────────────────────
    def _paste(self):
        try:
            text = self.clipboard_get().strip()
            self.url_entry.delete(0, "end")
            self.url_entry.insert(0, text)
        except Exception:
            pass

    def _browse_dir(self):
        d = filedialog.askdirectory()
        if d:
            self.dir_entry.delete(0, "end")
            self.dir_entry.insert(0, d)

    def _build_opts(self) -> dict:
        dl_dir = self.dir_entry.get().strip() or self.app.settings["download_dir"]
        t      = self.type_var.get()
        q      = self.qual_var.get()
        afmt   = self.afmt_var.get().lower()

        if t == "Audio Only":
            fmt = "bestaudio/best"
        elif q == "Best":
            fmt = "bestvideo+bestaudio/best"
        elif q == "4K":
            fmt = "bestvideo[height<=2160]+bestaudio/best[height<=2160]"
        else:
            h = q.replace("p", "")
            fmt = f"bestvideo[height<={h}]+bestaudio/best[height<={h}]"

        opts: dict = {
            "format":  fmt,
            "outtmpl": str(Path(dl_dir) / "%(title)s.%(ext)s"),
        }

        if t == "Audio Only":
            opts["postprocessors"] = [{
                "key":             "FFmpegExtractAudio",
                "preferredcodec":  afmt,
                "preferredquality": "192",
            }]

        if self.subs_var.get():
            opts["writesubtitles"] = True
            opts["embedsubtitles"] = True

        if self.thumb_var.get():
            opts["writethumbnail"]  = True
            opts["embedthumbnail"]  = True

        if not self.playlist_var.get():
            opts["noplaylist"] = True

        if self.sb_var.get():
            pp = opts.get("postprocessors", [])
            pp.append({"key": "SponsorBlock", "categories": ["sponsor"]})
            opts["postprocessors"] = pp

        return opts

    def _download(self, to_queue=False):
        if not YT_DLP_OK:
            messagebox.showerror("Missing dependency", "yt-dlp is not installed.\nRun: pip install yt-dlp")
            return
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning("No URL", "Please enter a URL.")
            return

        item = Item(url, self._build_opts())
        self.app.enqueue(item)

        if to_queue:
            self.app._nav("queue")
        else:
            self._track(item)

    def _track(self, item: Item):
        self.prog_title.configure(text=item.title[:80])
        if item.status == "downloading":
            self.prog_bar.set(item.progress)
            self.prog_pct.configure(
                text=f"{item.progress*100:.1f}%  {fmt_speed(item.speed) if item.speed else ''}  {'ETA ' + fmt_eta(item.eta) if item.eta else ''}",
                text_color=ACCENT
            )
        elif item.status == "done":
            self.prog_bar.set(1.0)
            self.prog_pct.configure(text="Done!", text_color=SUCCESS)
            return
        elif item.status == "error":
            self.prog_pct.configure(text=f"Error: {item.error[:60]}", text_color=ERROR)
            return
        elif item.status == "queued":
            self.prog_pct.configure(text="Queued...", text_color=TEXT_DIM)

        self.after(200, lambda: self._track(item))


# ── Queue Tab ─────────────────────────────────────────────────────────────────
class QueueTab(ctk.CTkFrame):
    def __init__(self, parent, app: Vortex):
        super().__init__(parent, fg_color=BG, corner_radius=0)
        self.app = app
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._widgets: dict[Item, QueueRow] = {}
        self._build()

    def _build(self):
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=32, pady=(30, 14))
        hdr.grid_columnconfigure(1, weight=1)

        lbl(hdr, "Queue", size=28, weight="bold").grid(row=0, column=0, sticky="w")
        self.count_lbl = lbl(hdr, "0 items", size=13, color=TEXT_DIM)
        self.count_lbl.grid(row=0, column=1, sticky="w", padx=(14, 0))

        ghost_btn(hdr, "Clear Done", self._clear_done, width=110, height=36).grid(
            row=0, column=2, sticky="e"
        )

        self.scroll = ctk.CTkScrollableFrame(
            self, fg_color=BG,
            scrollbar_button_color=BORDER,
            scrollbar_button_hover_color=CARD_HOVER,
        )
        self.scroll.grid(row=1, column=0, sticky="nsew", padx=32, pady=(0, 24))
        self.scroll.grid_columnconfigure(0, weight=1)

        self.empty_lbl = lbl(
            self.scroll,
            "No downloads yet.\nHead over to Download to add URLs.",
            size=14, color=TEXT_HINT
        )
        self.empty_lbl.grid(row=0, column=0, pady=70)

    def refresh(self):
        q = self.app.queue
        n = len(q)
        self.count_lbl.configure(text=f"{n} item{'s' if n != 1 else ''}")

        if not q:
            self.empty_lbl.grid()
        else:
            self.empty_lbl.grid_remove()

        current = set(q)
        for item in list(self._widgets):
            if item not in current:
                self._widgets.pop(item).destroy()

        for row, item in enumerate(q):
            if item not in self._widgets:
                w = QueueRow(self.scroll, item, self.app)
                w.grid(row=row + 1, column=0, sticky="ew", pady=(0, 10))
                self._widgets[item] = w
            else:
                self._widgets[item].update_ui()
                self._widgets[item].grid(row=row + 1, column=0, sticky="ew", pady=(0, 10))

    def _clear_done(self):
        gone = {i for i in self.app.queue if i.status in ("done", "error", "cancelled")}
        self.app.queue = [i for i in self.app.queue if i not in gone]
        for item in gone:
            if item in self._widgets:
                self._widgets.pop(item).destroy()
        self.refresh()


class QueueRow(ctk.CTkFrame):
    _STATUS_COLOR = {"queued": TEXT_DIM, "downloading": ACCENT, "done": SUCCESS, "error": ERROR}
    _STATUS_ICON  = {"queued": "◷", "downloading": "↓", "done": "✓", "error": "✗", "cancelled": "—"}
    _BAR_COLOR    = {"queued": BORDER, "downloading": ACCENT, "done": SUCCESS, "error": ERROR}

    def __init__(self, parent, item: Item, app: Vortex):
        super().__init__(
            parent, fg_color=CARD, corner_radius=12,
            border_width=1, border_color=BORDER
        )
        self.item = item
        self.app  = app
        self.grid_columnconfigure(1, weight=1)
        self._build()
        self.update_ui()

    def _build(self):
        self.icon_lbl = ctk.CTkLabel(
            self, text="◷", width=40,
            font=ctk.CTkFont(size=22), text_color=TEXT_DIM
        )
        self.icon_lbl.grid(row=0, column=0, rowspan=3, padx=(16, 6), pady=14)

        self.title_lbl = ctk.CTkLabel(
            self, text="", anchor="w",
            font=ctk.CTkFont(size=13, weight="bold"), text_color=TEXT
        )
        self.title_lbl.grid(row=0, column=1, sticky="ew", padx=(0, 12), pady=(12, 2))

        self.bar = ctk.CTkProgressBar(
            self, height=5, corner_radius=4,
            fg_color=SURFACE, progress_color=ACCENT
        )
        self.bar.set(0)
        self.bar.grid(row=1, column=1, sticky="ew", padx=(0, 12), pady=(0, 4))

        self.info_lbl = ctk.CTkLabel(
            self, text="", anchor="w", wraplength=500,
            font=ctk.CTkFont(size=11), text_color=TEXT_DIM
        )
        self.info_lbl.grid(row=2, column=1, sticky="w", padx=(0, 12), pady=(0, 4))

        self.cookie_btn = ghost_btn(
            self, "↺  Retry with browser cookies", self._retry_with_cookies,
            width=220, height=26
        )
        self.cookie_btn.grid(row=3, column=1, padx=(0, 12), pady=(0, 10), sticky="w")
        self.cookie_btn.grid_remove()

        ghost_btn(self, "✕", self._remove, width=28, height=28).grid(
            row=0, column=2, padx=(0, 12), pady=(12, 0), sticky="ne"
        )

    def update_ui(self):
        i = self.item
        color = self._STATUS_COLOR.get(i.status, TEXT_DIM)
        icon  = self._STATUS_ICON.get(i.status, "?")
        bar_c = self._BAR_COLOR.get(i.status, BORDER)

        self.icon_lbl.configure(text=icon, text_color=color)
        self.title_lbl.configure(text=i.title[:72])
        self.bar.set(i.progress)
        self.bar.configure(progress_color=bar_c)

        if i.status == "downloading":
            parts = [f"{i.progress*100:.1f}%"]
            if i.speed: parts.append(fmt_speed(i.speed))
            if i.eta:   parts.append(f"ETA {fmt_eta(i.eta)}")
            self.info_lbl.configure(text="  ".join(parts), text_color=ACCENT)
            self.cookie_btn.grid_remove()
        elif i.status == "done":
            size = f"  {fmt_bytes(i.total)}" if i.total else ""
            self.info_lbl.configure(text=f"Done{size}", text_color=SUCCESS)
            self.cookie_btn.grid_remove()
        elif i.status == "error":
            self.info_lbl.configure(text=f"Error: {i.error}", text_color=ERROR)
            if "Sign in to confirm" in i.error or "not a bot" in i.error:
                self.cookie_btn.grid()
            else:
                self.cookie_btn.grid_remove()
        else:
            self.info_lbl.configure(text=f"Queued · {i.added}", text_color=TEXT_DIM)
            self.cookie_btn.grid_remove()

    def _retry_with_cookies(self):
        browser = get_default_browser()
        self.item.opts["cookiesfrombrowser"] = (browser, None, None, None)
        self.item.status   = "queued"
        self.item.progress = 0.0
        self.item.speed    = 0.0
        self.item.eta      = 0
        self.item.error    = ""
        self.update_ui()
        self.app._tabs["queue"].refresh()
        if self.app.active is None:
            self.app._next()

    def _remove(self):
        if self.item.status == "downloading":
            return
        if self.item in self.app.queue:
            self.app.queue.remove(self.item)
        self.app._tabs["queue"].refresh()


# ── Convert Tab ───────────────────────────────────────────────────────────────
class ConvertTab(ctk.CTkFrame):
    def __init__(self, parent, app: Vortex):
        super().__init__(parent, fg_color=BG, corner_radius=0)
        self.app = app
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        self._build()

    def _build(self):
        # Header
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=32, pady=(30, 0))
        lbl(hdr, "Convert", size=28, weight="bold").pack(side="left")
        lbl(hdr, "Convert and process media files with ffmpeg", size=13, color=TEXT_DIM).pack(
            side="left", padx=(14, 0), pady=(10, 0)
        )

        # Main card
        c = card(self)
        c.grid(row=1, column=0, padx=32, pady=(20, 0), sticky="ew")
        c.grid_columnconfigure(0, weight=1)

        # File rows helper
        def file_row(parent, row, label_text, placeholder, attr, browse_fn):
            lbl(parent, label_text, size=11, weight="bold", color=TEXT_DIM).grid(
                row=row*2, column=0, padx=22, pady=(18 if row == 0 else 4, 4), sticky="w"
            )
            fr = ctk.CTkFrame(parent, fg_color="transparent")
            fr.grid(row=row*2+1, column=0, padx=22, pady=(0, 4), sticky="ew")
            fr.grid_columnconfigure(0, weight=1)
            entry = fancy_entry(fr, placeholder, height=44)
            entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))
            ghost_btn(fr, "Browse", browse_fn, width=88, height=44).grid(row=0, column=1)
            setattr(self, attr, entry)

        file_row(c, 0, "Input File",  "Select a file...",        "in_entry",  self._browse_in)
        file_row(c, 1, "Output File", "Output path (auto-filled)","out_entry", self._browse_out)

        # Options row
        opts = ctk.CTkFrame(c, fg_color="transparent")
        opts.grid(row=4, column=0, padx=22, pady=(8, 12), sticky="ew")

        self.fmt_var    = ctk.StringVar(value="MP4")
        self.vcodec_var = ctk.StringVar(value="Copy")
        self.acodec_var = ctk.StringVar(value="Copy")
        self.crf_var    = ctk.StringVar(value="Auto")

        def opt_col(parent, label_text, var, values, width, on_change=None):
            col = ctk.CTkFrame(parent, fg_color="transparent")
            lbl(col, label_text, size=11, weight="bold", color=TEXT_DIM).pack(anchor="w", pady=(0, 5))
            dropdown(col, values, width=width, variable=var, command=on_change).pack()
            return col

        fmt_col = opt_col(opts, "Format", self.fmt_var,
                          ["MP4","MKV","MOV","AVI","WEBM","MP3","M4A","FLAC","WAV"], 100,
                          on_change=self._on_fmt_change)
        fmt_col.grid(row=0, column=0, padx=(0, 22), sticky="w")

        self.vcodec_col = opt_col(opts, "Video Codec", self.vcodec_var,
                                  ["Copy","H.264","H.265","VP9","AV1"], 120)
        self.vcodec_col.grid(row=0, column=1, padx=(0, 22), sticky="w")

        acodec_col = opt_col(opts, "Audio Codec", self.acodec_var,
                             ["Copy","AAC","MP3","FLAC","Opus"], 110)
        acodec_col.grid(row=0, column=2, padx=(0, 22), sticky="w")

        self.crf_col = opt_col(opts, "Quality (CRF)", self.crf_var,
                               ["Auto","18","20","23","26","28","32"], 110)
        self.crf_col.grid(row=0, column=3, padx=(0, 22), sticky="w")

        # Trim row
        trim = ctk.CTkFrame(c, fg_color=SURFACE, corner_radius=10)
        trim.grid(row=5, column=0, padx=22, pady=(0, 14), sticky="ew")

        lbl(trim, "Trim  (optional)", size=11, weight="bold", color=TEXT_DIM).grid(
            row=0, column=0, padx=14, pady=(10, 5), columnspan=4, sticky="w"
        )
        for col_i, (txt, attr) in enumerate([("Start", "trim_start"), ("End", "trim_end")]):
            lbl(trim, txt, size=11, color=TEXT_DIM).grid(row=1, column=col_i*2, padx=(14 if col_i==0 else 14, 6), pady=(0, 10), sticky="w")
            entry = ctk.CTkEntry(
                trim, placeholder_text="00:00:00",
                width=108, height=36, corner_radius=8,
                border_color=BORDER, fg_color=CARD,
                text_color=TEXT, font=ctk.CTkFont(size=12),
            )
            entry.grid(row=1, column=col_i*2+1, padx=(0, 14 if col_i==1 else 0), pady=(0, 10))
            setattr(self, attr, entry)

        # Convert button
        accent_btn(c, "  ⇄  Convert", self._convert, width=190, height=54).grid(
            row=6, column=0, padx=22, pady=(4, 22), sticky="w"
        )

        # Progress
        self.prog_card = card(self)
        self.prog_card.grid(row=2, column=0, padx=32, pady=(16, 24), sticky="nsew")
        self.prog_card.grid_columnconfigure(0, weight=1)

        ph = ctk.CTkFrame(self.prog_card, fg_color="transparent")
        ph.grid(row=0, column=0, padx=22, pady=(18, 10), sticky="ew")
        ph.grid_columnconfigure(1, weight=1)
        lbl(ph, "Progress", size=13, weight="bold").grid(row=0, column=0, sticky="w")
        self.conv_status = lbl(ph, "Idle", size=12, color=TEXT_DIM)
        self.conv_status.grid(row=0, column=1, sticky="e")

        self.conv_bar = progress_bar(self.prog_card)
        self.conv_bar.grid(row=1, column=0, padx=22, pady=(0, 18), sticky="ew")

        # Set initial visibility based on default format
        self._on_fmt_change(self.fmt_var.get())

    # Output formats that are audio-only (no video stream)
    AUDIO_FORMATS = {"MP3", "M4A", "FLAC", "WAV"}

    def _on_fmt_change(self, value: str):
        is_audio = value in self.AUDIO_FORMATS
        if is_audio:
            self.vcodec_col.grid_remove()
            self.crf_col.grid_remove()
        else:
            self.vcodec_col.grid()
            self.crf_col.grid()

    def _browse_in(self):
        path = filedialog.askopenfilename(
            filetypes=[("Media files", "*.mp4 *.mkv *.mov *.avi *.webm *.mp3 *.m4a *.flac *.wav *.ts *.ogg"), ("All", "*.*")]
        )
        if path:
            self.in_entry.delete(0, "end")
            self.in_entry.insert(0, path)
            p = Path(path)
            ext = self.fmt_var.get().lower()
            self.out_entry.delete(0, "end")
            self.out_entry.insert(0, str(p.with_suffix(f".out.{ext}")))

    def _browse_out(self):
        path = filedialog.asksaveasfilename()
        if path:
            self.out_entry.delete(0, "end")
            self.out_entry.insert(0, path)

    def _convert(self):
        inp = self.in_entry.get().strip()
        out = self.out_entry.get().strip()
        if not inp:
            messagebox.showwarning("No Input", "Select an input file first.")
            return
        if not out:
            p   = Path(inp)
            out = str(p.with_suffix(f".out.{self.fmt_var.get().lower()}"))
            self.out_entry.insert(0, out)
        threading.Thread(target=self._run, args=(inp, out), daemon=True).start()

    def _run(self, inp: str, out: str):
        self.after(0, lambda: self.conv_status.configure(text="Starting...", text_color=ACCENT))
        self.after(0, lambda: self.conv_bar.set(0))

        ffmpeg = find_ffmpeg(self.app.settings.get("ffmpeg_path", ""))
        cmd    = [ffmpeg, "-i", inp]

        start = self.trim_start.get().strip()
        end   = self.trim_end.get().strip()
        if start: cmd += ["-ss", start]
        if end:   cmd += ["-to", end]

        vc_map = {"H.264": "libx264", "H.265": "libx265", "VP9": "libvpx-vp9", "AV1": "libaom-av1"}
        ac_map = {"AAC": "aac", "MP3": "libmp3lame", "FLAC": "flac", "Opus": "libopus"}

        vc = self.vcodec_var.get()
        ac = self.acodec_var.get()
        is_audio_out = self.fmt_var.get() in self.AUDIO_FORMATS

        if is_audio_out:
            # Audio-only output: strip video, no codec/CRF flags apply
            cmd += ["-vn"]
        else:
            cmd += ["-c:v", "copy" if vc == "Copy" else vc_map.get(vc, vc)]
            if vc != "Copy" and self.crf_var.get() != "Auto":
                cmd += ["-crf", self.crf_var.get()]

        cmd += ["-c:a", "copy" if ac == "Copy" else ac_map.get(ac, ac)]
        cmd += ["-progress", "pipe:1", "-y", out]

        duration = self._probe_duration(inp)

        try:
            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                **SUBPROCESS_FLAGS,
            )
            # Drain stderr on a background thread to prevent buffer deadlock
            stderr_buf: list[str] = []
            threading.Thread(target=lambda: [stderr_buf.append(l) for l in proc.stderr], daemon=True).start()

            for line in proc.stdout:
                if line.startswith("out_time_ms="):
                    try:
                        ms  = int(line.split("=")[1])
                        pct = min(ms / (duration * 1_000_000), 1.0) if duration else 0
                        self.after(0, lambda p=pct: self.conv_bar.set(p))
                        self.after(0, lambda p=pct: self.conv_status.configure(
                            text=f"{p*100:.1f}%", text_color=ACCENT
                        ))
                    except (ValueError, ZeroDivisionError):
                        pass

            proc.wait()
            if proc.returncode == 0:
                self.after(0, lambda: self.conv_bar.set(1.0))
                self.after(0, lambda: self.conv_status.configure(text="Done!", text_color=SUCCESS))
            else:
                err = "".join(stderr_buf[-5:])
                self.after(0, lambda e=err: self.conv_status.configure(
                    text=f"ffmpeg error — check terminal", text_color=ERROR
                ))
                print(err)
        except FileNotFoundError:
            self.after(0, lambda: self.conv_status.configure(
                text="ffmpeg not found. Set path in Settings.", text_color=ERROR
            ))
        except Exception as e:
            self.after(0, lambda: self.conv_status.configure(text=str(e), text_color=ERROR))

    def _probe_duration(self, path: str) -> float:
        """Get media duration in seconds by parsing ffmpeg's stderr.

        ffmpeg without an output file exits with code 1 ('At least one output
        file must be specified') but still prints media info to stderr first.
        That avoids a dependency on a separate ffprobe binary.
        """
        try:
            ffmpeg = find_ffmpeg(self.app.settings.get("ffmpeg_path", ""))
            r = subprocess.run(
                [ffmpeg, "-i", path],
                capture_output=True, text=True, timeout=10,
                **SUBPROCESS_FLAGS,
            )
            m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", r.stderr)
            if m:
                h, mn, s = int(m.group(1)), int(m.group(2)), float(m.group(3))
                return h * 3600 + mn * 60 + s
        except Exception:
            pass
        return 0.0


# ── Settings Tab ──────────────────────────────────────────────────────────────
class SettingsTab(ctk.CTkFrame):
    def __init__(self, parent, app: Vortex):
        super().__init__(parent, fg_color=BG, corner_radius=0)
        self.app = app
        self.grid_columnconfigure(0, weight=1)
        self._build()

    def _build(self):
        lbl(self, "Settings", size=28, weight="bold").grid(
            row=0, column=0, sticky="w", padx=32, pady=(30, 20)
        )

        c = card(self)
        c.grid(row=1, column=0, padx=32, sticky="ew")
        c.grid_columnconfigure(0, weight=1)

        self._entries: dict[str, ctk.CTkEntry] = {}

        fields = [
            ("Download Directory",   "download_dir",         "Where downloaded files are saved"),
            ("Default Audio Format", "default_audio_format", "mp3  m4a  flac  wav  opus"),
            ("ffmpeg Path",          "ffmpeg_path",          "Full path or just 'ffmpeg' if it's in your PATH"),
        ]

        for row, (label_text, key, hint) in enumerate(fields):
            fr = ctk.CTkFrame(c, fg_color="transparent")
            fr.grid(row=row, column=0, padx=22, pady=(20 if row == 0 else 10, 4), sticky="ew")
            fr.grid_columnconfigure(1, weight=1)

            info = ctk.CTkFrame(fr, fg_color="transparent")
            info.grid(row=0, column=0, sticky="w", padx=(0, 20))
            lbl(info, label_text, size=13, weight="bold").pack(anchor="w")
            lbl(info, hint, size=11, color=TEXT_DIM).pack(anchor="w")

            entry = fancy_entry(fr, height=40)
            entry.insert(0, str(self.app.settings.get(key, "")))
            entry.grid(row=0, column=1, sticky="ew")
            self._entries[key] = entry

            if key == "download_dir":
                ghost_btn(fr, "...", lambda e=entry: self._browse(e), width=36, height=40).grid(
                    row=0, column=2, padx=(8, 0)
                )

        # Checkboxes
        cb = ctk.CTkFrame(c, fg_color="transparent")
        cb.grid(row=len(fields), column=0, padx=22, pady=(12, 22), sticky="ew")

        self._checks: dict[str, ctk.BooleanVar] = {}
        for key, label_text in [
            ("embed_subs",      "Embed subtitles by default"),
            ("embed_thumbnail", "Embed thumbnail by default"),
            ("keep_video",      "Keep video when extracting audio"),
        ]:
            var = ctk.BooleanVar(value=bool(self.app.settings.get(key, False)))
            self._checks[key] = var
            checkbox(cb, label_text, var).pack(side="left", padx=(0, 28))

        # Save button + confirmation
        accent_btn(self, "Save Settings", self._save, width=160, height=46).grid(
            row=2, column=0, padx=32, pady=(18, 0), sticky="w"
        )
        self.saved_lbl = lbl(self, "", size=12, color=SUCCESS)
        self.saved_lbl.grid(row=3, column=0, padx=32, pady=(8, 0), sticky="w")

    def _browse(self, entry: ctk.CTkEntry):
        d = filedialog.askdirectory()
        if d:
            entry.delete(0, "end")
            entry.insert(0, d)

    def _save(self):
        for key, entry in self._entries.items():
            self.app.settings[key] = entry.get().strip()
        for key, var in self._checks.items():
            self.app.settings[key] = var.get()
        save_settings(self.app.settings)
        self.saved_lbl.configure(text="✓ Saved")
        self.after(3000, lambda: self.saved_lbl.configure(text=""))


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = Vortex()
    app.mainloop()
