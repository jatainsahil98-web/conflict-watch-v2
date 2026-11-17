"""Re-export the report (v2)'s charts in a light print theme at the size they are printed.

    python report/make_report_figs.py   ->  report/figs/*.png   (needs the outputs of run_pipeline.py)

The dashboard and deck use a dark theme; on a white A4 page dark panels waste ink and read badly,
so the same figure functions are restyled here. No data is changed.
"""
from __future__ import annotations

import glob
import os
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src import config as C, insights, viz  # noqa: E402
from src.cleaning import load  # noqa: E402

OUT = ROOT / "report" / "figs"
OUT.mkdir(exist_ok=True)
if "BROWSER_PATH" not in os.environ:
    c = glob.glob("/opt/pw-browsers/chromium-*/chrome-linux64/chrome")
    if c:
        os.environ["BROWSER_PATH"] = c[0]

T = C.THEME
INK, INK2, GRID = "#1b2733", "#44566a", "#dfe5ec"
LIGHT_OF = {T["text"].lower(): INK, T["text2"].lower(): INK, T["text3"].lower(): INK2, "#ffffff": INK,
            T["bg"].lower(): "#ffffff", T["cyan"].lower(): "#0b8ea3", T["amber"].lower(): "#c77d00",
            T["violet"].lower(): "#6a4fd8", T["teal"].lower(): "#12957c", T["muted"].lower(): "#7b8da0"}


def _ink(col):
    return LIGHT_OF.get(str(col).lower(), col) if col else INK


def light(fig, w_in, h_in, name, font=13, legend=True, title=False, ml=None, px=150):
    fig.update_layout(paper_bgcolor="white", plot_bgcolor="white", font=dict(color=INK, size=font),
                      showlegend=legend, legend=dict(font=dict(color=INK, size=font - 1)),
                      margin=dict(l=ml or 58, r=14, t=44 if (title or legend) else 14, b=44))
    if not title:
        fig.update_layout(title_text="")
    else:
        fig.update_layout(title_font=dict(color=INK, size=font + 2))
    fig.update_xaxes(gridcolor=GRID, linecolor="#9aa9b8", tickfont=dict(color=INK2, size=font - 1),
                     title_font=dict(color=INK2, size=font))
    fig.update_yaxes(gridcolor=GRID, linecolor="#9aa9b8", tickfont=dict(color=INK2, size=font - 1),
                     title_font=dict(color=INK2, size=font))
    for a in fig.layout.annotations:
        a.font = dict(color=_ink(a.font.color if a.font else None), size=font)
    for tr in fig.data:
        if getattr(tr, "textfont", None) is not None and tr.textfont.color is not None and isinstance(tr.textfont.color, str):
            tr.textfont.color = _ink(tr.textfont.color)
        ln = getattr(tr, "line", None)
        if ln is not None and isinstance(ln.color, str) and ln.color.lower() in (T["text"].lower(), T["text2"].lower(),
                                                                                 T["text3"].lower(), "#ffffff"):
            ln.color = INK
        mk = getattr(tr, "marker", None)
        if mk is not None and isinstance(mk.color, str) and mk.color.lower() in (T["text"].lower(), "#ffffff"):
            mk.color = INK
    fig.write_image(OUT / f"{name}.png", width=int(w_in * px), height=int(h_in * px), scale=2)


ins = insights.run(save=False)
cm = pd.read_parquet(C.PROCESSED / "case_month.parquet")
preds = pd.read_parquet(C.PROCESSED / "forecast_preds.parquet")
future = pd.read_parquet(C.PROCESSED / "forecast_future.parquet")
e = load("events")
HALF, FULL = 4.6, 9.4

light(viz.fig_monthly_deaths(cm), HALF, 2.8, "monthly_deaths", font=11)
light(viz.fig_afpak_interstate(e), HALF, 2.8, "afpak_interstate", font=11, legend=False)
light(viz.fig_afpak(ins["afpak_provinces"]), HALF, 2.8, "afpak_provinces", font=10)
light(viz.fig_india_exposure(ins["india_exposure"]), HALF, 2.8, "india_exposure", font=10)
light(viz.fig_media_gap(ins["media"]), HALF, 2.8, "media_gap", font=10)
light(viz.fig_displacement(ins["displacement"]), HALF, 2.8, "displacement", font=10)
light(viz.fig_forecast_case(cm, preds, "Russia–Ukraine", track="A", future=future), HALF, 2.6, "forecast_ru", font=10)
light(viz.fig_forecast_case(cm, preds, "Afghanistan–Pakistan", track="A", future=future), HALF, 2.6, "forecast_afpak", font=10)
light(viz.fig_ew_curves(pd.read_parquet(C.PROCESSED / "early_warning_preds.parquet")), HALF, 2.6, "ew_curves", font=10)
light(viz.fig_shap(pd.read_csv(C.TAB_DIR / "shap_early_warning.csv"), title=""), HALF, 2.6, "shap_ew", font=10, legend=False, ml=150)
print("report figures:", sorted(p.name for p in OUT.glob("*.png")))
