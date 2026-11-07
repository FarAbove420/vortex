"""The main window: sidebar, tabs, download queue."""
import sys
import threading
import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk

from .. import __version__, history, updater
from ..config import load_settings, log, resource_path, TEXT_SIZES
from ..media import Item, run_download
from ..system import notify, open_url, cookie_browser, acquire_single_instance
from ..ytdl import YT_DLP_OK, YT_DLP_VERSION
from .theme import (BG, SURFACE, CARD_HOVER, ACCENT, ACCENT_LT, TEXT, TEXT_DIM, SUCCESS, WARNING, BORDER, WHITE, hide)
from .home_tab import HomeTab
from .queue_tab import QueueTab
from .history_tab import HistoryTab
from .download_tab import DownloadTab
from .convert_tab import ConvertTab
from .settings_tab import SettingsTab
from . import scrolling

NAV = [
    ("home",     "  ⌂   Home",      False),
    ("queue",    "  ☰   Queue",     False),
    ("history",  "  ⟲   History",   False),
    ("download", "  ↓   Download",  True),    # advanced
    ("convert",  "  ⇄   Convert",   True),    # advanced
    ("settings", "  ⚙   Settings",  False),
]


class Vortex(ctk.CTk):
    def __init__(self):
        self.settings = load_settings()
        ctk.set_widget_scaling(TEXT_SIZES.get(self.settings.get("text_size"), 1.0))
        super().__init__()
        self.title("Vortex")
        self.geometry("1240x800")
        self.minsize(1000, 660)
        self.configure(fg_color=BG)
        self._set_icon()

        self.queue: list[Item] = []
        self.active: Item | None = None
        self._messages: list[tuple] = []   # from the updater thread, shown by _tick
        self._release_url = ""

        self._build()
        self.apply_settings()
        self._nav("home")
        self._tick()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.bind("<FocusIn>", self._on_focus, add="+")
        self.after(600, self._tabs["home"].check_clipboard)

        if YT_DLP_OK and self.settings.get("auto_update", True):
            updater.check_in_background(YT_DLP_VERSION, __version__,
                                        lambda *m: self._messages.append(m))

    def _set_icon(self):
        try:
            if sys.platform == "win32":
                # Also stops CustomTkinter from swapping in its own icon
                self.iconbitmap(str(resource_path("assets/Vortex.ico")))
            else:
                self._icon_img = tk.PhotoImage(file=str(resource_path("assets/icon.png")))
                self.iconphoto(True, self._icon_img)
        except Exception as e:
            log.warning("Could not set window icon: %s", e)

    # ── Layout ────────────────────────────────────────────────────────────────
    def _build(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._sidebar()
        self._content()
        scrolling.install(self)   # after all tabs exist: replaces their wheel handler

    def _sidebar(self):
        sb = ctk.CTkFrame(self, width=230, corner_radius=0, fg_color=SURFACE)
        sb.grid(row=0, column=0, sticky="nsew")
        sb.grid_propagate(False)
        sb.grid_columnconfigure(0, weight=1)
        sb.grid_rowconfigure(len(NAV) + 2, weight=1)

        logo_wrap = ctk.CTkFrame(sb, fg_color="transparent", height=88)
        logo_wrap.grid(row=0, column=0, sticky="ew")
        logo_wrap.grid_propagate(False)
        logo = ctk.CTkFrame(logo_wrap, fg_color="transparent")
        logo.place(relx=0.5, rely=0.56, anchor="center")
        try:
            # Plain Tk image: CustomTkinter's CTkImage needs Pillow, which the
            # app doesn't bundle. Made by assets/make_icon.py.
            self._logo_img = tk.PhotoImage(file=str(resource_path("assets/logo-40.png")))
            tk.Label(logo, image=self._logo_img, bg=SURFACE, bd=0).pack(side="left", padx=(0, 10))
        except Exception as e:
            log.warning("Could not load logo: %s", e)
        ctk.CTkLabel(logo, text="Vortex", font=ctk.CTkFont(size=26, weight="bold"),
                     text_color=TEXT).pack(side="left")
        ctk.CTkFrame(sb, height=1, fg_color=BORDER).grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 10))

        self._nav_btns: dict[str, ctk.CTkButton] = {}
        for i, (key, label, _adv) in enumerate(NAV):
            btn = ctk.CTkButton(
                sb, text=label, anchor="w", height=46, corner_radius=10, border_spacing=10,
                font=ctk.CTkFont(size=13), fg_color="transparent", hover_color=CARD_HOVER,
                text_color=TEXT_DIM, command=lambda k=key: self._nav(k))
            btn.grid(row=i + 2, column=0, padx=12, pady=2, sticky="ew")
            self._nav_btns[key] = btn

        self._status_lbl = ctk.CTkLabel(sb, text="● Ready", font=ctk.CTkFont(size=11), text_color=SUCCESS)
        self._status_lbl.grid(row=len(NAV) + 3, column=0, padx=20, pady=(0, 4), sticky="w")

        # Versions, so it's always clear which build is running. Update
        # messages show here too; a new Vortex release is clickable.
        self._version_lbl = ctk.CTkLabel(
            sb, text=f"Vortex {__version__}\nyt-dlp {YT_DLP_VERSION}", justify="left", anchor="w",
            wraplength=190, font=ctk.CTkFont(size=10), text_color=TEXT_DIM)
        self._version_lbl.grid(row=len(NAV) + 4, column=0, padx=20, pady=(0, 18), sticky="w")
        self._version_lbl.bind("<Button-1>", lambda e: self._release_url and open_url(self._release_url))

    def _content(self):
        cf = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        cf.grid(row=0, column=1, sticky="nsew")
        cf.grid_columnconfigure(0, weight=1)
        cf.grid_rowconfigure(0, weight=1)
        self._tabs = {
            "home":     HomeTab(cf, self),
            "queue":    QueueTab(cf, self),
            "history":  HistoryTab(cf, self),
            "download": DownloadTab(cf, self),
            "convert":  ConvertTab(cf, self),
            "settings": SettingsTab(cf, self),
        }
        for t in self._tabs.values():
            t.grid(row=0, column=0, sticky="nsew")

    def _nav(self, key: str):
        for k, btn in self._nav_btns.items():
            if k == key:
                btn.configure(fg_color=ACCENT, text_color=WHITE, hover_color=ACCENT_LT,
                              font=ctk.CTkFont(size=13, weight="bold"))
            else:
                btn.configure(fg_color="transparent", text_color=TEXT_DIM,
                              hover_color=CARD_HOVER, font=ctk.CTkFont(size=13))
        if key == "history":
            self._tabs["history"].refresh()
        self._tabs[key].tkraise()

    def apply_settings(self):
        """Apply saved settings everywhere (called at start and after Save).

        Text size is only applied at startup: changing CustomTkinter's scaling
        while the window is open re-lays out every widget."""
        show_adv = bool(self.settings.get("show_advanced"))
        for i, (key, _label, advanced) in enumerate(NAV):
            if advanced and not show_adv:
                hide(self._nav_btns[key])
            else:
                self._nav_btns[key].grid()
        self._tabs["download"].apply_settings()
        self._tabs["home"].refresh_labels()

    def set_status(self, text: str, color: str = SUCCESS):
        self._status_lbl.configure(text=f"● {text}", text_color=color)

    def _on_focus(self, event):
        if event.widget is self:
            self._tabs["home"].check_clipboard()

    def _on_close(self):
        busy = [i for i in self.queue if i.status in ("downloading", "queued")]
        if busy and not messagebox.askyesno(
                "Quit Vortex?",
                f"{len(busy)} download{'s are' if len(busy) > 1 else ' is'} not finished yet. "
                "Quit anyway? Unfinished downloads are lost."):
            return
        self.destroy()

    # ── Queue management ───────────────────────────────────────────────────────
    # The download thread only updates its Item. Everything that touches the
    # UI or self.active happens here on the main thread, in _tick().
    def enqueue(self, item: Item):
        self.queue.append(item)
        self._tabs["queue"].refresh()
        if self.active is None:
            self._next()

    def retry_with_cookies(self, item: Item):
        item.opts["cookiesfrombrowser"] = (cookie_browser(), None, None, None)
        item.info = None   # fetch again, now with cookies
        item.cancel_requested = False
        item.progress, item.speed, item.eta, item.error = 0.0, 0.0, 0, ""
        item.status = "queued"
        self._tabs["queue"].refresh()
        if self.active is None:
            self._next()

    def _finished(self, item: Item):
        history.add(item.title, item.url, item.filepath, item.status)
        if item.status == "done" and self.settings.get("notify", True) and self.focus_displayof() is None:
            notify(self, "Download finished", item.title)

    def _tick(self):
        if self.active is not None:
            if self.active.status != "downloading":
                self._finished(self.active)
                self.active = None
                self._tabs["queue"].refresh()
                self._next()
            else:
                self._tabs["queue"].refresh()
        while self._messages:
            kind, text, data = self._messages.pop(0)
            if kind == "vortex":
                self._release_url = updater.vortex_release_url(data)
                self._version_lbl.configure(cursor="hand2")
            self._version_lbl.configure(text=f"Vortex {__version__}\n{text}", text_color=ACCENT_LT)
        self.after(250, self._tick)

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
        threading.Thread(target=run_download, args=(item, self.settings.get("ffmpeg_path", "")),
                         daemon=True).start()


def run():
    if not acquire_single_instance():
        root = tk.Tk()
        root.withdraw()
        messagebox.showinfo("Vortex", "Vortex is already open.")
        root.destroy()
        return
    log.info("Vortex %s starting (yt-dlp %s)", __version__, YT_DLP_VERSION)
    app = Vortex()
    app.mainloop()
