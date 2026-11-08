"""Home: the simple way in. Paste a link or type a song name, check the
preview, press Song or Video."""
import threading
import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk

from ..config import log
from ..media import (Item, cli_to_opts, download_args, final_exts, fetch_preview, search,
                     looks_like_url, is_supported_site, best_thumbnail_url, thumbnail_png_b64)
from ..system import fmt_duration, open_path, reveal_in_folder
from ..ytdl import YT_DLP_OK
from .theme import (BG, CARD, CARD_HOVER, ACCENT_DK, TEXT_DIM, ERROR, lbl, card, fancy_entry, ghost_btn, accent_btn, progress_bar, hide)
from .progress import status_text


class HomeTab(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color=BG, corner_radius=0)
        self.app = app
        self.preview: dict | None = None   # info of what's shown in the preview
        self.preview_reusable = False      # the download may reuse it
        self.preview_url = ""
        self._thumb_img = None
        self._tracked: Item | None = None
        self._last_clip = ""
        self._lookup_id = 0
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(4, weight=1)
        self._build()

    # ── Layout ────────────────────────────────────────────────────────────────
    def _build(self):
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=32, pady=(30, 0))
        lbl(hdr, "Get a song or video", size=28, weight="bold").pack(side="left")

        # Search / link box
        box = card(self)
        box.grid(row=1, column=0, padx=32, pady=(20, 0), sticky="ew")
        box.grid_columnconfigure(0, weight=1)
        self.entry = fancy_entry(box, "Paste a YouTube link, or type a song name", height=54)
        self.entry.configure(font=ctk.CTkFont(size=15))
        self.entry.grid(row=0, column=0, sticky="ew", padx=(22, 10), pady=22)
        self.entry.bind("<Return>", lambda e: self.find())
        ghost_btn(box, "Paste", self._paste, width=86, height=54).grid(row=0, column=1, pady=22)
        accent_btn(box, "Find", self.find, width=110, height=54).grid(row=0, column=2, padx=(10, 22), pady=22)

        self.hint = lbl(self, "", size=13, color=TEXT_DIM)
        self.hint.grid(row=2, column=0, sticky="w", padx=36, pady=(10, 0))

        # Search results (hidden until a search)
        self.results = card(self)
        self.results.grid(row=3, column=0, padx=32, pady=(12, 0), sticky="ew")
        self.results.grid_columnconfigure(0, weight=1)
        hide(self.results)

        # Preview with the two big buttons (hidden until something is found)
        self.card = card(self)
        self.card.grid(row=3, column=0, padx=32, pady=(12, 0), sticky="ew")
        self.card.grid_columnconfigure(1, weight=1)
        self.thumb = tk.Label(self.card, bg=CARD, bd=0)
        self.thumb.grid(row=0, column=0, rowspan=3, padx=(22, 18), pady=22, sticky="nw")
        self.title_lbl = lbl(self.card, "", size=17, weight="bold", anchor="w", justify="left", wraplength=560)
        self.title_lbl.grid(row=0, column=1, sticky="ew", padx=(0, 22), pady=(22, 2))
        self.meta_lbl = lbl(self.card, "", size=13, color=TEXT_DIM, anchor="w", justify="left")
        self.meta_lbl.grid(row=1, column=1, sticky="nw", padx=(0, 22))
        btns = ctk.CTkFrame(self.card, fg_color="transparent")
        btns.grid(row=2, column=1, sticky="sw", padx=(0, 22), pady=(12, 22))
        self.song_btn = accent_btn(btns, "♪  Song", lambda: self._download("song"), width=190, height=58)
        self.song_btn.configure(font=ctk.CTkFont(size=16, weight="bold"))
        self.song_btn.pack(side="left")
        self.video_btn = accent_btn(btns, "▶  Video", lambda: self._download("video"), width=190, height=58)
        self.video_btn.configure(font=ctk.CTkFont(size=16, weight="bold"), fg_color=ACCENT_DK)
        self.video_btn.pack(side="left", padx=(14, 0))
        hide(self.card)

        # Progress of the last download started here
        self.prog = card(self)
        self.prog.grid(row=4, column=0, padx=32, pady=(16, 8), sticky="new")
        self.prog.grid_columnconfigure(0, weight=1)
        self.prog_title = lbl(self.prog, "", size=13, weight="bold", anchor="w")
        self.prog_title.grid(row=0, column=0, sticky="ew", padx=22, pady=(18, 6))
        self.prog_bar = progress_bar(self.prog)
        self.prog_bar.grid(row=1, column=0, sticky="ew", padx=22)
        self.prog_status = lbl(self.prog, "", size=12, color=TEXT_DIM, anchor="w", wraplength=700, justify="left")
        self.prog_status.grid(row=2, column=0, sticky="ew", padx=22, pady=(8, 6))
        acts = ctk.CTkFrame(self.prog, fg_color="transparent")
        acts.grid(row=3, column=0, sticky="w", padx=22, pady=(0, 16))
        self.open_btn = ghost_btn(acts, "↗  Play / open", self._open, width=140, height=34)
        self.folder_btn = ghost_btn(acts, "📂  Show in folder", self._reveal, width=160, height=34)
        hide(self.prog)

        # Tip at the bottom, only while the Advanced tab is switched off
        self.tip = lbl(self, "Tip: need a specific quality, format or subtitles? Turn on the "
                             "Advanced tab in Settings.", size=12, color=TEXT_DIM, cursor="hand2")
        self.tip.grid(row=5, column=0, sticky="w", padx=36, pady=(0, 20))
        self.tip.bind("<Button-1>", lambda e: self.app._nav("settings"))
        self.refresh_labels()

    def refresh_labels(self):
        """Button labels follow the settings (song format, MP4)."""
        afmt = str(self.app.settings.get("default_audio_format", "mp3")).upper()
        self.song_btn.configure(text=f"♪  Song ({afmt})")
        self.video_btn.configure(text="▶  Video (MP4)" if self.app.settings.get("prefer_mp4", True) else "▶  Video")
        if self.app.settings.get("show_advanced"):
            hide(self.tip)
        else:
            self.tip.grid()

    # ── Clipboard ─────────────────────────────────────────────────────────────
    def check_clipboard(self):
        """Called when the window gets focus: a fresh link on the clipboard is
        filled in and looked up, so it's one click from there. Only for sites
        yt-dlp supports: other links (a web page, a GitHub link) are ignored
        instead of showing "Unsupported URL"."""
        try:
            clip = self.clipboard_get().strip()
        except Exception:
            return
        if not looks_like_url(clip) or clip == self._last_clip:
            return
        self._last_clip = clip
        if not is_supported_site(clip):
            return
        current = self.entry.get().strip()
        if current and current != self.preview_url:
            return  # don't overwrite something the user is typing
        self.entry.delete(0, "end")
        self.entry.insert(0, clip)
        self.find()

    def _paste(self):
        try:
            text = self.clipboard_get().strip()
        except Exception:
            return
        self.entry.delete(0, "end")
        self.entry.insert(0, text)
        self.find()

    # ── Looking things up (on a thread, results polled on the main thread) ────
    def _in_background(self, func, done):
        self._lookup_id += 1
        my_id = self._lookup_id
        box = {}

        def run():
            try:
                box["result"] = func()
            except Exception as e:
                box["error"] = e

        t = threading.Thread(target=run, daemon=True)
        t.start()

        def poll():
            if my_id != self._lookup_id:
                return  # a newer lookup replaced this one
            if t.is_alive():
                self.after(100, poll)
            else:
                done(box.get("result"), box.get("error"))
        poll()

    def find(self):
        if not YT_DLP_OK:
            messagebox.showerror("Missing yt-dlp", "yt-dlp is not available.")
            return
        text = self.entry.get().strip()
        if not text:
            return
        hide(self.results)
        hide(self.card)
        if looks_like_url(text):
            self._lookup(text)
        else:
            self.hint.configure(text=f"Searching YouTube for “{text}”...", text_color=TEXT_DIM)
            self._in_background(lambda: search(text), self._show_results)

    def _show_results(self, results, error):
        for w in self.results.winfo_children():
            w.destroy()
        if error or not results:
            self.hint.configure(text="Nothing found. Try other words, or paste a link.", text_color=ERROR)
            if error:
                log.warning("Search failed: %s", error)
            return
        self.hint.configure(text="Pick the right one:", text_color=TEXT_DIM)
        for i, r in enumerate(results):
            meta = "  ·  ".join(x for x in (r["channel"], fmt_duration(r["duration"])) if x)
            self._result_row(i, r["title"], meta, r["url"], last=i == len(results) - 1)
        self.results.grid()

    def _result_row(self, i, title, meta, url, last):
        """One clickable search result: title, then channel and length,
        both lined up on the left (a CTkButton centres multi-line text)."""
        row = ctk.CTkFrame(self.results, fg_color="transparent", corner_radius=10, cursor="hand2")
        row.grid(row=i, column=0, sticky="ew", padx=12, pady=(10 if i == 0 else 2, 10 if last else 2))
        t = lbl(row, title, size=13, weight="bold", anchor="w")
        t.pack(fill="x", padx=12, pady=(8, 0))
        m = lbl(row, meta, size=12, color=TEXT_DIM, anchor="w")
        m.pack(fill="x", padx=12, pady=(0, 8))
        for w in (row, t, m):
            w.bind("<Button-1>", lambda e: self._lookup(url))
            w.bind("<Enter>", lambda e: row.configure(fg_color=CARD_HOVER))
            w.bind("<Leave>", lambda e: row.configure(fg_color="transparent"))

    def _lookup(self, url: str):
        hide(self.results)
        hide(self.card)
        self.hint.configure(text="Looking it up...", text_color=TEXT_DIM)
        ffmpeg_path = self.app.settings.get("ffmpeg_path", "")

        def work():
            info, reusable = fetch_preview(url)
            thumb = best_thumbnail_url(info)
            png = thumbnail_png_b64(thumb, 320, ffmpeg_path) if thumb else None
            return info, reusable, png
        self._in_background(work, lambda res, err: self._show_preview(url, res, err))

    def _show_preview(self, url, res, error):
        if error or not res:
            msg = str(error or "Nothing found").replace("ERROR: ", "")
            self.hint.configure(text=f"Couldn't open that link: {msg[:160]}", text_color=ERROR)
            log.warning("Preview failed for %s: %s", url, error)
            return
        info, reusable, png = res
        self.preview, self.preview_url, self.preview_reusable = info, url, reusable
        self.hint.configure(text="")
        if png:
            self._thumb_img = tk.PhotoImage(data=png)
            self.thumb.configure(image=self._thumb_img)
            self.thumb.grid()
        else:
            hide(self.thumb)
        if info.get("_type") == "playlist":
            n = info.get("playlist_count") or len(info.get("entries") or [])
            self.title_lbl.configure(text=info.get("title") or "Playlist")
            self.meta_lbl.configure(text=f"Playlist with {n} videos. The buttons download all of them.")
        else:
            meta = "  ·  ".join(x for x in (info.get("channel") or info.get("uploader") or "",
                                             fmt_duration(info.get("duration"))) if x)
            self.title_lbl.configure(text=info.get("title") or url)
            self.meta_lbl.configure(text=meta)
        self.refresh_labels()
        self.card.grid()

    # ── Downloading ───────────────────────────────────────────────────────────
    def _download(self, what: str):
        if not self.preview:
            return
        s = self.app.settings
        playlist = self.preview.get("_type") == "playlist"
        kind = "Audio Only" if what == "song" else "Video + Audio"
        afmt = s.get("default_audio_format", "mp3")
        args = download_args(kind=kind, quality="Best", audio_format=afmt, folder=s["download_dir"],
                             embed_thumbnail=s.get("embed_thumbnail", True),
                             prefer_mp4=s.get("prefer_mp4", True), playlist=playlist)
        try:
            opts = cli_to_opts(args)
        except ValueError as e:
            messagebox.showerror("Vortex", str(e))
            return
        item = Item(self.preview_url, opts, (self.preview.get("title") or "")[:60],
                    exts=final_exts(kind, afmt, s.get("prefer_mp4", True)),
                    info=self.preview if self.preview_reusable else None)
        self.app.enqueue(item)
        self._tracked = item
        self.prog.grid()
        self._track()

    def _track(self):
        item = self._tracked
        if item is None:
            return
        self.prog_title.configure(text=item.title)
        text, color = status_text(item)
        self.prog_status.configure(text=text, text_color=color)
        self.prog_bar.set(1.0 if item.status == "done" else item.progress)
        self.open_btn.pack_forget()
        self.folder_btn.pack_forget()
        if item.status == "done" and item.filepath:
            self.open_btn.pack(side="left", padx=(0, 8))
            self.folder_btn.pack(side="left")
        if item.status in ("queued", "downloading"):
            self.after(250, self._track)

    def _open(self):
        if self._tracked and self._tracked.filepath:
            open_path(self._tracked.filepath)

    def _reveal(self):
        if self._tracked and self._tracked.filepath:
            reveal_in_folder(self._tracked.filepath)
