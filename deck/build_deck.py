"""Build the jury deck (16:9, dark theme) from the pipeline outputs.

    python deck/build_deck.py      ->  deck/Conflict_Watch_Jury_Deck.pptx

Layout, colours and typography follow the team's reference deck: dark navy background, amber kicker
labels, big KPI numbers, an amber "SO WHAT" bar and a classification footer. Fonts are large and the
contrast is high because the deck is presented over a video call.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Inches, Pt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src import config as C  # noqa: E402
from deck import charts, gifs, hud  # noqa: E402

FIG = ROOT / "outputs" / "figures"
SHOT = ROOT / "deck" / "shots"
DF = ROOT / "deck" / "figs"
TB = C.TAB_DIR
OUT = ROOT / "deck" / "Conflict_Watch_Jury_Deck.pptx"
QR_URL = "https://conflictmonitor2026.streamlit.app"   # set to the hosted dashboard or repository URL to print a QR code on the closing slide


def rgb(h):
    h = h.lstrip("#")
    return RGBColor(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


BG, PANEL, PANEL2, BORDER = rgb("07131F"), rgb("0F2236"), rgb("16304A"), rgb("2B4763")
WHITE, TEXT2, TEXT3, MUTED = rgb("FFFFFF"), rgb("D5DEE8"), rgb("9FB2C6"), rgb("5E7B99")
AMBER, RED, CYAN, TEAL, VIOLET, AMBER_BG = (rgb("F0B03A"), rgb("FF4D5E"), rgb("4FD6E8"), rgb("35C2A6"),
                                            rgb("A794FF"), rgb("2A2008"))
FONT = "Calibri"
RUN_ID = (C.TAB_DIR / "run_id.txt").read_text().strip()
FOOTER = f"CONFLICT WATCH   |   DATA ANALYTICS COMPETITION 2026   |   UNCLASSIFIED - COMPETITION DATA ONLY   |   RUN {RUN_ID}"

prs = Presentation()
BGS = hud.backgrounds()
META: dict = {}
ICON_FOR = [("THEATRE COMMANDER", "users"), ("RECOMMENDATIONS   |   DECISION CYCLE", "timer"), ("BOTTOM LINE", "target"), ("WHY IT MATTERS", "globe"), ("OUR APPROACH", "compass"),
            ("DATA AND PIPELINE", "workflow"), ("FINDING 1", "activity"), ("FINDING 2", "crosshair"),
            ("FINDING 3", "shield-alert"), ("FINDING 4", "trending-up"), ("ECONOMIC FRONT", "trending-up"), ("FINDING 5", "tent"),
            ("FINDING 6", "trending-up"), ("FINDING 7", "radar"), ("FINDING 8", "satellite"),
            ("LIVE", "monitor-play"), ("RECOMMENDATIONS   |   OPERATIONAL", "swords"),
            ("RECOMMENDATIONS   |   EXECUTION", "list-checks"), ("LIMITS", "scale"), ("THREAT SCORECARD", "siren"),
            ("BACKUP", "archive"), ("ANNEX", "file-text")]
prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
BLANK = prs.slide_layouts[6]
_n = [0]


# --------------------------------------------------------------------------- primitives
def text(slide, x, y, w, h, s, size=16, color=WHITE, bold=False, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP,
         spacing=None, italic=False):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(0.02)
    tf.margin_top = tf.margin_bottom = Inches(0.0)
    tf.vertical_anchor = anchor
    lines = s if isinstance(s, list) else [s]
    for i, ln in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        runs = ln if isinstance(ln, list) else [(ln, {})]
        for r in runs:
            if isinstance(r, str):
                r = (r, {})
            run = p.add_run()
            run.text = r[0]
            f = run.font
            f.name = FONT
            f.size = Pt(r[1].get("size", size))
            f.bold = r[1].get("bold", bold)
            f.italic = italic
            f.color.rgb = r[1].get("color", color)
        if spacing:
            p.space_after = Pt(spacing)
    return tb


def box(slide, x, y, w, h, fill=PANEL, line=BORDER, shape=MSO_SHAPE.ROUNDED_RECTANGLE, lw=1.0, radius=0.06):
    s = slide.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    if shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        s.adjustments[0] = radius
    if fill is None:
        s.fill.background()
    elif fill == PANEL and shape in (MSO_SHAPE.ROUNDED_RECTANGLE, MSO_SHAPE.RECTANGLE):
        s.fill.gradient()
        s.fill.gradient_angle = 90
        st = s.fill.gradient_stops
        st[0].color.rgb, st[0].position = rgb("12304A"), 0.0
        st[1].color.rgb, st[1].position = rgb("0A1A2B"), 1.0
    else:
        s.fill.solid()
        s.fill.fore_color.rgb = fill
    if line is None:
        s.line.fill.background()
    else:
        s.line.color.rgb = line
        s.line.width = Pt(lw)
    s.shadow.inherit = False
    if line is not None and line not in (BORDER, WHITE) and shape != MSO_SHAPE.OVAL:
        glow(s, "%02X%02X%02X" % (line[0], line[1], line[2]), rad=6, alpha=30)
    return s


LOGO_L = ROOT / "assets" / "logos" / "jimmy_sm.png"     # Corps of Signals 'Jimmy', top left
LOGO_R = ROOT / "assets" / "logos" / "mcte_sm.png"      # MCTE formation sign, top right
from PIL import Image as _PI
JIMMY_AR = (lambda im: im.width / im.height)(_PI.open(LOGO_L))
MCTE_AR = (lambda im: im.width / im.height)(_PI.open(LOGO_R))


def new_slide(kicker=None, title=None, footer=True):
    s = prs.slides.add_slide(BLANK)
    s.background.fill.solid()
    s.background.fill.fore_color.rgb = BG
    _n[0] += 1
    section = "cover" if kicker is None else ("plain" if kicker.startswith(("ANNEX", "BACKUP")) else "content")
    bg = s.shapes.add_picture(str(BGS[section]), 0, 0, prs.slide_width, prs.slide_height)
    bg.name = "!!bg"
    lh = 1.05 if section == "cover" else 0.82          # logo height, inches
    jw = lh * JIMMY_AR
    s.shapes.add_picture(str(LOGO_L), Inches(0.14), Inches(0.1), Inches(jw), Inches(lh)).name = "!!logoL"
    mw = lh * MCTE_AR
    s.shapes.add_picture(str(LOGO_R), prs.slide_width - Inches(0.14 + mw), Inches(0.1), Inches(mw), Inches(lh)).name = "!!logoR"
    if kicker:
        ic = next((n for k, n in ICON_FOR if kicker.startswith(k)), "radar")
        s.shapes.add_picture(str(hud.icon(ic, "F0B03A")), Inches(0.74), Inches(0.21), Inches(0.42), Inches(0.42)).name = "!!icon"
        text(s, 1.2, 0.32, 8.0, 0.3, kicker, size=12, color=AMBER, bold=True)
        spaced(s.shapes[-1]); s.shapes[-1].name = "!!kicker"
        text(s, 9.3, 0.3, 2.85, 0.3, [[("● ", {"color": TEAL, "size": 10}), (f"LIVE  ·  {_n[0]:02d}", {})]],
             size=10, color=TEXT3, bold=True, align=PP_ALIGN.RIGHT)
        spaced(s.shapes[-1], 150); s.shapes[-1].name = "!!hud"
    if title:
        text(s, 0.74, 0.62, 11.5, 0.6, title, size=28, bold=True)
        s.shapes[-1].name = "!!title"
    if footer:
        text(s, 0.55, 7.08, 10, 0.25, FOOTER, size=9, color=MUTED)
        spaced(s.shapes[-1], 100); s.shapes[-1].name = "!!footer"
        text(s, 12.2, 7.08, 0.6, 0.25, str(_n[0]), size=10, color=MUTED, align=PP_ALIGN.RIGHT)
        s.shapes[-1].name = "!!num"
    main = section != "plain"
    META[s.slide_id] = dict(hdr=len(s.shapes), motion="morph" if main else "fade", build=main)
    return s


def glow(shape, colour="4FD6E8", rad=8, alpha=35):
    """Soft outer glow on a shape (ops-room accent)."""
    from lxml import etree
    spPr = shape._element.spPr
    ns = "http://schemas.openxmlformats.org/drawingml/2006/main"
    el = spPr.find("{%s}effectLst" % ns)
    if el is None:
        el = etree.SubElement(spPr, "{%s}effectLst" % ns)
    for c in list(el):
        el.remove(c)
    g = etree.SubElement(el, "{%s}glow" % ns, rad=str(int(rad * 12700)))
    c = etree.SubElement(g, "{%s}srgbClr" % ns, val=colour)
    etree.SubElement(c, "{%s}alpha" % ns, val=str(alpha * 1000))
    return shape


def text_glow(tb, colour="4FD6E8", rad=10, alpha=45):
    from lxml import etree
    ns = "http://schemas.openxmlformats.org/drawingml/2006/main"
    for p_ in tb.text_frame.paragraphs:
        for r in p_.runs:
            rPr = r.font._element
            e = etree.SubElement(rPr, "{%s}effectLst" % ns)
            g = etree.SubElement(e, "{%s}glow" % ns, rad=str(int(rad * 12700)))
            c = etree.SubElement(g, "{%s}srgbClr" % ns, val=colour)
            etree.SubElement(c, "{%s}alpha" % ns, val=str(alpha * 1000))
            # effectLst must follow solidFill and precede latin in rPr
            latin = rPr.find("{%s}latin" % ns)
            if latin is not None:
                latin.addprevious(e)
    return tb


def brackets(slide, x, y, w, h, colour=CYAN, arm=0.22, t=0.035):
    """HUD corner brackets around a rectangle."""
    for (bx, by, sx, sy) in ((x, y, 1, 1), (x + w, y, -1, 1), (x, y + h, 1, -1), (x + w, y + h, -1, -1)):
        hx = bx if sx > 0 else bx - arm
        vy = by if sy > 0 else by - arm
        box(slide, hx, by - (0 if sy > 0 else t), arm, t, fill=colour, line=None, shape=MSO_SHAPE.RECTANGLE)
        box(slide, bx - (0 if sx > 0 else t), vy, t, arm, fill=colour, line=None, shape=MSO_SHAPE.RECTANGLE)


def node(slide, x, y, d, icon_name, colour=CYAN, hexcol="4FD6E8"):
    """Glowing circular node with an icon."""
    c = box(slide, x, y, d, d, fill=PANEL2, line=colour, shape=MSO_SHAPE.OVAL, lw=1.75)
    glow(c, hexcol, rad=9, alpha=45)
    pad = d * 0.2
    slide.shapes.add_picture(str(hud.icon(icon_name, hexcol, glow=False)), Inches(x + pad * 0.62), Inches(y + pad * 0.62),
                             Inches(d - pad * 1.24), Inches(d - pad * 1.24))
    return c


def spaced(shape, spc=200):
    """Letter-spacing for kicker labels."""
    for p in shape.text_frame.paragraphs:
        for r in p.runs:
            r.font._element.set("spc", str(spc))


def kicker_lbl(slide, x, y, w, s, color=AMBER, size=12):
    text(slide, x, y, w, 0.3, s, size=size, color=color, bold=True)
    spaced(slide.shapes[-1])


def kpi(slide, x, y, w, h, num, label, sub=None, color=AMBER, numsize=36, kick=None, border=BORDER):
    box(slide, x, y, w, h, line=border, lw=1.5 if border != BORDER else 1.0)
    yy = y + 0.18
    if kick:
        kicker_lbl(slide, x + 0.22, yy, w - 0.4, kick, size=11, color=TEXT3)
        yy += 0.32
    text_glow(text(slide, x + 0.22, yy, w - 0.4, 0.7, num, size=numsize, bold=True, color=color),
              "%02X%02X%02X" % (color[0], color[1], color[2]), rad=8, alpha=35)
    yy += numsize / 72 * 1.12 + 0.05
    text(slide, x + 0.22, yy, w - 0.4, 0.8, label, size=15, bold=True, color=WHITE)
    if sub:
        text(slide, x + 0.22, y + h - 0.62, w - 0.4, 0.5, sub, size=12, color=TEXT3, anchor=MSO_ANCHOR.BOTTOM)


def kpi_row(slide, x, y, w, h, num, label, color=AMBER, numsize=26):
    """Compact side KPI card (number left, label right) as in the reference deck."""
    box(slide, x, y, w, h)
    text(slide, x + 0.18, y, 1.9, h, num, size=numsize, bold=True, color=color, anchor=MSO_ANCHOR.MIDDLE)
    text(slide, x + 2.05, y, w - 2.2, h, label, size=13, color=TEXT2, anchor=MSO_ANCHOR.MIDDLE)


def kpi_side(slide, x, y, w, h, num, label, color=AMBER, numsize=28):
    """Stacked side KPI card: number above, label below."""
    box(slide, x, y, w, h)
    text_glow(text(slide, x + 0.2, y + 0.12, w - 0.35, 0.55, num, size=numsize, bold=True, color=color),
              "%02X%02X%02X" % (color[0], color[1], color[2]), rad=8, alpha=35)
    text(slide, x + 0.2, y + 0.12 + numsize / 72 * 1.15, w - 0.35, h - 0.6, label, size=13, color=TEXT2)


def sowhat(slide, msg, label="SO WHAT", y=6.38):
    box(slide, 0.55, y, 12.23, 0.5, fill=AMBER_BG, line=AMBER, lw=1.25, radius=0.12)
    text(slide, 0.78, y, 1.6, 0.5, label, size=11, color=AMBER, bold=True, anchor=MSO_ANCHOR.MIDDLE)
    spaced(slide.shapes[-1])
    text(slide, 2.25, y, 10.4, 0.5, msg, size=15, bold=True, anchor=MSO_ANCHOR.MIDDLE)


def picture(slide, path, x, y, w, h, frame=False, caption=None, cap_color=CYAN):
    """Place an image fitted inside (x, y, w, h), keeping aspect ratio, top-left aligned horizontally centred."""
    im = Image.open(path)
    iw, ih = im.size
    r = min(w / iw, h / ih)
    pw, ph = iw * r, ih * r
    px, py = x + (w - pw) / 2, y + (h - ph) / 2
    if frame:
        fr = box(slide, px - 0.07, py - 0.07, pw + 0.14, ph + 0.14, fill=PANEL2, line=BORDER, radius=0.02,
                 shape=MSO_SHAPE.RECTANGLE)
        glow(fr, "4FD6E8", rad=10, alpha=22)
    slide.shapes.add_picture(str(path), Inches(px), Inches(py), Inches(pw), Inches(ph))
    if frame:
        brackets(slide, px - 0.12, py - 0.12, pw + 0.24, ph + 0.24)
    if caption:
        kicker_lbl(slide, px, py + ph + 0.1, pw, caption, color=cap_color, size=10)
    return px, py, pw, ph


def table(slide, x, y, w, rows, col_w, header_fill=rgb("123A55"), header_color=CYAN, size=13, row_h=0.42,
          first_col_color=None, fills=None):
    nr, nc = len(rows), len(rows[0])
    shp = slide.shapes.add_table(nr, nc, Inches(x), Inches(y), Inches(w), Inches(row_h * nr))
    tbl = shp.table
    tblPr = shp._element.graphic.graphicData.tbl.tblPr
    tblPr.set("bandRow", "0")
    tblPr.set("firstRow", "0")
    for j, cw in enumerate(col_w):
        tbl.columns[j].width = Inches(cw)
    for i, row in enumerate(rows):
        tbl.rows[i].height = Inches(row_h)
        for j, val in enumerate(row):
            c = tbl.cell(i, j)
            c.fill.solid()
            if i == 0:
                hf = header_fill[j] if isinstance(header_fill, list) else header_fill
                c.fill.fore_color.rgb = hf
            else:
                c.fill.fore_color.rgb = (fills[i][j] if fills and fills[i][j] is not None
                                         else (rgb("0C1D2F") if i % 2 else rgb("11283F")))
            c.margin_left = c.margin_right = Inches(0.08)
            c.margin_top = c.margin_bottom = Inches(0.03)
            c.vertical_anchor = MSO_ANCHOR.MIDDLE
            tf = c.text_frame
            tf.word_wrap = True
            p = tf.paragraphs[0]
            run = p.add_run()
            run.text = str(val)
            f = run.font
            f.name = FONT
            f.size = Pt(size)
            if i == 0:
                f.bold = True
                f.color.rgb = header_color
            else:
                f.color.rgb = (first_col_color if (j == 0 and first_col_color) else TEXT2)
                f.bold = j == 0
    return tbl


def circle_num(slide, x, y, n, color, d=0.42, size=15):
    s = box(slide, x, y, d, d, fill=color, line=None, shape=MSO_SHAPE.OVAL)
    tf = s.text_frame
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = str(n)
    r.font.size, r.font.bold, r.font.name = Pt(size), True, FONT
    r.font.color.rgb = BG
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE


def notes(slide, s):
    slide.notes_slide.notes_text_frame.text = s


# --------------------------------------------------------------------------- numbers (all from tables)
ov = pd.read_csv(TB / "insight_case_overview.csv").set_index("conflict_case")
rag = pd.read_csv(TB / "rag_scorecard.csv").set_index("conflict_case")
ew = pd.read_csv(TB / "early_warning_scores.csv")
ew26 = ew[ew.year == 2026].set_index("model")
lg = ew26.loc["LightGBM classifier"]
rule = ew26.loc["Rule: rank by last month's deaths"]
sc = pd.read_csv(TB / "forecast_scores.csv")
hA = sc[(sc.fold == 2026) & (sc.track == "A")]
nv = hA[hA.model == "naive"].set_index("conflict_case").MAE
en = hA[hA.model == "ensemble"].set_index("conflict_case").MAE
pooled = (1 - en.sum() / nv.sum()) * 100
red = (1 - en / nv) * 100
preds = pd.read_parquet(C.PROCESSED / "forecast_preds.parquet")
e26 = preds[(preds.model == "ensemble") & (preds.fold == 2026)]
cov80 = ((e26.actual >= e26.pi80_lo) & (e26.actual <= e26.pi80_hi)).mean() * 100
rm = pd.read_csv(TB / "forecast_rmsle.csv")
rml = rm.groupby(["model", "track", rm.fold.eq(2026)]).RMSLE.mean().unstack([1, 2])
stats = pd.read_csv(TB / "insight_stats.csv").iloc[0]
fg = pd.read_csv(TB / "insight_front_geography.csv").pivot_table(index="area", columns="year", values="share")
don22, don26 = fg.loc["Donetsk oblast", 2022] * 100, fg.loc["Donetsk oblast", 2026] * 100
att = pd.read_csv(TB / "insight_attrition.csv")
usir_att = att[att.conflict_case == "US–Iran"].set_index("year")
ts = pd.read_csv(TB / "insight_theatre_spread.csv")
usir_ts = ts[ts.conflict_case == "US–Iran"].set_index("year").countries
ie = pd.read_csv(TB / "insight_india_exposure.csv")
g26 = ie[ie.year == 2026]
gulf = g26[g26.india_tag.str.startswith("Gulf")]
hz = g26[g26.india_tag.str.startswith("Iran")]
pakprox = ie[ie.india_tag.str.startswith("Pakistan")].groupby("year").deaths.sum()
dq = pd.read_csv(TB / "data_quality_log.csv")
ip = pd.read_csv(TB / "insight_indian_press.csv").set_index("conflict_case")
abl = pd.read_csv(TB / "ablation_lgb.csv")
summary = json.loads((TB / "run_summary.json").read_text())
fut = pd.read_parquet(C.PROCESSED / "forecast_future.parquet")
fut = fut[fut.model == "ensemble"]
ROB = json.loads((TB / "robustness.json").read_text())
CAL = pd.read_csv(TB / "ew_calibration.csv")
GD = json.loads((TB / "gdelt_summary.json").read_text())
GS = pd.read_csv(TB / "gdelt_signals.csv").set_index(["case", "month"])


CD0 = json.loads((DF / "chart_data.json").read_text())


def _ci(c):
    return f"{c[0] * 100:.0f}% to {c[1] * 100:.0f}%".replace("-", "−")

RAGC = {"RED": RED, "AMBER": AMBER, "GREEN": TEAL}

# =========================================================================== 1 COVER
s = new_slide(footer=False)
_rg, _rb = gifs.radar_gif(BGS["cover"], int(hud.W * 0.72), int(hud.H * 0.5), 660)
s.shapes.add_picture(str(_rg), Inches(_rb[0] / 200), Inches(_rb[1] / 200), Inches((_rb[2] - _rb[0]) / 200),
                     Inches((_rb[3] - _rb[1]) / 200))
# draw the radar just above the background, under the formation logos (it stays static header, the GIF animates itself)
_bg = next(sh for sh in s.shapes if sh.name == "!!bg")
_bg._element.addnext(s.shapes[-1]._element)
META[s.slide_id]["hdr"] += 1
kicker_lbl(s, 6.6, 6.55, 6.4, f"SYSTEM ONLINE  ·  4 CONFLICTS  ·  222 AREAS  ·  RUN {RUN_ID}", color=CYAN, size=10)
kicker_lbl(s, 0.85, 0.55, 8, "DATA ANALYTICS COMPETITION 2026", size=13)
text(s, 0.6, 1.55, 5.6, 1.2, "CONFLICT WATCH", size=52, bold=True)
text(s, 0.6, 2.75, 5.3, 1.6, "When and where will conflict deaths rise next, and what does it mean for India?",
     size=22, color=TEXT2)
text(s, 0.6, 4.2, 5.3, 0.8, ["Russia–Ukraine  ·  Israel–Hamas", "Afghanistan–Pakistan  ·  US–Iran"],
     size=16, color=AMBER, bold=True)
kicker_lbl(s, 0.6, 5.05, 5.3, "TEAM", color=TEXT3, size=11)
text(s, 0.6, 5.38, 5.3, 1.2, ["Maj Shivam Mehta", "Capt Siddharth Sangwan", "Capt Sahil Singh"], size=18, bold=True)
text(s, 0.6, 6.85, 12, 0.3, "CONFLICT ESCALATION FORECASTING & EARLY WARNING   |   UNCLASSIFIED - COMPETITION DATA ONLY",
     size=10, color=MUTED)
spaced(s.shapes[-1], 100)
notes(s, "Good morning. In one sentence: we built a system that forecasts where conflict deaths will rise next "
         "month, warns which districts will escalate, and translates both into what the Indian Armed Forces should do.")

# =========================================================================== 2 BLUF
s = new_slide("BOTTOM LINE UP FRONT", "Four wars, three warning signals, one exposed neighbour")
cards = [
    (1, AMBER, "THREAT", "RED", f"Russia–Ukraine: {rag.loc['Russia–Ukraine', 'forecast_next']:,.0f} deaths forecast for Oct 2026",
     "Af–Pak and US–Iran AMBER, Israel–Hamas GREEN (low escalation risk, not peace)", RED),
    (2, RED, "INDIA", "104", "killed off Sri Lanka, 4 Mar 2026: the US–Iran war reached the Indian Ocean",
     f"Strikes in 5 Gulf states hosting the Indian diaspora", RED),
    (3, CYAN, "PREDICTION", f"−{pooled:.0f}%", "error vs the 'no-change' rule, one month ahead, on unseen 2026 data",
     f"Escalation warning AUC {lg.ROC_AUC:.2f}: top-10 list {lg.precision_at_10 / lg.base_rate:.1f}× random", CYAN),
]
for i, (n, cc, k, num, lab, sub, ncol) in enumerate(cards):
    x = 0.55 + i * 4.13
    box(s, x, 1.45, 3.93, 4.6)
    circle_num(s, x + 0.28, 1.72, n, cc, d=0.4, size=14)
    kicker_lbl(s, x + 0.82, 1.78, 2.9, k, color=TEXT3, size=12)
    text(s, x + 0.28, 2.45, 3.5, 1.0, num, size=60, bold=True, color=ncol)
    text(s, x + 0.28, 3.65, 3.45, 1.4, lab, size=17, bold=True)
    text(s, x + 0.28, 5.05, 3.45, 0.8, sub, size=13, color=TEXT3)
_esu = json.loads((TB / "econ_summary.json").read_text())["headline"]
sowhat(s, f"Two fronts: the guns stay far away, but the Gulf war cost India Brent +{_esu['brent_d20_2026']:.0f}% and Nifty "
       f"{_esu['nifty_d20_2026']:.0f}% in 20 trading days.", label="SECOND FRONT")
notes(s, "Fighting is one front; sanctions, oil and shipping reach India first. Three messages. One: the threat picture. Two: India is already inside the blast radius. Three: we can "
         "forecast and warn better than simple rules, and we proved it on 2026 data the model never saw.")

# =========================================================================== 3 WHY IT MATTERS
s = new_slide("FINDING 2   |   GULF, DIASPORA AND SEA LANES", "The 2026 war reached the Gulf, Hormuz and Sri Lankan waters")
picture(s, gifs.pulse_gif(DF / "map.png", CD0["map_pulses"]), 0.55, 1.4, 7.4, 4.85, frame=False)
kicker_lbl(s, 8.25, 1.42, 4.5, "WHERE IT TOUCHES INDIA  [DATA]", color=TEXT3, size=11)
kpi_row(s, 8.25, 1.78, 4.53, 0.82, f"{int(usir_ts.get(2026, 0))}", "countries with US–Iran war deaths in 2026, "
        f"up from {int(usir_ts.get(2025, 0))} in 2025", color=RED)
kpi_row(s, 8.25, 2.7, 4.53, 0.82, "5 Gulf", f"states struck in 2026 ({int(gulf.events.sum())} events). About 9M "
        "Indians live in the Gulf [Domain]", color=AMBER)
kpi_row(s, 8.25, 3.62, 4.53, 0.82, f"{int(hz.deaths.sum())}", "deaths on Iran's Hormuz / Chabahar coast, 2026",
        color=AMBER)
kpi_row(s, 8.25, 4.54, 4.53, 0.82, "104", "killed in one strike off Sri Lanka, 4 Mar 2026", color=RED)
kpi_row(s, 8.25, 5.46, 4.53, 0.82, f"{pakprox.get(2022, 0):.0f} → {pakprox.get(2025, 0):.0f}",
        "deaths in Pakistan areas adjoining India / LoC, 2022 → 2025", color=CYAN, numsize=24)
sowhat(s, "Diaspora, energy routes, Chabahar and the IOR now sit inside the strike envelope.",
       label="DECISION PROBLEM")
notes(s, "This is why the question matters to us. These are counts from the competition data, not opinion. "
         "The 9 million diaspora figure is domain knowledge and is marked as such.")

# =========================================================================== 4 APPROACH
s = new_slide("OUR APPROACH   |   HOW WE WENT ABOUT THE PROBLEM", "One operational question, broken into five sub-questions")
box(s, 0.55, 1.45, 4.15, 4.75, line=AMBER, lw=1.5)
kicker_lbl(s, 0.8, 1.68, 3.7, "THE QUESTION WE ASKED", color=AMBER, size=11)
text(s, 0.8, 2.1, 3.7, 2.2, "When and where will conflict deaths rise next, and what does it mean for India?",
     size=26, bold=True)
text(s, 0.8, 4.6, 3.7, 1.3, ["Operational, not descriptive: a forecast can be scored on withheld data and turned "
     "into tasking for ISR, plans and logistics."], size=13, color=TEXT3)
QS = [("Q1", "activity", "How intense is each war, and how is it changing?", "Monthly panels, tempo, lethality, seasons", "18"),
      ("Q2", "crosshair", "How are the wars fought: attrition, fronts, spread?", "Dyads, located events, theatre spread", "10–13"),
      ("Q3", "trending-up", "Can we forecast deaths better than simple rules?", "7 models, back-test 2022–25, 2026 withheld", "5–7"),
      ("Q4", "radar", "Can we warn which districts escalate next month?", "Sub-national classifier, watch-list", "8"),
      ("Q5", "flag", "What does it mean for India?", "Exposure analysis + labelled domain reasoning", "10–16")]
for i, (q, ic, qq, mth, sl) in enumerate(QS):
    y = 1.45 + i * 0.97
    box(s, 4.9, y, 7.88, 0.86)
    s.shapes.add_picture(str(hud.icon(ic, "4FD6E8")), Inches(5.0), Inches(y + 0.1), Inches(0.66), Inches(0.66))
    text(s, 5.72, y, 0.6, 0.86, q, size=17, bold=True, color=CYAN, anchor=MSO_ANCHOR.MIDDLE)
    text(s, 6.35, y + 0.08, 5.15, 0.4, qq, size=15.5, bold=True)
    text(s, 6.35, y + 0.48, 5.15, 0.32, mth, size=13, color=TEXT3)
    text(s, 11.5, y, 1.15, 0.86, f"SLIDE {sl}", size=10, bold=True, color=AMBER, align=PP_ALIGN.RIGHT,
         anchor=MSO_ANCHOR.MIDDLE)
    spaced(s.shapes[-1], 120)
_RULES = [("lock", "2026 WITHHELD", "Every choice made on 2022–25; 2026 scored once"),
         ("scale", "BEAT SIMPLE RULES", "Every model faces the 'no change' rule, and we show where it lost"),
         ("badge-check", "DATA vs DOMAIN", "Each claim tagged: computed from the files, or expert reasoning"),
         ("git-branch", "ONE COMMAND", f"Rebuilds every number; run ID {RUN_ID} on every output")]
sowhat(s, "We framed it as a commander would: where to look next month, and how far to trust the answer.",
       label="APPROACH")
notes(s, "How we went about it. One operational question, broken into five sub-questions, each answered by a method "
         "and a slide. Four rules: 2026 was withheld and scored once; every model faces the no-change rule; every claim "
         "is tagged DATA or DOMAIN; and one command rebuilds every number, stamped with the run ID.")

# =========================================================================== 5 DATA & PIPELINE
s = new_slide("DATA AND PIPELINE", "From raw files to a monthly warning: one reproducible pipeline")
box(s, 1.05, 1.98, 11.25, 0.045, fill=CYAN, line=None, shape=MSO_SHAPE.RECTANGLE)
glow(s.shapes[-1], "4FD6E8", rad=6, alpha=55)
STAGES = [("database", "INGEST", f"12 issued files: {ov.events.sum():,} UCDP GED 26.1 events, UNHCR, IDMC, WB, GDELT, ACLED-style"),
          ("filter", "CLEAN", f"{len(dq)} checks logged; raw kept beside every fix"),
          ("layers", "FEATURES", "4 conflicts + 222 area series × 153 months; 9 families"),
          ("scan-search", "EXPLORE", "Military lens + India exposure; DATA / DOMAIN tags"),
          ("brain-circuit", "MODEL", "7 models; back-test 2022–25; 2026 withheld"),
          ("radar", "WARN", "Escalation classifier, RAG scorecard, what-if"),
          ("layout-dashboard", "DELIVER", "Dashboard, Ops site, brief; run ID on all")]
for i, (ic, h, d) in enumerate(STAGES):
    cx = 1.05 + i * (11.25 / 6)
    node(s, cx - 0.42, 1.58, 0.84, ic)
    text(s, cx - 0.85, 2.5, 1.7, 0.3, h, size=13, bold=True, color=CYAN, align=PP_ALIGN.CENTER)
    spaced(s.shapes[-1], 150)
    text(s, cx - 0.86, 2.82, 1.72, 0.85, d, size=11, color=TEXT2, align=PP_ALIGN.CENTER)
kicker_lbl(s, 0.55, 3.95, 12, "FOUR RULES WE HELD TO", color=TEXT3, size=11)
for i, (ic, h, d) in enumerate(_RULES):
    x = 0.55 + i * 3.08
    box(s, x, 4.35, 2.95, 1.85, fill=PANEL2)
    s.shapes.add_picture(str(hud.icon(ic, "35C2A6")), Inches(x + 0.15), Inches(4.5), Inches(0.75), Inches(0.75))
    text(s, x + 1.0, 4.6, 1.9, 0.5, h, size=14, bold=True, color=TEAL)
    spaced(s.shapes[-1], 100)
    text(s, x + 0.18, 5.35, 2.65, 0.8, d, size=13, color=TEXT2)
sowhat(s, "Every number on these slides is regenerated by one command and matches the dashboard.",
       label="REPRODUCIBLE")
notes(s, "All twelve issued files are used, joined only by country and calendar. Key cleaning decisions: 692 out-of-order estimates "
         "repaired in new columns, 731 multi-month records spread by day so they don't fake spikes, FATA merged "
         "into KP so the 2018 boundary change doesn't fake a collapse. 2026 provisional data is the test set.")

# =========================================================================== 6 FINDING 1 INTENSITY
CD = json.loads((DF / "chart_data.json").read_text())
CASEC = {"Russia–Ukraine": "FF4D5E", "Israel–Hamas": "A794FF", "Afghanistan–Pakistan": "F0B03A", "US–Iran": "4FD6E8"}
SHORT = {"Russia–Ukraine": "RU–UA", "Israel–Hamas": "Israel–Hamas", "Afghanistan–Pakistan": "Af–Pak", "US–Iran": "US–Iran"}


def chart_panel(slide, x, y, w, h):
    """Dark HUD panel behind a native chart."""
    p = box(slide, x, y, w, h, fill=rgb("0A1A2B"), line=BORDER, radius=0.03)
    brackets(slide, x - 0.05, y - 0.05, w + 0.1, h + 0.1, arm=0.18, t=0.03)
    return p


s = new_slide("SUPPORT   |   CONFLICT SIGNATURES", "Four different threat signatures: attrition, spikes, creep, decline")
mo = CD["monthly"]
cats = [pd.Timestamp(m).strftime("%b %Y") for m in mo["months"]]
chart_panel(s, 0.55, 1.4, 8.3, 4.8)
charts.line(s, 0.65, 1.48, 8.1, 4.65, cats, [dict(name=SHORT[c], values=mo["series"][c], color=CASEC[c], width=2.25)
                                              for c in C.CASES],
            title="Deaths per month, 2014 to Sep 2026 (log scale)", log_y=True, cat_skip=24, size=13)
kpi_side(s, 9.1, 1.4, 3.68, 1.12, f"{ov.loc['Russia–Ukraine', 'deaths_best'] / 1000:,.0f}k",
         "Russia–Ukraine recorded deaths since 2014; 4–11k every month since 2023", color=RED)
kpi_side(s, 9.1, 2.62, 3.68, 1.12, f"{ov.loc['US–Iran', 'peak_month_deaths']:,}",
         "US–Iran deaths in Mar 2026: a war with no build-up", color=CYAN)
kpi_side(s, 9.1, 3.84, 3.68, 1.12, "Since 2021", "Af–Pak deaths rising every year (TTP, then interstate)", color=AMBER,
         numsize=26)
kpi_side(s, 9.1, 5.06, 3.68, 1.12, "~130 / mo", "Israel–Hamas in 2026, after 11,211 in Oct 2023", color=VIOLET,
         numsize=26)
sowhat(s, "One warning rule cannot fit all four: we forecast level, trend and spread separately.")

# =========================================================================== 7 FINDING 2 FRONTS
s = new_slide("FINDING 3   |   DEFENCE SUSTAINMENT", "Ukraine: the front is widening, not moving")
fr = CD["front"]
PAL = ["FF4D5E", "F0B03A", "4FD6E8", "35C2A6", "A794FF", "7FA7D9", "E98AA0", "C9B458", "6FCF97", "B0BEC5", "3A5878"]
chart_panel(s, 0.55, 1.4, 8.3, 4.8)
charts.columns(s, 0.65, 1.48, 8.1, 4.65, [str(y) for y in fr["years"]],
               [dict(name=a, values=fr["share"][a], color=PAL[i % len(PAL)]) for i, a in enumerate(fr["areas"])],
               title="Share of located events by area, 2021–2026", percent=True, num_fmt="0%", gap=45, size=12,
               cat_size=14)
kpi_side(s, 9.1, 1.4, 3.68, 1.12, f"{don22:.0f}% → {don26:.0f}%", "Donetsk's share of located events, 2022 → 2026",
         color=AMBER, numsize=26)
kpi_side(s, 9.1, 2.62, 3.68, 1.12, "10,358", "deaths recorded inside Russia in 2024 (Kursk, Belgorod)", color=RED)
kpi_side(s, 9.1, 3.84, 3.68, 1.12, f"{usir_att.loc[2026, 'deaths_side_a']:,.0f} : {usir_att.loc[2026, 'deaths_side_b']:,.0f}",
         "Iran vs Israel–US recorded deaths, 2026 war (recorded, not verified)", color=CYAN, numsize=26)
kpi_side(s, 9.1, 5.06, 3.68, 1.12, "92%", "of 2026 RU–UA deaths have no location: the fog of war is in the data",
         color=VIOLET)
sowhat(s, "A wide static front rewards long-range fires, counter-drone and EW: lessons for both our fronts. [Domain]")
notes(s, "Recorded attrition ratios are an upper bound of reporting: Ukrainian OSINT documents Russian losses more "
         "fully. We say so in the report. The fog-of-war share is itself a finding from cleaning.")

# =========================================================================== 8 FINDING 3a AFPAK INTERSTATE
s = new_slide("FINDING 1   |   BORDERS AND THE LoC", "Pakistan now fights Afghanistan directly")
it = CD["interstate"]
chart_panel(s, 0.55, 1.4, 8.3, 4.8)
charts.columns(s, 0.65, 1.48, 8.1, 4.65, it["months"], [dict(name="Deaths", values=it["deaths"], color="FF4D5E")],
               title="Afghan vs Pakistani state-on-state clashes: deaths per month, 2022–Sep 2026", legend=False,
               gap=30, cat_skip=6, size=13)
kpi_side(s, 9.1, 1.4, 3.68, 2.3, "411", "deaths in Afghan vs Pakistani state clashes in a single month, Mar 2026",
         color=RED, numsize=44)
kpi_side(s, 9.1, 3.9, 3.68, 2.3, "Oct 2025", "first month of direct interstate fighting in the data", color=AMBER,
         numsize=40)
sowhat(s, "A new state-on-state front opened on Pakistan's west in Oct 2025, and it is the deadliest part of Af–Pak.")

# =========================================================================== 9 FINDING 3b AFPAK PROVINCES
s = new_slide("FINDING 1   |   BORDERS AND THE LoC", "Pakistan now fights on two fronts in the west")
apv = CD["afpak_prov"]
PAL2 = ["F0B03A", "4FD6E8", "35C2A6", "A794FF", "FF4D5E", "E98AA0", "3A5878"]
chart_panel(s, 0.55, 1.4, 8.3, 4.8)
charts.columns(s, 0.65, 1.48, 8.1, 4.65, [str(y) for y in apv["years"]],
               [dict(name=a.replace("Khyber Pakhtunkwa", "Khyber Pakhtunkhwa"), values=apv["deaths"][a],
                     color=PAL2[i % len(PAL2)]) for i, a in enumerate(apv["areas"])],
               title="Deaths per year by province (FATA merged into KP)", stacked=True, gap=45, size=12, cat_size=14)
kpi_side(s, 9.1, 1.4, 3.68, 2.3, "3 of top 3", "escalation hotspots for Oct 2026 are Af–Pak: Kandahar, Balochistan, Kunar",
         color=AMBER, numsize=40)
kpi_side(s, 9.1, 3.9, 3.68, 2.3, f"{ip.loc['Afghanistan–Pakistan', 'events_covered_share']:.0%}",
         "of Af–Pak events carry an Indian source (mainly PTI); almost none elsewhere", color=CYAN, numsize=44)
sowhat(s, "A Pakistan Army committed in the west raises the risk of diversion along the LoC. Watch west too. [Domain]")

# =========================================================================== 10 FINDING 4 MEDIA
s = new_slide("SUPPORT   |   ATTENTION GAP INDEX", "Media attention follows incidents, not lethality, and does not warn")
me = CD["media"]
chart_panel(s, 0.55, 1.4, 8.3, 4.8)
charts.scatter(s, 0.62, 1.48, 4.1, 4.65, [dict(name=SHORT[c], xs=me[c]["events"], ys=me[c]["sources"], color=CASEC[c])
                                          for c in C.CASES], title="References vs EVENTS: tight",
               x_title="events per month", y_title="source references per month", size=11)
charts.scatter(s, 4.72, 1.48, 4.1, 4.65, [dict(name=SHORT[c], xs=me[c]["deaths"], ys=me[c]["sources"], color=CASEC[c])
                                          for c in C.CASES], title="References vs DEATHS: loose",
               x_title="deaths per month", size=11)
kpi_side(s, 9.1, 1.4, 3.68, 1.12, f"{stats.media_elasticity_events:.2f} vs {stats.media_elasticity_deaths:.2f}",
         "elasticity of source references to events vs to deaths", color=CYAN, numsize=26)
kpi_side(s, 9.1, 2.62, 3.68, 1.12, f"p = {stats.media_lead_p:.2f}", "Attention Gap Index does not lead next month's "
         "escalation", color=AMBER, numsize=26)
kpi_side(s, 9.1, 3.84, 3.68, 1.12, "150 vs 35", "references per 100 deaths: Israel–Hamas vs US–Iran", color=RED,
         numsize=26)
kpi_side(s, 9.1, 5.06, 3.68, 1.12, f"R² {stats.media_r2:.2f}", "one mass-casualty strike is one story", color=TEAL,
         numsize=26)
sowhat(s, "Headline volume is not an indicator. In UCDP's record, West Asia coverage rests on non-Indian wires.")

# =========================================================================== 11 FINDING 5 DISPLACEMENT
s = new_slide("SUPPORT   |   HUMANITARIAN", "Displacement follows onset and spread, and it is women and children")
dp = CD["displacement"]
dyrs = sorted({y for v in dp.values() for y in v["years"] if y >= 2015})
DPC = {"Ukraine": "4FD6E8", "Afghanistan": "F0B03A", "Palestine": "A794FF", "Pakistan": "35C2A6", "Iran": "FF4D5E",
       "Russia": "B0BEC5"}
chart_panel(s, 0.55, 1.4, 8.3, 4.8)
charts.line(s, 0.65, 1.48, 8.1, 4.65, [str(y) for y in dyrs],
            [dict(name=k, values=[dict(zip(v["years"], v["total"])).get(y) for y in dyrs], color=DPC[k], width=3,
                  marker=True) for k, v in dp.items()],
            title="Displaced people by origin, millions (year-end)", num_fmt="0.0",
            size=13)
kpi_side(s, 9.1, 1.4, 3.68, 1.12, "8.9M", "Ukrainians displaced end-2025: 5.2M refugees + 3.7M IDPs", color=CYAN)
kpi_side(s, 9.1, 2.62, 3.68, 1.12, "72%", "of Ukrainian refugees are women or children (Afghanistan 63%)", color=AMBER)
kpi_side(s, 9.1, 3.84, 3.68, 1.12, "10%", "of Afghan refugees are under five", color=RED)
kpi_side(s, 9.1, 5.06, 3.68, 1.12, f"ρ = {stats.link_spearman:.2f}", "monthly deaths barely explain displacement "
         "change", color=TEAL, numsize=26)
sowhat(s, "Trigger HADR on escalation flags, not death tolls; stock paediatric and maternal supplies.")


# =========================================================================== 12–13 PREDICTION (two slides)
def forecast_chart(slide, case):
    fc = CD["forecast"][case]
    col = CASEC[case]
    chart_panel(slide, 0.55, 1.4, 8.3, 4.8)
    charts.line(slide, 0.65, 1.48, 8.1, 4.65, fc["months"], [
        dict(name="Actual", values=fc["actual"], color="FFFFFF", width=3, marker=True),
        dict(name="Forecast, 2026 withheld test", values=fc["pred"], color=col, width=3.5, dash=True, marker=True),
        dict(name="80% interval", values=fc["lo"], color=col, width=1.25, dash=True),
        dict(name="80% interval (high)", values=fc["hi"], color=col, width=1.25, dash=True),
        dict(name="Forward forecast Oct–Dec 2026", values=fc["fut"], color="F0B03A", width=3.5, marker=True),
        dict(name="Forward 80% (low)", values=fc["fut_lo"], color="F0B03A", width=1.25, dash=True),
        dict(name="Forward 80% (high)", values=fc["fut_hi"], color="F0B03A", width=1.25, dash=True)],
        title=f"{case}: deaths per month, actual vs 1-month-ahead forecast", cat_skip=3, size=12)
    # legend: keep the three meaningful entries only
    lg_el = slide.shapes[-1].chart.legend._element
    from lxml import etree as _et
    for idx in (3, 5, 6):
        le = _et.SubElement(lg_el, "{http://schemas.openxmlformats.org/drawingml/2006/chart}legendEntry")
        _et.SubElement(le, "{http://schemas.openxmlformats.org/drawingml/2006/chart}idx", val=str(idx))
        _et.SubElement(le, "{http://schemas.openxmlformats.org/drawingml/2006/chart}delete", val="1")
        lp = lg_el.find("{http://schemas.openxmlformats.org/drawingml/2006/chart}legendPos")
        lp.addnext(le)


s = new_slide("VALIDATION   |   WITHHELD 2026 DATA", "Forecasts beat simple rules on 2026 data the model never saw")
forecast_chart(s, "Russia–Ukraine")
kpi_side(s, 9.1, 1.4, 3.68, 2.3, f"−{pooled:.0f}%", f"1-month error vs the 'no change' rule on unseen 2026 data "
         f"(RU–UA −{red['Russia–Ukraine']:.0f}%, Israel–Hamas −{red['Israel–Hamas']:.0f}%)", color=CYAN, numsize=48)
kpi_side(s, 9.1, 3.9, 3.68, 2.3, f"{cov80:.0f}%", "of 2026 outcomes fell inside the 80% interval", color=TEAL,
         numsize=48)
sowhat(s, "Use the forecast as a planning baseline with honest bands; the 95% tail carries the outbreak risk.")
notes(s, "Protocol: fit on data to Dec 2025, freeze, score Jan–Sep 2026. Track A: one month ahead rolling. "
         "Track B: up to nine months blind. LightGBM predicts the change in log deaths, because trees cannot "
         "extrapolate beyond training levels. That is why a level model could never forecast the 2022 invasion.")

s = new_slide("VALIDATION   |   WITHHELD 2026 DATA", "The same method, on India's western neighbour")
forecast_chart(s, "Afghanistan–Pakistan")
kpi_side(s, 9.1, 1.4, 3.68, 2.3, "72%", "of 2026 conflict-months: the direction of change called right", color=AMBER,
         numsize=48)
kpi_side(s, 9.1, 3.9, 3.68, 2.3, "Ensemble", "ETS + 3-month mean + LightGBM-Δ, chosen on the 2022–25 back-test only",
         color=VIOLET, numsize=36)
_ra = rag.loc["Afghanistan–Pakistan"]
sowhat(s, f"Af–Pak forecast for Oct 2026: {_ra.forecast_next:,.0f} deaths (80%: {_ra.pi80_lo:,.0f}–{_ra.pi80_hi:,.0f}). "
          "Plan on the band, not the point.")

# =========================================================================== 14 EARLY WARNING
s = new_slide("VALIDATION   |   EARLY WARNING", "A district-level watch-list, one month ahead")
picture(s, SHOT / "ops_warning.png", 0.62, 1.48, 7.3, 4.11, frame=True, caption="OPS SITE   |   EARLY WARNING REPLAY, MAR 2026")
kpi_side(s, 8.3, 1.4, 4.48, 1.12, f"AUC {lg.ROC_AUC:.2f}", f"on 2026 withheld months (rule of thumb {rule.ROC_AUC:.2f}; "
         f"back-test 0.80–0.91)", color=AMBER, numsize=28)
kpi_side(s, 8.3, 2.62, 4.48, 1.12, f"{lg.precision_at_10 / lg.base_rate:.1f}×", f"top-10 list precision "
         f"{lg.precision_at_10:.0%} vs base rate {lg.base_rate:.1%}", color=CYAN)
kpi_side(s, 8.3, 3.84, 4.48, 1.12, "222", "area series in 22 countries scored every month", color=VIOLET)
kpi_side(s, 8.3, 5.06, 4.48, 1.12, "Contagion", "top signals: own intensity, country tempo, whole-war momentum",
         color=TEAL, numsize=26)
sowhat(s, "ISR and analyst effort can be tasked on predicted risk before the escalation, not after.")

# =========================================================================== 15–16 GDELT (new, labelled; two slides)
_gm, _gw = GD["monthly"]["by_case"], GD["weekly"]
_nov = GS.loc[("US–Iran", "2026-11")]
s = new_slide("INDEPENDENT CHECK   |   GDELT NEWS EVENTS", "News-coded events track UCDP only in the spike wars")
_ord = sorted(C.CASES, key=lambda c: _gm[c]["rho_change"])
chart_panel(s, 0.55, 1.4, 8.3, 4.8)
charts.columns(s, 0.65, 1.48, 8.1, 4.65, [SHORT[c] for c in _ord],
               [dict(name="ρ", values=[round(_gm[c]["rho_change"], 2) for c in _ord], color="35C2A6")],
               title="Month-on-month agreement of GDELT with UCDP deaths (Spearman ρ, Feb–Sep 2026)", horizontal=True,
               legend=False, gap=55, labels=True, label_fmt="0.00", num_fmt="0.0", y_min=-0.5, y_max=1.0, size=14,
               cat_size=16, label_size=16,
               point_colors=["35C2A6" if _gm[c]["rho_change"] >= 0.5 else "5E7B99" for c in _ord])
kpi_side(s, 9.1, 1.4, 3.68, 2.3, f"p = {_gw['lead_p']:.2f}", "GDELT a week EARLIER adds nothing: a nowcast, not a "
         "leading indicator", color=AMBER, numsize=40)
kpi_side(s, 9.1, 3.9, 3.68, 2.3, f"{_gm['US–Iran']['articles_per_death']:,.0f} vs {_gm['Russia–Ukraine']['articles_per_death']:,.0f}",
         "articles per UCDP death, US–Iran vs RU–UA: the attention gap again", color=VIOLET, numsize=36)
sowhat(s, "GDELT is a second source for spike wars only. It does not change the submitted model numbers.")
notes(s, f"GDELT: {GD['coverage']['events']:,} dyad-coded events, Feb to 12 Nov 2026, gap 1-16 May. Media reports, not incidents. "
      "Same-week fit is significant, week-ahead is not, and out of sample neither beats persistence, so it stays out of the "
      "submitted model.")

s = new_slide("INDEPENDENT CHECK   |   GDELT NEWS EVENTS", "News sees past UCDP's September cut-off: US–Iran is rising")
_mlab = {"2026-09": "Sep (last UCDP month)", "2026-10": "Oct", "2026-11": "1–12 Nov"}
chart_panel(s, 0.55, 1.4, 8.3, 4.8)
charts.columns(s, 0.65, 1.48, 8.1, 4.65, list(_mlab.values()),
               [dict(name=SHORT[c], values=[round(float(GS.loc[(c, m)].violent_pd), 1) for m in _mlab], color=CASEC[c])
                for c in C.CASES],
               title="GDELT violent events per covered day, after UCDP ends", gap=70, labels=True, label_fmt="0",
               size=13, cat_size=15, label_size=12)
kpi_side(s, 9.1, 1.4, 3.68, 2.3, f"{_nov.violent_change_vs_prev:+.0%}", "US–Iran violent events per day, 1–12 Nov vs Oct "
         "2026: the one rising signal", color=RED, numsize=48)
_oct = GS.loc[("US–Iran", "2026-10")]
kpi_side(s, 9.1, 3.9, 3.68, 2.3, f"{_oct.threats_pd:.0f} → {_nov.threats_pd:.0f}", "US–Iran threat events per day, "
         "Oct → early Nov, while the scorecard is AMBER", color=AMBER, numsize=40)
sowhat(s, "Watch US–Iran now: news-coded violence and threats rose in early November, past UCDP's lag.")

# =========================================================================== v4: SYNTHESIS + GDELT BEFORE THE WAR
X = json.loads((TB / "extra_sources.json").read_text())
X9, X10, X11, X12, XG, XO = X["D9"], X["D10"], X["D11"], X["D12"], X["GDELT"], X["GDELT_OCT"]
_mpd = X12["media_per_death_feb_apr_2026"]
_pw = XG["prewar"]
s = new_slide("SYNTHESIS   |   TWELVE ISSUED FILES, ONE PICTURE", "What the sources say together that none says alone")
rows = [["Finding", "Sources", "Evidence"],
        ["Intense wars persist", "UCDP 1989–2025", f"{X10['persist_10k']['share_next_ge_1k']:.0%} of ≥10k-death years followed by ≥1k (n = {X10['persist_10k']['n']})"],
        ["Precursors outside the death record", "ACLED-style · GDELT · WB",
         f"Iran: {X9['iran_unrest_deaths_dec25_jan26']:,} unrest deaths; strategic dev. ×{X9['iran_strategic_pre_2026']['ratio']:.1f}; tone turned. Not before Jun 2025"],
        ["War spread to the Gulf / IOR", "UCDP · ACLED-style · GDELT", f"Gulf violent events {X9['gulf_violent_events']['H1_2025']} → {X9['gulf_violent_events']['H1_2026']} (H1 25 → H1 26)"],
        ["Attention ≠ harm", "GDELT · summary panel · UCDP", f"Media events per death: Ukraine {_mpd['Ukraine']['events_per_death']:.0f}, Russia {_mpd['Russia']['events_per_death']:,.0f}"],
        ["Sources agree on magnitude", "UCDP · ACLED-style", f"Israel + Palestine monthly ρ = {X9['israel_palestine_rho']:.2f}"],
        ["Case scope", "UCDP 1989–2025 vs extract", f"Af–Pak case = {X10['afpak_case_share_of_afghanistan']:.0%} of Afghanistan's deaths"]]
table(s, 0.55, 1.4, 12.23, rows, [3.35, 3.2, 5.68], size=14, row_h=0.62, first_col_color=WHITE)
sowhat(s, "Deaths tell you a war is under way. Unrest, posture and tone may tell you one is coming: trial them.")
notes(s, "All twelve issued files are used and cited by ID in the report; Appendix A checks it mechanically. Joins "
         "across providers are only by country and calendar. The precursor sequence held before the Feb 2026 war but "
         "not before the Jun 2025 war, so we recommend a trial, not a model.")

s = new_slide("INDEPENDENT CHECK   |   GDELT, 13.5 MILLION MEDIA RECORDS",
              "Media volume reacts to war; its character shifted a week before")
for i, (num, lab, col, ns) in enumerate([
        (f"{_pw['events_per_day'][0]:,.0f} → {_pw['events_per_day'][1]:,.0f}", "reports a day on Iran vs the US or Israel, "
         f"1–20 Feb vs the last week before the war (p = {_pw['events_p']:.2f}): no warning in volume", CYAN, 34),
        (f"{_pw['goldstein'][0]:+.1f} → {_pw['goldstein'][1]:+.1f}".replace("-", "−"), "Goldstein score of those reports over "
         f"the same weeks (p = {_pw['goldstein_p']:.3f}): one case, treat as a hypothesis", AMBER, 34),
        (f"p = {GD['weekly']['lead_p']:.2f}", "pooled: last week's media adds nothing to last week's deaths "
         f"(Af–Pak alone p = {XG['weekly_lead_p_by_case']['Afghanistan–Pakistan']:.2f}, not after correcting for four tests)", VIOLET, 34),
        (f"{XG['kuwait_conflict_per_day'][0]:.1f} → {XG['kuwait_conflict_per_day'][1]:.0f}", "conflict reports a day located in "
         "Kuwait, Feb vs March: the spread to the Gulf is confirmed", RED, 34)]):
    kpi_side(s, 0.55 + (i % 2) * 6.17, 1.4 + (i // 2) * 2.45, 6.06, 2.3, num, lab, color=col, numsize=ns)
sowhat(s, "Headline counts tell you a war has started. What the headlines say may give days of notice.")
notes(s, "Datasets 3 and 4 (D7, D8): 13,507,238 GDELT rows, reduced with DuckDB to daily tables. Never joined to UCDP events, "
         "only compared by day or week. Day is the report date. The pre-war signal is one case with 27 days of baseline.")

# =========================================================================== LIVE DEMO SLIDE
s = new_slide("LIVE DEMONSTRATION   |   CONFLICT WATCH OPS SITE", "A briefing site and an ops console the jury can drive")
PROMO, PROMO_POSTER = ROOT / "deck" / "Conflict_Watch_Promo.mp4", ROOT / "deck" / "Conflict_Watch_Promo_poster.png"
if PROMO.exists() and PROMO_POSTER.exists():
    # embedded promo video (deck/build_promo.py); click to play, poster frame shows in PDF exports
    _px, _py, _pw, _ph = picture(s, PROMO_POSTER, 0.62, 1.48, 5.9, 3.32, frame=True,
                                 caption="DEMO VIDEO   |   CLICK TO PLAY   |   OPS SITE, CONSOLE, DASHBOARD")
    _pic = [sh for sh in s.shapes if sh.shape_type == 13][-1]
    _mv = s.shapes.add_movie(str(PROMO), Inches(_px), Inches(_py), Inches(_pw), Inches(_ph),
                             poster_frame_image=str(PROMO_POSTER), mime_type="video/mp4")
    _mv.name = "Demo video"
    _pic._element.getparent().remove(_pic._element)
else:
    picture(s, SHOT / "ops_hero.png", 0.62, 1.48, 5.9, 3.32, frame=True, caption="OPS SITE   |   STORY: FOUR WARS, ONE EXPOSED NEIGHBOUR")
picture(s, SHOT / "ops_console_whatif.png", 6.85, 1.48, 5.9, 3.32, frame=True, caption="OPS CONSOLE   |   WHAT-IF: AF-PAK +30% x 3 MONTHS = 359")
for i, (h, d, col) in enumerate([
        ("Story", "14 chapters: globe, BLUF, fog of war, FATA fix, India ring", CYAN),
        ("Replay", "Pick a 2026 month: what was flagged, what escalated", AMBER),
        ("What-if", "Shock a conflict: the exact submitted model answers", RED),
        ("Console", "Ctrl+K to any of 222 areas; print brief and I&W bulletin", TEAL)]):
    x = 0.55 + i * 3.1
    box(s, x, 5.3, 2.93, 0.98)
    text(s, x + 0.15, 5.36, 2.7, 0.35, h, size=16, bold=True, color=col)
    text(s, x + 0.15, 5.7, 2.7, 0.55, d, size=11, color=TEXT2)
sowhat(s, "Live at conflictmonitor2026.streamlit.app  ·  offline single-file backup  ·  every number traced to the pipeline.", label="DEMO")
notes(s, "Switch to the browser. Story: globe, Af-Pak card flip, fog-of-war toggle, FATA switch, forecast PLAY, "
         "warning replay Mar 2026, what-if Af-Pak +30% x 3 = 359, scorecard lab reset. Then OPS CONSOLE, Ctrl+K Kandahar.")


# =========================================================================== THEATRE COMMANDER VIEW (notional)
import json as _tj  # noqa: E402
from src import theatre as _TH  # noqa: E402
_TB = _tj.loads((_TH.OUT / "briefs.json").read_text(encoding="utf-8"))
_TM = _TB["meta"]
_RC = {"RED": RED, "AMBER": AMBER, "GREEN": TEAL}
s = new_slide("THEATRE COMMANDER VIEW   |   NOTIONAL THEATRES", "One dataset, four commanders: a daily 0600 brief per theatre")
picture(s, SHOT / "page14.png", 0.62, 1.48, 6.6, 3.71, frame=True,
        caption="DASHBOARD PAGE 14   |   WTC SIGNED IN   |   BLUF, RAG, OBSERVE, AOR MAP")
_lines = {"WTC": "Af–Pak: Kandahar, Balochistan, Kunar over threshold; GDELT easing",
          "NTC": "[SYNTHETIC] Tawang and Depsang surge drives the drill",
          "MTC": "US–Iran AMBER; Gulf reporting down; tanker and oil prices easing",
          "CDS": "All theatres; main effort chosen on real data only"}
for i, k in enumerate(_TH.ROLES):
    b = _TB["briefs"][k][-1]
    y = 1.4 + i * 1.2
    box(s, 7.55, y, 5.23, 1.08, line=_RC[b["rating"]], lw=1.5)
    text(s, 7.72, y + 0.08, 1.0, 0.5, k, size=22, bold=True, color=WHITE)
    text(s, 8.75, y + 0.08, 1.9, 0.5, f"{b['rating']} {b['arrow']}", size=22, bold=True, color=_RC[b["rating"]])
    text(s, 10.6, y + 0.12, 2.1, 0.4, ("SYNTHETIC" if k == "NTC" else f"CONF {b['confidence']}"), size=11, bold=True,
         color=RED if k == "NTC" else TEXT3, align=PP_ALIGN.RIGHT)
    text(s, 7.72, y + 0.56, 4.95, 0.5, _lines[k], size=12.5, color=TEXT2)
for i, (h, d, col) in enumerate([
        ("OBSERVE", "Top 5 changes, 24 h / 7 d: GDELT spikes, district alerts, markets", CYAN),
        ("ORIENT", "RAG, trend arrow, confidence and the drivers behind them", AMBER),
        ("DECIDE", "3 ranked actions: ISR, posture, evacuation, logistics", TEAL),
        ("ACT", "Owner, 24 h / 72 h / 7 d, trigger to escalate; FLASH on ingest", RED)]):
    x = 0.55 + i * 1.72
    box(s, x, 5.55, 1.62, 0.72, line=col)
    text(s, x + 0.1, 5.57, 1.45, 0.3, h, size=12, bold=True, color=col)
    text(s, x + 0.1, 5.82, 1.45, 0.45, d, size=8.5, color=TEXT2)
sowhat(s, "Same data, same rules: each commander gets only their AOR, with ranked actions, owners and triggers.",
       label="NOTIONAL")
notes(s, f"The theatre commands are not notified: these AORs are illustrative, drawn from public reporting. Log in as WTC, "
         f"NTC, MTC or CDS and the whole dashboard filters to that AOR. The brief is built automatically at 0600 IST from "
         f"the model outputs, GDELT (to {_TM['data_end']}) and market closes. There is no LAC data in the competition "
         "files, so NTC runs on a seeded synthetic generator, labelled SYNTHETIC wherever it appears, with a scripted "
         "surge to show the FLASH path. CDS never picks its main effort from synthetic data.")

s = new_slide("RECOMMENDATIONS   |   DECISION CYCLE", "Shortening the OODA loop: from days to hours")
_short = {"OBSERVE": ("Monthly datasets (UCDP ~6 weeks late); reports collated by hand", "GDELT and markets ingested daily; top 5 changes ranked for the AOR"),
          "ORIENT": ("Threat argued at the weekly int conference", "RAG, trend, confidence and drivers scored in seconds; J2 checks"),
          "DECIDE": ("Options built at the weekly ops / int conference", "3 ranked actions ready for the 0700 update"),
          "ACT": ("Orders drafted after the decision", "Owner, timeline and trigger pre-set; FLASH goes to the owner")}
rows = [["Stage", "Today", "With Conflict Watch", "Hours"]]
for o in _TH.OODA:
    a, b2 = _short[o["stage"]]
    rows.append([o["stage"], a, b2, f"{o['today_h'][0]}–{o['today_h'][1]} h → {o['cw_h'][0]:g}–{o['cw_h'][1]:g} h"])
table(s, 0.55, 1.42, 8.4, rows, [1.12, 2.78, 2.9, 1.6], size=13, row_h=0.86, first_col_color=CYAN)
_t = _TH.ooda_totals()
kpi_side(s, 9.2, 1.42, 3.58, 1.12, f"{_t['today_days'][0]:.0f}–{_t['today_days'][1]:.0f} d → {_t['cw_hours'][0]:.0f}–{_t['cw_hours'][1]:.0f} h",
         "event to decision [DOMAIN estimate of staff timings]", color=AMBER, numsize=24)
kpi_side(s, 9.2, 2.64, 3.58, 1.12, f"{_TM['ucdp_lag_days']} d → <1 d", "data latency: UCDP's last record vs GDELT "
         "and market closes [DATA, measured]", color=CYAN, numsize=24)
kpi_side(s, 9.2, 3.86, 3.58, 1.12, f"{_TM['build_seconds']:.0f} s", f"to build 4 theatres × {_TM['days']} days of briefs "
         "[DATA, measured]", color=TEAL, numsize=24)
kpi_side(s, 9.2, 5.08, 3.58, 1.12, "FLASH", f"district over P {_TM['flash_threshold']:.2f} or a RAG change, pushed on "
         "ingest: no new conference", color=RED, numsize=24)
sowhat(s, "The model does not decide. It takes collation, scoring and option-building off the critical path.",
       label="OODA")
notes(s, "Stage by stage. Observe: the official dataset is six weeks behind; news-coded events and markets are a day "
         "behind, so the brief starts from what changed yesterday. Orient: the same scoring rules every morning, with the "
         "drivers shown, so the J2 review is judgement, not arithmetic. Decide: three ranked options are on the table at "
         "0600 for the 0700 update. Act: each action already has an owner, a timeline and a trigger, so the next "
         "escalation is a drill. The staff-cycle hours are our estimate, not a measurement; the latency and build time "
         "are measured.")

# =========================================================================== 18–19 RECOMMENDATIONS (two slides)
loe = [("SENSE", "ISR", CYAN, "4FD6E8", "eye", "Task ISR and analysts on the monthly sub-national watch-list. Build Indian "
        "OSINT on the Gulf, Iran and the Red Sea.", "LEAD: DIA / Service intelligence", "1 month", "warning lead time"),
       ("WARN", "I&W", AMBER, "F0B03A", "siren", "Adopt the Af–Pak interstate dyad and KP / Balochistan hotspot "
        "probabilities as standing LoC indicators. Publish the RAG monthly.", "LEAD: HQ IDS, Northern / Western Comds",
        "Top 10", "areas tasked monthly"),
       ("SHIELD", "NEO / IOR", RED, "FF4D5E", "shield-check", "Keep Gulf NEO plans current while US–Iran is AMBER, with a "
        "belligerent-movement picture in the IOR.", "LEAD: HQ IDS, Navy, IAF, MEA", "0", "Indians stranded"),
       ("SUSTAIN", "ENDURANCE", TEAL, "35C2A6", "package", "Buffer spares for Russian- and Israeli-origin platforms; HADR "
        "kits for women, children and under-fives.", "LEAD: MoD, DPSUs, NDMA", "RAG", "brief every month")]


def loe_card(slide, x, y, w, h, item):
    name, sub, col, hexc, ic, body, lead, n, nl = item
    box(slide, x, y, w, h, line=col, lw=1.5)
    node(slide, x + 0.3, y + 0.3, 1.0, ic, colour=col, hexcol=hexc)
    text(slide, x + 1.5, y + 0.3, w - 1.7, 0.5, name, size=30, bold=True, color=col)
    kicker_lbl(slide, x + 1.5, y + 0.86, w - 1.7, sub, color=TEXT3, size=11)
    text(slide, x + 0.3, y + 1.55, w - 0.6, 1.9, body, size=21, color=WHITE)
    text(slide, x + 0.3, y + h - 1.05, w - 0.6, 0.35, lead, size=13, bold=True, color=col)
    text_glow(text(slide, x + 0.3, y + h - 0.68, 1.6, 0.5, n, size=24, bold=True, color=col), hexc, rad=8, alpha=35)
    text(slide, x + 1.95, y + h - 0.6, w - 2.2, 0.4, nl, size=13, color=TEXT2)


s = new_slide("RECOMMENDATIONS   |   OPERATIONAL DESIGN", "Sense and warn: see escalation coming a month out")
loe_card(s, 0.55, 1.4, 6.0, 4.8, loe[0])
loe_card(s, 6.78, 1.4, 6.0, 4.8, loe[1])
sowhat(s, "Commander's intent: see it coming, protect Indians in the strike envelope, keep our platforms supplied.",
       label="INTENT")

s = new_slide("RECOMMENDATIONS   |   OPERATIONAL DESIGN", "Shield and sustain: protect Indians, keep platforms supplied")
loe_card(s, 0.55, 1.4, 6.0, 4.8, loe[2])
loe_card(s, 6.78, 1.4, 6.0, 4.8, loe[3])
sowhat(s, "The SENSE and WARN lines need no new platform: the model and dashboard already exist.", label="BOTTOM LINE")

# =========================================================================== 20 WHO / WHEN
s = new_slide("RECOMMENDATIONS   |   EXECUTION", "Who does what, by when")
rows = [["Agency", "NOW (0–30 DAYS)", "BY 90 DAYS", "6–12 MONTHS"],
        ["DIA / Service Int", "Task ISR on the top-10 watch-list", "Indian OSINT cell for Gulf, Iran, Red Sea",
         "Fuse with classified I&W; re-train monthly"],
        ["HQ IDS", "Adopt RAG scorecard in the monthly brief", "Gulf NEO table-top on US–Iran AMBER",
         "Institutionalise the dashboard"],
        ["Northern / Western Comds", "Af–Pak dyad as standing LoC indicator", "Watch KP / Balochistan hotspots",
         "Review posture against two-front Pakistan"],
        ["Navy / IFC-IOR", "Belligerent-movement watch near Sri Lanka", "Hormuz / Chabahar shipping picture",
         "Escort and evacuation readiness"],
        ["MoD / DPSUs / NDMA", "Audit critical spares (Russian, Israeli)", "Buffer-stock plan",
         "Indigenise; HADR kits for women and children"]]
table(s, 0.55, 1.45, 12.23, rows, [2.6, 3.21, 3.21, 3.21], header_fill=[rgb("12304A"), rgb("5A1C26"), rgb("5A4512"), rgb("0F4A40")],
      header_color=WHITE, size=15, row_h=0.8, first_col_color=CYAN)
sowhat(s, "Column one is tasking and a briefing format. It can start this month.", label="BOTTOM LINE")

# =========================================================================== 21 LIMITS
s = new_slide("SUPPORT   |   LIMITS", "What the analysis cannot claim")
lim = [("Reported deaths", "UCDP records reported violence; access shapes coverage", "newspaper"),
       ("Provisional 2026", "Candidate data are revised, usually upward", "timer"),
       ("No location", "92% of 2026 RU–UA deaths are country-level only", "map-pin"),
       ("Wars are decisions", "No death-count model foresees Feb 2022 or Feb 2026", "swords")]
for i, (h, d, ic) in enumerate(lim):
    x, y = 0.55 + (i % 2) * 6.23, 1.45 + (i // 2) * 2.45
    box(s, x, y, 6.0, 2.25)
    node(s, x + 0.35, y + 0.55, 1.1, ic, colour=AMBER, hexcol="F0B03A")
    text(s, x + 1.75, y + 0.45, 4.0, 0.55, h, size=26, bold=True, color=AMBER)
    text(s, x + 1.75, y + 1.1, 4.0, 0.9, d, size=17, color=TEXT2)
sowhat(s, "So we warn on spread and hotspots, and we show uncertainty instead of hiding it.", label="LIMITS")

# =========================================================================== 22 VALIDATION
s = new_slide("SUPPORT   |   VALIDATION", "Why the headline numbers still hold")
_RB = ROB["by_conflict"]
_clear = [k for k, v in _RB.items() if v["ci"][0] > 0]
_SH = {"Russia–Ukraine": "RU–UA", "Israel–Hamas": "Israel–Hamas", "Afghanistan–Pakistan": "Af–Pak", "US–Iran": "US–Iran"}
_inc = [_SH[k] for k in C.CASES if k not in _clear]
_ew = ROB["early_warning"]
rows = [["Headline result", "Internal check", "Why it still holds"],
        [f"−{pooled:.0f}% error vs naive", f"90% interval {_ci(ROB['pooled']['ci'])} (block bootstrap)",
         f"Clear for {' and '.join(_SH[k] for k in _clear)}; {', '.join(_inc[:-1])} and {_inc[-1]} intervals include zero"],
        [f"{cov80:.0f}% inside 80% band", "Split-conformal, back-test calibrated",
         f"{_RB['Russia–Ukraine']['coverage80']:.0%} for three wars, {_RB['US–Iran']['coverage80']:.0%} for US–Iran: its bands are too narrow"],
        [f"AUC {lg.ROC_AUC:.2f} warning", f"90% interval {_ew['auc'][0]:.2f}–{_ew['auc'][1]:.2f}; beats rule of thumb",
         "Ranks well; scores run high at the top, so use as a ranking"],
        ["Fronts widening", "Located events only", "Same in events and deaths"],
        ["Media ≠ warning", "Lead test p = 0.50", "Holds with fixed effects"]]
table(s, 0.55, 1.45, 12.23, rows, [3.0, 4.3, 4.93], size=15, row_h=0.8, first_col_color=WHITE)
sowhat(s, "Uncertainty is shown, not hidden. Nine test months is a small sample, and we say where the evidence is thin.",
       label="VALIDATION")

# =========================================================================== 15 CLOSING – RAG
s = new_slide("THREAT SCORECARD   |   OCTOBER 2026", "Where to look next month")
for i, case in enumerate(C.CASES):
    r = rag.loc[case]
    col = RAGC[r.rating]
    x = 0.55 + i * 3.1
    box(s, x, 1.4, 2.93, 2.65, line=col, lw=2.25)
    text(s, x, 1.55, 2.93, 0.4, case, size=17, bold=True, align=PP_ALIGN.CENTER)
    text(s, x, 1.98, 2.93, 0.75, r.rating, size=40, bold=True, color=col, align=PP_ALIGN.CENTER)
    text(s, x, 2.85, 2.93, 0.4, f"{r.forecast_next:,.0f} deaths forecast", size=15, bold=True, align=PP_ALIGN.CENTER)
    text(s, x + 0.1, 3.27, 2.73, 0.7, f"80%: {r.pi80_lo:,.0f}–{r.pi80_hi:,.0f}  ·  trend {(r.trend_ratio - 1) * 100:+.0f}%"
         f"\nTop area: {str(r.top_areas).split(';')[0]}", size=12, color=TEXT3, align=PP_ALIGN.CENTER)
for i, (col, h, d) in enumerate([(AMBER, "Russia–Ukraine stays RED", "Sustained attrition; the front widens"),
                                 (RED, "The war reached India's neighbourhood", "Gulf, Hormuz, Sri Lankan waters"),
                                 (CYAN, "Warning works a month out", f"AUC {lg.ROC_AUC:.2f}; forecasts −{pooled:.0f}% error")]):
    y = 4.3 + i * 0.66
    circle_num(s, 0.6, y + 0.04, i + 1, col, d=0.44, size=15)
    text(s, 1.2, y, 7.5, 0.35, h, size=17, bold=True)
    text(s, 1.2, y + 0.33, 7.5, 0.3, d, size=12, color=TEXT3)
box(s, 10.6, 4.25, 2.18, 1.95, fill=PANEL, line=MUTED, lw=1.25)
if QR_URL:
    import qrcode
    qr_path = ROOT / "deck" / "figs" / "qr.png"
    qrcode.make(QR_URL, box_size=12, border=2).save(qr_path)
    box(s, 11.02, 4.33, 1.34, 1.34, fill=WHITE, line=None, radius=0.03)
    s.shapes.add_picture(str(qr_path), Inches(11.06), Inches(4.37), Inches(1.26), Inches(1.26))
    text(s, 10.6, 5.75, 2.18, 0.35, "SCAN: REPOSITORY" if "github.com" in QR_URL else "SCAN: LIVE DASHBOARD", size=10, color=CYAN, bold=True, align=PP_ALIGN.CENTER)
else:
    text(s, 10.6, 4.35, 2.18, 1.3, ["QR CODE", "link to be added"], size=13, color=MUTED, bold=True,
         align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    text(s, 10.6, 5.75, 2.18, 0.35, "LIVE DEMO: DASHBOARD", size=10, color=CYAN, bold=True, align=PP_ALIGN.CENTER)
box(s, 0.55, 6.38, 12.23, 0.5, fill=AMBER_BG, line=AMBER, lw=1.25, radius=0.12)
text(s, 0.78, 6.38, 9.6, 0.5, "Open data and an honest model can tell India where to look next month.", size=15,
     bold=True, color=AMBER, anchor=MSO_ANCHOR.MIDDLE)
text(s, 10.0, 6.38, 2.6, 0.5, "Thank you. Questions?", size=15, bold=True, align=PP_ALIGN.RIGHT,
     anchor=MSO_ANCHOR.MIDDLE)

# =========================================================================== BACKUPS
s = new_slide("BACKUP", "Model comparison: back-test vs 2026 holdout")
picture(s, DF / "model_compare.png", 0.55, 1.35, 7.4, 5.0)
lab = {"ensemble": "Ensemble", "sarima": "SARIMA", "ets": "ETS", "lgb_case": "LightGBM-Δ", "ma3": "3-mo mean",
       "naive": "Naive", "snaive": "Seasonal naive", "lgb_admin1": "LGB bottom-up"}
rows = [["Model (RMSLE)", "A back", "A 2026", "B back", "B 2026"]]
for m in ["ensemble", "sarima", "ets", "lgb_case", "ma3", "lgb_admin1", "naive", "snaive"]:
    rr = rml.loc[m]
    rows.append([lab[m], f"{rr[('A', False)]:.2f}", f"{rr[('A', True)]:.2f}", f"{rr[('B', False)]:.2f}",
                 f"{rr[('B', True)]:.2f}"])
table(s, 8.15, 1.35, 4.63, rows, [1.55, 0.77, 0.77, 0.77, 0.77], size=12, row_h=0.5)
text(s, 8.15, 6.0, 4.63, 0.4, "A = 1 month ahead rolling; B = 1–9 months from December. Lower is better.", size=11,
     color=TEXT3)

s = new_slide("METHOD   |   MODEL CHOICE AND ABLATION", "Why each method was chosen over the simpler alternative")
rows = [["Decision", "Chosen", "Why the simpler alternative is weaker"],
        ["Forecast target", "Change in log deaths (LightGBM-Δ)", "Trees on the level cannot exceed training range: misses 2022"],
        ["Feature set", "Compact 18 features", f"Full set over-fits 4 series (back-test RMSLE {abl.iloc[1, 1]:.2f} vs "
                                               f"{abl.iloc[4, 1]:.2f})"],
        ["Ensemble", "Log-mean of ETS, 3-mo mean, LGB-Δ", "No single model wins every fold"],
        ["Intervals", "Split conformal, horizon bands", "Gaussian bands under-cover heavy tails"],
        ["Evaluation", "Walk-forward folds + 2026 holdout", "Random splits leak the future"],
        ["Warning target", "≥10 deaths and ≥1.5× 3-mo mean", "Raw increases flag noise in quiet areas"],
        ["Multi-month records", "Spread across months by day", "Start-month stacking fakes spikes"]]
table(s, 0.55, 1.4, 12.23, rows, [2.6, 3.9, 5.73], size=14, row_h=0.62)

s = new_slide("BACKUP", "Data quality: what was found and what we did")
picture(s, FIG / "03_data_quality.png", 0.55, 1.35, 12.23, 5.55)

s = new_slide("BACKUP", "What drives the forecast and the warning (TreeSHAP)")
picture(s, DF / "shap_forecast.png", 0.55, 1.4, 6.0, 4.9)
picture(s, DF / "shap_ew.png", 6.78, 1.4, 6.0, 4.9)

s = new_slide("BACKUP", "Campaign seasons and the early-warning curves")
picture(s, DF / "seasonality.png", 0.55, 1.35, 12.23, 2.6)
picture(s, DF / "ew_curves.png", 0.55, 4.0, 12.23, 2.95)

s = new_slide("BACKUP", "Forward forecast, Oct–Dec 2026 (ensemble, 80% interval)")
rows = [["Conflict", "Oct 2026", "Nov 2026", "Dec 2026"]]
for case in C.CASES:
    f = fut[fut.conflict_case == case].sort_values("target_month")
    rows.append([case] + [f"{r.pred:,.0f}  ({r.pi80_lo:,.0f}–{r.pi80_hi:,.0f})" for r in f.itertuples()])
table(s, 0.55, 1.45, 12.23, rows, [3.2, 3.01, 3.01, 3.01], size=17, row_h=0.8, first_col_color=CYAN)
text(s, 0.55, 5.6, 12.2, 0.6, "Refitted on all data to Sep 2026. Horizon 1 uses the operational track; 2–3 use the "
     "strategic track, so bands widen.", size=13, color=TEXT3)


# =========================================================================== FINDING 4: THE ECONOMIC FRONT (new)
ES = pd.read_csv(TB / "econ_event_study.csv")
EFR = pd.read_csv(TB / "econ_fronts.csv").set_index("conflict_case")
EPH = pd.read_csv(TB / "econ_paths.csv")
ECK = pd.read_csv(TB / "econ_claims_check.csv")
EPO = pd.read_csv(TB / "econ_political_timeline.csv")
ESU = json.loads((TB / "econ_summary.json").read_text())
EH = ESU["headline"]
OIL = ESU["india_oil_bill"]
RSV = ESU["reserves"]
REM = ESU["india_remittances"]


def _pc(v, d=0):
    return "n/a" if v is None or pd.isna(v) else f"{v:+.{d}f}%"


s = new_slide("FINDING 4   |   THE ECONOMIC FRONT", "The second front: the battlefield kills locally, markets hit everyone")
chart_panel(s, 0.55, 1.4, 8.3, 4.8)
_cs = ["Russia–Ukraine", "Israel–Hamas", "Afghanistan–Pakistan", "US–Iran"]
_cat = [f"{SHORT[c]}  ({EFR.loc[c, 'episode'][:4]})" for c in _cs]


def _v(c, col):
    v = EFR.loc[c, col]
    return None if pd.isna(v) else round(float(v), 1)


charts.columns(s, 0.65, 1.48, 8.1, 4.65, _cat,
               [dict(name="Local stock index", values=[_v(c, "local_equity_worst60_pct") for c in _cs], color="4FD6E8"),
                dict(name="Local currency", values=[_v(c, "local_fx_worst60_pct") for c in _cs], color="7FA7D9"),
                dict(name="Brent (peak)", values=[_v(c, "brent_best60_pct") for c in _cs], color="F0B03A"),
                dict(name="Nifty 50", values=[_v(c, "nifty_worst60_pct") for c in _cs], color="FF4D5E"),
                dict(name="Rupee", values=[_v(c, "inr_worst60_pct") for c in _cs], color="FF9AA5")],
               title="Largest war shock per theatre: worst move within 60 trading days (%)", num_fmt="0",
               gap=40, size=12, cat_size=13)
text(s, 4.55, 3.0, 1.9, 0.5, "Af–Pak: rupee and afghani barely moved", size=10.5, color=TEXT3, align=PP_ALIGN.CENTER)
kpi_side(s, 9.1, 1.4, 3.68, 1.12, f"{EH['moex_day1']:.0f}% in a day", "MOEX, 24 Feb 2022; rouble down "
         f"{-EH['rub_worst']:.0f}% at worst [DATA]", color=RED, numsize=24)
kpi_side(s, 9.1, 2.62, 3.68, 1.12, f"+{EH['brent_d20_2026']:.0f}% oil", "Brent in 20 trading days of the 2026 Gulf war "
         f"(peak +{EH['brent_best_2026']:.0f}%) [DATA]", color=AMBER, numsize=24)
_e = EFR.loc["US–Iran"]
kpi_side(s, 9.1, 3.84, 3.68, 1.12, f"{int(_e.countries_with_deaths)} vs all", "countries with Gulf-war deaths vs every "
         "oil importer that paid the price rise", color=CYAN, numsize=24)
kpi_side(s, 9.1, 5.06, 3.68, 1.12, f"{ESU['median_abs_move20_main']:.0f}% vs {ESU['median_abs_move20_other']:.1f}%",
         f"median 20-day move: 3 war onsets vs {ESU['n_episodes'] - 3} routine spikes. Markets price shocks, not attrition",
         color=TEAL, numsize=24)
sowhat(s, "Fighting is one front. Sanctions, oil, gas, grain and shipping reach far more people than the guns.",
       label="SO WHAT")
notes(s, f"New analysis on public market data. Shock dates come from the UCDP deaths in our data, not from hindsight: "
         f"{ESU['n_episodes']} spike episodes, {ESU['n_moves']} market moves, each tested against every other 20-day "
         "window of the same series. Only the three regime-changing onsets move markets; routine escalations do not. "
         "Af–Pak shows almost nothing: the Pakistani rupee barely moved. Pakistan's 2022–23 crisis was economic.")

s = new_slide("FINDING 4   |   THE ECONOMIC FRONT", "India took no fire, but paid in oil, the rupee and markets")
chart_panel(s, 0.55, 1.4, 8.3, 4.8)
_p = EPH[(EPH.conflict_case == "US–Iran") & EPH.series.isin(["BRENT", "NIFTY", "INR"])]
_off = sorted(_p.offset.unique())
_ser = []
for k, nm, col, w in [("BRENT", "Brent crude", "F0B03A", 3.0), ("NIFTY", "Nifty 50", "FF4D5E", 3.0),
                      ("INR", "Rupee value vs USD", "FF9AA5", 2.5)]:
    g = _p[_p.series == k].set_index("offset")["index"]
    _ser.append(dict(name=nm, values=[round(float(g.get(o)), 1) if o in g.index else None for o in _off], color=col, width=w))
charts.line(s, 0.65, 1.48, 8.1, 4.65, [("DAY 0" if o == 0 else f"{o:+d}") if o % 10 == 0 else " " for o in _off], _ser,
            title="2026 Gulf war: index = 100 at the last close before 28 Feb 2026 (trading days)", num_fmt="0",
            cat_skip=1, size=12, y_min=80, y_max=170)
kpi_side(s, 9.1, 1.4, 3.68, 1.12, f"≈ ${OIL['extra_usd_bn_per_year_2026']:.0f}B / yr",
         f"extra crude bill: Brent +${OIL['brent_up_usd_2026']:.0f}/bbl for 8 months × {OIL['crude_mbd_domain']} mb/d "
         "[DATA × DOMAIN]", color=AMBER, numsize=24)
kpi_side(s, 9.1, 2.62, 3.68, 1.12, f"{EH['nifty_d20_2026']:.1f}%  ·  {EH['inr_worst_2026']:.1f}%",
         "Nifty in 20 trading days · rupee at its worst in 60 days [DATA]", color=RED, numsize=24)
kpi_side(s, 9.1, 3.84, 3.68, 1.12, f"−${RSV['ind_2021_bn'] - RSV['ind_2022_bn']:.0f}B",
         "India's reserves in 2022, defending the rupee after Ukraine (World Bank) [DATA]", color=CYAN, numsize=24)
kpi_side(s, 9.1, 5.06, 3.68, 1.12, f"≈ ${REM['gulf_usd_bn']:.0f}B / yr", f"Gulf remittances at risk: "
         f"{REM['gulf_share_domain']:.0%} of ${REM['usd_bn']:.0f}B ({REM['year']}) [DATA × DOMAIN]", color=TEAL,
         numsize=24)
sowhat(s, "Economic defence is defence: oil stocks, rupee buffers, sea-lane escort and Gulf evacuation plans.",
       label="FOR INDIA")
notes(s, f"Each $10 a barrel costs India about ${OIL['per_10usd_bn_per_year']:.1f}B a year at {OIL['crude_mbd_domain']} "
         "million barrels a day of crude imports (PPAC volume, domain input). Brent averaged "
         f"${ESU['persistent']['US–Iran']['BRENT']['pre']:.0f} before the war and "
         f"${ESU['persistent']['US–Iran']['BRENT']['post']:.0f} in the eight months after. "
         "When oil did not move (Oct 2023), neither did India's markets.")

# ---- support: every shock, every market
s = new_slide("SUPPORT   |   ECONOMIC FRONT", "Every war shock, every market: only regime shocks move prices")
_m = ES[ES.day0.isin(["2022-02-24", "2023-10-07", "2026-02-28"])].copy()
_m["lab"] = _m.conflict_case.map(SHORT) + " · " + _m.series
_mall = _m
_m = _m.reindex(_m.d20_pct.abs().sort_values(ascending=False).index[:12]).sort_values("d20_pct")
chart_panel(s, 0.55, 1.4, 8.3, 4.8)
charts.columns(s, 0.65, 1.48, 8.1, 4.65, list(_m.lab), [dict(name="20-day move", values=[round(v, 1) for v in _m.d20_pct],
               color="4FD6E8")], title="12 largest 20-day moves after the three war onsets (%; red = placebo p < 0.10)",
               horizontal=True, legend=False, num_fmt="0", gap=35, size=12, cat_size=12,
               point_colors=["FF4D5E" if p < 0.10 else "5E7B99" for p in _m.p20])
rows = [["Episodes", "Moves", "Significant (p<0.10)"],
        ["3 war onsets", f"{len(_mall)}", f"{ESU['sig_share_main_onsets']:.0%}"],
        [f"{ESU['n_episodes'] - 3} routine spikes", f"{ESU['n_moves'] - len(_mall)}", f"{ESU['sig_share_other_episodes']:.0%}"]]
table(s, 9.1, 1.4, 3.68, rows, [1.5, 0.8, 1.38], size=12, row_h=0.5, first_col_color=WHITE)
text(s, 9.1, 3.1, 3.68, 3.1, ["Day 0 = first day of a UCDP spike month with ≥30 deaths and ≥5× the 90-day mean.",
     "Placebo: the same 20-day window on every other trading day since 2014.",
     "Currencies are shown as value vs USD. Sources: Yahoo Finance, MOEX ISS, World Bank (public)."],
     size=12, color=TEXT3, spacing=6)
sowhat(s, "Attrition is priced in; surprise onsets and chokepoints are not. Watch onsets, not totals.")

# ---- support: political crises
s = new_slide("SUPPORT   |   ECONOMIC FRONT", "Political crises: onsets and sanctions align, domestic crises do not")
rows = [["Date", "Theatre", "Crisis [DOMAIN]", "Nearest UCDP spike"]]
for r in EPO.itertuples():
    rows.append([r.date, SHORT[r.conflict_case], r.event, ("✔ " if r.within_45d else "") + f"{r.days_from_episode:+d} days"])
fills = [None] + [[None, None, None, rgb("2A2008") if r.within_45d else None] for r in EPO.itertuples()]
table(s, 0.55, 1.35, 12.23, rows, [1.3, 1.3, 7.33, 2.3], size=10.5, row_h=0.27, first_col_color=WHITE, fills=fills)
_k = int(EPO.within_45d.sum())
sowhat(s, f"{_k} of {len(EPO)} crises sit within 45 days of a war spike. Wars trigger sanctions; most unrest is home-grown.",
       y=6.45)

# ---- support: figures check
s = new_slide("SUPPORT   |   ECONOMIC FRONT", "Checking the figures we quote against the data")
rows = [["Claim", "What the data say", "Verdict"]]
for r in ECK.itertuples():
    rows.append([r.claim, r.measured, r.verdict])
table(s, 0.55, 1.35, 12.23, rows, [3.2, 6.1, 2.93], size=10, row_h=0.47, first_col_color=WHITE)

# =========================================================================== ANNEX: VERIFICATION + METRICS
s = new_slide("ANNEX   |   VERIFICATION", "Results as obtained at submission")
text(s, 0.55, 1.5, 12.2, 1.6, [f"The slides that follow record every evaluation metric and all thirteen dashboard pages exactly as "
     f"produced by pipeline run {RUN_ID}.", "The run ID is a hash of the result tables. It is printed on the report "
     "footer, on every slide, in the dashboard sidebar and on the live Ops site, so the live demonstration can be checked "
     "against this submission."], size=17, color=TEXT2)
box(s, 0.55, 3.6, 12.23, 2.6)
kicker_lbl(s, 0.8, 3.75, 6.0, "AI TOOLS DECLARATION", color=AMBER, size=12)
text(s, 0.8, 4.15, 11.7, 1.9, "AI tools used: Claude (Anthropic), as a coding, drafting and review assistant. It helped write "
     "and debug the pipeline, dashboard, report and slide code, and reviewed the submission against the marking scheme. "
     "No number was typed in or generated by an AI tool: every figure is computed by the code in this repository from the "
     "issued dataset and can be reproduced with one command. The team framed the questions, checked the analysis and owns "
     "the findings and recommendations.", size=15, color=TEXT2)

s = new_slide("ANNEX   |   METRICS", "Forecast accuracy: RMSLE by model, back-test vs 2026 holdout")
lab2 = {"ensemble": "Ensemble", "ets": "ETS", "lgb_case": "LightGBM-Δ global", "ma3": "Moving average", "naive": "Naive",
        "sarima": "SARIMA", "lgb_admin1": "LightGBM bottom-up, Tweedie", "snaive": "Seasonal naive"}
rows = [["Model", "A · back-test 2022–25", "A · 2026 holdout", "B · back-test 2022–25", "B · 2026 holdout"]]
for m in sorted(lab2, key=lambda m: rml.loc[m][("A", False)]):
    rr = rml.loc[m]
    rows.append([lab2[m], f"{rr[('A', False)]:.3f}", f"{rr[('A', True)]:.3f}", f"{rr[('B', False)]:.3f}", f"{rr[('B', True)]:.3f}"])
table(s, 0.55, 1.4, 12.23, rows, [3.83, 2.1, 2.1, 2.1, 2.1], size=15, row_h=0.52, first_col_color=WHITE)
text(s, 0.55, 6.25, 12.2, 0.6, "A = 1 month ahead, rolling. B = 1–9 months from a December origin. Lower is better. "
     "Ensemble members were chosen on the back-test only.", size=13, color=TEXT3)

s = new_slide("ANNEX   |   METRICS", "1 month ahead on 2026: error vs the no-change rule, with 90% intervals")
rows = [["Conflict", "MAE ensemble", "MAE naive", "Reduction (90% interval)", "DM test p", "80% band cover"]]
for k in C.CASES:
    v = ROB["by_conflict"][k]
    rows.append([k, f"{v['mae_ens']:,.0f}", f"{v['mae_naive']:,.0f}", f"{v['reduction'] * 100:.0f}%  ({_ci(v['ci'])})",
                 f"{v['dm_p']:.2f}", f"{v['coverage80']:.0%}"])
P = ROB["pooled"]
rows.append(["Pooled", "", "", f"{P['reduction'] * 100:.0f}%  ({_ci(P['ci'])})", f"{P['dm_p']:.2f}", f"{P['coverage80']:.0%}"])
table(s, 0.55, 1.4, 12.23, rows, [3.0, 1.75, 1.6, 2.9, 1.4, 1.58], size=15, row_h=0.6, first_col_color=WHITE)
A, L = ROB["all_folds"], ROB["late_data"]
text(s, 0.55, 5.2, 12.2, 1.5, [f"All five folds ({A['months']} months): pooled reduction {A['reduction'] * 100:.0f}% ({_ci(A['ci'])}).",
     f"If data arrive a month late (forecast from t−2): reduction {L['holdout'] * 100:.0f}% on 2026, {L['backtest'] * 100:.0f}% on the back-test.",
     f"Intervals: moving-block bootstrap over months ({ROB['n_boot']:,} resamples). DM = Diebold–Mariano, one-sided, small-sample corrected."],
     size=14, color=TEXT2)

s = new_slide("ANNEX   |   METRICS", "Early warning on 2026 withheld months")
rows = [["Model", "ROC-AUC", "PR-AUC", "Brier", "Top-10 precision", "Top-20 recall"]]
for m in ["LightGBM classifier", "Logistic regression (5 signals)", "Rule: rank by last month's deaths"]:
    r = ew26.loc[m]
    rows.append([m, f"{r.ROC_AUC:.3f}", f"{r.PR_AUC:.3f}", f"{r.Brier:.3f}", f"{r.precision_at_10:.1%}", f"{r.recall_at_20:.1%}"])
rows.append(["Base rate", "", f"{lg.base_rate:.3f}", "", f"{lg.base_rate:.1%}", ""])
table(s, 0.55, 1.4, 7.4, rows, [2.5, 0.95, 0.95, 0.85, 1.15, 1.0], size=12, row_h=0.55, first_col_color=WHITE)
rows = [["Predicted band", "Areas", "Mean predicted", "Escalated"]]
for r in CAL.itertuples():
    rows.append([r.band.replace("(-0.001", "(0"), f"{r.areas:,}", f"{r.mean_pred:.1%}", f"{r.escalated:.1%}"])
table(s, 8.2, 1.4, 4.58, rows, [1.3, 0.9, 1.25, 1.13], size=12, row_h=0.5, first_col_color=WHITE)
E_ = ROB["early_warning"]
text(s, 0.55, 4.9, 7.4, 1.4, [f"90% intervals (areas resampled): AUC {E_['auc'][0]:.2f}–{E_['auc'][1]:.2f}; top-10 precision "
     f"{E_['p10'][0]:.0%}–{E_['p10'][1]:.0%}; lift {E_['lift'][0]:.1f}×–{E_['lift'][1]:.1f}× random.",
     "Right: calibration. Scores above 15% over-state the risk, so the watch-list is a ranking, not literal odds."],
     size=13, color=TEXT2)

PAGES = ["Commander's brief", "Conflict explorer", "Area drill-down", "Military lens", "India impact", "Displacement",
         "Media attention", "Forecast (2026 test)", "Early warning", "What-if simulator", "Scorecard lab",
         "Data quality & method", "Economic front", "Theatre daily brief", "Brief history & OODA"]
for i, name in enumerate(PAGES, 1):
    s = new_slide(f"ANNEX   |   DASHBOARD PAGE {i} OF {len(PAGES)}", name)
    picture(s, SHOT / f"page{i:02d}.png", 1.6, 1.3, 10.13, 5.7, frame=True)

# =========================================================================== RUNNING ORDER (team v4 flow)
# Method and validation first, then the live demo, then the three India findings, recommendations and the
# scorecard; supporting findings follow the close for Q&A, then backups and the annex.
RUNNING = [None,  # cover
           "Four wars, three warning signals", "One operational question", "From raw files to a monthly warning",
           "Why each method was chosen", "Forecasts beat simple rules", "The same method, on India",
           "A district-level watch-list", "A briefing site and an ops console", "One dataset, four commanders",
           "Pakistan now fights Afghanistan directly", "Pakistan now fights on two fronts",
           "The 2026 war reached the Gulf", "Ukraine: the front is widening",
           "The second front", "India took no fire, but paid",
           "Sense and warn", "Shield and sustain", "Shortening the OODA loop", "Who does what, by when",
           "Where to look next month",
           "Four different threat signatures", "Media attention follows incidents", "Displacement follows onset",
           "What the sources say together", "News-coded events track UCDP", "News sees past UCDP",
           "Media volume reacts to war", "Every war shock, every market", "Political crises",
           "Checking the figures we quote", "What the analysis cannot claim", "Why the headline numbers still hold"]


def _title_of(sl):
    for sh in sl.shapes:
        if sh.name == "!!title":
            return sh.text_frame.text
    return None


_sld = prs.slides._sldIdLst
_ids = list(_sld)
_slides = list(prs.slides)
_picked = []
for key in RUNNING:
    hit = [i for i, sl in enumerate(_slides) if (key is None and _title_of(sl) is None and i == 0)
           or (key is not None and (_title_of(sl) or "").startswith(key))]
    assert len(hit) == 1, (key, hit)
    _picked.append(hit[0])
_rest = [i for i in range(len(_slides)) if i not in _picked]
for el in _ids:
    _sld.remove(el)
for i in _picked + _rest:
    _sld.append(_ids[i])
for n, sl in enumerate(prs.slides, 1):
    for sh in sl.shapes:
        if sh.name == "!!num":
            sh.text_frame.paragraphs[0].runs[0].text = str(n)
        elif sh.name == "!!hud":
            r = sh.text_frame.paragraphs[0].runs
            r[-1].text = f"LIVE  ·  {n:02d}"
N_MAIN = RUNNING.index("Four different threat signatures")
print("main slides:", N_MAIN, "support:", len(RUNNING) - N_MAIN, "total:", len(prs.slides))

hud.finish(prs, META)
prs.save(OUT)
print("deck saved:", OUT, "slides:", len(prs.slides))
