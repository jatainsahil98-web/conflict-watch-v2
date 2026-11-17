"""Re-export the deck's charts at slide proportions with large fonts (legible over a video call).

    python deck/make_deck_figs.py   ->  deck/figs/*.png   (needs the outputs of run_pipeline.py)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src import config as C, insights, viz  # noqa: E402
from src.cleaning import load  # noqa: E402

OUT = ROOT / "deck" / "figs"
OUT.mkdir(exist_ok=True)
if "BROWSER_PATH" not in os.environ:
    import glob
    c = glob.glob("/opt/pw-browsers/chromium-*/chrome-linux64/chrome")
    if c:
        os.environ["BROWSER_PATH"] = c[0]


def big(fig, w_in, h_in, name, font=19, legend=True, keep_title=False, px_per_in=150, ml=70):
    fig.update_layout(font=dict(size=font), legend=dict(font=dict(size=font - 2)), showlegend=legend,
                      margin=dict(l=ml, r=30, t=60 if keep_title else 30, b=60))
    fig.update_annotations(font_size=font - 1)
    if not keep_title:
        fig.update_layout(title_text="")
    fig.update_xaxes(tickfont=dict(size=font - 2), title_font=dict(size=font - 1))
    fig.update_yaxes(tickfont=dict(size=font - 2), title_font=dict(size=font - 1))
    fig.write_image(OUT / f"{name}.png", width=int(w_in * px_per_in), height=int(h_in * px_per_in), scale=2)


ins = insights.run(save=False)
cm = pd.read_parquet(C.PROCESSED / "case_month.parquet")
preds = pd.read_parquet(C.PROCESSED / "forecast_preds.parquet")
future = pd.read_parquet(C.PROCESSED / "forecast_future.parquet")
e = load("events")

big(viz.fig_monthly_deaths(cm), 8.3, 4.8, "monthly_deaths")
big(viz.fig_front_geography(ins["front_geography"]), 8.3, 4.8, "front_geography", font=18)
big(viz.fig_afpak_interstate(e), 8.3, 2.45, "afpak_interstate", font=17)
big(viz.fig_afpak(ins["afpak_provinces"]), 8.3, 2.45, "afpak_provinces", font=16)
big(viz.fig_media_scatter(ins["media"]), 8.3, 4.8, "media_scatter")
big(viz.fig_displacement(ins["displacement"]), 8.3, 4.8, "displacement", font=16)
big(viz.fig_forecast_case(cm, preds, "Russia–Ukraine", track="A", future=future), 8.3, 2.45, "forecast_ru", font=16,
    keep_title=True)
big(viz.fig_forecast_case(cm, preds, "Afghanistan–Pakistan", track="A", future=future), 8.3, 2.45, "forecast_afpak",
    font=16, keep_title=True)
m = viz.fig_country_map(ins["country_deaths"])
m.update_layout(title_text="", margin=dict(l=0, r=0, t=0, b=0))
m.write_image(OUT / "map.png", width=1110, height=730, scale=2)
print("deck figures:", sorted(p.name for p in OUT.glob("*.png")))

# backup slides
rmsle = pd.read_csv(C.TAB_DIR / "forecast_rmsle.csv")
big(viz.fig_model_compare(rmsle), 7.4, 5.0, "model_compare", font=14, ml=330)
big(viz.fig_shap(pd.read_csv(C.TAB_DIR / "shap_lgb_case.csv"), title="Forecast (LightGBM-Δ)"), 6.0, 4.9,
    "shap_forecast", font=15, keep_title=True, ml=190, legend=False)
big(viz.fig_shap(pd.read_csv(C.TAB_DIR / "shap_early_warning.csv"), title="Escalation warning"), 6.0, 4.9,
    "shap_ew", font=15, keep_title=True, ml=190, legend=False)
big(viz.fig_seasonality(ins["seasonality"]), 12.2, 2.6, "seasonality", font=15, ml=190)
big(viz.fig_ew_curves(pd.read_parquet(C.PROCESSED / "early_warning_preds.parquet")), 12.2, 2.95, "ew_curves", font=15)
print("backup figures done")

# ------------------------------------------------------------------ data for native (animated) PowerPoint charts
import json  # noqa: E402

import numpy as np  # noqa: E402

D: dict = {}
mm = sorted(cm.month.unique())
D["monthly"] = dict(months=[pd.Timestamp(x).strftime("%Y-%m") for x in mm],
                    series={c: cm[cm.conflict_case == c].set_index("month").deaths.reindex(mm).fillna(0)
                            .clip(lower=1).round(0).tolist() for c in C.CASES})
fg = ins["front_geography"]
fd = fg[fg.year >= 2021]
order = fd[fd.year == fd.year.max()].sort_values("share", ascending=False).area.tolist()
order = [a for a in order if a != "Other areas"] + ["Other areas"]
yrs = sorted(fd.year.unique())
D["front"] = dict(years=[int(y) for y in yrs], areas=[a.replace(" oblast", "") for a in order],
                  share={a.replace(" oblast", ""): fd[fd.area == a].set_index("year").share.reindex(yrs).fillna(0)
                         .mul(100).round(2).tolist() for a in order})
f = e[(e.conflict_case == "Afghanistan–Pakistan") & (e.case_scope == "Focal")]
im = f.groupby("month").deaths_best.sum().reindex(pd.date_range("2022-01-01", C.PANEL_END, freq="MS"), fill_value=0)
D["interstate"] = dict(months=[x.strftime("%b %y") for x in im.index], deaths=im.round(0).tolist())
ap = ins["afpak_provinces"]
ap = ap[ap.year >= 2016].copy()
top = ap.groupby("admin1").deaths.sum().nlargest(6).index
ap["area"] = np.where(ap.admin1.isin(top), ap.country_iso3 + " · " + ap.admin1.str.replace(" province", ""), "Other")
pv = ap.pivot_table(index="year", columns="area", values="deaths", aggfunc="sum").fillna(0)
cols = sorted(pv.columns, key=lambda a: (a == "Other", a))
D["afpak_prov"] = dict(years=[int(y) for y in pv.index], areas=cols, deaths={a: pv[a].round(0).tolist() for a in cols})
md = ins["media"]
D["media"] = {c: dict(events=md[md.conflict_case == c].n_events.clip(lower=1).tolist(),
                      sources=md[md.conflict_case == c].n_sources.clip(lower=1).tolist(),
                      deaths=md[md.conflict_case == c].deaths.clip(lower=1).round(0).tolist()) for c in C.CASES}
ds = ins["displacement"]
D["displacement"] = {}
for iso in ("UKR", "AFG", "PSE", "PAK", "IRN", "RUS"):
    x = ds[ds.iso3 == iso].sort_values("year")
    D["displacement"][viz.NAMES[iso]] = dict(
        years=x.year.astype(int).tolist(),
        total=((x.refugees.fillna(0) + x.asylum_seekers.fillna(0) + x.idps.fillna(0)) / 1e6).round(3).tolist())
D["forecast"] = {}
for case in ("Russia–Ukraine", "Afghanistan–Pakistan"):
    h = cm[(cm.conflict_case == case) & (cm.month >= "2024-01-01")].set_index("month").deaths
    p = preds[(preds.conflict_case == case) & (preds.fold == 2026) & (preds.track == "A") & (preds.model == "ensemble")]
    p = p.set_index("target_month")
    fu = future[(future.conflict_case == case) & (future.model == "ensemble")].set_index("target_month")
    months = pd.date_range("2024-01-01", fu.index.max(), freq="MS")

    def g(s, t):
        return None if t not in s.index or pd.isna(s[t]) else round(float(s[t]))
    D["forecast"][case] = dict(months=[t.strftime("%b %y") for t in months], actual=[g(h, t) for t in months],
                               pred=[g(p.pred, t) for t in months], lo=[g(p.pi80_lo, t) for t in months],
                               hi=[g(p.pi80_hi, t) for t in months], fut=[g(fu.pred, t) for t in months],
                               fut_lo=[g(fu.pi80_lo, t) for t in months], fut_hi=[g(fu.pi80_hi, t) for t in months])
# map pulse positions, as fractions of map.png
ff = m.full_figure_for_development(warn=False)
xa, ya = ff.layout.xaxis, ff.layout.yaxis


def _px(lon, lat):
    fx = xa.domain[0] + (lon - xa.range[0]) / (xa.range[1] - xa.range[0]) * (xa.domain[1] - xa.domain[0])
    fy = ya.domain[0] + (lat - ya.range[0]) / (ya.range[1] - ya.range[0]) * (ya.domain[1] - ya.domain[0])
    return [round(fx, 4), round(1 - fy, 4)]


D["map_pulses"] = [dict(name="Sri Lanka strike", xy=_px(79.9, 6.9), color="FF4D5E"),
                   dict(name="Hormuz", xy=_px(56.3, 26.6), color="F0B03A"),
                   dict(name="LoC", xy=_px(74.6, 34.3), color="4FD6E8")]
(OUT / "chart_data.json").write_text(json.dumps(D))
print("chart data written")
