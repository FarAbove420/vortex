"""History: everything downloaded before, also after a restart."""
from pathlib import Path
from tkinter import messagebox

import customtkinter as ctk

from .. import history
from ..system import open_path, reveal_in_folder
from .theme import (BG, CARD, CARD_HOVER, TEXT_DIM, TEXT_HINT, BORDER, lbl, ghost_btn)

SHOW_MAX = 100


class HistoryTab(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color=BG, corner_radius=0)
        self.app = app
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=32, pady=(30, 14))
        hdr.grid_columnconfigure(1, weight=1)
        lbl(hdr, "History", size=28, weight="bold").grid(row=0, column=0, sticky="w")
        self.count_lbl = lbl(hdr, "", size=13, color=TEXT_DIM)
        self.count_lbl.grid(row=0, column=1, sticky="w", padx=(14, 0))
        ghost_btn(hdr, "Clear history", self._clear, width=120, height=36).grid(row=0, column=2, sticky="e")

        self.scroll = ctk.CTkScrollableFrame(self, fg_color=BG, scrollbar_button_color=BORDER,
                                             scrollbar_button_hover_color=CARD_HOVER)
        self.scroll.grid(row=1, column=0, sticky="nsew", padx=32, pady=(0, 24))
        self.scroll.grid_columnconfigure(0, weight=1)

    def refresh(self):
        for w in self.scroll.winfo_children():
            w.destroy()
        entries = [e for e in history.load() if e.get("status") == "done"]
        self.count_lbl.configure(text=f"{len(entries)} download{'s' if len(entries) != 1 else ''}")
        if not entries:
            lbl(self.scroll, "Nothing downloaded yet.", size=14, color=TEXT_HINT).grid(row=0, column=0, pady=70)
            return
        for i, e in enumerate(entries[:SHOW_MAX]):
            row = ctk.CTkFrame(self.scroll, fg_color=CARD, corner_radius=12, border_width=1, border_color=BORDER)
            row.grid(row=i, column=0, sticky="ew", pady=(0, 8))
            row.grid_columnconfigure(0, weight=1)
            path = e.get("filepath") or ""
            exists = bool(path) and Path(path).exists()
            lbl(row, e.get("title") or e.get("url", ""), size=13, weight="bold", anchor="w").grid(
                row=0, column=0, sticky="ew", padx=16, pady=(10, 0))
            where = Path(path).name if exists else "File moved or deleted"
            lbl(row, f"{e.get('date', '')}  ·  {where}", size=11,
                color=TEXT_DIM if exists else TEXT_HINT, anchor="w").grid(
                row=1, column=0, sticky="ew", padx=16, pady=(0, 10))
            if exists:
                acts = ctk.CTkFrame(row, fg_color="transparent")
                acts.grid(row=0, column=1, rowspan=2, padx=12)
                ghost_btn(acts, "↗  Open", lambda p=path: open_path(p), width=90, height=30).pack(side="left", padx=(0, 6))
                ghost_btn(acts, "📂", lambda p=path: reveal_in_folder(p), width=40, height=30).pack(side="left")

    def _clear(self):
        if messagebox.askyesno("Clear history", "Remove the download history? Your files stay where they are."):
            history.clear()
            self.refresh()
