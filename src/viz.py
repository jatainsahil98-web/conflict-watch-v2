"""Plotly figures shared by the notebooks, the dashboard, the report and the deck.

Styled to match the team's jury deck (dark navy, amber / cyan / red / teal) and
sized for a video call: large fonts, thick lines, few gridlines, direct labels.
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
from plotly.subplots import make_subplots

from . import config as C

T = C.THEME
FONT = "Calibri, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif"

pio.templates["deck"] = go.layout.Template(
    layout=dict(
        font=dict(family=FONT, size=16, color=T["text2"]),
        paper_bgcolor=T["bg"], plot_bgcolor=T["bg"],
        colorway=[T["cyan"], T["amber"], T["teal"], T["red"], T["violet"], "#7FA7D9"],
        title=dict(font=dict(size=22, color=T["text"]), x=0.01, xanchor="left"),
        xaxis=dict(gridcolor="rgba(43,71,99,0.45)", linecolor=T["border"], zeroline=False,
                   tickfont=dict(size=14, color=T["text3"]), title=dict(font=dict(size=15, color=T["text3"]))),
        yaxis=dict(gridcolor="rgba(43,71,99,0.45)", linecolor=T["border"], zeroline=False,
                   tickfont=dict(size=14, color=T["text3"]), title=dict(font=dict(size=15, color=T["text3"]))),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=14, color=T["text2"]), orientation="h",
                    yanchor="bottom", y=1.02, x=0),
        margin=dict(l=60, r=30, t=70, b=50),
        hoverlabel=dict(bgcolor=T["panel"], bordercolor=T["border"], font=dict(color=T["text"], size=14)),
    )
)
pio.templates.default = "deck"
CC = C.CASE_COLORS


def _rgba(hex_, a):
    h = hex_.lstrip("#")
    return f"rgba({int(h[:2], 16)},{int(h[2:4], 16)},{int(h[4:], 16)},{a})"


def _holdout_band(fig, row=None, col=None, label=True):
    kw = dict(row=row, col=col) if row else {}
    fig.add_vrect(x0="2026-01-01", x1="2026-09-30", fillcolor=_rgba(T["violet"], 0.12), line_width=0, **kw)
    if label and not row:
        fig.add_annotation(x="2026-05-01", y=1.0, yref="paper", text="2026 HOLDOUT<br>(provisional)",
                           showarrow=False, font=dict(size=12, color=T["violet"]), yanchor="top")


# ---------------------------------------------------------------------------
# Overview
# ---------------------------------------------------------------------------
def fig_monthly_deaths(cm: pd.DataFrame, log=True, cases=None, title="Monthly conflict deaths, 2014 to Sep 2026"):
    fig = go.Figure()
    for case in cases or C.CASES:
        d = cm[cm.conflict_case == case]
        fig.add_trace(go.Scatter(x=d.month, y=d.deaths, name=case, mode="lines",
                                 line=dict(color=CC[case], width=3),
                                 hovertemplate="%{x|%b %Y}: %{y:,.0f} deaths<extra>" + case + "</extra>"))
    _holdout_band(fig)
    fig.update_layout(title=title, yaxis_title="Deaths per month (UCDP best)" + (" - log scale" if log else ""),
                      height=480)
    if log:
        fig.update_yaxes(type="log", dtick=1)
    return fig


def fig_case_small_multiples(cm: pd.DataFrame):
    fig = make_subplots(rows=2, cols=2, subplot_titles=C.CASES, vertical_spacing=0.14, horizontal_spacing=0.07)
    for i, case in enumerate(C.CASES):
        r, c = i // 2 + 1, i % 2 + 1
        d = cm[cm.conflict_case == case]
        fig.add_trace(go.Bar(x=d.month, y=d.deaths, marker_color=CC[case], name=case, showlegend=False,
                             hovertemplate="%{x|%b %Y}: %{y:,.0f}<extra></extra>"), row=r, col=c)
        fig.add_trace(go.Scatter(x=d.month, y=d.deaths_high, line=dict(color=T["text3"], width=1, dash="dot"),
                                 showlegend=False, hovertemplate="high: %{y:,.0f}<extra></extra>"), row=r, col=c)
    fig.update_layout(height=620, title="Deaths per month by conflict (bars = best estimate, dotted = UCDP high)",
                      bargap=0)
    for a in fig.layout.annotations:
        a.font = dict(size=17, color=T["text"])
    return fig


# ---------------------------------------------------------------------------
# Data quality
# ---------------------------------------------------------------------------
def fig_dq_summary(dq: pd.DataFrame):
    d = dq[dq.rows_affected > 0].copy()
    d["label"] = d.id + "  " + d.check.str.slice(0, 58)
    d = d.sort_values("pct_affected")
    colors = {"Validity": T["red"], "Temporal": T["amber"], "Missing": T["cyan"], "Provenance": T["violet"],
              "Consistency": T["teal"], "Duplicates": T["amber"], "Granularity": T["cyan"], "Outlier": T["red"],
              "Precision": T["text3"], "Format": T["text3"], "Semantics": T["violet"], "Join coverage": T["teal"]}
    fig = go.Figure(go.Bar(y=d.label, x=d.pct_affected, orientation="h",
                           marker_color=[colors.get(c, T["cyan"]) for c in d.category],
                           text=[f"{n:,} rows" for n in d.rows_affected], textposition="outside",
                           textfont=dict(size=12, color=T["text3"]),
                           hovertemplate="%{y}<br>%{x:.2f}% of table<extra></extra>"))
    fig.update_layout(title="Data-quality issues found and handled (% of rows in the table)", height=760,
                      xaxis_title="% of rows affected", xaxis_type="log", margin=dict(l=470))
    fig.update_yaxes(tickfont=dict(size=12))
    return fig


def fig_fog_of_war(gp: pd.DataFrame):
    fig = go.Figure()
    for case in C.CASES:
        d = gp[(gp.conflict_case == case) & (gp.year >= 2018) & (gp.deaths >= 50)]
        fig.add_trace(go.Scatter(x=d.year, y=d.share_deaths_country_level * 100, name=case, mode="lines+markers",
                                 line=dict(color=CC[case], width=3), marker=dict(size=9)))
    fig.update_layout(title="Fog of war in the data: share of deaths with no sub-national location",
                      yaxis_title="% of deaths located only to country", height=430, yaxis_range=[0, 100])
    return fig


# ---------------------------------------------------------------------------
# Military lens
# ---------------------------------------------------------------------------
def fig_front_geography(fg: pd.DataFrame):
    d = fg[fg.year >= 2021]
    order = (d[d.year == d.year.max()].sort_values("share", ascending=False).area.tolist())
    order = [a for a in order if a != "Other areas"] + ["Other areas"]
    pal = [T["red"], T["amber"], T["cyan"], T["teal"], T["violet"], "#7FA7D9", "#E98AA0", "#C9B458", "#6FCF97",
           "#B0BEC5", "#8E7CC3", T["muted"]]
    fig = go.Figure()
    for i, a in enumerate(order):
        x = d[d.area == a]
        fig.add_trace(go.Bar(x=x.year, y=x.share * 100, name=a.replace(" oblast", ""), marker_color=pal[i % len(pal)],
                             hovertemplate=a + ": %{y:.1f}%<extra></extra>"))
    fig.update_layout(barmode="stack", height=500, yaxis_title="% of geolocated discrete events",
                      title="Russia–Ukraine: the front is widening, not moving (share of located events by area)",
                      legend=dict(orientation="v", x=1.01, y=1, yanchor="top"), margin=dict(r=200))
    return fig


def fig_attrition(att: pd.DataFrame, case="Russia–Ukraine"):
    d = att[(att.conflict_case == case) & (att.year >= 2022)]
    a_name, b_name = d.side_a_name.iloc[0], d.side_b_name.iloc[0]
    short = lambda s: s.replace("Government of ", "").replace(" (Soviet Union)", "")
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Bar(x=d.year, y=d.deaths_side_a, name=f"{short(a_name)} (side A)", marker_color=T["red"]))
    fig.add_trace(go.Bar(x=d.year, y=d.deaths_side_b, name=f"{short(b_name)} (side B)", marker_color=T["cyan"]))
    fig.add_trace(go.Bar(x=d.year, y=d.deaths_civilians, name="Civilians", marker_color=T["amber"]))
    fig.add_trace(go.Scatter(x=d.year, y=d.ratio_a_to_b, name="Recorded ratio A:B", mode="lines+markers+text",
                             text=[f"{r:.1f}:1" for r in d.ratio_a_to_b], textposition="top center",
                             textfont=dict(size=15, color=T["text"]),
                             line=dict(color=T["text"], width=3, dash="dot"), marker=dict(size=10)),
                  secondary_y=True)
    fig.update_layout(title=f"{case}: UCDP-recorded fatalities by side (focal dyad) - reported, not verified",
                      barmode="group", height=470, yaxis_title="Deaths per year")
    fig.update_yaxes(title_text="Ratio", secondary_y=True, showgrid=False, rangemode="tozero")
    return fig


def fig_theatre_spread(ts: pd.DataFrame):
    d = ts[ts.year >= 2018]
    fig = go.Figure()
    for case in C.CASES:
        x = d[d.conflict_case == case]
        fig.add_trace(go.Scatter(x=x.year, y=x.countries, name=case, mode="lines+markers",
                                 line=dict(color=CC[case], width=3), marker=dict(size=10)))
    fig.update_layout(title="Horizontal escalation: countries with recorded deaths per year", height=420,
                      yaxis_title="Countries hit", yaxis_dtick=2)
    return fig


_GEOJSON = None


def world_geojson():
    """Natural Earth 1:110m countries (public domain), shipped locally so maps work offline."""
    global _GEOJSON
    if _GEOJSON is None:
        import json
        _GEOJSON = json.loads((C.ROOT / "assets" / "world_lowres.geojson").read_text())
    return _GEOJSON


def _rings(geom):
    if geom["type"] == "Polygon":
        return [geom["coordinates"][0]]
    return [poly[0] for poly in geom["coordinates"]]


def fig_country_map(cd: pd.DataFrame, case=None, year_from=2024, india=True, height=620,
                    lon_range=(14, 100), lat_range=(3, 56)):
    """Choropleth drawn as filled polygons on plain axes (equirectangular).

    Avoids Plotly's geo basemap, which downloads topojson from a CDN: the map
    therefore renders offline, in static export and through a proxy."""
    gj = world_geojson()
    d = cd[cd.year >= year_from]
    if case:
        d = d[d.conflict_case == case]
    d = d.groupby(["country_iso3", "ucdp_location_name"], as_index=False)[["deaths", "events"]].sum()
    dmap = d.set_index("country_iso3").deaths.to_dict()
    bins = [(0, 1, "#10273D", "no recorded deaths"), (1, 100, "#5C4A1E", "1–99"), (100, 1000, "#B07A1F", "100–999"),
            (1000, 10000, T["amber"], "1k–10k"), (10000, 1e9, T["red"], "10k+")]
    fig = go.Figure()
    # background countries in one trace; each affected country as its own trace
    # (one closed path per trace keeps Plotly's 'toself' fill unambiguous)
    xs, ys = [], []
    for f in gj["features"]:
        if dmap.get(f["id"], 0) >= 1:
            continue
        for ring in _rings(f["geometry"]):
            xs += [p[0] for p in ring] + [None]
            ys += [p[1] for p in ring] + [None]
    fig.add_trace(go.Scatter(x=xs, y=ys, fill="toself", fillcolor=bins[0][2], mode="lines",
                             line=dict(color=T["border"], width=0.7), hoverinfo="skip", showlegend=False))
    shown = set()
    for f in gj["features"]:
        v = dmap.get(f["id"], 0)
        if v < 1:
            continue
        lo, hi, col, lab = next(b for b in bins[1:] if b[0] <= v < b[1])
        for k, ring in enumerate(_rings(f["geometry"])):
            fig.add_trace(go.Scatter(x=[p[0] for p in ring], y=[p[1] for p in ring], fill="toself",
                                     fillcolor=col, mode="lines", line=dict(color=T["bg"], width=0.8),
                                     name=lab, legendgroup=lab, showlegend=lab not in shown, hoverinfo="skip",
                                     legendrank=int(np.log10(lo + 1) * 10)))
            shown.add(lab)
    # hover points at country label positions
    cent = []
    for f in gj["features"]:
        if f["id"] in dmap:
            ring = max(_rings(f["geometry"]), key=len)
            arr = np.array(ring)
            cent.append((f["id"], f["properties"]["name"], arr[:, 0].mean(), arr[:, 1].mean(), dmap[f["id"]]))
    if cent:
        c = pd.DataFrame(cent, columns=["iso", "name", "x", "y", "deaths"])
        fig.add_trace(go.Scatter(x=c.x, y=c.y, mode="markers", marker=dict(size=14, opacity=0), showlegend=False,
                                 text=c.name, customdata=c.deaths,
                                 hovertemplate="%{text}: %{customdata:,.0f} deaths<extra></extra>"))
    if india:
        for f in gj["features"]:
            if f["id"] == "IND":
                for ring in _rings(f["geometry"]):
                    fig.add_trace(go.Scatter(x=[p[0] for p in ring], y=[p[1] for p in ring], mode="lines",
                                             line=dict(color=T["cyan"], width=3), hoverinfo="skip", showlegend=False))
        pts = pd.DataFrame([
            ("INDIA", 78.5, 22.0, T["cyan"], "middle center"), ("Strait of Hormuz", 56.3, 26.6, T["amber"], "top left"),
            ("Chabahar", 60.6, 25.3, T["amber"], "bottom right"),
            ("Sri Lanka strike 4 Mar 2026<br>104 killed", 79.9, 6.9, T["red"], "middle right"),
            ("Bab el-Mandeb", 43.4, 12.6, T["amber"], "bottom right"), ("LoC / J&K", 74.6, 34.3, T["cyan"], "top right"),
        ], columns=["name", "x", "y", "color", "pos"])
        fig.add_trace(go.Scatter(x=pts.x, y=pts.y, text=pts.name, mode="markers+text", showlegend=False,
                                 marker=dict(size=10, color=pts.color, line=dict(color=T["bg"], width=1)),
                                 textposition=pts.pos.tolist(), textfont=dict(size=14, color=T["text"]),
                                 hoverinfo="text"))
    fig.update_xaxes(visible=False, range=list(lon_range), constrain="domain")
    fig.update_yaxes(visible=False, range=list(lat_range), scaleanchor="x", scaleratio=1.2, constrain="domain")
    fig.update_layout(title=f"Where the four conflicts killed people, {year_from}–Sep 2026 (India outlined)",
                      height=height, margin=dict(l=0, r=0, t=60, b=0),
                      legend=dict(orientation="v", x=0.0, y=0.02, yanchor="bottom", bgcolor="rgba(7,19,31,0.7)",
                                  title=dict(text="Deaths", font=dict(size=14))))
    return fig


def fig_afpak(ap: pd.DataFrame, focal_monthly: pd.DataFrame | None = None):
    d = ap[ap.year >= 2016].copy()
    top = d.groupby("admin1").deaths.sum().nlargest(6).index
    d["area"] = np.where(d.admin1.isin(top), d.country_iso3 + " · " + d.admin1.str.replace(" province", ""),
                         "Other")
    d = d.groupby(["year", "area"], as_index=False).deaths.sum()
    pal = [T["red"], T["amber"], T["cyan"], T["teal"], T["violet"], "#7FA7D9", T["muted"]]
    fig = go.Figure()
    for i, a in enumerate(sorted(d.area.unique(), key=lambda a: (a == "Other", a))):
        x = d[d.area == a]
        fig.add_trace(go.Bar(x=x.year, y=x.deaths, name=a, marker_color=pal[i % len(pal)]))
    fig.update_layout(barmode="stack", title="Afghanistan–Pakistan: deaths by province (FATA merged into KP)",
                      height=470, yaxis_title="Deaths per year")
    return fig


def fig_afpak_interstate(e: pd.DataFrame):
    f = e[(e.conflict_case == "Afghanistan–Pakistan") & (e.case_scope == "Focal")]
    m = f.groupby("month").agg(deaths=("deaths_best", "sum"), events=("event_id", "count")).reset_index()
    m = m.set_index("month").reindex(pd.date_range("2022-01-01", C.PANEL_END, freq="MS"), fill_value=0).reset_index()
    fig = go.Figure(go.Bar(x=m["index"], y=m.deaths, marker_color=T["red"], name="deaths",
                           hovertemplate="%{x|%b %Y}: %{y} deaths<extra></extra>"))
    fig.update_layout(title="Afghanistan vs Pakistan, state-on-state clashes (focal dyad): a new front opens",
                      height=420, yaxis_title="Deaths per month")
    _holdout_band(fig)
    return fig


def fig_seasonality(se: pd.DataFrame):
    p = se.pivot(index="conflict_case", columns="moy", values="index_pct").reindex(C.CASES)
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    z = p.values.clip(-60, 60)
    fig = go.Figure(go.Heatmap(z=z, x=months, y=p.index, zmid=0,
                               colorscale=[[0, T["cyan"]], [0.5, T["panel"]], [1, T["red"]]],
                               text=np.where(np.isnan(p.values), "", np.vectorize(lambda v: f"{v:+.0f}%")(p.values)),
                               texttemplate="%{text}", textfont=dict(size=14, color=T["text"]),
                               colorbar=dict(title="vs trend")))
    fig.update_layout(title="Campaign seasons: deaths vs 12-month trend, by calendar month", height=380)
    return fig


def fig_violence_mix(vm: pd.DataFrame):
    d = vm.groupby(["conflict_case", "violence_type"]).deaths.sum().reset_index()
    tot = d.groupby("conflict_case").deaths.transform("sum")
    d["share"] = d.deaths / tot * 100
    fig = go.Figure()
    for vt, col in (("State-based", T["cyan"]), ("Non-state", T["violet"]), ("One-sided", T["red"])):
        x = d[d.violence_type == vt].set_index("conflict_case").reindex(C.CASES)
        fig.add_trace(go.Bar(y=x.index, x=x.share, name=vt, orientation="h", marker_color=col,
                             text=[f"{v:.0f}%" if v >= 4 else "" for v in x.share.fillna(0)], textposition="inside"))
    fig.update_layout(barmode="stack", title="Type of violence (share of deaths, 2014–2026)", height=330,
                      xaxis_title="% of deaths", margin=dict(l=190))
    return fig


# ---------------------------------------------------------------------------
# Media attention
# ---------------------------------------------------------------------------
def fig_media_scatter(md: pd.DataFrame):
    fig = make_subplots(rows=1, cols=2, subplot_titles=("References vs EVENTS (tight)", "References vs DEATHS (loose)"),
                        horizontal_spacing=0.08)
    for case in C.CASES:
        d = md[md.conflict_case == case]
        fig.add_trace(go.Scatter(x=d.n_events, y=d.n_sources, mode="markers", name=case,
                                 marker=dict(color=CC[case], size=8, opacity=0.75)), row=1, col=1)
        fig.add_trace(go.Scatter(x=d.deaths.clip(lower=1), y=d.n_sources, mode="markers", name=case, showlegend=False,
                                 marker=dict(color=CC[case], size=8, opacity=0.75)), row=1, col=2)
    fig.update_xaxes(type="log", title_text="events per month", row=1, col=1)
    fig.update_xaxes(type="log", title_text="deaths per month", row=1, col=2)
    fig.update_yaxes(type="log", title_text="source references per month", row=1, col=1)
    fig.update_yaxes(type="log", row=1, col=2)
    fig.update_layout(title="Attention follows incidents, not lethality", height=460)
    return fig


def fig_media_gap(md: pd.DataFrame):
    fig = go.Figure()
    for case in C.CASES:
        d = md[md.conflict_case == case].sort_values("month")
        fig.add_trace(go.Scatter(x=d.month, y=d.agi.rolling(3, 1).mean(), name=case, mode="lines",
                                 line=dict(color=CC[case], width=3)))
    fig.add_hline(y=0, line_color=T["text3"], line_dash="dot")
    fig.update_layout(title="Attention Gap Index (3-month mean): above 0 = over-reported, below 0 = forgotten",
                      height=430, yaxis_title="AGI (z-score)")
    return fig


# ---------------------------------------------------------------------------
# Displacement
# ---------------------------------------------------------------------------
NAMES = {"UKR": "Ukraine", "PSE": "Palestine", "AFG": "Afghanistan", "PAK": "Pakistan", "IRN": "Iran",
         "RUS": "Russia", "ISR": "Israel", "IND": "India"}


def fig_displacement(ds: pd.DataFrame, iso_list=("UKR", "AFG", "PSE", "PAK", "IRN", "RUS")):
    fig = make_subplots(rows=2, cols=3, subplot_titles=[NAMES[i] for i in iso_list], vertical_spacing=0.16)
    for k, iso in enumerate(iso_list):
        r, c = k // 3 + 1, k % 3 + 1
        d = ds[ds.iso3 == iso]
        for col, name, color in (("refugees", "Refugees abroad (UNHCR)", T["cyan"]),
                                 ("asylum_seekers", "Asylum seekers", T["violet"]),
                                 ("idps", "Internally displaced (IDMC)", T["amber"])):
            fig.add_trace(go.Bar(x=d.year, y=d[col] / 1e6, name=name, marker_color=color, showlegend=k == 0),
                          row=r, col=c)
    fig.update_layout(barmode="stack", height=600, title="Displaced populations by origin (millions, year-end)")
    for a in fig.layout.annotations:
        a.font = dict(size=17, color=T["text"])
    return fig


def fig_demographics(dp: pd.DataFrame):
    d = dp.sort_values("year").groupby("origin_iso3").tail(1)
    d = d.sort_values("women_children_share")
    d["name"] = d.origin_iso3.map(NAMES)
    fig = go.Figure()
    fig.add_trace(go.Bar(y=d.name, x=d.women_children_share * 100, orientation="h", marker_color=T["amber"],
                         name="Women + children", text=[f"{v:.0%}" for v in d.women_children_share],
                         textposition="outside"))
    fig.add_trace(go.Bar(y=d.name, x=d.children_share * 100, orientation="h", marker_color=T["cyan"],
                         name="Children (0-17)", text=[f"{v:.0%}" for v in d.children_share], textposition="outside"))
    fig.update_layout(barmode="group", title="Who is displaced: women and children among recorded refugees (2025)",
                      height=440, xaxis_title="% of people with sex and age recorded", xaxis_range=[0, 85])
    return fig


# ---------------------------------------------------------------------------
# India
# ---------------------------------------------------------------------------
def fig_india_exposure(ie: pd.DataFrame):
    d = ie[ie.year >= 2022].groupby(["india_tag", "year"], as_index=False)[["events", "deaths"]].sum()
    pal = {"Gulf state (Indian diaspora / energy)": T["amber"], "Indian Ocean (Sri Lanka)": T["red"],
           "Iran: Hormuz / Chabahar coast": T["cyan"], "Pakistan area adjoining India/LoC": T["teal"],
           "Yemen (Red Sea / Bab el-Mandeb)": T["violet"]}
    fig = go.Figure()
    for tag, col in pal.items():
        x = d[d.india_tag == tag]
        fig.add_trace(go.Bar(x=x.year, y=x.deaths, name=tag, marker_color=col,
                             customdata=x.events, hovertemplate="%{y:,} deaths in %{customdata} events<extra></extra>"))
    fig.update_layout(barmode="group", title="Violence reaching places that matter to India (deaths per year)",
                      height=460, yaxis_title="Deaths", yaxis_type="log")
    return fig


def fig_india_hosted(ih: pd.DataFrame):
    p = ih.pivot_table(index="year", columns="origin_iso3", values="total_international", aggfunc="sum")
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Bar(x=p.index, y=p.get("AFG"), name="Afghans in India", marker_color=T["teal"]))
    for iso, col in (("RUS", T["red"]), ("UKR", T["cyan"]), ("IRN", T["amber"])):
        if iso in p:
            fig.add_trace(go.Scatter(x=p.index, y=p[iso], name=f"{NAMES[iso]}ns in India" if iso != "UKR" else
                                     "Ukrainians in India", mode="lines+markers", line=dict(color=col, width=3)),
                          secondary_y=True)
    fig.update_layout(title="Refugees and asylum seekers hosted by India (UNHCR)", height=430)
    fig.update_yaxes(title_text="Afghans", secondary_y=False)
    fig.update_yaxes(title_text="Others", secondary_y=True, showgrid=False)
    return fig


# ---------------------------------------------------------------------------
# Forecasting
# ---------------------------------------------------------------------------
def fig_forecast_case(cm, preds, case, fold=2026, track="A", model="ensemble", history_from="2024-01-01",
                      future=None, scenario=None):
    h = cm[(cm.conflict_case == case) & (cm.month >= history_from)]
    p = preds[(preds.conflict_case == case) & (preds.fold == fold) & (preds.track == track) & (preds.model == model)]
    p = p.sort_values("target_month")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=p.target_month, y=p.pi80_hi, mode="lines", line=dict(width=0), showlegend=False,
                             hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=p.target_month, y=p.pi80_lo, mode="lines", fill="tonexty",
                             fillcolor=_rgba(CC[case], 0.22), line=dict(width=0), name="80% interval", hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=h.month, y=h.deaths, name="Actual", mode="lines+markers",
                             line=dict(color=T["text"], width=3), marker=dict(size=6)))
    fig.add_trace(go.Scatter(x=p.target_month, y=p.pred, name="Forecast", mode="lines+markers",
                             line=dict(color=CC[case], width=4, dash="dash"), marker=dict(size=9)))
    if future is not None:
        f = future[(future.conflict_case == case) & (future.model == model)].sort_values("target_month")
        fig.add_trace(go.Scatter(x=f.target_month, y=f.pi80_hi, mode="lines", line=dict(width=0), showlegend=False,
                                 hoverinfo="skip"))
        fig.add_trace(go.Scatter(x=f.target_month, y=f.pi80_lo, mode="lines", fill="tonexty",
                                 fillcolor=_rgba(T["amber"], 0.22), line=dict(width=0), showlegend=False,
                                 hoverinfo="skip"))
        fig.add_trace(go.Scatter(x=f.target_month, y=f.pred, name="Forward forecast Oct–Dec 2026",
                                 mode="lines+markers", line=dict(color=T["amber"], width=4), marker=dict(size=10)))
    if scenario is not None:
        fig.add_trace(go.Scatter(x=scenario.target_month, y=scenario.pred, name="What-if scenario",
                                 mode="lines+markers", line=dict(color=T["red"], width=4, dash="dot"),
                                 marker=dict(size=10, symbol="diamond")))
    _holdout_band(fig)
    lab = "1-month-ahead (rolling)" if track == "A" else "1–9 months ahead from Dec 2025"
    fig.update_layout(title=f"{case}: forecast vs actual, 2026 withheld test ({lab})", height=470,
                      yaxis_title="Deaths per month")
    return fig


def fig_model_compare(rm: pd.DataFrame, fold_sel="holdout"):
    d = rm.copy()
    d["set"] = np.where(d.fold == 2026, "2026 holdout", "Back-test 2022–25")
    t = d.groupby(["model", "track", "set"]).RMSLE.mean().reset_index()
    from .models import MODEL_LABELS
    t["label"] = t.model.map(MODEL_LABELS)
    fig = make_subplots(rows=1, cols=2, subplot_titles=("Track A: 1 month ahead", "Track B: 1–9 months ahead"),
                        shared_yaxes=True, horizontal_spacing=0.04)
    order = (t[(t.track == "A") & (t.set == "2026 holdout")].sort_values("RMSLE", ascending=False).label.tolist())
    for j, tr in enumerate(("A", "B")):
        for s, col in (("Back-test 2022–25", T["muted"]), ("2026 holdout", T["cyan"])):
            x = t[(t.track == tr) & (t.set == s)].set_index("label").reindex(order)
            fig.add_trace(go.Bar(y=x.index, x=x.RMSLE, orientation="h", name=s, marker_color=col, showlegend=j == 0,
                                 text=[f"{v:.2f}" for v in x.RMSLE], textposition="outside",
                                 textfont=dict(size=12)), row=1, col=j + 1)
    fig.update_layout(barmode="group", height=580, title="Model comparison: log-scale error (RMSLE, lower is better)",
                      margin=dict(l=360, t=110), legend=dict(y=1.13, x=0.55))
    return fig


def fig_shap(imp: pd.DataFrame, title="What drives the forecast (mean |SHAP|, LightGBM-Δ)", top=14):
    d = imp.head(top).iloc[::-1]
    fig = go.Figure(go.Bar(y=d.feature, x=d.mean_abs_shap, orientation="h", marker_color=T["amber"]))
    fig.update_layout(title=title, height=480, margin=dict(l=220), xaxis_title="mean |SHAP| (log-deaths units)")
    return fig


def fig_ew_curves(ewp: pd.DataFrame, fold=2026):
    from sklearn.metrics import precision_recall_curve, roc_curve
    d = ewp[ewp.fold == fold]
    fig = make_subplots(rows=1, cols=2, subplot_titles=("ROC curve", "Precision–recall"), horizontal_spacing=0.1)
    for col, name, color in (("p_lgb", "LightGBM", T["amber"]), ("p_logit", "Logistic", T["cyan"]),
                             ("p_rule", "Last-month rule", T["text3"])):
        fpr, tpr, _ = roc_curve(d.escalation, d[col])
        pr, rc, _ = precision_recall_curve(d.escalation, d[col])
        fig.add_trace(go.Scatter(x=fpr, y=tpr, name=name, line=dict(color=color, width=3)), row=1, col=1)
        fig.add_trace(go.Scatter(x=rc, y=pr, name=name, showlegend=False, line=dict(color=color, width=3)), row=1, col=2)
    fig.add_trace(go.Scatter(x=[0, 1], y=[0, 1], line=dict(color=T["muted"], dash="dot"), showlegend=False), row=1, col=1)
    fig.add_hline(y=d.escalation.mean(), line_dash="dot", line_color=T["muted"], row=1, col=2)
    fig.update_xaxes(title_text="False-positive rate", row=1, col=1)
    fig.update_xaxes(title_text="Recall", row=1, col=2)
    fig.update_yaxes(title_text="True-positive rate", row=1, col=1)
    fig.update_yaxes(title_text="Precision", row=1, col=2)
    fig.update_layout(title=f"Sub-national escalation warning, {fold} withheld months", height=450)
    return fig


def fig_ew_calibration(cal: pd.DataFrame):
    """Predicted probability band vs share that escalated (2026 withheld months)."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=[0, 0.4], y=[0, 0.4], mode="lines", line=dict(color=T["muted"], dash="dot"),
                             name="Perfect calibration"))
    fig.add_trace(go.Scatter(x=cal.mean_pred, y=cal.escalated, mode="lines+markers+text", name="LightGBM, 2026",
                             line=dict(color=T["amber"], width=3), marker=dict(size=8 + 22 * (cal.areas / cal.areas.max()) ** 0.5),
                             text=[f"n={n:,}" for n in cal.areas], textposition="top left"))
    fig.update_xaxes(title_text="Mean predicted probability", tickformat=".0%", range=[0, 0.4])
    fig.update_yaxes(title_text="Share that escalated", tickformat=".0%", range=[0, 0.4])
    fig.update_layout(title="Calibration: predicted vs observed escalation", height=450)
    return fig


def fig_gdelt_vs_ucdp(gd: pd.DataFrame, wk: pd.DataFrame):
    """Daily-rate GDELT violent events (weekly) vs UCDP deaths in discrete dated events, 2026."""
    fig = make_subplots(rows=2, cols=2, subplot_titles=C.CASES, vertical_spacing=0.16, horizontal_spacing=0.09,
                        specs=[[{"secondary_y": True}] * 2] * 2)
    d = gd.copy()
    d["date"] = pd.to_datetime(d.date)
    d["week"] = d.date.dt.to_period("W-SUN").dt.start_time
    case = {"RU-UA": "Russia–Ukraine", "ISR-HAMAS": "Israel–Hamas", "AF-PAK": "Afghanistan–Pakistan", "US-IRAN": "US–Iran"}
    d["case"] = d.case_id.map(case)
    g = d.groupby(["case", "week"]).agg(v=("violent_events", "sum"), n=("date", "nunique")).reset_index()
    g = g[g.n >= 4]
    g["v"] = g.v / g.n
    wk = wk.assign(week=pd.to_datetime(wk.week))
    for i, c in enumerate(C.CASES):
        r, k = i // 2 + 1, i % 2 + 1
        x = g[g.case == c]
        u = wk[wk.case == c]
        fig.add_trace(go.Bar(x=u.week, y=u.ucdp_deaths, name="UCDP deaths (dated events, weekly)", marker_color=CC[c],
                             opacity=0.55, showlegend=i == 0), row=r, col=k, secondary_y=False)
        fig.add_trace(go.Scatter(x=x.week, y=x.v, name="GDELT violent events per day", line=dict(color=T["amber"], width=2.5),
                                 showlegend=i == 0), row=r, col=k, secondary_y=True)
        fig.add_vrect(x0="2026-10-01", x1="2026-11-12", fillcolor=T["amber"], opacity=0.08, line_width=0, row=r, col=k)
    fig.update_layout(title="GDELT (media-coded) vs UCDP (recorded deaths), 2026 · shaded = beyond UCDP's Sep 2026 end",
                      height=620, legend=dict(orientation="h", y=-0.08))
    return fig


def fig_gdelt_lags(lags: pd.DataFrame):
    fig = go.Figure()
    for c in C.CASES:
        x = lags[lags.case == c]
        fig.add_trace(go.Bar(x=x.lag_weeks, y=x.spearman, name=c, marker_color=CC[c]))
    fig.update_xaxes(title_text="GDELT shift (weeks; positive = GDELT earlier than UCDP)", tickvals=[-2, -1, 0, 1, 2])
    fig.update_yaxes(title_text="Spearman correlation with UCDP weekly deaths", range=[-0.5, 1])
    fig.update_layout(title="Does GDELT lead UCDP? Mostly same-week, and only for spike wars", barmode="group", height=450)
    return fig


def fig_rag(rag: pd.DataFrame):
    fig = go.Figure()
    for i, r in rag.reset_index(drop=True).iterrows():
        col = C.RAG_COLORS[r.rating]
        fig.add_shape(type="rect", x0=i, x1=i + 0.94, y0=0, y1=1, fillcolor=T["panel"], line=dict(color=col, width=4))
        fig.add_annotation(x=i + 0.47, y=0.86, text=f"<b>{r.conflict_case}</b>", showarrow=False,
                           font=dict(size=19, color=T["text"]))
        fig.add_annotation(x=i + 0.47, y=0.63, text=f"<b>{r.rating}</b>", showarrow=False, font=dict(size=34, color=col))
        fig.add_annotation(x=i + 0.47, y=0.40, text=f"{r.forecast_next:,.0f} deaths forecast "
                           f"{pd.Timestamp(r.forecast_month):%b %Y}", showarrow=False, font=dict(size=15, color=T["text2"]))
        fig.add_annotation(x=i + 0.47, y=0.27, text=f"trend {r.trend_ratio - 1:+.0%} vs last 6 months", showarrow=False,
                           font=dict(size=14, color=T["text3"]))
        fig.add_annotation(x=i + 0.47, y=0.14, text=f"{r.hotspots} hotspot areas · {r.score} pts", showarrow=False,
                           font=dict(size=14, color=T["text3"]))
    fig.update_xaxes(visible=False, range=[-0.03, len(rag)])
    fig.update_yaxes(visible=False, range=[0, 1])
    fig.update_layout(height=260, margin=dict(l=10, r=10, t=10, b=10))
    return fig


# ---------------------------------------------------------------------------
def save(fig, name, width=1400, height=None, scale=2):
    """Write PNG (for report/deck) and HTML (interactive). PNG needs kaleido + Chrome."""
    C.FIG_DIR.mkdir(parents=True, exist_ok=True)
    fig.write_html(C.FIG_DIR / f"{name}.html", include_plotlyjs="cdn")
    try:
        if "BROWSER_PATH" not in os.environ and os.path.exists("/opt/pw-browsers"):
            import glob
            c = glob.glob("/opt/pw-browsers/chromium-*/chrome-linux64/chrome")
            if c:
                os.environ["BROWSER_PATH"] = c[0]
        fig.write_image(C.FIG_DIR / f"{name}.png", width=width, height=height or fig.layout.height or 500,
                        scale=scale)
    except Exception as ex:  # static export is optional
        print(f"[viz] PNG export skipped for {name}: {ex}")


# ---------------------------------------------------------------------------
# Economic front (new, separately labelled; public market data, see src/econ.py)
# ---------------------------------------------------------------------------
ECON_LABEL = {"MOEX": "MOEX Russia", "RUB": "Rouble value", "BRENT": "Brent crude", "WHEAT": "Wheat",
              "NIFTY": "Nifty 50", "INR": "Rupee value", "TA35": "Tel Aviv 35", "ILS": "Shekel value",
              "ZIM": "ZIM shipping", "VIX": "VIX fear gauge", "FRO": "Tanker stocks", "GOLD": "Gold",
              "TTF": "EU gas (TTF)", "PKR": "PKR value", "AFN": "Afghani value", "IRR": "Rial value", "UAH": "Hryvnia value"}
ECON_COL = {"MOEX": T["cyan"], "RUB": "#7FA7D9", "BRENT": T["amber"], "WHEAT": T["teal"], "NIFTY": T["red"],
            "INR": "#FF9AA5", "TA35": T["cyan"], "ILS": "#7FA7D9", "ZIM": T["violet"], "VIX": T["violet"],
            "FRO": T["teal"], "GOLD": "#E8D27A", "TTF": T["teal"]}


def fig_econ_paths(ph: pd.DataFrame, case: str, title=None):
    """Event-study paths: index = 100 at the last close before day 0."""
    d = ph[ph.conflict_case == case]
    fig = go.Figure()
    fig.add_vline(x=0, line=dict(color=T["red"], width=2, dash="dash"))
    fig.add_hline(y=100, line=dict(color=T["border"], width=1))
    for k, g in d.groupby("series", sort=False):
        w = 4 if k in ("NIFTY", "INR", "BRENT") else 2.5
        fig.add_trace(go.Scatter(x=g.offset, y=g["index"], name=ECON_LABEL.get(k, k), mode="lines",
                                 line=dict(color=ECON_COL.get(k, T["text3"]), width=w),
                                 customdata=g.date, hovertemplate="day %{x} (%{customdata}): %{y:.1f}<extra>"
                                 + ECON_LABEL.get(k, k) + "</extra>"))
    day0 = d.day0.iloc[0] if len(d) else ""
    fig.add_annotation(x=0, y=1.0, yref="paper", text=f"DAY 0  {day0}", showarrow=False, xanchor="left",
                       font=dict(color=T["red"], size=13))
    fig.update_layout(title=title or f"{case}: markets around the war shock (index, last close before day 0 = 100)",
                      xaxis_title="Trading days from the shock (day 0 from UCDP deaths)", yaxis_title="Index",
                      height=480)
    return fig


def fig_econ_event_bars(es: pd.DataFrame, horizon="d20_pct"):
    """20-day move per episode and series, coloured by placebo significance."""
    d = es.copy()
    d["lab"] = d.conflict_case.map(C.CASE_SHORT) + " " + d.day0.str[:7] + " · " + d.series.map(lambda k: ECON_LABEL.get(k, k))
    d = d.sort_values(horizon)
    col = np.where(d.p20 < 0.05, T["red"], np.where(d.p20 < 0.10, T["amber"], T["muted"]))
    fig = go.Figure(go.Bar(x=d[horizon], y=d.lab, orientation="h", marker_color=col,
                           customdata=np.stack([d.p20, d.label], axis=1),
                           hovertemplate="%{y}<br>%{x:+.1f}% in 20 trading days<br>placebo p = %{customdata[0]:.2f}<extra></extra>"))
    fig.update_layout(title="Every war shock, every market: move over 20 trading days (red p<0.05, amber p<0.10 vs placebo days)",
                      xaxis_title="% change (currencies: value vs USD)", height=max(520, 15 * len(d)),
                      margin=dict(l=330), yaxis=dict(tickfont=dict(size=11)))
    return fig


def fig_econ_india(ind: pd.DataFrame, gp: pd.DataFrame | None = None):
    d = ind.copy()
    d["month"] = pd.to_datetime(d.month)
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.06,
                        subplot_titles=["Brent crude (USD/bbl, monthly mean)", "Nifty 50 and rupee (INR per USD)",
                                        "War deaths per month (UCDP, log)"],
                        specs=[[{}], [{"secondary_y": True}], [{}]], row_heights=[0.3, 0.35, 0.35])
    fig.add_trace(go.Scatter(x=d.month, y=d.BRENT, name="Brent", line=dict(color=T["amber"], width=3)), 1, 1)
    fig.add_trace(go.Scatter(x=d.month, y=d.NIFTY, name="Nifty 50", line=dict(color=T["red"], width=3)), 2, 1)
    fig.add_trace(go.Scatter(x=d.month, y=d.INR, name="INR per USD", line=dict(color="#FF9AA5", width=2, dash="dot")),
                  2, 1, secondary_y=True)
    for case in C.CASES:
        fig.add_trace(go.Scatter(x=d.month, y=d["deaths_" + C.CASE_SHORT[case]], name=case,
                                 line=dict(color=CC[case], width=2)), 3, 1)
    fig.update_yaxes(type="log", row=3, col=1)
    for x, t in [("2022-02-24", "RU–UA"), ("2023-10-07", "7 Oct"), ("2026-02-28", "Gulf war")]:
        fig.add_vline(x=x, line=dict(color=T["red"], width=1.5, dash="dash"))
        fig.add_annotation(x=x, y=1.0, yref="paper", text=t, showarrow=False, font=dict(color=T["red"], size=12),
                           xanchor="left")
    fig.update_layout(title="India's exposure is economic: oil, equities and the rupee move with the wars", height=760,
                      margin=dict(t=120), legend=dict(y=1.1, yanchor="bottom"))
    return fig


def fig_econ_fronts(fr: pd.DataFrame):
    """Battlefield vs economic front, one row per theatre's largest episode."""
    d = fr.copy()
    fig = make_subplots(rows=1, cols=2, column_widths=[0.38, 0.62], horizontal_spacing=0.12,
                        subplot_titles=["Battlefield: deaths in the episode (UCDP)", "Economic front: worst move within 60 trading days (%)"])
    d["conflict_case"] = d.conflict_case.map(C.CASE_SHORT)
    fig.add_trace(go.Bar(y=d.conflict_case, x=d.episode_deaths, orientation="h",
                         marker_color=[CC[c] for c in fr.conflict_case], showlegend=False,
                         text=[f"{v:,.0f} · {n} countries" for v, n in zip(d.episode_deaths, d.countries_with_deaths)],
                         textposition="outside"), 1, 1)
    for col, lab, colr in [("local_equity_worst60_pct", "Local stock index", T["cyan"]),
                           ("local_fx_worst60_pct", "Local currency", "#7FA7D9"),
                           ("brent_best60_pct", "Brent (peak rise)", T["amber"]),
                           ("nifty_worst60_pct", "Nifty 50", T["red"]),
                           ("inr_worst60_pct", "Rupee", "#FF9AA5")]:
        fig.add_trace(go.Bar(y=d.conflict_case, x=d[col], name=lab, orientation="h", marker_color=colr), 1, 2)
    fig.update_layout(barmode="group", height=520, title="Two fronts: who dies on the battlefield, who pays on the economic front",
                      legend=dict(y=-0.18, yanchor="top"), margin=dict(l=90))
    fig.update_xaxes(type="log", row=1, col=1, range=[2.5, 5.6])
    return fig


def fig_econ_reserves(res: pd.DataFrame):
    d = res[res.iso3.isin(["IND", "PAK", "RUS", "ISR", "UKR"])].copy()
    fig = go.Figure()
    nm = {"IND": "India", "PAK": "Pakistan", "RUS": "Russia", "ISR": "Israel", "UKR": "Ukraine"}
    cl = {"IND": T["red"], "PAK": T["teal"], "RUS": T["cyan"], "ISR": T["amber"], "UKR": T["violet"]}
    for iso, g in d.groupby("iso3"):
        fig.add_trace(go.Scatter(x=g.year, y=g.months_of_imports, name=nm[iso], mode="lines+markers",
                                 line=dict(color=cl[iso], width=3)))
    fig.add_hline(y=3, line=dict(color=T["amber"], dash="dot"), annotation_text="3-month import cover (IMF rule of thumb)")
    fig.update_layout(title="Reserves in months of imports (World Bank, end-year)", yaxis_title="Months of imports",
                      height=440)
    return fig
