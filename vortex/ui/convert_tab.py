"""Convert tab: ffmpeg conversions of local files."""
import threading
import subprocess
import re
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from ..config import log, SUBPROCESS_FLAGS
from ..media import find_ffmpeg
from .theme import (BG, SURFACE, CARD, ACCENT, TEXT, TEXT_DIM, SUCCESS, ERROR, BORDER, lbl, card, fancy_entry, dropdown, ghost_btn, accent_btn, progress_bar, hide)

# ── Convert Tab ───────────────────────────────────────────────────────────────
class ConvertTab(ctk.CTkFrame):
    def __init__(self, parent, app):
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

        self.acodec_col = opt_col(opts, "Audio Codec", self.acodec_var,
                                  ["Copy","AAC","MP3","FLAC","Opus"], 110)
        self.acodec_col.grid(row=0, column=2, padx=(0, 22), sticky="w")

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
        self.convert_btn = accent_btn(c, "  ⇄  Convert", self._convert, width=190, height=54)
        self.convert_btn.grid(row=6, column=0, padx=22, pady=(4, 22), sticky="w")

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

    # Output formats that are audio-only (no video stream), with the encoder
    # each one needs. The audio stream can't simply be copied into these:
    # an MP4's AAC audio, for example, is not valid inside an .mp3 file.
    AUDIO_FORMATS = {"MP3": "libmp3lame", "M4A": "aac", "FLAC": "flac", "WAV": "pcm_s16le"}

    _auto_out = ""  # output path we filled in ourselves, so we may replace it

    def _on_fmt_change(self, value: str):
        is_audio = value in self.AUDIO_FORMATS
        if is_audio:
            hide(self.vcodec_col)
            hide(self.crf_col)
            hide(self.acodec_col)
        else:
            self.vcodec_col.grid()
            self.crf_col.grid()
            self.acodec_col.grid()
        # Keep an auto-filled output name in step with the chosen format
        if self._auto_out and self.out_entry.get().strip() == self._auto_out:
            self._fill_out(self.in_entry.get().strip())

    def _fill_out(self, inp: str):
        self._auto_out = str(Path(inp).with_suffix(f".out.{self.fmt_var.get().lower()}"))
        self.out_entry.delete(0, "end")
        self.out_entry.insert(0, self._auto_out)

    def _browse_in(self):
        path = filedialog.askopenfilename(
            filetypes=[("Media files", "*.mp4 *.mkv *.mov *.avi *.webm *.mp3 *.m4a *.flac *.wav *.ts *.ogg"), ("All", "*.*")]
        )
        if path:
            self.in_entry.delete(0, "end")
            self.in_entry.insert(0, path)
            self._fill_out(path)

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
            self._fill_out(inp)
            out = self._auto_out
        self.convert_btn.configure(state="disabled")
        threading.Thread(target=self._run, args=(inp, out), daemon=True).start()

    def _run(self, inp: str, out: str):
        try:
            self._run_ffmpeg(inp, out)
        finally:
            self.after(0, lambda: self.convert_btn.configure(state="normal"))

    def _run_ffmpeg(self, inp: str, out: str):
        self.after(0, lambda: self.conv_status.configure(text="Starting...", text_color=ACCENT))
        self.after(0, lambda: self.conv_bar.set(0))

        ffmpeg = find_ffmpeg(self.app.settings.get("ffmpeg_path", ""))
        cmd    = [ffmpeg, "-hide_banner", "-loglevel", "error", "-i", inp]

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
            # Audio-only output: strip video and use the format's own encoder
            cmd += ["-vn", "-c:a", self.AUDIO_FORMATS[self.fmt_var.get()]]
        else:
            cmd += ["-c:v", "copy" if vc == "Copy" else vc_map.get(vc, vc)]
            if vc != "Copy" and self.crf_var.get() != "Auto":
                cmd += ["-crf", self.crf_var.get()]
            cmd += ["-c:a", "copy" if ac == "Copy" else ac_map.get(ac, ac)]

        cmd += ["-progress", "pipe:1", "-y", out]

        duration = self._probe_duration(inp)
        log.info("Convert: %s", subprocess.list2cmdline(cmd))

        try:
            proc = subprocess.Popen(
                cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, text=True, errors="replace",
                **SUBPROCESS_FLAGS,
            )
            # Drain stderr on a background thread to prevent buffer deadlock
            stderr_buf: list[str] = []
            drain = threading.Thread(target=lambda: stderr_buf.extend(proc.stderr), daemon=True)
            drain.start()

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
            drain.join(timeout=5)
            if proc.returncode == 0:
                self.after(0, lambda: self.conv_bar.set(1.0))
                self.after(0, lambda: self.conv_status.configure(text="Done!", text_color=SUCCESS))
            else:
                lines = [l.strip() for l in stderr_buf if l.strip()]
                log.error("ffmpeg exited with %s:\n%s", proc.returncode, "\n".join(lines))
                short = lines[-1] if lines else f"ffmpeg exited with code {proc.returncode}"
                self.after(0, lambda e=short: self.conv_status.configure(
                    text=f"Error: {e[:90]}", text_color=ERROR
                ))
        except FileNotFoundError:
            self.after(0, lambda: self.conv_status.configure(
                text="ffmpeg not found. Set path in Settings.", text_color=ERROR
            ))
        except Exception as e:
            # Bind the message now: Python deletes `e` when the except block ends
            log.exception("Convert failed")
            self.after(0, lambda msg=str(e): self.conv_status.configure(text=msg, text_color=ERROR))

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


