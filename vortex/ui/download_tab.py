"""Advanced download tab: every yt-dlp option the UI offers."""
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from ..media import Item, AUDIO_FORMATS, cli_to_opts, download_args, final_exts
from ..ytdl import YT_DLP_OK
from ..system import open_path
from .theme import (BG, ACCENT, TEXT_DIM, lbl, card, fancy_entry, dropdown, ghost_btn, accent_btn, progress_bar, checkbox, hide)
from .progress import status_text

# ── Download Tab ──────────────────────────────────────────────────────────────
class DownloadTab(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color=BG, corner_radius=0)
        self.app = app
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        self._build()

    def _build(self):
        # ── Header
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=32, pady=(30, 0))
        lbl(hdr, "Download (advanced)", size=28, weight="bold").pack(side="left")
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
                                self.AUDIO_FORMATS, 110)
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
        ghost_btn(dir_row, "↗", self._open_dir, width=36, height=36).grid(row=0, column=2, padx=(8, 0))

        # Checkboxes
        cb_row = ctk.CTkFrame(url_card, fg_color="transparent")
        cb_row.grid(row=2, column=0, padx=22, pady=(0, 14), sticky="ew")

        self.subs_var     = ctk.BooleanVar(value=self.app.settings.get("embed_subs", False))
        self.thumb_var    = ctk.BooleanVar(value=self.app.settings.get("embed_thumbnail", True))
        self.mp4_var      = ctk.BooleanVar(value=self.app.settings.get("prefer_mp4", True))
        self.playlist_var = ctk.BooleanVar(value=False)
        self.sb_var       = ctk.BooleanVar(value=False)

        self.subs_cb     = checkbox(cb_row, "Embed subtitles",   self.subs_var)
        self.thumb_cb    = checkbox(cb_row, "Embed thumbnail / cover", self.thumb_var)
        self.mp4_cb      = checkbox(cb_row, "Prefer MP4 (plays everywhere)", self.mp4_var)
        self.playlist_cb = checkbox(cb_row, "Download playlist", self.playlist_var)
        self.sb_cb       = checkbox(cb_row, "SponsorBlock",      self.sb_var)

        self.subs_cb.grid(    row=0, column=0, padx=(0, 22), sticky="w")
        self.thumb_cb.grid(   row=0, column=1, padx=(0, 22), sticky="w")
        self.playlist_cb.grid(row=0, column=2, padx=(0, 22), sticky="w")
        self.sb_cb.grid(      row=0, column=3, padx=(0, 22), sticky="w")
        self.mp4_cb.grid(     row=0, column=4,               sticky="w")

        # Extra args toggle
        extra_toggle_row = ctk.CTkFrame(url_card, fg_color="transparent")
        extra_toggle_row.grid(row=3, column=0, padx=22, pady=(0, 4), sticky="w")
        self.extra_show_var = ctk.BooleanVar(value=False)
        checkbox(extra_toggle_row, "Use extra args", self.extra_show_var,
                 command=self._toggle_extra_args).pack(anchor="w")

        # Extra args input (hidden by default)
        self.extra_row = ctk.CTkFrame(url_card, fg_color="transparent")
        self.extra_row.grid(row=4, column=0, padx=22, pady=(0, 10), sticky="ew")
        self.extra_row.grid_columnconfigure(1, weight=1)

        lbl(self.extra_row, "Extra args", size=11, weight="bold", color=TEXT_DIM).grid(
            row=0, column=0, padx=(0, 12), sticky="w"
        )
        self.extra_entry = fancy_entry(self.extra_row, "--cookies-from-browser firefox", height=36)
        self.extra_entry.grid(row=0, column=1, sticky="ew")
        hide(self.extra_row)

        # Buttons
        btn_row = ctk.CTkFrame(url_card, fg_color="transparent")
        btn_row.grid(row=5, column=0, padx=22, pady=(8, 22), sticky="ew")

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

        # Make the whole progress card jump to the queue when clicked
        self._make_clickable(self.prog_card, lambda: self.app._nav("queue"))

        # Set initial visibility based on default type
        self._on_type_change(self.type_var.get())

    def _make_clickable(self, widget, command):
        try:
            widget.bind("<Button-1>", lambda e: command(), add="+")
            widget.configure(cursor="hand2")
        except Exception:
            pass
        try:
            for child in widget.winfo_children():
                self._make_clickable(child, command)
        except Exception:
            pass

    # ── Reactivity ────────────────────────────────────────────────────────────
    def _on_type_change(self, value: str):
        is_audio = value == "Audio Only"
        if is_audio:
            hide(self.qual_col)
            self.afmt_col.grid()
            hide(self.subs_cb)
            hide(self.mp4_cb)
        else:
            self.qual_col.grid()
            hide(self.afmt_col)
            self.subs_cb.grid()
            self.mp4_cb.grid()

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

    def _open_dir(self):
        open_path(self.dir_entry.get().strip())

    def _toggle_extra_args(self):
        if self.extra_show_var.get():
            self.extra_row.grid()
        else:
            hide(self.extra_row)

    def apply_settings(self):
        """Pick up changes saved on the Settings tab."""
        s = self.app.settings
        self.dir_entry.delete(0, "end")
        self.dir_entry.insert(0, s.get("download_dir", ""))
        afmt = str(s.get("default_audio_format", "mp3")).upper()
        if afmt in self.AUDIO_FORMATS:
            self.afmt_var.set(afmt)
        self.subs_var.set(bool(s.get("embed_subs", False)))
        self.thumb_var.set(bool(s.get("embed_thumbnail", True)))
        self.mp4_var.set(bool(s.get("prefer_mp4", True)))

    AUDIO_FORMATS = AUDIO_FORMATS

    def _choices(self) -> dict:
        t = self.type_var.get()
        return dict(
            kind=t, quality=self.qual_var.get(), audio_format=self.afmt_var.get(),
            folder=self.dir_entry.get().strip() or self.app.settings["download_dir"],
            embed_thumbnail=self.thumb_var.get(), embed_subs=self.subs_var.get(),
            prefer_mp4=self.mp4_var.get(), playlist=self.playlist_var.get(),
            sponsorblock=self.sb_var.get(),
            extra=self.extra_entry.get().strip() if self.extra_show_var.get() else "",
        )

    def _build_opts(self) -> dict:
        """Raises ValueError when the extra args are invalid."""
        return cli_to_opts(download_args(**self._choices()))

    def _download(self, to_queue=False):
        if not YT_DLP_OK:
            messagebox.showerror("Missing dependency", "yt-dlp is not installed.\nRun: pip install yt-dlp")
            return
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning("No URL", "Please enter a URL.")
            return

        try:
            opts = self._build_opts()
        except ValueError as e:
            messagebox.showerror("Extra args", str(e))
            return

        c = self._choices()
        item = Item(url, opts, exts=final_exts(c["kind"], c["audio_format"], c["prefer_mp4"]))
        self.app.enqueue(item)

        if to_queue:
            self.app._nav("queue")
        else:
            self._tracked = item
            self._track(item)

    _tracked: Item | None = None

    def _track(self, item: Item):
        if item is not self._tracked:
            return  # a newer download took over the progress card
        self.prog_title.configure(text=item.title[:80])
        text, color = status_text(item)
        self.prog_pct.configure(text=text, text_color=color)
        self.prog_bar.set(1.0 if item.status == "done" else item.progress)
        if item.status in ("done", "error", "cancelled"):
            return
        self.after(200, lambda: self._track(item))
