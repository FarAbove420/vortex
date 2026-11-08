"""Mouse wheel and trackpad scrolling for every CTkScrollableFrame.

CustomTkinter (5.2.2 and 6.0.0) only listens for <MouseWheel> and assumes Tk
8.6's wheel values. Python 3.14 on macOS ships Tk 9, where:
- trackpads send a separate <TouchpadScroll> event, with the x and y
  distance packed into one number (see ::tk::PreciseScrollDeltas in Tk), so
  two-finger scrolling did nothing at all;
- a mouse wheel's delta is scaled differently (Tk's own Text widget scrolls
  delta / 4 pixels).

This replaces CustomTkinter's handler with one that finds the scrollable
frame under the pointer and scrolls it by the right amount on Tk 8.6 and 9.
"""
import sys

import customtkinter as ctk


def _find_scrollable(widget):
    w = widget
    while w is not None:
        if isinstance(w, ctk.CTkScrollableFrame):
            return w
        w = getattr(w, "master", None)
    return None


def install(root):
    tk_major = int(str(root.tk.call("info", "tclversion")).split(".")[0])
    leftover = {}   # sub-unit scroll distance per canvas, so slow scrolls still move

    def scroll_pixels(widget, pixels):
        if isinstance(widget, str):
            try:
                widget = root.nametowidget(widget)
            except KeyError:
                return
        frame = _find_scrollable(widget)
        if frame is None:
            return
        canvas = frame._parent_canvas
        if canvas.yview() == (0.0, 1.0):
            return  # everything fits, nothing to scroll
        step = float(canvas.cget("yscrollincrement") or 1) or 1.0
        total = leftover.get(canvas, 0.0) + pixels
        units = int(total / step)
        leftover[canvas] = total - units * step
        if units:
            canvas.yview("scroll", units, "units")

    def on_wheel(event):
        if tk_major >= 9:
            px = -event.delta / 4                 # same as Tk 9's Text binding
        elif sys.platform == "darwin":
            px = -event.delta * 8                 # Tk 8.6: small steps per notch
        else:
            px = -event.delta / 6                 # Windows: 120 per notch
        scroll_pixels(event.widget, px)

    def on_touchpad(event):
        low = event.delta & 0xFFFF                # low 16 bits: signed y distance
        dy = low if low < 0x8000 else low - 0x10000
        if dy:
            scroll_pixels(event.widget, -dy)

    root.unbind_all("<MouseWheel>")               # CustomTkinter's Tk 8.6 handler
    root.bind_all("<MouseWheel>", on_wheel, add="+")
    if tk_major >= 9:
        root.bind_all("<TouchpadScroll>", on_touchpad, add="+")
