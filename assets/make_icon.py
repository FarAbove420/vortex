"""Draws the Vortex app icon and writes every format the builds need.

    pip install pillow
    python assets/make_icon.py

Writes, next to this script:
  icon.png     1024 px, macOS icon grid (used for the window icon)
  Vortex.icns  macOS app icon (needs macOS: uses iconutil)
  Vortex.ico   Windows app and installer icon
"""
import math
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

HERE = Path(__file__).parent
SS   = 4               # draw at 4x and scale down, for smooth edges
N    = 1024 * SS

BG_CORE   = "#3b1a7a"
BG_EDGE   = "#0b0b18"
ARM_OUT   = "#5b21b6"
ARM_IN    = "#f0abfc"
GLOW      = "#7c3aed"   # ACCENT in main.py
BORDER    = (157, 92, 245, 70)


def rgba(h, a=255):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) + (a,)


def mix(c1, c2, t):
    return tuple(int(a + (b - a) * t) for a, b in zip(c1, c2))


def layer():
    return Image.new("RGBA", (N, N), (0, 0, 0, 0))


def radial_bg(inner, outer, rmax):
    img = Image.new("RGBA", (N, N), outer)
    d = ImageDraw.Draw(img)
    for i in range(200):
        t = i / 200
        r = rmax * (1 - t)
        d.ellipse([N/2 - r, N/2 - r, N/2 + r, N/2 + r], fill=mix(outer, inner, t ** 1.6))
    return img.filter(ImageFilter.GaussianBlur(6 * SS))


def glow(radius, color, blur, dy=0):
    g = layer()
    cy = N/2 + dy
    ImageDraw.Draw(g).ellipse([N/2 - radius, cy - radius, N/2 + radius, cy + radius], fill=color)
    return g.filter(ImageFilter.GaussianBlur(blur))


def spiral(arms, r_out, r_in, turns, w_out, w_in, col_out, col_in, rot):
    """Logarithmic spiral arms, tapered at both ends, with a soft bloom."""
    arm_layer = layer()
    d = ImageDraw.Draw(arm_layer)
    k = math.log(r_out / r_in) / (turns * 2 * math.pi)
    steps = 900
    for a in range(arms):
        th0 = rot + a * 2 * math.pi / arms
        for i in range(steps + 1):
            t   = i / steps                         # 0 = outer tip, 1 = core
            ang = t * turns * 2 * math.pi
            r   = r_out * math.exp(-k * ang)
            x, y = N/2 + r * math.cos(th0 + ang), N/2 + r * math.sin(th0 + ang)
            env = math.sin(math.pi * min(1, t * 1.15)) ** 0.8
            w   = (w_out + (w_in - w_out) * t) * max(env, 0.05)
            col = mix(col_out, col_in, t ** 1.3)[:3] + (int(255 * min(1, t * 3)),)
            d.ellipse([x - w, y - w, x + w, y + w], fill=col)
    bloom = arm_layer.filter(ImageFilter.GaussianBlur(14 * SS))
    out = layer()
    out.alpha_composite(bloom)
    out.alpha_composite(bloom)
    out.alpha_composite(arm_layer)
    return out


def arrow(size, color):
    a = layer()
    d = ImageDraw.Draw(a)
    cx, cy = N/2, N/2
    shaft = size * 0.30
    head  = size * 0.95
    top, neck, tip = cy - size * 0.62, cy + size * 0.02, cy + size * 0.58
    d.rounded_rectangle([cx - shaft/2, top, cx + shaft/2, neck + shaft * 0.3], radius=shaft/2, fill=color)
    d.polygon([(cx - head/2, neck), (cx + head/2, neck), (cx, tip)], fill=color)
    # Round the arrowhead corners: blur the shape, then cut it back
    alpha = a.split()[3].filter(ImageFilter.GaussianBlur(size * 0.04)).point(lambda v: 255 if v > 128 else 0)
    alpha = alpha.filter(ImageFilter.GaussianBlur(1.2 * SS))
    out = Image.new("RGBA", (N, N), color[:3] + (0,))
    out.putalpha(alpha)
    return out


def draw(margin_frac, radius_frac):
    margin, radius = int(N * margin_frac), int(N * radius_frac)
    inner = N - 2 * margin
    R = inner * 0.47

    img = radial_bg(rgba(BG_CORE), rgba(BG_EDGE), inner * 0.75)
    img.alpha_composite(glow(R * 0.55, rgba(GLOW, 150), 40 * SS))
    img.alpha_composite(spiral(5, R, R * 0.10, 0.9, 6 * SS, 34 * SS, rgba(ARM_OUT), rgba(ARM_IN), -0.4))
    img.alpha_composite(glow(R * 0.30, rgba(BG_EDGE, 200), 18 * SS))
    shadow = arrow(R * 0.68, rgba("#000000", 255))
    shadow.putalpha(shadow.split()[3].point(lambda v: v * 0.45))
    img.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(10 * SS)), (0, int(10 * SS)))
    img.alpha_composite(arrow(R * 0.68, rgba("#ffffff")))

    hl = layer()
    ImageDraw.Draw(hl).ellipse([margin - inner * 0.3, margin - inner * 0.75,
                                N - margin + inner * 0.3, margin + inner * 0.35], fill=(255, 255, 255, 10))
    img.alpha_composite(hl.filter(ImageFilter.GaussianBlur(90 * SS)))

    mask = Image.new("L", (N, N), 0)
    ImageDraw.Draw(mask).rounded_rectangle([margin, margin, N - margin, N - margin], radius=radius, fill=255)
    out = layer()
    out.paste(img, (0, 0), mask)
    border = layer()
    ImageDraw.Draw(border).rounded_rectangle([margin, margin, N - margin, N - margin],
                                             radius=radius, outline=BORDER, width=3 * SS)
    out.alpha_composite(border)
    return out.resize((1024, 1024), Image.LANCZOS)


def main():
    # macOS: Apple's icon grid leaves ~10% padding around a rounded square
    mac = draw(100 / 1024, 185 / 1024)
    mac.save(HERE / "icon.png")

    # Windows: icons fill nearly the whole square
    win = draw(24 / 1024, 200 / 1024)
    win.save(HERE / "Vortex.ico", sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)])

    if sys.platform == "darwin" and shutil.which("iconutil"):
        with tempfile.TemporaryDirectory() as tmp:
            iconset = Path(tmp) / "Vortex.iconset"
            iconset.mkdir()
            for s in (16, 32, 128, 256, 512):
                mac.resize((s, s), Image.LANCZOS).save(iconset / f"icon_{s}x{s}.png")
                mac.resize((s * 2, s * 2), Image.LANCZOS).save(iconset / f"icon_{s}x{s}@2x.png")
            subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(HERE / "Vortex.icns")], check=True)
    else:
        print("Skipped Vortex.icns: needs macOS (iconutil)")
    print("Done:", ", ".join(p.name for p in sorted(HERE.glob("*")) if p.suffix in (".png", ".ico", ".icns")))


if __name__ == "__main__":
    main()
