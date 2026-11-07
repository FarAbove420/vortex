"""Queue tab and its rows."""
import customtkinter as ctk

from ..media import Item
from ..system import open_path, reveal_in_folder
from .theme import (BG, SURFACE, CARD, CARD_HOVER, ACCENT, TEXT, TEXT_DIM, TEXT_HINT, SUCCESS, ERROR, BORDER, lbl, ghost_btn, hide)
from .progress import status_text

# ── Queue Tab ─────────────────────────────────────────────────────────────────
class QueueTab(ctk.CTkFrame):
    def __init__(self, parent, app):
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
            hide(self.empty_lbl)

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
    _STATUS_COLOR = {"queued": TEXT_DIM, "downloading": ACCENT, "done": SUCCESS, "error": ERROR,
                     "cancelled": TEXT_DIM}
    _STATUS_ICON  = {"queued": "◷", "downloading": "↓", "done": "✓", "error": "✗", "cancelled": "—"}
    _BAR_COLOR    = {"queued": BORDER, "downloading": ACCENT, "done": SUCCESS, "error": ERROR}

    def __init__(self, parent, item: Item, app):
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
        self.info_lbl.grid(row=2, column=1, sticky="w", padx=(0, 12), pady=(0, 8))

        self.action_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.action_frame.grid(row=3, column=1, padx=(0, 12), pady=(0, 10), sticky="w")

        self.cookie_btn = ghost_btn(
            self.action_frame, "↺  Retry with browser cookies", self._retry_with_cookies,
            width=220, height=26
        )
        self.open_btn = ghost_btn(
            self.action_frame, "↗  Open file", self._open_file,
            width=110, height=26
        )
        self.folder_btn = ghost_btn(
            self.action_frame, "📂  Show in folder", self._show_in_folder,
            width=150, height=26
        )

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

        self.cookie_btn.pack_forget()
        self.open_btn.pack_forget()
        self.folder_btn.pack_forget()

        text, tcolor = status_text(i, short_error=False)
        self.info_lbl.configure(text=text, text_color=tcolor)
        has_buttons = True
        if i.status == "done" and i.filepath:
            self.open_btn.pack(side="left", padx=(0, 8))
            self.folder_btn.pack(side="left")
        elif i.status == "error" and ("Sign in to confirm" in i.error or "not a bot" in i.error):
            self.cookie_btn.pack(side="left")
        else:
            has_buttons = False
        # An empty CTkFrame keeps its default 200 px height, so hide it
        if has_buttons:
            self.action_frame.grid()
        else:
            hide(self.action_frame)

    def _open_file(self):
        if self.item.filepath:
            open_path(self.item.filepath)

    def _show_in_folder(self):
        if self.item.filepath:
            reveal_in_folder(self.item.filepath)

    def _retry_with_cookies(self):
        self.app.retry_with_cookies(self.item)
        self.update_ui()

    def _remove(self):
        if self.item.status == "downloading":
            # Stops at the next progress update; _tick() then moves on.
            self.item.cancel_requested = True
            self.update_ui()
            return
        if self.item in self.app.queue:
            self.app.queue.remove(self.item)
        self.app._tabs["queue"].refresh()


