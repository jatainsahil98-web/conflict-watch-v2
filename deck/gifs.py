"""Looping GIF animations for the deck (PowerPoint plays them in slideshow; PDF shows the first frame).

* radar_gif(): a rotating radar sweep with blips, cut from the cover background so it blends in.
* pulse_gif(): the India-exposure map with pulsing rings on the Sri Lanka strike, Hormuz and the LoC.
"""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

HERE = Path(__file__).resolve().parent
OUT = HERE / "figs" / "hud"


def _hex(h, a=255):
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), a)


def _save(frames, path, ms):
    pal = [f.convert("RGB").quantize(colors=200, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
           for f in frames]
    pal[0].save(path, save_all=True, append_images=pal[1:], duration=ms, loop=0, optimize=True, disposal=1)
    return path


def radar_gif(bg_path: Path, cx: int, cy: int, R: int, size=560, frames=30, colour="4FD6E8") -> tuple[Path, tuple]:
    """Returns the GIF path and its crop box in background pixels (x0, y0, x1, y1)."""
    OUT.mkdir(parents=True, exist_ok=True)
    bg = Image.open(bg_path).convert("RGBA")
    pad = 20
    box = (cx - R - pad, cy - R - pad, cx + R + pad, cy + R + pad)
    base = bg.crop(box)
    W = base.width
    c = W // 2
    blips = [(0.55, 40), (0.78, 145), (0.35, 230), (0.68, 300), (0.9, 200)]
    out = []
    for k in range(frames):
        ang = k * 360 / frames
        im = base.copy()
        g = Image.new("RGBA", im.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(g)
        for i in range(55):                       # trailing wedge
            a0 = ang - 55 + i
            d.pieslice([c - R, c - R, c + R, c + R], a0, a0 + 1.2, fill=_hex(colour, int(1 + i * 1.5)))
        x1 = c + R * math.cos(math.radians(ang))
        y1 = c + R * math.sin(math.radians(ang))
        d.line([(c, c), (x1, y1)], fill=_hex(colour, 210), width=4)
        for rr, ba in blips:                       # blips light up as the sweep passes, then fade
            age = (ang - ba) % 360
            if age < 200:
                a = int(255 * (1 - age / 200))
                bx = c + rr * R * math.cos(math.radians(ba))
                by = c + rr * R * math.sin(math.radians(ba))
                d.ellipse([bx - 9, by - 9, bx + 9, by + 9], fill=_hex("F0B03A", a))
        glow = g.filter(ImageFilter.GaussianBlur(6))
        im = Image.alpha_composite(Image.alpha_composite(im, glow), g)
        out.append(im.resize((size, size), Image.LANCZOS))
    return _save(out, OUT / "radar.gif", 70), box


def pulse_gif(map_path: Path, pulses: list, scale=0.6, frames=24) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    m = Image.open(map_path).convert("RGBA")
    m = m.resize((int(m.width * scale), int(m.height * scale)), Image.LANCZOS)
    W, H = m.size
    out = []
    for k in range(frames):
        im = m.copy()
        g = Image.new("RGBA", im.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(g)
        for j, p in enumerate(pulses):
            x, y = p["xy"][0] * W, p["xy"][1] * H
            for wave in (0, 0.5):                  # two rings per point, half a cycle apart
                t = ((k / frames) + wave + j * 0.17) % 1
                r = 6 + t * 46
                a = int(230 * (1 - t))
                d.ellipse([x - r, y - r, x + r, y + r], outline=_hex(p["color"], a), width=4)
            d.ellipse([x - 7, y - 7, x + 7, y + 7], fill=_hex(p["color"], 255))
        glow = g.filter(ImageFilter.GaussianBlur(4))
        im = Image.alpha_composite(Image.alpha_composite(im, glow), g)
        out.append(im)
    return _save(out, OUT / "map_pulse.gif", 80)
