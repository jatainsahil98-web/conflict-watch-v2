"""Presentation, version 2: 12 main slides for a 15-minute talk + backup slides.

    python deck/build_deck_v2.py   ->  deck/FCE_Conflict_Watch_Deck.pptx

Needs: run_pipeline.py, report/make_report_figs.py, report/build_report_v2.py (v2 figures),
scripts/build_site.py and the site screenshots in deck/shots_v2 (scripts/shoot_site_v2.js).
Every number is read from outputs/tables.
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
from pptx.enum.text import PP_ALIGN
from pptx.util import Emu, Inches, Pt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src import config as C  # noqa: E402

TB, RF, SH = C.TAB_DIR, ROOT / "report" / "figs", ROOT / "deck" / "shots_v2"
j = lambda f: json.loads((TB / f).read_text(encoding="utf-8"))
t = lambda f: pd.read_csv(TB / f)
RUN_ID = (TB / "run_id.txt").read_text().strip()
TEAM = "FCE"
MEMBERS = "Maj Shivam Mehta · Capt Siddharth Sangwan · Capt Sahil Singh"

NAVY, INK, MUTED, GOLD = RGBColor(0x07, 0x13, 0x1F), RGBColor(0x1B, 0x27, 0x33), RGBColor(0x5E, 0x7B, 0x99), RGBColor(0xF0, 0xB0, 0x3A)
RED, AMBER, GREEN, TEAL, WHITE = RGBColor(0xD7, 0x26, 0x3D), RGBColor(0xC7, 0x7D, 0x00), RGBColor(0x1F, 0x9E, 0x83), RGBColor(0x0B, 0x8E, 0xA3), RGBColor(0xFF, 0xFF, 0xFF)
RAGC = {"RED": RED, "AMBER": AMBER, "GREEN": GREEN}
FONT = "Calibri"

# ---------------------------------------------------------------------------
rag = t("rag_scorecard.csv").set_index("conflict_case")
rob = j("robustness.json"); pool, byc = rob["pooled"], rob["by_conflict"]
ewr = t("early_warning_scores.csv"); lg = ewr[(ewr.year == 2026) & (ewr.model == "LightGBM classifier")].iloc[0]
rule = ewr[(ewr.year == 2026) & (ewr.model == "Rule: rank by last month's deaths")].iloc[0]
pre = j("preregistration.json"); v26 = j("ew_variants_2026.json")
trip, tal = j("tripwire_summary.json"), t("tripwire_alerts.csv")
comp = t("completeness.csv"); ind = j("india_front.json"); seal = j("sealed_predictions.json")
rm = t("forecast_rmsle.csv"); hold = rm[rm.fold == 2026].groupby(["track", "model"]).RMSLE.mean().unstack(0)
dq = t("data_quality_log.csv"); abl = t("ablation_lgb.csv")
ov = t("insight_case_overview.csv").set_index("conflict_case")
live = pd.read_parquet(C.PROCESSED / "early_warning_live.parquet")
live = live[~live.admin1.str.startswith("(")].head(10)
facts = json.loads((ROOT / "web" / "public" / "data" / "facts.json").read_text(encoding="utf-8"))
pct = lambda x, d=0: f"{100 * x:.{d}f}%"
fmt = lambda x: f"{x:,.0f}"
ru90 = comp[(comp.case == "Russia–Ukraine") & (comp.days == 90)].share_known.iloc[0]
named = {"2016-09-18": "Uri", "2019-02-14": "Pulwama", "2025-04-22": "Pahalgam"}
trig = [x for x in ind["triggers"] if x["date"] in named]
_d10 = pd.read_csv(C.ROOT / "data" / "raw" / "extra" / "6. war_terror_violence_200k.csv", usecols=["country", "country_group", "adm_1"])
_d10 = _d10[_d10.country_group != "Focus country"]
N_CTY, N_AREA = _d10.country.nunique(), _d10.drop_duplicates(["country", "adm_1"]).shape[0]

prs = Presentation()
prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
BL = prs.slide_layouts[6]
W, H = prs.slide_width, prs.slide_height


def tb(s, x, y, w, h, text="", size=16, bold=False, color=INK, align=PP_ALIGN.LEFT, font=FONT):
    box = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box.text_frame
    tf.word_wrap = True
    lines = text if isinstance(text, list) else [text]
    for i, ln in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        runs = ln if isinstance(ln, list) else [(ln, {})]
        for r_text, st in runs:
            r = p.add_run()
            r.text = r_text
            r.font.size = Pt(st.get("size", size)); r.font.bold = st.get("bold", bold)
            r.font.color.rgb = st.get("color", color); r.font.name = font
        p.alignment = align
        p.space_after = Pt(st.get("after", 6) if runs else 6)
    return box


def rect(s, x, y, w, h, fill, line=None):
    r = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    r.fill.solid(); r.fill.fore_color.rgb = fill
    if line is None:
        r.line.fill.background()
    else:
        r.line.color.rgb = line
    r.shadow.inherit = False
    return r


def img(s, path, x, y, w=None, h=None):
    path = Path(path)
    iw, ih = Image.open(path).size
    if w and h:   # fit inside the box, keep aspect
        if iw / ih > w / h:
            h2 = w * ih / iw; y += (h - h2) / 2; h = h2
        else:
            w2 = h * iw / ih; x += (w - w2) / 2; w = w2
        return s.shapes.add_picture(str(path), Inches(x), Inches(y), Inches(w), Inches(h))
    return s.shapes.add_picture(str(path), Inches(x), Inches(y), width=Inches(w) if w else None, height=Inches(h) if h else None)


def table(s, x, y, w, rows, head, col_w=None, size=12, row_h=0.36, colors=None):
    shp = s.shapes.add_table(len(rows) + 1, len(head), Inches(x), Inches(y), Inches(w), Inches(row_h * (len(rows) + 1)))
    tbl = shp.table
    for ci, hcell in enumerate(head):
        c = tbl.cell(0, ci); c.text = hcell
        c.fill.solid(); c.fill.fore_color.rgb = NAVY
        p = c.text_frame.paragraphs[0]; p.runs[0].font.size = Pt(size); p.runs[0].font.bold = True
        p.runs[0].font.color.rgb = WHITE; p.runs[0].font.name = FONT
    for ri, row in enumerate(rows, start=1):
        for ci, v in enumerate(row):
            c = tbl.cell(ri, ci); c.text = str(v) if str(v) != "" else " "
            c.fill.solid(); c.fill.fore_color.rgb = RGBColor(0xF4, 0xF7, 0xFA) if ri % 2 == 0 else WHITE
            p = c.text_frame.paragraphs[0]; r = p.runs[0]
            r.font.size = Pt(size); r.font.name = FONT; r.font.color.rgb = INK
            if colors and (ri - 1, ci) in colors:
                r.font.color.rgb = colors[(ri - 1, ci)]; r.font.bold = True
    if col_w:
        for ci, cw in enumerate(col_w):
            tbl.columns[ci].width = Inches(cw)
    return tbl


SLIDE_NO = [0]


def slide(kicker, title, section="MAIN", notes=""):
    s = prs.slides.add_slide(BL)
    SLIDE_NO[0] += 1
    rect(s, 0, 0, 13.333, 1.05, NAVY)
    rect(s, 0, 1.05, 13.333, 0.05, GOLD)
    tb(s, 0.45, 0.12, 10.5, 0.3, kicker.upper(), size=11, bold=True, color=GOLD)
    tb(s, 0.45, 0.38, 12.4, 0.65, title, size=26, bold=True, color=WHITE)
    tb(s, 0.45, 7.08, 12.4, 0.3, f"TEAM {TEAM} · CONFLICT WATCH · UNCLASSIFIED – COMPETITION DATA ONLY · RUN {RUN_ID} · "
       f"{'BACKUP ' if section == 'BACKUP' else ''}{SLIDE_NO[0]}", size=9, color=MUTED)
    if notes:
        s.notes_slide.notes_text_frame.text = notes
    return s


def bullets(s, x, y, w, h, items, size=16):
    lines = []
    for it in items:
        if isinstance(it, tuple):
            lines.append([(it[0] + " ", {"bold": True, "color": NAVY, "size": size}), (it[1], {"size": size})])
        else:
            lines.append([("▪ " + it, {"size": size})])
    return tb(s, x, y, w, h, lines, size=size)


def deduce(s, y, deduction, action):
    rect(s, 0.45, y, 12.4, 0.82, RGBColor(0xFF, 0xF8, 0xEA))
    rect(s, 0.45, y, 0.07, 0.82, GOLD)
    tb(s, 0.65, y + 0.06, 12.1, 0.75, [[("DEDUCTION  ", {"bold": True, "color": AMBER, "size": 14}), (deduction, {"size": 14})],
                                      [("ACTION  ", {"bold": True, "color": RED, "size": 14}), (action, {"size": 14})]])


# ============================== MAIN (12) ===================================
# 1 Title
s = prs.slides.add_slide(BL); SLIDE_NO[0] += 1
rect(s, 0, 0, 13.333, 7.5, NAVY)
rect(s, 0.6, 1.55, 0.09, 2.6, GOLD)
tb(s, 0.9, 1.35, 11, 0.4, f"LT GEN MS SODHI MEDAL · DATA ANALYTICS COMPETITION 2026 · TEAM {TEAM}", size=14, bold=True, color=GOLD)
tb(s, 0.9, 1.85, 11.5, 1.2, "CONFLICT WATCH", size=60, bold=True, color=WHITE)
tb(s, 0.9, 3.05, 11.5, 1.0, "When and where will conflict deaths rise next, and what does it mean for India?", size=24, color=RGBColor(0xD5, 0xDE, 0xE8))
tb(s, 0.9, 4.6, 11.5, 0.5, MEMBERS, size=18, color=WHITE)
tb(s, 0.9, 5.1, 11.5, 0.5, f"Issued competition data only · UCDP to 30 Sep 2026, GDELT to 12 Nov 2026 · Run {RUN_ID}", size=14, color=RGBColor(0x9F, 0xB2, 0xC6))
tb(s, 0.9, 6.5, 11.5, 0.5, "AI tools declaration: Anthropic's Claude assisted with code, text and design; the team made every decision and checked every number.",
   size=11, color=RGBColor(0x9F, 0xB2, 0xC6))
s.notes_slide.notes_text_frame.text = "0:00–0:30. Team, question, one line: four wars, two clocks, one exposed neighbour."

# 2 BLUF
s = slide("Bottom line up front · Oct 2026", "Russia–Ukraine RED; Af–Pak AMBER is India's front; watch US–Iran by the day",
          notes="0:30–2:00. Read the table left to right. Stress: 29% fewer errors on data the model never saw.")
rows, cols = [], {}
for i, c in enumerate(C.CASES):
    r = rag.loc[c]
    rows.append([c, r.rating, fmt(r.forecast_next), f"{fmt(r.pi80_lo)}–{fmt(r.pi80_hi)}", f"{(r.trend_ratio - 1) * 100:+.0f}%", r.top_areas.split("; ")[0]])
    cols[(i, 1)] = RAGC[r.rating]
table(s, 0.45, 1.35, 12.4, rows, ["Conflict", "Rating", "Forecast deaths", "80% range", "vs last 6 months", "Top watch area"],
      col_w=[2.6, 1.3, 1.9, 2.0, 2.0, 2.6], size=15, row_h=0.45, colors=cols)
for i, (v, l) in enumerate([(pct(pool["reduction"]), "fewer forecast errors than 'no change' on withheld 2026"),
                            (f"{lg.precision_at_10 / lg.base_rate:.1f}×", "top-10 watch-list vs chance"),
                            (f"{trip['red_confirmed']}/{trip['red_episodes']}", "news tripwire alerts confirmed (p = %.3f)" % trip["p_value"])]):
    x = 0.45 + i * 4.18
    rect(s, x, 3.85, 4.0, 1.25, RGBColor(0xF4, 0xF7, 0xFA))
    tb(s, x + 0.15, 3.88, 3.8, 0.7, v, size=34, bold=True, color=TEAL)
    tb(s, x + 0.15, 4.58, 3.8, 0.5, l, size=13, color=INK)
bullets(s, 0.45, 5.3, 12.4, 1.7, [("1 SENSE", "Task ISR on the monthly top-10 areas: Kandahar, Kunar, Kabul lead."),
                                  ("2 WARN", "Any J&K attack with 15+ deaths starts a 15-day escalation watch."),
                                  ("3 SHIELD", "Gulf evacuation and sea lanes: act the day the tripwire turns RED, not six weeks later.")], size=16)

# 3 Questions and data
s = slide("Problem understanding · issued data only", "Five questions, each tied to a decision; twelve files, never joined on event IDs",
          notes="2:00–3:00. Mention: all of 2026 withheld from every modelling choice.")
bullets(s, 0.45, 1.35, 6.2, 5.6, [("Q1", "How intense is each war, and where is it heading? → watch level"),
                                  ("Q2", "Which areas escalate next month? → ISR tasking"),
                                  ("Q3", "Can we see a change of state before deaths are published? → warning time"),
                                  ("Q4", "How far can the record be trusted? → confidence"),
                                  ("Q5", "What touches India: Pakistan, the Gulf, the sea lanes? → plans"),
                                  ("Rule", "All of 2026 withheld; choices made on the 2022–25 back-test only.")], size=16)
table(s, 6.9, 1.35, 6.0, [["D1", "UCDP events 2014–Sep 2026", fmt(ov.events.sum())], ["D2", "UCDP source references", "85,406"],
                          ["D3–D5", "UNHCR, IDMC, UNRWA displacement", "26,215"], ["D6", "World Bank context", "1,764"],
                          ["D7–D8", "GDELT, Feb–Nov 2026", "13,507,238"], ["D9", "Middle East weekly (ACLED-style)", "149,825"],
                          ["D10", "UCDP long file 1989–2025", "200,000"], ["D11–D12", "Pre-joined panels (audited)", "3,467"]],
      ["ID", "Issued file", "Rows"], col_w=[1.1, 3.4, 1.5], size=13, row_h=0.42)

# 4 Data preparation
s = slide("Data preparation and feature engineering", f"{len(dq)} logged checks; nothing deleted, nothing missing turned into zero",
          notes="3:00–4:15. Pick two: multi-month records spread by day; FATA→KP harmonised; panel showed 0 deaths in 2026.")
sel = dq[dq.id.isin(["DQ05", "DQ07", "DQ10", "DQ13", "DQ14", "DQ15"])]
table(s, 0.45, 1.35, 7.6, [[r.id, r.check[:58], fmt(r.rows_affected)] for r in sel.itertuples()], ["ID", "Issue found", "Rows"],
      col_w=[0.8, 5.8, 1.0], size=12, row_h=0.5)
bullets(s, 8.3, 1.35, 4.6, 5.6, [("Imputation", "true zeros only where UCDP has no event; blank areas → explicit '(unspecified)'; GDELT gap 1–16 May left missing."),
                                 ("Joins", "providers meet only on country and day/week/month/year."),
                                 ("Features", "log deaths and lags, 3/6/12-month means, momentum, volatility, months since last death, reporting intensity, season; area model adds conflict and country tempo."),
                                 ("Dropped", "a 40-feature set with macro and displacement overfit (ablation, backup).")], size=14)

# 5 Four wars
s = slide("Analysis · four wars, four shapes", "One watch level cannot fit all four wars",
          notes="4:15–5:15. RU–UA flat 6–8k/month; IL–Hamas down after ceasefire; Af–Pak rising; US–Iran sudden.")
img(s, RF / "monthly_deaths.png", 0.45, 1.3, 6.2, 4.4)
img(s, RF / "afpak_interstate.png", 6.75, 1.3, 6.1, 4.4)
deduce(s, 5.95, f"RU–UA holds {pct(ov.loc['Russia–Ukraine'].deaths_best / ov.deaths_best.sum())} of deaths and is flat; Af–Pak passed its 2025 total by Sep; "
                f"since Oct 2025 the two governments fight each other.",
       "attrition watch for RU–UA, onset watch for US–Iran, standing watch for Af–Pak.")

# 6 India's front
s = slide("Analysis · India's own front (D10)", "After Uri, Pulwama and Pahalgam, state fighting followed in 11–15 days",
          notes="5:15–6:30. Floors, not totals; a pattern to watch, not proof.")
img(s, RF / "afpak_provinces.png", 0.45, 1.3, 6.0, 4.3)
table(s, 6.7, 1.4, 6.2, [[named[x["date"]], x["date"], f"{x['deaths']} ({x['civilians']})", x["state_deaths_45d_before"], x["state_deaths_45d_after"],
                          x["days_to_state_fighting"]] for x in trig],
      ["Attack", "Date", "Deaths (civ)", "State, 45d before", "45d after", "Days"], col_w=[1.1, 1.2, 1.1, 1.0, 0.9, 0.9], size=12, row_h=0.5)
tb(s, 6.7, 3.6, 6.2, 1.9, ["Pakistan fights the TTP inside (KP, Balochistan) and Afghanistan across the Durand Line.",
                           "D10 keeps only deadlier records outside focus countries: these are floors. Cross-border firing was routine in 2016–20."], size=13, color=MUTED)
deduce(s, 5.95, "a stretched Pakistan raises the risk of miscalculation on the LoC.",
       "treat Af–Pak hotspots as LoC indicators; start a 15-day watch after any J&K attack with 15+ deaths.")

# 7 Neighbourhood + lag
s = slide("Analysis · neighbourhood and trust", "The 2026 war reached the Gulf and Sri Lanka; RU–UA deaths arrive late",
          notes="6:30–7:30. Only 40% of RU–UA deaths are known at 90 days: the 2026 'decline' is reporting.")
img(s, RF / "india_exposure.png", 0.45, 1.3, 6.2, 4.4)
img(s, RF / "completeness.png", 6.75, 1.3, 6.1, 4.4)
deduce(s, 5.95, f"US–Iran deaths were recorded in {facts['india']['usir_countries'][1]} countries in 2026; only {pct(ru90)} of RU–UA deaths are known 90 days on.",
       "keep Gulf NEO plans live; brief recent months as floors, never as a fall.")

# 8 Forecast model
s = slide("Model · monthly forecast", f"{pct(pool['reduction'])} fewer errors than 'no change' on withheld 2026",
          notes="7:30–9:00. Three members with different errors; Δ target won the ablation; conformal bands.")
table(s, 0.45, 1.35, 6.4, [["Ensemble (adopted)", f"{hold.loc['ensemble', 'A']:.3f}", pct(pool["reduction"]), f"{pool['dm_p']:.3f}"],
                           ["No change (naive)", f"{hold.loc['naive', 'A']:.3f}", "–", "–"],
                           ["ETS alone", f"{hold.loc['ets', 'A']:.3f}", "", ""], ["LightGBM-Δ alone", f"{hold.loc['lgb_case', 'A']:.3f}", "", ""]],
      ["2026, 1 month ahead", "RMSLE", "MAE cut", "DM p"], col_w=[2.6, 1.2, 1.3, 1.3], size=13, row_h=0.45)
bullets(s, 0.45, 3.85, 6.4, 3.0, [("Members", "3-month mean · damped ETS on log deaths · LightGBM-Δ (change in log deaths, pooled, L1)."),
                                  ("Why", "4 series × ~150 months: too few for deep models; members fail differently."),
                                  ("Bands", f"split-conformal from real past errors; 80% coverage {pct(pool['coverage80'])} on 2026."),
                                  ("Limit", "cannot forecast an onset (US–Iran Feb 2026) → next slide.")], size=14)
img(s, RF / "forecast_ru.png", 7.05, 1.3, 5.8, 2.75)
img(s, RF / "forecast_afpak.png", 7.05, 4.15, 5.8, 2.75)

# 9 Tripwire
s = slide("Model · the fast clock", f"A news tripwire flagged the US–Iran war on day 0: {trip['red_confirmed']} of {trip['red_episodes']} alerts confirmed",
          notes="9:00–10:15. Rules fixed before testing. Permutation test vs random dates. It misses routine insurgency.")
img(s, RF / "tripwire_usir.png", 0.45, 1.3, 7.3, 4.2)
alerts = tal.sort_values("date")
table(s, 7.95, 1.35, 4.9, [[a.date, a.case.replace("Afghanistan–Pakistan", "Af–Pak"), a.light, "yes" if a.confirmed else "false alarm"] for a in alerts.itertuples()],
      ["Date", "Conflict", "Light", "Confirmed"], col_w=[1.3, 1.4, 0.9, 1.3], size=11, row_h=0.38,
      colors={(i, 2): (RED if a.light == "RED" else AMBER) for i, a in enumerate(alerts.itertuples())})
deduce(s, 5.95, f"RED = violent news ≥4× its 14-day median. Chance would confirm {trip['perm_mean_hits']:.1f}; p = {trip['p_value']:.3f}. "
                f"Misses most routine insurgent spikes.",
       "act on RED the same day; do not wait for casualty data.")

# 10 Escalation warning
s = slide("Model · where next", "Learning from the wider world: a pre-registered upgrade",
          notes="10:15–11:30. Choice written down before 2026 was scored; hash in the file. Calibration added after, disclosed.")
A = v26["A cases_only"][0]
table(s, 0.45, 1.35, 7.0, [["Competition-day (cases only)", f"{A['auc']:.3f}", f"{A['pr']:.3f}", pct(A["p10"], 1)],
                           ["v2: cases + world areas", f"{lg.ROC_AUC:.3f}", f"{lg.PR_AUC:.3f}", pct(lg.precision_at_10, 1)],
                           ["Rule: last month's deaths", f"{rule.ROC_AUC:.3f}", f"{rule.PR_AUC:.3f}", pct(rule.precision_at_10, 1)]],
      ["2026 escalation (222 areas)", "ROC-AUC", "PR-AUC", "Top-10 prec."], col_w=[3.2, 1.2, 1.2, 1.4], size=13, row_h=0.45)
bullets(s, 0.45, 3.4, 7.0, 3.5, [("Label", f"next month ≥{C.ESCALATION_MIN_DEATHS} deaths and ≥{C.ESCALATION_RATIO}× the 3-month mean (base rate {pct(lg.base_rate, 1)})."),
                                 ("Transfer", f"{N_AREA:,} areas in {N_CTY} other countries from D10, training only; focus countries removed."),
                                 ("Pre-registered", f"rule and choice hashed before scoring 2026 ({pre['sha256'][:10]}…)."),
                                 ("Sealed", f"Oct–Dec forecasts and list hashed ({seal['sha256'][:10]}…) to score later.")], size=14)
table(s, 7.7, 1.35, 5.15, [[i + 1, r.admin1.replace(" province", "").replace(" oblast", ""), r.conflict_case.replace("Afghanistan–Pakistan", "Af–Pak"),
                            pct(r.p_escalation)] for i, r in enumerate(live.head(10).itertuples())],
      ["#", "Area", "Conflict", "P(esc)"], col_w=[0.5, 2.2, 1.45, 1.0], size=12, row_h=0.4)

# 11 Ops site
s = slide("Innovation and tools · live demonstration", "One screen for the commander; depth on demand",
          notes="11:30–13:30 LIVE DEMO. Open picker → CDS → MORE DETAIL (D) → WTC → Ops Console ▸ Warning → Fast clock chapter. Screens below match the live build.")
img(s, SH / "commander_CDS.png", 0.45, 1.3, 7.6, 4.3)
img(s, SH / "view_picker.png", 8.25, 1.3, 4.6, 2.1)
img(s, SH / "console_warning.png", 8.25, 3.5, 4.6, 2.1)
bullets(s, 0.45, 5.75, 12.4, 1.3, ["Single offline HTML file + Streamlit app · CDS and two notional theatre views (WTC, MTC) · three depths · Ops console with "
                                   "brief, theatre, warning, map, area, forecast, what-if, scorecard, data quality · ratings re-checked against the pipeline on load"], size=14)

# 12 Recommendations
s = slide("Recommendations", "Each action has evidence, a trigger and a confidence level",
          notes="13:30–15:00. Close on ADAPT: score the sealed claims when UCDP publishes. Thank the panel.")
recs = [["SENSE", "ISR on monthly top-10 areas; daily tripwire", f"Top-10 {lg.precision_at_10 / lg.base_rate:.1f}× chance; 4/5 alerts", "Monthly list; RED", "Medium"],
        ["WARN", "Af–Pak hotspots + J&K 15+ deaths = LoC indicators", "11–15 days to state fighting", "Af–Pak AMBER; J&K attack", "Medium"],
        ["SHIELD", "Gulf NEO and sea lanes on RED", f"War reached {facts['india']['usir_countries'][1]} countries; RED on day 0", "US–Iran RED/AMBER", "High"],
        ["SUSTAIN", "Russian-platform spares for a long war (DOMAIN)", "RU–UA RED, 6–8k deaths/month", "RU–UA stays RED", "Medium"],
        ["ADAPT", "Brief recent months as floors; score sealed claims", f"{pct(ru90)} of RU–UA deaths known at 90 d", "Each UCDP release", "High"]]
table(s, 0.45, 1.35, 12.4, recs, ["Line", "Action", "Evidence", "Trigger", "Confidence"], col_w=[1.3, 4.2, 3.3, 2.4, 1.2], size=14, row_h=0.62)
tb(s, 0.45, 5.4, 12.4, 1.5, ["Limits: 2026 UCDP data are provisional; four series give small samples; the tripwire rests on 5 alerts; theatres are notional.",
                             "Reproduce: python run_pipeline.py → python scripts/export_web.py → python scripts/check_submission.py"], size=13, color=MUTED)

# ============================== BACKUP =====================================
s = slide("Backup · forecast ablation", "Why LightGBM-Δ: the change target and compact features won the back-test", section="BACKUP")
table(s, 0.45, 1.35, 12.4, [[r[0], f"{r[1]:.3f}", f"{r[2]:.3f}"] for r in abl.itertuples(index=False)], list(abl.columns), col_w=[7.4, 2.5, 2.5], size=14, row_h=0.5)
table(s, 0.45, 5.0, 12.4, [[c, pct(byc[c]["reduction"]), f"{pct(byc[c]['ci'][0])} to {pct(byc[c]['ci'][1])}", f"{byc[c]['dm_p']:.3f}", pct(byc[c]["coverage80"])] for c in C.CASES],
      ["2026 by conflict", "MAE cut", "90% interval", "DM p", "80% coverage"], col_w=[3.4, 2.0, 3.0, 2.0, 2.0], size=13, row_h=0.36)

s = slide("Backup · escalation warning detail", "Ranking curves and drivers on 2026", section="BACKUP")
img(s, RF / "ew_curves.png", 0.45, 1.3, 6.2, 4.6)
img(s, RF / "shap_ew.png", 6.75, 1.3, 6.1, 4.6)
tb(s, 0.45, 6.05, 12.4, 0.9, "Back-test variants (2023–25, chosen on PR-AUC): " + "; ".join(
    f"{k.split(' ', 1)[1]} {sum(r['pr'] for r in v) / len(v):.3f}" for k, v in pre["backtest_2023_2025"].items()), size=12, color=MUTED)

s = slide("Backup · data-quality log", "Every issue, the rows affected and the action", section="BACKUP")
dqi = dq[dq.rows_affected > 0]
table(s, 0.45, 1.3, 12.4, [[r.id, r.table, r.check[:60], fmt(r.rows_affected), r.action[:70]] for r in dqi.itertuples()],
      ["ID", "Table", "Check", "Rows", "Action"], col_w=[0.7, 2.4, 4.1, 0.9, 4.3], size=8, row_h=0.2)

s = slide("Backup · attention and displacement", "News follows politics; displacement follows lethality", section="BACKUP")
img(s, RF / "media_gap.png", 0.45, 1.3, 6.2, 4.6)
img(s, RF / "displacement.png", 6.75, 1.3, 6.1, 4.6)

s = slide("Backup · scorecard rules and site screens", "Ratings follow written rules; the site re-checks them", section="BACKUP")
bullets(s, 0.45, 1.35, 5.6, 5.5, ["Intensity: forecast ≥1,000 → 2 points; ≥100 → 1",
                                  "Trend vs last 6 months: ≥+20% → +1; ≤−20% → −1",
                                  "Hotspots: areas with P(escalation) ≥15%: ≥3 → 2; ≥1 → 1",
                                  "Spread (more countries than last year) +1; volatility (a 1,000-death month in 12) +1",
                                  "RED if forecast ≥1,000 or points ≥5 · AMBER if points ≥2 · else GREEN",
                                  "US–Iran: spread +1, volatility +1, trend −1 = 1 → GREEN; the tripwire guards its onset"], size=15)
img(s, SH / "console_scorecard.png", 6.3, 1.3, 6.55, 2.75)
img(s, SH / "commander_WTC.png", 6.3, 4.15, 6.55, 2.75)

s = slide("Backup · reproducibility and integrity", "One command rebuilds everything; hashes make claims checkable", section="BACKUP")
bullets(s, 0.45, 1.35, 12.4, 5.5, [("Pipeline", "python run_pipeline.py: clean → features → insights → forecast + warning → scorecard + v2 → figures (seed 42)."),
                                   ("Site", "python scripts/export_web.py stops if any headline number drifts; python scripts/build_site.py builds the offline file."),
                                   ("Gate", "python scripts/check_submission.py: report ≤10 pages, team name on every product, code included, AI declaration, no outside data."),
                                   ("Run ID", f"{RUN_ID} = hash of the result tables; printed on every product."),
                                   ("Pre-registration", f"outputs/tables/preregistration.json, sha256 {pre['sha256'][:24]}…"),
                                   ("Sealed claims", f"outputs/tables/sealed_predictions.json, sha256 {seal['sha256'][:24]}…"),
                                   ("AI tools", "Anthropic's Claude assisted with code, text and design; the team made every decision and checked every number.")], size=15)

out = ROOT / "deck" / "FCE_Conflict_Watch_Deck.pptx"
prs.save(out)
print("deck:", out.name, "|", len(prs.slides), "slides (12 main + backup) | run", RUN_ID)
