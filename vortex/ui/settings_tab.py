"""Settings tab."""
from tkinter import filedialog, messagebox

import customtkinter as ctk

from .. import updater
from ..config import save_settings, TEXT_SIZES
from ..media import AUDIO_LABELS, key_for
from ..ytdl import YT_DLP_VERSION, using_downloaded
from .theme import (BG, CARD_HOVER, TEXT_DIM, SUCCESS, BORDER, lbl, card, fancy_entry, dropdown, ghost_btn, accent_btn, checkbox)


class SettingsTab(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color=BG, corner_radius=0)
        self.app = app
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._build()

    # ── Layout helpers ────────────────────────────────────────────────────────
    def _section(self, title: str):
        lbl(self.body, title, size=15, weight="bold").pack(anchor="w", pady=(18, 6))
        c = card(self.body)
        c.pack(fill="x")
        c.grid_columnconfigure(0, minsize=320)   # same label width in every section
        c.grid_columnconfigure(1, weight=1)
        return c

    def _row(self, c, row, title, hint=""):
        info = ctk.CTkFrame(c, fg_color="transparent")
        info.grid(row=row, column=0, sticky="w", padx=(22, 20), pady=(14 if row == 0 else 6, 6))
        lbl(info, title, size=13, weight="bold").pack(anchor="w")
        if hint:
            lbl(info, hint, size=11, color=TEXT_DIM).pack(anchor="w")

    def _check(self, c, row, key, text):
        var = ctk.BooleanVar(value=bool(self.app.settings.get(key)))
        self._checks[key] = var
        checkbox(c, text, var).grid(row=row, column=0, columnspan=3, sticky="w", padx=22, pady=6)

    # ── Build ─────────────────────────────────────────────────────────────────
    def _build(self):
        lbl(self, "Settings", size=28, weight="bold").grid(
            row=0, column=0, sticky="w", padx=32, pady=(30, 4))

        self.body = ctk.CTkScrollableFrame(self, fg_color=BG, scrollbar_button_color=BORDER,
                                           scrollbar_button_hover_color=CARD_HOVER)
        self.body.grid(row=1, column=0, sticky="nsew", padx=24, pady=(0, 8))
        s = self.app.settings
        self._checks: dict[str, ctk.BooleanVar] = {}

        # Downloads
        c = self._section("Downloads")
        self._row(c, 0, "Save to", "Where downloads go")
        self.dir_entry = fancy_entry(c, height=40)
        self.dir_entry.insert(0, s.get("download_dir", ""))
        self.dir_entry.grid(row=0, column=1, sticky="ew", pady=(14, 6))
        ghost_btn(c, "...", self._browse, width=40, height=40).grid(row=0, column=2, padx=(8, 22), pady=(14, 6))

        self._row(c, 1, "Song format", "Used by the Song button and as the advanced default")
        afmt = str(s.get("default_audio_format", "mp3")).upper()
        self.afmt_var = ctk.StringVar(value=AUDIO_LABELS.get(afmt, AUDIO_LABELS["MP3"]))
        dropdown(c, list(AUDIO_LABELS.values()), width=300, variable=self.afmt_var).grid(row=1, column=1, sticky="w")
        self._check(c, 2, "embed_thumbnail", "Add cover art and the video thumbnail to files")
        self._check(c, 3, "prefer_mp4", "Prefer MP4 for videos, so they play on any device")
        self._check(c, 4, "embed_subs", "Embed subtitles in videos (advanced tab)")
        ctk.CTkFrame(c, height=8, fg_color="transparent").grid(row=5, column=0)

        # App
        c = self._section("App")
        self._row(c, 0, "Text size")
        self.size_var = ctk.StringVar(value=s.get("text_size", "Normal"))
        dropdown(c, list(TEXT_SIZES), width=120, variable=self.size_var).grid(row=0, column=1, sticky="w", pady=(14, 6))
        self._check(c, 1, "show_advanced", "Show the Advanced tab (every quality, format and yt-dlp option)")
        self._check(c, 2, "notify", "Notify me when a download finishes in the background")
        ctk.CTkFrame(c, height=8, fg_color="transparent").grid(row=3, column=0)

        # Updates
        c = self._section("Updates")
        state = updater.read_state()
        where = "downloaded update" if using_downloaded() else "built into the app"
        self._row(c, 0, f"yt-dlp {YT_DLP_VERSION}", f"Running the copy {where}")
        self._check(c, 1, "auto_update", "Keep yt-dlp and Deno up to date automatically")
        self.builtin_var = ctk.BooleanVar(value=bool(state.get("use_builtin")))
        checkbox(c, "Always use the yt-dlp built into the app", self.builtin_var).grid(
            row=2, column=0, columnspan=3, sticky="w", padx=22, pady=6)
        if using_downloaded():
            ghost_btn(c, "Undo the last yt-dlp update", self._undo_update, width=220, height=34).grid(
                row=3, column=0, sticky="w", padx=22, pady=(6, 14))
        else:
            ctk.CTkFrame(c, height=8, fg_color="transparent").grid(row=3, column=0)

        # Advanced
        c = self._section("Advanced")
        self._row(c, 0, "FFmpeg path", "Leave as 'ffmpeg' to use the one built into Vortex")
        self.ffmpeg_entry = fancy_entry(c, height=40)
        self.ffmpeg_entry.insert(0, s.get("ffmpeg_path", "ffmpeg"))
        self.ffmpeg_entry.grid(row=0, column=1, columnspan=2, sticky="ew", padx=(0, 22), pady=(14, 14))

        # Save
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=2, column=0, sticky="ew", padx=32, pady=(4, 20))
        accent_btn(bar, "Save Settings", self._save, width=160, height=46).pack(side="left")
        self.saved_lbl = lbl(bar, "", size=12, color=SUCCESS)
        self.saved_lbl.pack(side="left", padx=14)

    # ── Actions ───────────────────────────────────────────────────────────────
    def _browse(self):
        d = filedialog.askdirectory()
        if d:
            self.dir_entry.delete(0, "end")
            self.dir_entry.insert(0, d)

    def _undo_update(self):
        if messagebox.askyesno("Undo yt-dlp update",
                               "Go back to the previous yt-dlp (or the built-in one) "
                               "the next time Vortex starts?"):
            updater.revert_ytdlp()
            self.saved_lbl.configure(text="Restart Vortex to use the previous yt-dlp")

    def _save(self):
        s = self.app.settings
        s["download_dir"] = self.dir_entry.get().strip() or s["download_dir"]
        s["default_audio_format"] = key_for(self.afmt_var.get(), AUDIO_LABELS).lower()
        s["ffmpeg_path"] = self.ffmpeg_entry.get().strip() or "ffmpeg"
        size_changed = s.get("text_size") != self.size_var.get()
        s["text_size"] = self.size_var.get()
        for key, var in self._checks.items():
            s[key] = var.get()
        save_settings(s)
        if bool(updater.read_state().get("use_builtin")) != self.builtin_var.get():
            updater.set_use_builtin(self.builtin_var.get())
            self.saved_lbl.configure(text="✓ Saved. Restart Vortex to switch yt-dlp")
        elif size_changed:
            self.saved_lbl.configure(text="✓ Saved. Restart Vortex to change the text size")
        else:
            self.saved_lbl.configure(text="✓ Saved")
        self.app.apply_settings()
        self.after(4000, lambda: self.saved_lbl.configure(text=""))
