"""Figures for the Theatre Commander layer (AOR map, GDELT nowcast strip, market strip, RAG history, OODA timeline).

Maps use the India-point-of-view boundaries (assets/web/world_ind.json) on plain axes, like the rest of the app,
so they render offline and show India's boundary as India claims it.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from . import config as C
from . import theatre as TH

T = C.THEME
_W = None
VIEW = {"WTC": ((58, 80), (20, 40)), "NTC": ((72, 99), (24, 39)), "MTC": ((30, 100), (-9, 32)),
        "CDS": ((30, 100), (-9, 42))}


def _world():
    global _W
    if _W is None:
        _W = json.loads((C.ROOT / "assets" / "web" / "world_ind.json").read_text(encoding="utf-8"))
    return _W


def _rings(geom):
    if geom["type"] == "Polygon":
        return [geom["coordinates"][0]]
    return [p[0] for p in geom["coordinates"]]


def _layout(fig, title, height):
    fig.update_layout(title=title, height=height, paper_bgcolor=T["bg"], plot_bgcolor=T["bg"],
                      font=dict(color=T["text2"], size=15), margin=dict(l=10, r=10, t=56, b=10))
    return fig


def fig_aor_map(brief: dict, code: str, height=620):
    lon_r, lat_r = VIEW[code]
    fig = go.Figure()
    xs, ys, ix, iy = [], [], [], []
    for f in _world()["features"]:
        iso = f["properties"].get("ADM0_A3")
        if not f.get("geometry"):
            continue
        for ring in _rings(f["geometry"]):
            a = np.array(ring)
            if a[:, 0].max() < lon_r[0] - 15 or a[:, 0].min() > lon_r[1] + 15:
                continue
            tx, ty = (ix, iy) if iso == "IND" else (xs, ys)
            tx += list(a[:, 0]) + [None]
            ty += list(a[:, 1]) + [None]
    fig.add_trace(go.Scatter(x=xs, y=ys, fill="toself", fillcolor="#10273D", mode="lines",
                             line=dict(color=T["border"], width=0.6), hoverinfo="skip", showlegend=False))
    fig.add_trace(go.Scatter(x=ix, y=iy, fill="toself", fillcolor="#133349", mode="lines",
                             line=dict(color=T["cyan"], width=2.5), hoverinfo="skip", showlegend=False, name="India"))
    for k, t in TH.THEATRES.items():
        ring = t["polygon"] + [t["polygon"][0]]
        on = code in (k, "CDS")
        fig.add_trace(go.Scatter(x=[p[0] for p in ring], y=[p[1] for p in ring], mode="lines", fill="toself",
                                 fillcolor=_rgba(t["color"], 0.16 if on else 0.03),
                                 line=dict(color=t["color"], width=3 if on else 1, dash="solid" if on else "dot"),
                                 name=f"{k} AOR (notional)", hoverinfo="name", showlegend=on))
    ds = pd.DataFrame(brief["districts"])
    if len(ds):
        ds = ds.dropna(subset=["lon", "lat"])
        real, syn = ds[~ds.synthetic], ds[ds.synthetic]
        for sub, sym, lab in [(real, "circle", "District nowcast P(escalation)"), (syn, "diamond", "[SYNTHETIC] LAC sector")]:
            if not len(sub):
                continue
            fig.add_trace(go.Scatter(
                x=sub.lon, y=sub.lat, mode="markers", name=lab,
                marker=dict(size=10 + 60 * sub.p_now.clip(0, 0.45), symbol=sym, color=sub.p_now, cmin=0, cmax=0.35,
                            colorscale=[[0, T["teal"]], [0.43, T["amber"]], [1, T["red"]]],
                            line=dict(color="#fff", width=1.2), showscale=sym == "circle",
                            colorbar=dict(title="P now", x=1.0, len=0.6, tickformat=".2f")),
                text=[f"{'[SYNTHETIC] ' if s else ''}{n} ({i})<br>nowcast P {p:.2f}" for n, i, p, s in
                      zip(sub.name, sub.iso, sub.p_now, sub.synthetic)], hoverinfo="text"))
        hot = ds[ds.p_now >= TH.FLASH_P]
        if len(hot):
            fig.add_trace(go.Scatter(x=hot.lon, y=hot.lat, mode="text", text=hot.name, textposition="top center",
                                     textfont=dict(color=T["text"], size=13), showlegend=False, hoverinfo="skip"))
    marks = [("LoC / J&K", 74.6, 34.3, "WTC"), ("Punjab", 75.4, 30.9, "WTC"), ("Rajasthan", 73.6, 26.6, "WTC"),
             ("Sir Creek", 68.6, 23.7, "WTC"), ("Strait of Hormuz", 56.3, 26.6, "MTC"), ("Chabahar", 60.6, 25.3, "MTC"),
             ("Bab-el-Mandeb", 43.4, 12.6, "MTC"), ("Sri Lanka", 80.7, 7.6, "MTC"), ("Bay of Bengal", 88.0, 15.0, "MTC"),
             ("Tawang", 91.9, 27.6, "NTC"), ("Ladakh", 77.6, 34.2, "NTC"), ("Sikkim", 88.5, 27.5, "NTC")]
    m = pd.DataFrame(marks, columns=["n", "x", "y", "t"])
    m = m[(m.x.between(*lon_r)) & (m.y.between(*lat_r)) & ((m.t == code) | (code == "CDS"))]
    fig.add_trace(go.Scatter(x=m.x, y=m.y, text=m.n, mode="markers+text", textposition="bottom right",
                             marker=dict(size=6, color=T["amber"]), textfont=dict(size=12, color=T["amber"]),
                             showlegend=False, hoverinfo="text"))
    fig.update_xaxes(visible=False, range=list(lon_r), constrain="domain")
    fig.update_yaxes(visible=False, range=list(lat_r), scaleanchor="x", scaleratio=1.15, constrain="domain")
    fig.update_layout(legend=dict(orientation="h", y=-0.02, x=0, bgcolor="rgba(7,19,31,0.7)", font=dict(size=13)))
    return _layout(fig, f"{code} AOR (notional) · India's boundary as India claims it", height)


def _rgba(hexc: str, a: float) -> str:
    h = hexc.lstrip("#")
    return f"rgba({int(h[0:2], 16)},{int(h[2:4], 16)},{int(h[4:6], 16)},{a})"


def fig_gdelt_strip(code: str, end: str, days: int = 75, height=360):
    t = TH.theatre(code)
    gc = pd.read_csv(TH.GD / "gdelt_case_daily.csv", parse_dates=["date"])
    ga = pd.read_csv(TH.GD / "gdelt_actiongeo_daily.csv", parse_dates=["date"])
    e = pd.Timestamp(end)
    fig = go.Figure()
    pal = [T["amber"], T["cyan"], T["teal"], T["violet"], T["red"], "#7FA7C9", "#E28CC1", "#9AD07F", "#C9B37F"]
    i = 0
    for c in t["gdelt_case"]:
        s = gc[gc.case_id == c].set_index("date").violent_events
        i = _strip(fig, s, e, days, f"{TH.CASE_LABEL.get(c, c)} violent events", pal[i % 9], i)
    for g in t["gdelt_geo"]:
        s = ga[ga.actiongeo_country_code == g].set_index("date").material_conflict
        i = _strip(fig, s, e, days, f"{TH.GEO_LABEL.get(g, g)} material conflict", pal[i % 9], i)
    fig.add_vrect(x0=e - pd.Timedelta(days=6.5), x1=e + pd.Timedelta(days=0.5), fillcolor=T["amber"], opacity=0.08,
                  line_width=0, annotation_text="last 7 days", annotation_position="top left")
    fig.update_yaxes(type="log", title="events / day (7-day mean)")
    return _layout(fig, "GDELT nowcast for the AOR (7-day mean, log scale): runs 43 days past UCDP's last record",
                   height)


def _strip(fig, s, e, days, name, col, i):
    s = s.sort_index()
    s = s[(s.index > e - pd.Timedelta(days=days)) & (s.index <= e)]
    fig.add_trace(go.Scatter(x=s.index, y=s.rolling(7, min_periods=3).mean() + 0.5, name=name,
                             line=dict(color=col, width=3)))
    return i + 1


def fig_econ_strip(code: str, end: str, days: int = 120, height=360):
    from . import econ as EC
    e = pd.Timestamp(end)
    fig = go.Figure()
    pal = [T["amber"], T["cyan"], T["teal"], T["violet"], T["red"]]
    for i, k in enumerate(TH.theatre(code)["econ"]):
        try:
            s = EC.load_series(k)
        except Exception:  # noqa: BLE001
            continue
        s = s[(s.index > e - pd.Timedelta(days=days)) & (s.index <= e)]
        if not len(s):
            continue
        fig.add_trace(go.Scatter(x=s.index, y=100 * s / s.iloc[0], name=TH.ECON_LABEL[k], line=dict(color=pal[i % 5], width=3)))
    fig.add_hline(y=100, line=dict(color=T["muted"], dash="dot"))
    fig.update_yaxes(title=f"index, {days} days ago = 100")
    return _layout(fig, "Economic second front for this theatre (oil, shipping, rupee)", height)


def fig_rag_history(H: dict, height=300):
    codes = TH.ROLES
    z, txt = [], []
    lvl = {"GREEN": 0, "AMBER": 1, "RED": 2}
    for k in codes:
        z.append([lvl[b["rating"]] for b in H["briefs"][k]])
        txt.append([f"{b['rating']} {b['arrow']}" + (" *" if b["synthetic"] and k == "NTC" else "") for b in H["briefs"][k]])
    fig = go.Figure(go.Heatmap(z=z, x=[pd.Timestamp(d) + pd.Timedelta(days=1) for d in H["dates"]], y=codes, text=txt,
                               texttemplate="%{text}", textfont=dict(size=15, color=T["bg"]), zmin=0, zmax=2,
                               colorscale=[[0, T["teal"]], [0.5, T["amber"]], [1, T["red"]]], showscale=False, xgap=4,
                               ygap=4, hovertemplate="%{y} %{x|%d %b}: %{text}<extra></extra>"))
    fig.update_xaxes(tickformat="%d %b<br>0600 IST")
    fig.update_yaxes(autorange="reversed", tickfont=dict(size=17, color=T["text"]))
    _layout(fig, "Seven days of 0600 briefs: threat level by theatre (* NTC runs on synthetic LAC data)", height)
    fig.update_layout(margin=dict(l=70, r=10, t=56, b=60))
    return fig


def fig_ooda(height=420):
    tot = TH.ooda_totals()
    fig = go.Figure()
    y0, y1 = "Today (staff cycle)", "With Conflict EW"
    s0 = s1 = 0.0
    cols = [T["cyan"], T["amber"], T["teal"], T["violet"]]
    for i, st in enumerate(TH.OODA):
        a = np.mean(st["today_h"])
        b = np.mean(st["cw_h"])
        fig.add_trace(go.Bar(y=[y0], x=[a], base=[s0], orientation="h", marker_color=cols[i], name=st["stage"],
                             legendgroup=st["stage"], text=f"{st['stage']}<br>{a / 24:.1f} d", textposition="inside",
                             insidetextanchor="middle", hovertemplate=f"{st['stage']} today: {st['today_h'][0]}–{st['today_h'][1]} h<extra></extra>"))
        fig.add_trace(go.Bar(y=[y1], x=[b], base=[s1], orientation="h", marker_color=cols[i], name=st["stage"],
                             legendgroup=st["stage"], showlegend=False, hovertemplate=f"{st['stage']} with CW: {st['cw_h'][0]}–{st['cw_h'][1]} h<extra></extra>"))
        s0 += a
        s1 += b
    fig.add_annotation(x=s1, y=y1, text=f"  ≈{s1:.0f} h", showarrow=False, xanchor="left", font=dict(size=20, color=T["amber"]))
    fig.add_annotation(x=s0, y=y0, text=f"  ≈{s0 / 24:.1f} days", showarrow=False, xanchor="left", font=dict(size=20, color=T["text"]))
    fig.update_layout(barmode="overlay", xaxis=dict(title="hours from event to action (midpoint of the range)",
                                                    range=[0, s0 * 1.18]),
                      legend=dict(orientation="h", y=-0.42, x=0), yaxis=dict(tickfont=dict(size=16, color=T["text"])))
    _layout(fig, f"Event to decision: {tot['today_days'][0]:.0f}–{tot['today_days'][1]:.0f} days -> "
                        f"{tot['cw_hours'][0]:.0f}–{tot['cw_hours'][1]:.0f} hours (DOMAIN estimate of staff timings)", height)
    fig.update_layout(margin=dict(l=210, r=20, t=60, b=120))
    return fig


def export_figures(B: dict) -> list[str]:
    """Static figures for the report and deck (outputs/figures/34-36_*). Needs kaleido."""
    from . import viz
    end = B["dates"][-1]
    cds = B["briefs"]["CDS"][-1]
    out = []
    for name, fig, kw in [("34_theatre_aor", fig_aor_map(cds, "CDS", height=720), dict(width=1300)),
                          ("35_theatre_history", fig_rag_history(B, height=330), dict(width=1300)),
                          ("36_theatre_ooda", fig_ooda(height=430), dict(width=1300)),
                          ("37_theatre_wtc", fig_aor_map(B["briefs"]["WTC"][-1], "WTC", height=640), dict(width=900)),
                          ("38_theatre_gdelt_mtc", fig_gdelt_strip("MTC", end), dict(width=1100))]:
        viz.save(fig, name, **kw)
        out.append(name)
    return out
