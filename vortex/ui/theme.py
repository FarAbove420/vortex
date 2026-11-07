"""Colours and small widget helpers shared by all tabs."""
import customtkinter as ctk


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

