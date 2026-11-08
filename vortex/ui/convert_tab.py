"""Convert tab: change a local file's format, make it smaller, or cut a part.

All FFmpeg work happens in vortex/convert.py on a worker thread; this tab
only reads the choices (main thread) and polls the job for progress.
"""
import threading
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from ..convert import (FORMATS, VIDEO_QUALITY, AUDIO_QUALITY, CODECS, LOSSLESS_NOTE,
                       ConvertChoices, ConvertJob, parse_time, run_convert)
from ..media import find_ffmpeg
from ..system import open_path, reveal_in_folder
from .theme import (BG, SURFACE, ACCENT, TEXT_DIM, SUCCESS, ERROR, WARNING,
                    lbl, card, fancy_entry, dropdown, ghost_btn, accent_btn, progress_bar,
                    checkbox, hide)


def _key_for(label: str, table: dict) -> str:
    return next(k for k, v in table.items() if v[0] == label)


def _minutes(sec: float) -> str:
    sec = int(sec)
    if sec < 60:
        return f"{sec} s"
    if sec < 600:
        return f"{sec // 60} min {sec % 60:02d} s"
    if sec < 3600:
        return f"{round(sec / 60)} min"
    return f"{sec // 3600} h {round(sec % 3600 / 60)} min"


class ConvertTab(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color=BG, corner_radius=0)
        self.app = app
        self.job: ConvertJob | None = None
        self._auto_out = ""   # output path we filled in ourselves, so we may replace it
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._build()

    # ── Layout ────────────────────────────────────────────────────────────────
    def _label(self, parent, row, text, hint=""):
        box = ctk.CTkFrame(parent, fg_color="transparent")
        box.grid(row=row, column=0, sticky="nw", padx=(22, 16), pady=(14, 4))
        lbl(box, text, size=13, weight="bold").pack(anchor="w")
        if hint:
            lbl(box, hint, size=11, color=TEXT_DIM).pack(anchor="w")

    def _build(self):
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=32, pady=(30, 12))
        lbl(hdr, "Convert", size=28, weight="bold").pack(side="left")
        lbl(hdr, "Change a file's format, make it smaller, or cut out a part", size=13,
            color=TEXT_DIM).pack(side="left", padx=(14, 0), pady=(10, 0))

        body = self.body = ctk.CTkScrollableFrame(self, fg_color=BG)
        body.grid(row=1, column=0, sticky="nsew", padx=24, pady=(0, 16))
        body.grid_columnconfigure(0, weight=1)

        c = card(body)
        c.grid(row=0, column=0, sticky="ew")
        c.grid_columnconfigure(1, weight=1)
        c.grid_columnconfigure(0, minsize=200)

        # File
        self._label(c, 0, "File")
        row = ctk.CTkFrame(c, fg_color="transparent")
        row.grid(row=0, column=1, sticky="ew", padx=(0, 22), pady=(14, 4))
        row.grid_columnconfigure(0, weight=1)
        self.in_entry = fancy_entry(row, "Pick a video or audio file", height=40)
        self.in_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        ghost_btn(row, "Browse", self._browse_in, width=88, height=40).grid(row=0, column=1)

        # Format
        self._label(c, 1, "Convert to")
        self.fmt_var = ctk.StringVar(value=FORMATS["MP4"][0])
        dropdown(c, [v[0] for v in FORMATS.values()], width=340, variable=self.fmt_var,
                 command=lambda _v: self._on_change()).grid(row=1, column=1, sticky="w", pady=(14, 4))

        # Quality, with an explanation of the current choice
        self._label(c, 2, "Quality", "Better quality means a bigger file")
        self.vq_var = ctk.StringVar(value=VIDEO_QUALITY["keep"][0])
        self.aq_var = ctk.StringVar(value=AUDIO_QUALITY["standard"][0])
        self.vq_menu = dropdown(c, [v[0] for v in VIDEO_QUALITY.values()], width=340,
                                variable=self.vq_var, command=lambda _v: self._on_change())
        self.aq_menu = dropdown(c, [v[0] for v in AUDIO_QUALITY.values()], width=340,
                                variable=self.aq_var, command=lambda _v: self._on_change())
        self.vq_menu.grid(row=2, column=1, sticky="w", pady=(14, 0))
        self.aq_menu.grid(row=2, column=1, sticky="w", pady=(14, 0))
        self.q_note = lbl(c, "", size=12, color=TEXT_DIM, anchor="w", justify="left", wraplength=560)
        self.q_note.grid(row=3, column=1, sticky="w", padx=(0, 22), pady=(6, 4))

        # More options: codec and trimming
        self.more_var = ctk.BooleanVar(value=False)
        checkbox(c, "More options (video codec, cut out a part)", self.more_var,
                 command=self._on_change).grid(row=4, column=1, sticky="w", pady=(10, 4))
        self.more = ctk.CTkFrame(c, fg_color=SURFACE, corner_radius=10)
        self.more.grid(row=5, column=0, columnspan=2, sticky="ew", padx=22, pady=(4, 6))
        self.more.grid_columnconfigure(1, weight=1)
        codec_lbl = lbl(self.more, "Video codec", size=12, weight="bold")
        codec_lbl.grid(row=0, column=0, sticky="w", padx=14, pady=(12, 0))
        self.codec_var = ctk.StringVar(value=CODECS["auto"][0])
        codec_menu = dropdown(self.more, [v[0] for v in CODECS.values()], width=260, variable=self.codec_var,
                              command=lambda _v: self._on_change())
        codec_menu.grid(row=0, column=1, sticky="w", pady=(12, 0))
        self.codec_note = lbl(self.more, "", size=11, color=TEXT_DIM, anchor="w", justify="left", wraplength=520)
        self.codec_note.grid(row=1, column=1, sticky="w", pady=(4, 6))
        self._codec_widgets = [codec_lbl, codec_menu, self.codec_note]   # only for video
        lbl(self.more, "Cut out a part", size=12, weight="bold").grid(row=2, column=0, sticky="w", padx=14, pady=(6, 12))
        trim = ctk.CTkFrame(self.more, fg_color="transparent")
        trim.grid(row=2, column=1, sticky="w", pady=(6, 12))
        lbl(trim, "from", size=12, color=TEXT_DIM).pack(side="left")
        self.trim_start = fancy_entry(trim, "0:00", height=34, width=90)
        self.trim_start.pack(side="left", padx=8)
        lbl(trim, "to", size=12, color=TEXT_DIM).pack(side="left")
        self.trim_end = fancy_entry(trim, "the end", height=34, width=90)
        self.trim_end.pack(side="left", padx=8)
        lbl(trim, "like 1:30 or 0:01:30", size=11, color=TEXT_DIM).pack(side="left", padx=(6, 0))

        # Output
        self._label(c, 6, "Save as")
        row = ctk.CTkFrame(c, fg_color="transparent")
        row.grid(row=6, column=1, sticky="ew", padx=(0, 22), pady=(14, 4))
        row.grid_columnconfigure(0, weight=1)
        self.out_entry = fancy_entry(row, "Filled in when you pick a file", height=40)
        self.out_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        ghost_btn(row, "Browse", self._browse_out, width=88, height=40).grid(row=0, column=1)

        btns = ctk.CTkFrame(c, fg_color="transparent")
        btns.grid(row=7, column=1, sticky="w", pady=(14, 22))
        self.convert_btn = accent_btn(btns, "  ⇄  Convert", self._convert, width=190, height=50)
        self.convert_btn.pack(side="left")
        self.cancel_btn = ghost_btn(btns, "Cancel", self._cancel, width=100, height=50)

        # Progress
        self.prog = card(body)
        self.prog.grid(row=1, column=0, sticky="ew", pady=(14, 0))
        self.prog.grid_columnconfigure(0, weight=1)
        self.p_title = lbl(self.prog, "", size=13, weight="bold", anchor="w")
        self.p_title.grid(row=0, column=0, sticky="ew", padx=22, pady=(16, 2))
        self.p_what = lbl(self.prog, "", size=12, color=TEXT_DIM, anchor="w", justify="left", wraplength=700)
        self.p_what.grid(row=1, column=0, sticky="ew", padx=22, pady=(0, 8))
        self.p_bar = progress_bar(self.prog)
        self.p_bar.grid(row=2, column=0, sticky="ew", padx=22)
        self.p_status = lbl(self.prog, "", size=12, color=ACCENT, anchor="w", justify="left", wraplength=700)
        self.p_status.grid(row=3, column=0, sticky="ew", padx=22, pady=(8, 2))
        self.p_hint = lbl(self.prog, "", size=11, color=WARNING, anchor="w", justify="left", wraplength=700)
        self.p_hint.grid(row=4, column=0, sticky="ew", padx=22, pady=(0, 16))
        acts = self.acts = ctk.CTkFrame(self.prog, fg_color="transparent")
        acts.grid(row=5, column=0, sticky="w", padx=22, pady=(8, 16))
        hide(acts)   # an empty CTkFrame would keep its default 200 px height
        self.open_btn = ghost_btn(acts, "↗  Open", self._open, width=100, height=32)
        self.folder_btn = ghost_btn(acts, "📂  Show in folder", self._reveal, width=150, height=32)
        hide(self.prog)

        self._on_change()

    # ── Choices ───────────────────────────────────────────────────────────────
    def _fmt(self) -> str:
        return _key_for(self.fmt_var.get(), FORMATS)

    def _on_change(self):
        fmt = self._fmt()
        is_audio = FORMATS[fmt][1] == "audio"
        if is_audio:
            hide(self.vq_menu)
            if fmt in ("MP3", "M4A"):
                self.aq_menu.grid()
                self.q_note.configure(text=AUDIO_QUALITY[_key_for(self.aq_var.get(), AUDIO_QUALITY)][1])
            else:
                hide(self.aq_menu)
                self.q_note.configure(text=LOSSLESS_NOTE)
        else:
            hide(self.aq_menu)
            self.vq_menu.grid()
            self.q_note.configure(text=VIDEO_QUALITY[_key_for(self.vq_var.get(), VIDEO_QUALITY)][1])
        show_codec = self.more_var.get() and not is_audio
        codec = _key_for(self.codec_var.get(), CODECS)
        self.codec_note.configure(text=CODECS[codec][1])
        if self.more_var.get():
            self.more.grid()
        else:
            hide(self.more)
        for w in self._codec_widgets:
            if show_codec:
                w.grid()
            else:
                hide(w)
        # keep an auto-filled output name in step with the format
        if self._auto_out and self.out_entry.get().strip() == self._auto_out:
            self._fill_out(self.in_entry.get().strip())

    def _fill_out(self, inp: str):
        if not inp:
            return
        self._auto_out = str(Path(inp).with_suffix(f".converted.{self._fmt().lower()}"))
        self.out_entry.delete(0, "end")
        self.out_entry.insert(0, self._auto_out)

    def _browse_in(self):
        path = filedialog.askopenfilename(filetypes=[
            ("Video and audio", "*.mp4 *.mkv *.mov *.avi *.webm *.mp3 *.m4a *.flac *.wav *.ts *.ogg *.opus"),
            ("All files", "*.*")])
        if path:
            self.in_entry.delete(0, "end")
            self.in_entry.insert(0, path)
            self._fill_out(path)

    def _browse_out(self):
        path = filedialog.asksaveasfilename(defaultextension=f".{self._fmt().lower()}")
        if path:
            self.out_entry.delete(0, "end")
            self.out_entry.insert(0, path)

    # ── Converting ────────────────────────────────────────────────────────────
    def _convert(self):
        inp = self.in_entry.get().strip()
        if not inp or not Path(inp).is_file():
            messagebox.showwarning("Convert", "Pick a file to convert first.")
            return
        if not self.out_entry.get().strip():
            self._fill_out(inp)
        out = self.out_entry.get().strip()
        if Path(out).resolve() == Path(inp).resolve():
            messagebox.showwarning("Convert", "Save the result under another name than the original.")
            return
        if Path(out).exists() and not messagebox.askyesno("Convert", f"{Path(out).name} already exists. Replace it?"):
            return
        try:
            start = parse_time(self.trim_start.get()) if self.more_var.get() else None
            end = parse_time(self.trim_end.get()) if self.more_var.get() else None
        except ValueError as e:
            messagebox.showwarning("Convert", str(e))
            return
        # Everything the worker needs is read here, on the main thread
        choices = ConvertChoices(
            fmt=self._fmt(),
            video_quality=_key_for(self.vq_var.get(), VIDEO_QUALITY),
            audio_quality=_key_for(self.aq_var.get(), AUDIO_QUALITY),
            codec=_key_for(self.codec_var.get(), CODECS) if self.more_var.get() else "auto",
            start=start, end=end)
        self.job = ConvertJob(inp, out, choices, ffmpeg=find_ffmpeg(self.app.settings.get("ffmpeg_path", "")))
        threading.Thread(target=run_convert, args=(self.job,), daemon=True).start()
        self.convert_btn.configure(state="disabled")
        self.cancel_btn.pack(side="left", padx=(12, 0))
        self.prog.grid()
        self._poll()
        # bring the progress into view
        self.update_idletasks()
        self.body._parent_canvas.yview_moveto(1.0)

    def _cancel(self):
        if self.job:
            self.job.cancel()

    def _poll(self):
        job = self.job
        if job is None:
            return
        self.p_title.configure(text=Path(job.out).name)
        self.p_what.configure(text=job.what)
        self.p_bar.set(job.progress)
        self.p_hint.configure(text="")
        self.open_btn.pack_forget()
        self.folder_btn.pack_forget()
        hide(self.acts)

        if job.status in ("starting", "running"):
            parts = [f"{job.progress * 100:.0f}%"]
            if job.speed:
                parts.append(f"{job.speed:.1f}× real time")
            if job.eta and job.progress > 0.02:
                parts.append(f"about {_minutes(job.eta)} left")
            elif job.elapsed > 3:
                parts.append(f"{_minutes(job.elapsed)} so far")
            self.p_status.configure(text="  ·  ".join(parts) if job.status == "running" else "Starting...",
                                    text_color=ACCENT)
            if job.cancel_requested:
                self.p_status.configure(text="Cancelling...", text_color=TEXT_DIM)
            elif job.speed and job.speed < 1 and "Re-encoding" in job.what:
                self.p_hint.configure(text=(
                    f"Slow: at {job.speed:.1f}× a 10-minute video takes about "
                    f"{_minutes(600 / job.speed)}. Re-encoding is heavy work for the processor. "
                    "\"Keep original\" is much faster, and \"Small file\" has less to write."))
            self.after(250, self._poll)
            return

        self.convert_btn.configure(state="normal")
        self.cancel_btn.pack_forget()
        if job.status == "done":
            size = Path(job.out).stat().st_size if Path(job.out).exists() else 0
            before = Path(job.inp).stat().st_size if Path(job.inp).exists() else 0
            change = ""
            if size and before:
                pct = size / before * 100
                change = f"  ·  {pct:.0f}% of the original size"
            self.p_status.configure(
                text=f"Done in {_minutes(job.elapsed)}  ·  {size / 1024 / 1024:.1f} MB{change}", text_color=SUCCESS)
            self.open_btn.pack(side="left", padx=(0, 8))
            self.folder_btn.pack(side="left")
            self.acts.grid()
        elif job.status == "cancelled":
            self.p_status.configure(text="Cancelled", text_color=TEXT_DIM)
        else:
            self.p_status.configure(text=f"Error: {job.error[:160]}", text_color=ERROR)

    def _open(self):
        if self.job:
            open_path(self.job.out)

    def _reveal(self):
        if self.job:
            reveal_in_folder(self.job.out)
