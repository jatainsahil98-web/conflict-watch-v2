"""Ops-room styling and motion for the jury deck.

* backgrounds(): HUD background images (grid, vignette, corner brackets, title glow line), drawn with PIL.
* icon(name, colour): a tinted, softly glowing Lucide icon PNG (icons in deck/assets/icons, ISC licence).
* finish(prs, meta): adds slide transitions (Morph, falling back to Fade) and automatic build-in animations.
  Builds play by themselves after each slide appears ("with previous" + delay), so the presenter never
  has to click through them on a video call. PDF exports show every slide fully built.
"""
from __future__ import annotations

import copy
from pathlib import Path

from lxml import etree
from PIL import Image, ImageDraw, ImageFilter

HERE = Path(__file__).resolve().parent
ICONS = HERE / "assets" / "icons"
CACHE = HERE / "figs" / "hud"
W, H = 2667, 1500          # 13.333 x 7.5 in at 200 dpi
NS = {"p": "http://schemas.openxmlformats.org/presentationml/2006/main",
      "a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
P = "{%s}" % NS["p"]


def _hex(h, a=255):
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), a)


def _base(top="0A1828", bottom="050D16"):
    im = Image.new("RGBA", (W, H))
    d = ImageDraw.Draw(im)
    t, b = _hex(top), _hex(bottom)
    for y in range(H):
        f = y / H
        d.line([(0, y), (W, y)], fill=tuple(int(t[i] + (b[i] - t[i]) * f) for i in range(3)) + (255,))
    return im


def _grid(im, step=67, alpha=16):
    g = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(g)
    for x in range(0, W, step):
        d.line([(x, 0), (x, H)], fill=(79, 214, 232, alpha), width=1)
    for y in range(0, H, step):
        d.line([(0, y), (W, y)], fill=(79, 214, 232, alpha), width=1)
    for x in range(0, W, step * 4):          # brighter crosses at major grid points
        for y in range(0, H, step * 4):
            d.line([(x - 6, y), (x + 6, y)], fill=(79, 214, 232, alpha * 3), width=2)
            d.line([(x, y - 6), (x, y + 6)], fill=(79, 214, 232, alpha * 3), width=2)
    # vignette: fade the grid toward the edges
    m = Image.new("L", im.size, 0)
    ImageDraw.Draw(m).ellipse([-W * 0.15, -H * 0.35, W * 1.15, H * 1.35], fill=255)
    m = m.filter(ImageFilter.GaussianBlur(220))
    g.putalpha(Image.composite(g.getchannel("A"), Image.new("L", im.size, 0), m))
    return Image.alpha_composite(im, g)


def _glow(im, box, colour, radius, alpha):
    g = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ImageDraw.Draw(g).ellipse(box, fill=_hex(colour, alpha))
    return Image.alpha_composite(im, g.filter(ImageFilter.GaussianBlur(radius)))


def _brackets(im, colour="4FD6E8", inset=34, arm=70, width=4, alpha=170):
    d = ImageDraw.Draw(im)
    c = _hex(colour, alpha)
    # bottom corners only: the two formation logos sit in the top corners
    for (x, y, sx, sy) in ((inset, H - inset, 1, -1), (W - inset, H - inset, -1, -1)):
        d.line([(x, y), (x + sx * arm, y)], fill=c, width=width)
        d.line([(x, y), (x, y + sy * arm)], fill=c, width=width)
    return im


def _title_line(im, y=255, x0=148, length=900):
    g = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(g)
    for i in range(length):
        a = int(230 * (1 - i / length) ** 1.6)
        d.line([(x0 + i, y), (x0 + i, y + 3)], fill=(79, 214, 232, a))
    glow = g.filter(ImageFilter.GaussianBlur(7))
    im = Image.alpha_composite(im, glow)
    im = Image.alpha_composite(im, glow)
    return Image.alpha_composite(im, g)


def _scan(im, alpha=10):
    g = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(g)
    for y in range(0, H, 6):
        d.line([(0, y), (W, y)], fill=(0, 0, 0, alpha), width=2)
    return Image.alpha_composite(im, g)


def _footer_rule(im, y=1395):
    d = ImageDraw.Draw(im)
    d.line([(110, y), (W - 110, y)], fill=(43, 71, 99, 200), width=2)
    for x in range(110, W - 110, 160):
        d.line([(x, y - 6), (x, y + 6)], fill=(43, 71, 99, 200), width=2)
    return im


def _radar(im, cx, cy, rings=5, step=120, colour="4FD6E8", sweep=True):
    d = ImageDraw.Draw(im)
    for k in range(1, rings + 1):
        r = k * step
        d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=_hex(colour, 34 if k % 2 else 22), width=2)
    d.line([(cx - rings * step, cy), (cx + rings * step, cy)], fill=_hex(colour, 26), width=2)
    d.line([(cx, cy - rings * step), (cx, cy + rings * step)], fill=_hex(colour, 26), width=2)
    if not sweep:          # the cover's sweep is an animated GIF (deck/gifs.py)
        return im
    # sweep wedge
    g = Image.new("RGBA", im.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(g)
    R = rings * step
    for i in range(40):
        gd.pieslice([cx - R, cy - R, cx + R, cy + R], -60 + i, -59 + i, fill=_hex(colour, int(2 + i * 1.6)))
    return Image.alpha_composite(im, g.filter(ImageFilter.GaussianBlur(3)))


def backgrounds() -> dict:
    """Write and return the background PNGs: 'content', 'cover', 'section'."""
    CACHE.mkdir(parents=True, exist_ok=True)
    out = {}
    im = _grid(_base())
    im = _glow(im, [W * 0.55, -H * 0.5, W * 1.25, H * 0.45], "1D5C7A", 260, 120)
    im = _title_line(_brackets(im))
    out["content"] = _scan(_footer_rule(im))
    im = _grid(_base("0B1C2E", "04090F"), alpha=20)
    im = _glow(im, [W * 0.45, H * 0.05, W * 1.05, H * 0.95], "1B6A86", 240, 150)
    im = _radar(im, int(W * 0.72), int(H * 0.5), rings=6, step=110, sweep=False)
    out["cover"] = _scan(_brackets(im, alpha=200))
    im = _grid(_base("081522", "04090F"), alpha=12)
    out["plain"] = _scan(_footer_rule(_brackets(im, alpha=110)))
    paths = {}
    for k, v in out.items():
        p = CACHE / f"bg_{k}.png"
        v.convert("RGB").save(p, optimize=True)
        paths[k] = p
    return paths


def icon(name: str, colour: str = "4FD6E8", glow: bool = True) -> Path:
    """Tinted icon PNG with a soft glow, cached under deck/figs/hud."""
    CACHE.mkdir(parents=True, exist_ok=True)
    p = CACHE / f"ic_{name}_{colour}{'_g' if glow else ''}.png"
    if p.exists():
        return p
    src = Image.open(ICONS / f"{name}.png").convert("RGBA")
    a = src.getchannel("A")
    pad = 48
    canvas = Image.new("RGBA", (src.width + 2 * pad, src.height + 2 * pad), (0, 0, 0, 0))
    solid = Image.new("RGBA", src.size, _hex(colour))
    solid.putalpha(a)
    if glow:
        halo = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        halo.paste(solid, (pad, pad), solid)
        halo = halo.filter(ImageFilter.GaussianBlur(16))
        canvas = Image.alpha_composite(canvas, halo)
        canvas = Image.alpha_composite(canvas, halo)
    canvas.paste(solid, (pad, pad), solid)
    canvas.save(p)
    return p


# ----------------------------------------------------------------------------------------------- motion
MORPH = ('<mc:AlternateContent xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006">'
         '<mc:Choice xmlns:p159="http://schemas.microsoft.com/office/powerpoint/2015/09/main" Requires="p159">'
         '<p:transition xmlns:p="{p}" spd="slow"><p159:morph option="byObject"/></p:transition></mc:Choice>'
         '<mc:Fallback><p:transition xmlns:p="{p}" spd="slow"><p:fade/></p:transition></mc:Fallback>'
         '</mc:AlternateContent>').replace("{p}", NS["p"])
FADE = '<p:transition xmlns:p="{p}" spd="med"><p:fade/></p:transition>'.replace("{p}", NS["p"])

EFFECT = {  # name -> (presetID, presetSubtype, filter)
    "fade": (10, 0, "fade"),
    "wipe_left": (22, 8, "wipe(left)"),
    "wipe_up": (22, 4, "wipe(down)"),      # "from bottom": columns grow up from the axis
    "wipe_down": (22, 1, "wipe(up)"),      # "from top"
    "zoom": (53, 16, "fade"),              # fade + zoom from the centre: KPI numbers pop in
}


class _Ids:
    def __init__(self):
        self.n = 2

    def __call__(self):
        self.n += 1
        return self.n


def _zoom_xml(ids, spid):
    out = ""
    for a in ("ppt_w", "ppt_h"):
        out += (f'<p:anim calcmode="lin" valueType="num"><p:cBhvr><p:cTn id="{ids()}" dur="550" fill="hold"/>'
                f'<p:tgtEl><p:spTgt spid="{spid}"/></p:tgtEl><p:attrNameLst><p:attrName>{a}</p:attrName>'
                f'</p:attrNameLst></p:cBhvr><p:tavLst><p:tav tm="0"><p:val><p:fltVal val="0"/></p:val></p:tav>'
                f'<p:tav tm="100000"><p:val><p:strVal val="#{a}"/></p:val></p:tav></p:tavLst></p:anim>')
    return out


def _effect_xml(ids, spid, kind, delay, dur):
    pid, sub, flt = EFFECT[kind]
    zoom = _zoom_xml(ids, spid) if kind == "zoom" else ""
    return (f'<p:par><p:cTn id="{ids()}" presetID="{pid}" presetClass="entr" presetSubtype="{sub}" fill="hold" '
            f'nodeType="withEffect"><p:stCondLst><p:cond delay="{delay}"/></p:stCondLst><p:childTnLst>'
            f'<p:set><p:cBhvr><p:cTn id="{ids()}" dur="1" fill="hold"><p:stCondLst><p:cond delay="0"/></p:stCondLst>'
            f'</p:cTn><p:tgtEl><p:spTgt spid="{spid}"/></p:tgtEl><p:attrNameLst><p:attrName>style.visibility'
            f'</p:attrName></p:attrNameLst></p:cBhvr><p:to><p:strVal val="visible"/></p:to></p:set>{zoom}'
            f'<p:animEffect transition="in" filter="{flt}"><p:cBhvr><p:cTn id="{ids()}" dur="{dur}"/>'
            f'<p:tgtEl><p:spTgt spid="{spid}"/></p:tgtEl></p:cBhvr></p:animEffect></p:childTnLst></p:cTn></p:par>')


def _timing(steps):
    """steps: list of (delay_ms, [(spid, effect, dur_ms)]). One automatic sequence that starts with the slide."""
    ids = _Ids()
    o1, o2 = ids(), ids()
    body = "".join(_effect_xml(ids, sp, kind, d, dur) for d, items in steps for sp, kind, dur in items)
    return (f'<p:timing xmlns:p="{NS["p"]}"><p:tnLst><p:par><p:cTn id="1" dur="indefinite" restart="never" '
            f'nodeType="tmRoot"><p:childTnLst><p:seq concurrent="1" nextAc="seek"><p:cTn id="2" dur="indefinite" '
            f'nodeType="mainSeq"><p:childTnLst><p:par><p:cTn id="{o1}" fill="hold"><p:stCondLst>'
            f'<p:cond delay="indefinite"/><p:cond evt="onBegin" delay="0"><p:tn val="2"/></p:cond></p:stCondLst>'
            f'<p:childTnLst><p:par><p:cTn id="{o2}" fill="hold"><p:stCondLst><p:cond delay="0"/></p:stCondLst>'
            f'<p:childTnLst>{body}</p:childTnLst></p:cTn></p:par></p:childTnLst></p:cTn></p:par></p:childTnLst>'
            f'</p:cTn><p:prevCondLst><p:cond evt="onPrev" delay="0"><p:tgtEl><p:sldTgt/></p:tgtEl></p:cond>'
            f'</p:prevCondLst><p:nextCondLst><p:cond evt="onNext" delay="0"><p:tgtEl><p:sldTgt/></p:tgtEl></p:cond>'
            f'</p:nextCondLst></p:seq></p:childTnLst></p:cTn></p:par></p:tnLst></p:timing>')


def _bounds(sh):
    return sh.left or 0, sh.top or 0, (sh.left or 0) + (sh.width or 0), (sh.top or 0) + (sh.height or 0)


def _inside(inner, outer, slack=0.15):
    x0, y0, x1, y1 = inner
    X0, Y0, X1, Y1 = outer
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    sw, sh = (X1 - X0) * slack, (Y1 - Y0) * slack
    return (X0 - sw <= cx <= X1 + sw and Y0 - sh <= cy <= Y1 + sh and (x1 - x0) <= (X1 - X0) * 1.05
            and (y1 - y0) <= (Y1 - Y0) * 1.05)


def _is_panel(sh):
    return sh.shape_type == 1 and not (sh.has_text_frame and sh.text_frame.text.strip())


def _plan(shapes):
    """Group content shapes into build steps: a panel and everything drawn inside it appear together."""
    steps, cur_box = [], None
    for sh in shapes:
        b = _bounds(sh)
        if cur_box is not None and _inside(b, cur_box):
            steps[-1].append(sh)
            continue
        steps.append([sh])
        cur_box = b if _is_panel(sh) else None
    return steps


def _chart_kind(sh):
    name = str(sh.chart.chart_type)
    if "BAR" in name:                               # horizontal bars grow from the left axis
        return "wipe_left", 1100
    if "COLUMN" in name:                            # columns grow up from zero
        return "wipe_up", 1100
    return "wipe_left", 1500                        # lines and scatters draw left to right


def _big_number(sh):
    if not sh.has_text_frame or not sh.text_frame.text.strip() or len(sh.text_frame.text) > 14:
        return False
    return any(r.font.size is not None and r.font.size.pt >= 22
               for p_ in sh.text_frame.paragraphs for r in p_.runs)


def _kind(step):
    first = step[0]
    if getattr(first, "has_chart", False) and first.has_chart:
        return _chart_kind(first)
    if first.shape_type == 13:                      # picture
        return "wipe_left", 650
    if getattr(first, "has_table", False) and first.has_table:
        return "wipe_down", 700
    if first.shape_type == 1 and getattr(first, "auto_shape_type", None) in (52, 53):   # pentagon / chevron
        return "wipe_left", 420
    return "fade", 450


def finish(prs, meta: dict):
    """meta[slide_id] = dict(hdr=n_header_shapes, motion='morph'|'fade', build=bool, order=optional)."""
    for slide in prs.slides:
        m = meta.get(slide.slide_id, {})
        el = slide._element
        for old in el.findall(P + "transition") + el.findall(P + "timing"):
            el.remove(old)
        anchor = el.find(P + "clrMapOvr")
        tr = etree.fromstring(MORPH if m.get("motion", "fade") == "morph" else FADE)
        if anchor is not None:
            anchor.addnext(tr)
        else:
            el.find(P + "cSld").addnext(tr)
        if not m.get("build"):
            continue
        content = list(slide.shapes)[m.get("hdr", 0):]
        for i, sh in enumerate(content):          # unique names, so Morph only carries the shared header
            sh.name = f"s{slide.slide_id}-{i}"
        if not content:
            continue
        steps = _plan(content)
        gap = max(140, min(380, int(3200 / max(len(steps), 1))))
        plan = []
        for k, st in enumerate(steps):
            kind, dur = _kind(st)
            items = []
            for j, sh in enumerate(st):
                big = _big_number(sh)
                if j == 0:
                    items.append((sh.shape_id, "zoom" if (kind == "fade" and big) else kind, dur))
                elif getattr(sh, "has_chart", False) and sh.has_chart:
                    ck, cdur = _chart_kind(sh)          # a chart inside its panel still grows from zero
                    items.append((sh.shape_id, ck, cdur))
                else:
                    items.append((sh.shape_id, "zoom" if big else "fade", 550 if big else dur))
            plan.append((300 + k * gap, items))
        tr.addnext(etree.fromstring(_timing(plan)))
    return prs
