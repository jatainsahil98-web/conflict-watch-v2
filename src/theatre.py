"""Theatre Commander layer: notional theatre AORs, daily OODA briefs, FLASH alerts and a mock inbox.

NEW, separately labelled layer. It reads the frozen outputs of ``run_pipeline.py`` (RAG scorecard,
early-warning watch-list, SHAP drivers) plus the daily GDELT and market files, and writes only to
``outputs/theatre/``. It never writes to ``outputs/tables/``, so the run ID (a hash of those tables)
and every number in the report and deck stay the same.

NOTIONAL. India's theatre commands have not been notified. The three AORs below are illustrative,
drawn from public reporting, and their polygons are coarse sketches, not boundaries.

SYNTHETIC. The competition data hold no LAC (India–China) incidents. The Northern theatre therefore
runs on a seeded synthetic incident generator, flagged ``synthetic=True`` on every row and marked
[SYNTHETIC] wherever it is shown. It includes a scripted demo surge (flagged) so the FLASH path can be
shown. Nothing synthetic feeds the forecasting or early-warning models.

Daily logic (data up to day d; the brief is dated d+1, 0600 IST)
  OBSERVE  candidate changes in the AOR, ranked by size: GDELT spikes (last 24 h z-score vs the prior
           28 days; last 7 days vs the 28 days before), district escalation alerts, market moves
           (5-day change z-scored against two years of 5-day changes), the latest UCDP week, and
           [SYNTHETIC] LAC incidents. Top five go in the brief.
  ORIENT   theatre score = base from the monthly RAG of the linked conflicts (RED 6, AMBER 4,
           GREEN 2) + daily modifiers (GDELT 7-day ratio, 24 h spike, districts over threshold, market
           stress, LAC surge). Score >= 6 RED, 3-5 AMBER, <= 2 GREEN. Trend arrow from the 7-day
           GDELT ratio. Confidence from source agreement and how much of the picture is real data.
  DECIDE   a playbook of candidate actions (ISR tasking, force posture, evacuation readiness,
           logistics buffers, maritime domain awareness) scored on the same signals; top three.
  ACT      each action carries an owner (notional staff branch), a timeline (24 h / 72 h / 7 d) and a
           quantitative trigger to escalate.
  FLASH    raised when a district's nowcast probability crosses the escalation threshold upward,
           or a theatre's RAG changes, between two consecutive daily runs.

District nowcast (heuristic, NOT back-tested): the model's monthly P(escalation) is nudged by the
theatre's 7-day GDELT ratio: logit(p_now) = logit(p) + 0.5 * clip(ln r7, -1, 1).
"""
from __future__ import annotations

import json
import math
from datetime import timedelta

import numpy as np
import re

import pandas as pd

from . import config as C

OUT = C.ROOT / "outputs" / "theatre"
GD = C.ROOT / "data" / "gdelt"
IST = timedelta(hours=5, minutes=30)

ALERT_P = 0.15          # district shown as an alert (dashboard default slider)
FLASH_P = 0.20          # escalation threshold: crossing it upward raises a FLASH
NOWCAST_BETA = 0.5
RAG_BASE = {"RED": 3, "AMBER": 2, "GREEN": 1}

NOTIONAL = ("NOTIONAL: India's theatre commands are not yet notified. AORs, owners and HQs are "
            "illustrative, based on public reporting.")
SYN_NOTE = "SYNTHETIC: seeded generator (seed 2026), not real incidents. Shown only to demonstrate the workflow."

# ---------------------------------------------------------------------------
# Theatre definitions (notional)
# ---------------------------------------------------------------------------
# Polygons are [lon, lat] rings, coarse and illustrative. Overlaps are deliberate (Gilgit-Baltistan
# sits in both WTC and NTC: the collusive two-front problem; the Makran coast in WTC and MTC).
THEATRES = {
    "WTC": dict(
        code="WTC", name="Western Theatre Command", short="Western", color=C.THEME["teal"],
        front="Pakistan front", hq="notional",
        sectors=["LoC / J&K", "IB: Punjab", "IB: Rajasthan", "Sir Creek / Gujarat", "Af–Pak spill-over"],
        cases=["Afghanistan–Pakistan"], context_cases=[],
        gdelt_case=["AF-PAK"], gdelt_geo=["PK", "AF"],
        econ=["INR", "NIFTY", "AFN"],   # PKR left out: its daily quotes alternate between two sources (see caveats)
        polygon=[[60.9, 29.4], [61.2, 31.4], [60.8, 34.4], [62.5, 35.6], [65.0, 37.3], [70.8, 38.4], [74.9, 37.4],
                 [77.8, 35.6], [76.9, 33.2], [77.2, 31.6], [77.0, 30.2], [78.2, 27.6], [77.4, 25.2], [75.4, 23.4],
                 [74.4, 21.4], [72.7, 20.6], [70.6, 20.7], [68.6, 22.3], [67.4, 23.6], [66.2, 25.0], [64.0, 25.1],
                 [61.6, 25.1], [61.6, 27.0]],
        india_lens="Pakistan's western front, the TTP insurgency and the Af–Pak interstate clashes are a standing "
                   "indicator for diversionary activity on the LoC and the IB.",
    ),
    "NTC": dict(
        code="NTC", name="Northern Theatre Command", short="Northern", color="#E28CC1",
        front="China / LAC", hq="notional",
        sectors=["Eastern Ladakh", "Central sector", "Sikkim", "Arunachal Pradesh"],
        cases=[], context_cases=["Afghanistan–Pakistan", "Russia–Ukraine"],
        gdelt_case=[], gdelt_geo=["IN"],
        econ=["INR", "NIFTY", "GOLD"],
        polygon=[[74.0, 36.6], [76.0, 37.2], [78.0, 36.2], [80.5, 35.9], [80.6, 34.3], [79.5, 32.6], [81.2, 30.5],
                 [83.5, 29.6], [86.0, 28.9], [88.2, 28.3], [90.0, 28.5], [92.0, 28.3], [93.5, 29.3], [95.5, 29.5],
                 [97.4, 28.4], [96.5, 27.0], [93.5, 26.9], [91.5, 26.6], [89.5, 26.5], [88.0, 26.7], [88.3, 27.0],
                 [84.5, 27.3], [80.8, 28.8], [79.0, 29.9], [77.5, 31.3], [76.8, 32.6], [75.8, 34.0], [74.2, 35.0]],
        india_lens="The LAC is outside the competition data. This view runs on [SYNTHETIC] incidents to show the "
                   "workflow; Af–Pak and Russia–Ukraine are linked as context (collusive threat via Gilgit-"
                   "Baltistan; Russian-origin spares and air-defence deliveries).",
    ),
    "MTC": dict(
        code="MTC", name="Maritime Theatre Command", short="Maritime", color=C.THEME["violet"],
        front="Indian Ocean Region", hq="notional",
        sectors=["Arabian Sea", "Gulf / Strait of Hormuz", "Red Sea / Bab-el-Mandeb", "Bay of Bengal",
                 "Sri Lanka waters", "Chabahar sea lanes"],
        cases=["US–Iran"], context_cases=["Israel–Hamas"],
        gdelt_case=["US-IRAN"], gdelt_geo=["IR", "AE", "SA", "KU", "QA", "BA", "MU", "CE"],
        econ=["BRENT", "TTF", "FRO", "ZIM", "INR"],
        polygon=[[32.6, 29.9], [35.0, 29.6], [38.0, 25.5], [44.0, 25.0], [47.6, 30.6], [49.5, 31.4], [51.5, 30.2],
                 [54.5, 28.2], [57.5, 28.0], [60.6, 26.6], [61.6, 25.1], [66.2, 25.0], [67.4, 23.6], [69.2, 22.2],
                 [72.7, 21.2], [72.9, 17.5], [74.4, 13.5], [76.4, 9.0], [77.6, 8.2], [79.3, 9.6], [80.3, 13.2],
                 [82.4, 17.0], [86.9, 20.6], [88.8, 21.6], [91.8, 22.3], [94.3, 18.5], [98.6, 10.0], [98.0, 4.0],
                 [94.0, -2.0], [70.0, -8.0], [40.0, -8.0], [42.0, -1.5], [48.5, 5.0], [51.4, 11.8], [43.4, 12.4],
                 [39.5, 15.8], [36.5, 22.0], [33.6, 27.5]],
        india_lens="The 2026 war struck Gulf states that host Indian workers and reached Sri Lanka's waters "
                   "(104 killed, 4 Mar 2026). Evacuation, energy and sea lanes are the issues (DOMAIN).",
    ),
}
CDS = dict(code="CDS", name="Chief of Defence Staff", short="All theatres", color=C.THEME["amber"],
           front="All theatres + strategic", hq="notional", sectors=["WTC", "NTC", "MTC", "Strategic (RU–UA)"],
           cases=list(C.CASES), context_cases=[], gdelt_case=["AF-PAK", "US-IRAN", "ISR-HAMAS", "RU-UA"],
           gdelt_geo=[], econ=["BRENT", "INR", "NIFTY", "GOLD", "VIX"], polygon=None,
           india_lens="Both notional theatres plus the strategic Russia–Ukraine sustainment picture.")
# v2: the Northern (LAC) view is dropped. The issued data hold no LAC incidents, and a rating built on
# synthetic incidents should not be shown to a decision-maker.
THEATRES.pop("NTC")
CDS["sectors"] = ["WTC", "MTC", "Strategic (RU–UA)"]
ROLES = ["WTC", "MTC", "CDS"]


def theatre(code: str) -> dict:
    return CDS if code == "CDS" else THEATRES[code]


ROLE_LABEL = {k: f"{k} · {theatre(k)['name']}" for k in ROLES}

# Synthetic LAC sectors (approximate public locations of past face-offs)
LAC_SECTORS = [
    # name, sector, lon, lat, base incidents per day
    ("Depsang Plains", "Eastern Ladakh", 78.10, 35.30, 0.10),
    ("Galwan", "Eastern Ladakh", 78.20, 34.75, 0.05),
    ("Pangong Tso", "Eastern Ladakh", 78.70, 33.75, 0.08),
    ("Demchok", "Eastern Ladakh", 79.45, 32.70, 0.07),
    ("Barahoti", "Central sector", 79.90, 30.80, 0.04),
    ("Naku La", "Sikkim", 88.70, 28.00, 0.05),
    ("Yangtse (Tawang)", "Arunachal Pradesh", 91.90, 27.80, 0.08),
    ("Asaphila", "Arunachal Pradesh", 93.50, 28.40, 0.04),
    ("Kibithu", "Arunachal Pradesh", 96.90, 28.30, 0.03),
]
LAC_TYPES = {"transgression": 0.35, "face-off": 0.20, "airspace violation": 0.15, "infrastructure activity": 0.20,
             "PLA exercise nearby": 0.10}
# Scripted demo surge (flagged on every row it creates): build-up in Tawang and at Depsang in the last week.
LAC_SURGE = [("Yangtse (Tawang)", "2026-11-08", "2026-11-12", 1.2, "face-off"),
             ("Depsang Plains", "2026-11-10", "2026-11-12", 0.9, "infrastructure activity")]

ECON_ADVERSE = {"BRENT": 1, "TTF": 1, "FRO": 1, "ZIM": 1, "GOLD": 1, "VIX": 1, "INR": -1, "PKR": -1, "AFN": -1,
                "NIFTY": -1}
ECON_LABEL = {"BRENT": "Brent crude", "TTF": "European gas (TTF)", "FRO": "Tanker equities (Frontline)",
              "ZIM": "Container shipping (ZIM)", "GOLD": "Gold", "VIX": "VIX", "INR": "Rupee vs USD",
              "PKR": "Pakistan rupee vs USD", "AFN": "Afghani vs USD", "NIFTY": "Nifty 50"}
GEO_LABEL = {"PK": "Pakistan", "AF": "Afghanistan", "IN": "India", "IR": "Iran", "AE": "UAE", "SA": "Saudi Arabia",
             "KU": "Kuwait", "QA": "Qatar", "BA": "Bahrain", "MU": "Oman", "CE": "Sri Lanka"}
CASE_LABEL = {"AF-PAK": "Af–Pak", "US-IRAN": "US–Iran", "ISR-HAMAS": "Israel–Hamas", "RU-UA": "Russia–Ukraine"}
FEATURE_PLAIN = {"y_ewm": "recent trend in the area's deaths", "cty_y_l0": "country-wide tempo this month",
                 "y_rm12": "12-month level", "case_momentum_3v12": "whole-conflict momentum",
                 "y_max12": "12-month peak", "cty_mom": "country momentum", "log_events_rm3": "event count, 3 months",
                 "case_n_admin1_rm3": "how many areas are active"}


# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------
def inside(lon: float, lat: float, poly: list) -> bool:
    """Ray casting point-in-polygon (no shapely dependency)."""
    if lon is None or lat is None or poly is None:
        return False
    x, y, n, ok = lon, lat, len(poly), False
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi:
            ok = not ok
        j = i
    return ok


def aor_geojson() -> dict:
    feats = []
    for k, t in THEATRES.items():
        ring = t["polygon"] + [t["polygon"][0]]
        feats.append(dict(type="Feature", geometry=dict(type="Polygon", coordinates=[ring]),
                          properties=dict(code=k, name=t["name"], front=t["front"], sectors=t["sectors"],
                                          cases=t["cases"], context_cases=t["context_cases"], color=t["color"],
                                          notional=True, note=NOTIONAL)))
    return dict(type="FeatureCollection", name="theatre_aor_notional", features=feats)


# ---------------------------------------------------------------------------
# Synthetic LAC data (flagged)
# ---------------------------------------------------------------------------
def synthetic_lac(start="2026-01-01", end="2026-11-12", seed=2026) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    days = pd.date_range(start, end, freq="D")
    season = 0.55 + 0.45 * np.sin((days.dayofyear - 80) / 365 * 2 * np.pi)  # summer peak, winter low
    rows = []
    types, tp = list(LAC_TYPES), np.array(list(LAC_TYPES.values()))
    for name, sector, lon, lat, lam in LAC_SECTORS:
        n = rng.poisson(lam * season)
        for d, k in zip(days, n):
            for _ in range(k):
                rows.append(dict(date=d, location=name, sector=sector, lon=lon, lat=lat,
                                 type=rng.choice(types, p=tp), scripted_demo_surge=False))
    for name, a, b, lam, typ in LAC_SURGE:
        loc = next(s for s in LAC_SECTORS if s[0] == name)
        for d in pd.date_range(a, b):
            for _ in range(max(1, rng.poisson(lam))):
                rows.append(dict(date=d, location=name, sector=loc[1], lon=loc[2], lat=loc[3], type=typ,
                                 scripted_demo_surge=True))
    df = pd.DataFrame(rows).sort_values(["date", "location"]).reset_index(drop=True)
    df["synthetic"] = True
    df["source"] = "SYNTHETIC (seeded generator, seed 2026) - not real incidents"
    return df


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------
def load_inputs() -> dict:
    TB = C.TAB_DIR
    areas = json.loads((C.ROOT / "web" / "public" / "data" / "areas.json").read_text(encoding="utf-8"))["areas"]
    ll = {a["key"]: (a["lon"], a["lat"], a["name"]) for a in areas}
    lv = pd.read_parquet(C.PROCESSED / "early_warning_live.parquet")
    lv = lv[~lv.admin1.str.startswith("(")].copy()
    lv["lon"] = lv.admin1_key.map(lambda k: ll.get(k, (None,))[0])
    lv["lat"] = lv.admin1_key.map(lambda k: ll.get(k, (None, None))[1])
    lv["name"] = lv.admin1_key.map(lambda k: ll.get(k, (None, None, None))[2]).fillna(lv.admin1)
    gc = pd.read_csv(GD / "gdelt_case_daily.csv", parse_dates=["date"])
    ga = pd.read_csv(GD / "gdelt_actiongeo_daily.csv", parse_dates=["date"])
    econ = {}   # v2: issued competition data only, so no market series
    ev = pd.read_parquet(C.PROCESSED / "events.parquet", columns=["conflict_case", "date_start", "admin1_key",
                                                                   "country_iso3", "deaths_best"])
    ev = ev[ev.date_start >= "2026-06-01"]
    shap = pd.read_csv(TB / "shap_early_warning.csv")
    gsig = pd.read_csv(TB / "gdelt_signals.csv")
    return dict(rag=pd.read_csv(TB / "rag_scorecard.csv"), live=lv, gc=gc, ga=ga, econ=econ, events=ev, shap=shap,
                gsig=gsig, lac=synthetic_lac(), areas=areas)


def latest_date(I: dict) -> pd.Timestamp:
    return min(I["gc"].date.max(), I["ga"].date.max())


# ---------------------------------------------------------------------------
# Signals
# ---------------------------------------------------------------------------
def _spike(v: pd.Series, d: pd.Timestamp) -> dict | None:
    v = v.sort_index()
    v = v[v.index <= d]
    if len(v) < 40 or d not in v.index:
        return None
    prev28 = v[(v.index > d - pd.Timedelta(days=29)) & (v.index < d)]
    last7 = v[v.index > d - pd.Timedelta(days=7)]
    prior28 = v[(v.index <= d - pd.Timedelta(days=7)) & (v.index > d - pd.Timedelta(days=35))]
    sd = prev28.std() or 1.0
    return dict(last=float(v.loc[d]), mean28=float(prev28.mean()), z=float((v.loc[d] - prev28.mean()) / sd),
                r7=float((last7.mean() + 1) / (prior28.mean() + 1)), last7=float(last7.mean()),
                prior28=float(prior28.mean()))


def gdelt_signals(T: dict, d: pd.Timestamp, I: dict) -> list[dict]:
    out = []
    gc, ga = I["gc"], I["ga"]
    for c in T["gdelt_case"]:
        s = gc[gc.case_id == c].set_index("date").violent_events
        r = _spike(s, d)
        if r:
            out.append(dict(series=f"GDELT violent events, {CASE_LABEL.get(c, c)} dyad", kind="gdelt", key=c, **r))
    for g in T["gdelt_geo"]:
        s = ga[ga.actiongeo_country_code == g].set_index("date").material_conflict
        r = _spike(s, d)
        if r:
            out.append(dict(series=f"GDELT material-conflict events in {GEO_LABEL.get(g, g)}", kind="gdelt", key=g, **r))
    return out


def econ_signals(T: dict, d: pd.Timestamp, I: dict) -> list[dict]:
    out = []
    for k in T["econ"]:
        s = I["econ"].get(k)
        if s is None:
            continue
        s = s[s.index <= d]
        if len(s) < 300:
            continue
        # 5-session median vs the 5 sessions before: robust to quote flicker (e.g. PKR alternating sources)
        m5 = s.rolling(5).median()
        r5 = np.log(m5 / m5.shift(5)).dropna()
        hist = r5[r5.index > d - pd.Timedelta(days=730)]
        z5 = float((r5.iloc[-1] - hist.mean()) / (hist.std() or 1))
        ch1 = float(m5.iloc[-1] / m5.iloc[-2] - 1) if len(m5) > 1 else 0.0
        ch5 = float(math.expm1(r5.iloc[-1]))
        adverse = ECON_ADVERSE[k] * z5
        out.append(dict(series=ECON_LABEL[k], key=k, kind="econ", close=float(s.iloc[-1]), asof=str(s.index[-1].date()),
                        ch1=ch1, ch5=ch5, z5=z5, adverse=adverse))
    return out


def lac_signals(d: pd.Timestamp, I: dict) -> list[dict]:
    lac = I["lac"]
    lac = lac[lac.date <= d]
    out = []
    for name, sector, lon, lat, _ in LAC_SECTORS:
        g = lac[lac.location == name]
        n7 = int((g.date > d - pd.Timedelta(days=7)).sum())
        n1 = int((g.date == d).sum())
        base = ((g.date <= d - pd.Timedelta(days=7)) & (g.date > d - pd.Timedelta(days=35))).sum() / 4
        r = (n7 + 0.5) / (base + 0.5)
        p = 1 / (1 + math.exp(-(-2.6 + 0.9 * math.log(r) + 0.25 * n7)))
        out.append(dict(name=name, sector=sector, lon=lon, lat=lat, n7=n7, n1=n1, base_wk=float(base), r7=float(r),
                        p_now=float(p), synthetic=True,
                        types=g[g.date > d - pd.Timedelta(days=7)].type.value_counts().to_dict()))
    return out


def theatre_r7(gs: list[dict]) -> float:
    if not gs:
        return 1.0
    return float(np.exp(np.median([np.log(max(x["r7"], 1e-3)) for x in gs])))


def in_aor(T: dict, df: pd.DataFrame) -> pd.Series:
    if T["polygon"] is None:
        return pd.Series(True, index=df.index)
    return df.apply(lambda r: inside(r.lon, r.lat, T["polygon"]), axis=1)


def district_signals(T: dict, d: pd.Timestamp, I: dict, r7: float) -> pd.DataFrame:
    lv = I["live"]
    x = lv[in_aor(T, lv)].copy()
    adj = NOWCAST_BETA * float(np.clip(np.log(max(r7, 1e-3)), -1, 1))
    lg = np.log(x.p_escalation / (1 - x.p_escalation)) + adj
    x["p_now"] = 1 / (1 + np.exp(-lg))
    x["synthetic"] = False
    return x.sort_values("p_now", ascending=False)


def ucdp_week(T: dict, I: dict) -> list[dict]:
    """Latest UCDP week (data end 30 Sep 2026) vs the mean of the previous 8 weeks, per AOR area."""
    ev = I["events"]
    keys = set(I["live"][in_aor(T, I["live"])].admin1_key)
    ev = ev[ev.admin1_key.isin(keys)]
    end = pd.Timestamp(C.PANEL_END)
    out = []
    for k, g in ev.groupby("admin1_key"):
        w = g[g.date_start > end - pd.Timedelta(days=7)].deaths_best.sum()
        b = g[(g.date_start <= end - pd.Timedelta(days=7)) & (g.date_start > end - pd.Timedelta(days=63))].deaths_best.sum() / 8
        if w >= 5 and w > 1.5 * b:
            out.append(dict(area=k.split(" | ")[1], iso=k.split(" | ")[0], deaths=float(w), base=float(b),
                            ratio=float((w + 1) / (b + 1))))
    return sorted(out, key=lambda r: -r["ratio"])


# ---------------------------------------------------------------------------
# Brief
# ---------------------------------------------------------------------------
def _arrow(r7: float) -> tuple[str, str]:
    if r7 >= 1.15:
        return "▲", "rising"
    if r7 <= 0.87:
        return "▼", "easing"
    return "►", "steady"


def _rag(score: int) -> str:
    """Base = 2 x the monthly RAG level (GREEN 2, AMBER 4, RED 6) plus daily modifiers. Escalating takes +2 from
    the base, de-escalating takes -2: the scale leans to warning, which is the prudent error for I&W."""
    return "RED" if score >= 6 else "AMBER" if score >= 3 else "GREEN"


def dtg(d: pd.Timestamp) -> str:
    b = d + pd.Timedelta(days=1)
    return f"{b:%d}0600 IST {b:%b %y}".upper()


def apply_shock(I: dict, d: pd.Timestamp, gdelt_mult: float = 1.0, p_shift: float = 0.0, lac_extra: int = 0) -> dict:
    """What-if: scale the last 7 days of GDELT, shift the model's district probabilities, add LAC incidents."""
    J = dict(I)
    wk = lambda df: (df.date > d - pd.Timedelta(days=7)) & (df.date <= d)   # noqa: E731
    for k, cols in (("gc", ["violent_events"]), ("ga", ["material_conflict"])):
        df = I[k].copy()
        m = wk(df)
        df.loc[m, cols] = df.loc[m, cols] * gdelt_mult
        J[k] = df
    lv = I["live"].copy()
    lv["p_escalation"] = (lv.p_escalation + p_shift).clip(0.001, 0.95)
    J["live"] = lv
    if lac_extra:
        add = pd.DataFrame([dict(date=d, location=n, sector=sc, lon=lo, lat=la, type="face-off", scripted_demo_surge=True,
                                 synthetic=True, source="WHAT-IF") for n, sc, lo, la, _ in LAC_SECTORS[:1]] * lac_extra)
        J["lac"] = pd.concat([I["lac"], add], ignore_index=True)
    return J


def build_brief(code: str, d: pd.Timestamp, I: dict) -> dict:
    T = theatre(code)
    if code == "CDS":
        subs = {k: build_brief(k, d, I) for k in THEATRES}
        return _cds_brief(d, I, subs)
    rag = I["rag"].set_index("conflict_case")
    gs = gdelt_signals(T, d, I)
    es = econ_signals(T, d, I)
    r7 = theatre_r7(gs)
    dist = district_signals(T, d, I, r7)
    lac = lac_signals(d, I) if code == "NTC" else []
    uw = ucdp_week(T, I)

    # ---- ORIENT: score
    pts = []
    if T["cases"]:
        base_case = max(T["cases"], key=lambda c: RAG_BASE[rag.loc[c, "rating"]])
        base = 2 * RAG_BASE[rag.loc[base_case, "rating"]]
        pts.append((base, f"{base_case} monthly RAG {rag.loc[base_case, 'rating']} (model scorecard, Oct 2026)"))
    else:
        base = 4
        pts.append((4, "Standing AMBER on the LAC: disengagement incomplete, forces forward (DOMAIN assumption)"))
    if gs:
        if r7 >= 1.75:
            pts.append((2, f"GDELT conflict reporting ×{r7:.2f} in the last 7 days vs the 4 weeks before"))
        elif r7 >= 1.3:
            pts.append((1, f"GDELT conflict reporting ×{r7:.2f} in the last 7 days vs the 4 weeks before"))
        elif r7 <= 0.75:
            pts.append((-1, f"GDELT conflict reporting down to ×{r7:.2f} of the 4 weeks before"))
        zmax = max(gs, key=lambda x: x["z"])
        if zmax["z"] >= 3:
            pts.append((1, f"24 h spike: {zmax['series']} z = {zmax['z']:.1f}"))
    n_flash = int((dist.p_now >= FLASH_P).sum()) + sum(1 for x in lac if x["p_now"] >= FLASH_P)
    if n_flash >= 2:
        pts.append((1, f"{n_flash} districts/sectors over the escalation threshold ({FLASH_P:.2f})"))
    stress = [x for x in es if x["adverse"] >= 2]
    if stress:
        pts.append((1, "Market stress: " + ", ".join(f"{x['series']} {x['ch5']:+.1%} in 5 days" for x in stress[:2])))
    if lac:
        tot7 = sum(x["n7"] for x in lac)
        totb = sum(x["base_wk"] for x in lac)
        lr = (tot7 + 1) / (totb + 1)
        if lr >= 2.5:
            pts.append((2, f"[SYNTHETIC] LAC incidents ×{lr:.1f} in 7 days ({tot7} vs {totb:.1f} a week)"))
        elif lr >= 1.5:
            pts.append((1, f"[SYNTHETIC] LAC incidents ×{lr:.1f} in 7 days ({tot7} vs {totb:.1f} a week)"))
    score = int(sum(p for p, _ in pts))
    rating = _rag(score)
    if code == "NTC":
        tr = (sum(x["n7"] for x in lac) + 1) / (sum(x["base_wk"] for x in lac) + 1)
        arrow, trend = _arrow(tr)
    else:
        arrow, trend = _arrow(r7)

    # confidence
    agree = I["gsig"]
    caseflag = {"Afghanistan–Pakistan": "Afghanistan–Pakistan", "US–Iran": "US–Iran"}
    trk = [bool(agree[(agree.case == caseflag[c])].gdelt_tracks_ucdp.iloc[-1]) for c in T["cases"] if c in caseflag]
    if code == "NTC":
        conf, conf_why = "LOW", "Picture is mostly [SYNTHETIC]; only India-wide GDELT and markets are real."
    elif trk and all(trk) and len(gs) >= 2:
        conf, conf_why = "MEDIUM", ("GDELT tracks UCDP for this conflict and several sources agree; UCDP itself "
                                    f"stops at {pd.Timestamp(C.PANEL_END):%d %b} (lagged), so not HIGH.")
    else:
        conf, conf_why = "LOW", "Sources disagree or GDELT does not track UCDP deaths for this conflict."

    drivers = [t for _, t in pts]
    shap_top = [FEATURE_PLAIN.get(f, f) for f in I["shap"].feature.head(3)]
    model_why = (f"Warning-model drivers (SHAP): {', '.join(shap_top)}." if code != "NTC" else
                 "No model covers the LAC: the warning model is trained on the four conflicts only, so this rating is "
                 "rules on [SYNTHETIC] counts.")

    # ---- OBSERVE
    obs = []
    for x in gs:
        if max(x["last7"], x["prior28"]) < 5:      # too few events a day for a ratio to mean anything
            continue
        if abs(x["z"]) >= 1.5 or abs(math.log(x["r7"])) >= math.log(1.25):
            win = "24h" if abs(x["z"]) >= abs(math.log(x["r7"])) * 3 else "7d"
            verb = "up" if x["r7"] >= 1 else "down"
            txt = (f"{x['series']} {verb}: {x['last7']:.0f}/day over 7 days vs {x['prior28']:.0f}/day the 4 weeks "
                   f"before (×{x['r7']:.2f}); yesterday {x['last']:.0f} (z {x['z']:+.1f})")
            obs.append(dict(text=txt, window=win, source="GDELT", tag="DATA",
                            mag=max(abs(x["z"]), 3 * abs(math.log(x["r7"])))))
    for _, r in dist.head(6).iterrows():
        if r.p_now >= ALERT_P:
            obs.append(dict(text=f"{r['name']} ({r.country_iso3}): P(escalation) {r.p_escalation:.2f}, nowcast "
                                 f"{r.p_now:.2f}{' - over threshold' if r.p_now >= FLASH_P else ''}",
                            window="7d", source="Warning model", tag="MODEL", mag=2 * r.p_now / ALERT_P,
                            area=r["name"]))
    for x in es:
        if abs(x["z5"]) >= 1.5:
            obs.append(dict(text=f"{x['series']} {x['ch5']:+.1%} over 5 sessions (median basis, z {x['z5']:+.1f}; "
                                 f"close {x['close']:,.2f} on {x['asof']})", window="7d", source="Markets", tag="DATA",
                            mag=abs(x["z5"]) * (1.2 if x["adverse"] > 0 else 0.8)))
    for u in uw[:3]:
        obs.append(dict(text=f"{u['area']} ({u['iso']}): {u['deaths']:.0f} deaths in the last UCDP week vs "
                             f"{u['base']:.1f}/week (data to 30 Sep)", window="7d", source="UCDP", tag="DATA",
                        mag=1.2 * math.log(u["ratio"])))
    for x in sorted(lac, key=lambda x: -x["r7"])[:4]:
        if x["n7"] >= 2 and x["r7"] >= 1.5:
            ty = ", ".join(f"{v} {k}" for k, v in x["types"].items())
            obs.append(dict(text=f"[SYNTHETIC] {x['name']} ({x['sector']}): {x['n7']} incidents in 7 days vs "
                                 f"{x['base_wk']:.1f}/week ({ty})", window="7d" if x["n1"] == 0 else "24h",
                            source="Synthetic LAC", tag="SYNTHETIC", mag=1.5 * math.log(x["r7"]) + 0.2 * x["n7"],
                            area=x["name"]))
    obs = sorted(obs, key=lambda o: -o["mag"])[:5]
    if not obs:
        obs = [dict(text="No significant change in the AOR in the last 7 days.", window="7d", source="-", tag="DATA",
                    mag=0)]

    # ---- DECIDE / ACT
    top_areas = [r["name"] for _, r in dist.head(3).iterrows()] if len(dist) else []
    if lac:
        top_areas = [x["name"] for x in sorted(lac, key=lambda x: -x["p_now"])[:3]]
    gmax = max(gs, key=lambda x: x["last7"] / max(x["mean28"], 1)) if gs else None
    acts = _playbook(code, T, rating, trend, n_flash, top_areas, stress, es, gs, gmax, dist, lac)
    acts = sorted(acts, key=lambda a: -a["priority"])[:3]
    for i, a in enumerate(acts, 1):
        a["rank"] = i

    head = obs[0]["text"]
    bluf = (f"{T['short']} theatre {rating} {arrow} ({trend}): {head.rstrip('.')}. "
            f"Recommend: {acts[0]['short']} within {acts[0]['timeline']}.")
    return dict(code=code, theatre=T["name"], date=str(d.date()), dtg=dtg(d), rating=rating, score=score,
                arrow=arrow, trend=trend, r7=round(r7, 3), confidence=conf, confidence_why=conf_why, bluf=bluf,
                observe=[{k: v for k, v in o.items() if k != "mag"} for o in obs],
                orient=dict(points=[dict(pts=p, why=t) for p, t in pts], drivers=drivers, model_why=model_why),
                decide=acts,
                districts=[dict(name=r["name"], iso=r.country_iso3, case=r.conflict_case, p=round(float(r.p_escalation), 3),
                                p_now=round(float(r.p_now), 3), lon=r.lon, lat=r.lat, synthetic=False)
                           for _, r in dist.head(12).iterrows()]
                          + [dict(name=x["name"], iso="IND", case="LAC (synthetic)", p=None, p_now=round(x["p_now"], 3),
                                  lon=x["lon"], lat=x["lat"], synthetic=True, n7=x["n7"]) for x in lac],
                gdelt=[{k: (round(v, 3) if isinstance(v, float) else v) for k, v in x.items()} for x in gs],
                econ=[{k: (round(v, 4) if isinstance(v, float) else v) for k, v in x.items()} for x in es],
                ucdp_week=uw[:5], synthetic=bool(lac), notional=True,
                caveats=[NOTIONAL] +
                        ["District nowcast is a heuristic adjustment of the back-tested model, not itself back-tested.",
                         f"UCDP data end {pd.Timestamp(C.PANEL_END):%d %b %Y}; GDELT fills the gap to {d:%d %b %Y}."])


def _act(kind, short, text, owner, priority, timeline, trigger):
    return dict(kind=kind, short=short, text=text, owner=owner, priority=round(float(priority), 2), timeline=timeline,
                trigger=trigger)


def _tl(p: float) -> str:
    return "24h" if p >= 5 else "72h" if p >= 3.5 else "7d"


def _playbook(code, T, rating, trend, n_flash, top_areas, stress, es, gs, gmax, dist, lac) -> list[dict]:
    up = trend == "rising"
    rr = {"RED": 2, "AMBER": 1, "GREEN": 0}[rating]
    areas = ", ".join(top_areas) if top_areas else "the AOR"
    acts = []
    gtxt = f"{gmax['series']} above {max(gmax['mean28'] * 1.5, gmax['mean28'] + 2):.0f}/day for 2 days" if gmax else "a 24 h GDELT spike (z >= 3)"
    # ISR
    p = 2.5 + 0.8 * n_flash + (1 if up else 0) + 0.5 * rr
    acts.append(_act("ISR tasking", f"task ISR on {areas}",
                     f"Re-task ISR (UAV, satellite revisit, SIGINT focus) onto {areas}; daily change detection.",
                     "Theatre J2 (Int) / ISR cell", p, _tl(p),
                     f"Any area nowcast P >= 0.30, or {gtxt} -> FLASH to {('CDS' if code != 'CDS' else 'CCS')}"))
    # posture
    sect = {"WTC": "LoC / IB holding formations", "NTC": "LAC forward formations (winter posture)",
            "MTC": "Western Fleet units in the Arabian Sea"}[code]
    p = 2 + 1.2 * rr + (1 if up else 0)
    acts.append(_act("Force posture", f"raise readiness of {sect}",
                     f"Raise readiness of {sect} one step; review reserves and reaction times.",
                     "Theatre J3 (Ops)", p, _tl(p),
                     f"RAG turns RED, or two days of rising trend with >= 2 areas over {FLASH_P:.2f} -> move to the next state"))
    # logistics
    worst = max(es, key=lambda x: x["adverse"]) if es else None
    p = 1.5 + (1.5 if stress else 0) + (0.8 if code == "NTC" else 0) + 0.3 * rr
    what = {"WTC": "ammunition and POL forward stocks", "NTC": "winter stocking (POL, rations, spares) before passes close",
            "MTC": "fleet fuel and crude cover"}[code]
    acts.append(_act("Logistics buffers", f"top up {what}",
                     f"Top up {what}." + (f" Market signal: {worst['series']} {worst['ch5']:+.1%} in 5 days." if worst else ""),
                     "Theatre J4 (Log)", p, _tl(p),
                     (f"{worst['series']} adverse move z >= 2.5 over 5 days -> request a strategic reserve release" if worst
                      else "Supply route closure -> request a strategic reserve release")))
    if code == "MTC":
        gulf = [x for x in gs if x["key"] in ("AE", "SA", "KU", "QA", "BA", "MU")]
        gr = theatre_r7(gulf) if gulf else 1.0
        p = 2 + 1.5 * rr + (1.5 if gr >= 1.25 else 0)
        acts.append(_act("Evacuation readiness", "place the NEO task group on 72 h notice",
                         "Place a NEO task group (amphibious ship + escorts, notional) on 72 h notice; update Gulf "
                         "diaspora lists with MEA and the missions.", "Theatre J1 / NEO cell with MEA", p, _tl(p),
                         f"Strikes on a GCC state hosting Indians, or Gulf GDELT reporting ×1.5 for 3 days (now ×{gr:.2f}) -> launch"))
        ship = [x for x in es if x["key"] in ("FRO", "ZIM", "BRENT")]
        sm = max([x["adverse"] for x in ship], default=0)
        p = 2.2 + 0.6 * max(sm, 0) + rr
        acts.append(_act("Maritime domain awareness", "surge MDA over Hormuz and the Arabian Sea",
                         "Surge maritime patrol sorties over Hormuz, the Gulf of Oman and Chabahar approaches; "
                         "prepare escort for Indian-flag tankers.", "Theatre J3 Maritime / IFC-IOR", p, _tl(p),
                         "Attack on merchant shipping in the AOR, or tanker equities z >= 2.5 -> start escort"))
    if code == "WTC":
        afg = dist[dist.country_iso3 == "AFG"]
        p = 1.5 + (1.5 if len(afg) and afg.p_now.max() >= FLASH_P else 0)
        acts.append(_act("Evacuation readiness", "refresh the Afghanistan evacuation plan",
                         "Refresh evacuation lists for Indian nationals in Afghanistan; confirm air bridge options.",
                         "Theatre J1 with MEA", p, _tl(p),
                         "Interstate strikes on Kabul or Kandahar -> activate"))
    if code == "NTC":
        p = 2.5 + 0.8 * n_flash + (1 if up else 0) + 0.5 * rr + 0.1    # always just above ISR: verify first
        acts.append(_act("Verification", "verify the surge with patrol and satellite reports",
                         "Because this view runs on [SYNTHETIC] data, first confirm the surge with real patrol reports "
                         "and satellite imagery before any posture change.", "Theatre J2 (Int)", p, _tl(p),
                         "Confirmed by two independent sources -> FLASH to CDS"))
    return acts


def _cds_brief(d: pd.Timestamp, I: dict, subs: dict) -> dict:
    # Real-data theatres first: the main effort is never chosen on synthetic data (NTC is shown as a drill).
    order = sorted(subs.values(), key=lambda b: (b["synthetic"], -RAG_BASE[b["rating"]], -b["score"]))
    worst = order[0]
    rag = I["rag"].set_index("conflict_case")
    gs = gdelt_signals(CDS, d, I)
    es = econ_signals(CDS, d, I)
    obs = []
    for b in order:
        o = b["observe"][0]
        obs.append(dict(o, text=f"{b['code']}: {o['text']}"))
    ru = rag.loc["Russia–Ukraine"]
    obs.append(dict(text=f"Strategic: Russia–Ukraine {ru.rating}, {ru.forecast_next:,.0f} deaths forecast for Oct 2026 "
                         "(sustainment of Russian-origin kit)", window="7d", source="Forecast model", tag="MODEL"))
    acts = []
    for b in order:
        a = dict(b["decide"][0])
        if b["synthetic"]:
            a["priority"] = min(a["priority"], 3.0)    # a synthetic drill never outranks a real-data action
        a["short"] = f"{b['code']}: {a['short']}"
        a["text"] = f"{b['code']}: {a['text']}"
        acts.append(a)
    acts = sorted(acts, key=lambda a: -a["priority"])[:3]
    for i, a in enumerate(acts, 1):
        a["rank"] = i
    real = [b for b in order if not b["synthetic"]]
    rating = max((b["rating"] for b in real), key=lambda r: RAG_BASE[r])
    up = sum(b["trend"] == "rising" for b in real)
    arrow = "▲" if up >= 2 else worst["arrow"]
    trend = "rising" if up >= 2 else worst["trend"]
    line = "; ".join(f"{b['code']} {b['rating']}{b['arrow']}" + (" (synthetic drill)" if b["synthetic"] else "")
                     for b in order)
    bluf = (f"All theatres: {line}. Main effort {worst['code']}: {worst['observe'][0]['text'].rstrip('.')}. "
            f"Recommend: {acts[0]['short']} within {acts[0]['timeline']}.")
    return dict(code="CDS", theatre=CDS["name"], date=str(d.date()), dtg=dtg(d), rating=rating,
                score=max(b["score"] for b in real), arrow=arrow, trend=trend, r7=None,
                confidence=min((b["confidence"] for b in order), key=lambda c: {"LOW": 0, "MEDIUM": 1, "HIGH": 2}[c]),
                confidence_why="Rating and main effort use the two theatres the issued data cover (WTC, MTC).",
                bluf=bluf, observe=obs[:5],
                orient=dict(points=[dict(pts=b["score"], why=f"{b['code']} {b['rating']} {b['arrow']} (score {b['score']})")
                                    for b in order], drivers=[b["bluf"] for b in order],
                            model_why=order[0]["orient"]["model_why"]),
                decide=acts, districts=sum((b["districts"] for b in order), []), gdelt=gs, econ=es, ucdp_week=[],
                synthetic=False, notional=True, theatres={b["code"]: dict(rating=b["rating"], arrow=b["arrow"],
                                                                         score=b["score"], bluf=b["bluf"]) for b in order},
                caveats=[NOTIONAL])


# ---------------------------------------------------------------------------
# History, FLASH, inbox
# ---------------------------------------------------------------------------
def build_history(I: dict, end: pd.Timestamp | None = None, days: int = 7) -> dict:
    end = end or latest_date(I)
    dates = [end - pd.Timedelta(days=i) for i in range(days, -1, -1)]  # one extra day to diff against
    hist = {k: [build_brief(k, d, I) for d in dates] for k in ROLES}
    flashes = []
    for k in THEATRES:
        for prev, cur in zip(hist[k][:-1], hist[k][1:]):
            if prev["rating"] != cur["rating"]:
                flashes.append(dict(code=k, date=cur["date"], kind="RAG change", dtg=_flash_dtg(cur["date"], 0),
                                    text=f"FLASH {k}: RAG {prev['rating']} -> {cur['rating']} {cur['arrow']}. "
                                         f"{cur['observe'][0]['text']}"))
            pp = {x["name"]: x["p_now"] for x in prev["districts"]}
            for x in cur["districts"]:
                if x["p_now"] >= FLASH_P and pp.get(x["name"], 0) < FLASH_P - 0.01:   # 0.01 band stops jitter
                    flashes.append(dict(code=k, date=cur["date"], kind="District over threshold",
                                        dtg=_flash_dtg(cur["date"], 1),
                                        text=f"FLASH {k}: {'[SYNTHETIC] ' if x['synthetic'] else ''}{x['name']} crossed "
                                             f"the escalation threshold: nowcast P {pp.get(x['name'], 0):.2f} -> "
                                             f"{x['p_now']:.2f} (threshold {FLASH_P:.2f})."))
    for k in ROLES:
        hist[k] = hist[k][1:]
    return dict(dates=[str(d.date()) for d in dates[1:]], briefs=hist, flashes=flashes)


def _flash_dtg(date: str, i: int) -> str:
    t = pd.Timestamp(date) + pd.Timedelta(hours=18, minutes=40 + 7 * i)   # raised on ingest, the evening of day d (IST)
    return f"{t:%d%H%M} IST {t:%b %y}".upper()


# ---------------------------------------------------------------------------
# Renderers (email / SMS / WhatsApp / markdown)
# ---------------------------------------------------------------------------
RAG_EMOJI = {"RED": "🔴", "AMBER": "🟠", "GREEN": "🟢"}


PRECEDENCE = {"RED": "IMMEDIATE", "AMBER": "PRIORITY", "GREEN": "ROUTINE"}
_ASCII = {"×": "x", "–": "-", "—": "-", "▲": "UP", "▼": "DOWN", "►": "STEADY", "▶": "STEADY", "→": "->", "≥": ">=", "·": "-"}


def _nlt(b: dict, timeline: str) -> str:
    """Deadline as a date-time group: brief issue time plus the action timeline (24h, 72h, 7d)."""
    m = re.match(r"(\d+)\s*([hd])", str(timeline))
    try:
        t0 = pd.Timestamp(b["date"]).normalize() + pd.Timedelta(days=1, hours=6)   # issued 0600 IST the next morning
        if not m:
            return str(timeline)
        t = t0 + pd.Timedelta(**{"hours" if m.group(2) == "h" else "days": int(m.group(1))})
        return f"{t:%d%H%M} {t:%b}".upper()
    except Exception:
        return str(timeline)


def _owner(a: dict) -> str:
    return a["owner"].split(" /")[0].replace("Theatre ", "").strip()


def _tactical_obs(b: dict) -> list:
    """Observations for a tactical message: market lines are left to the full brief."""
    return [o for o in b["observe"] if o.get("source") != "Markets"]


def _hot(b: dict, n: int = 3) -> list:
    d = sorted(b.get("districts", []), key=lambda d: -d.get("p_now", 0))
    return [x for x in d if x.get("p_now", 0) >= 0.10][:n] or d[:1]   # areas worth a commander's attention


def _ascii(t: str) -> str:
    for k, v in _ASCII.items():
        t = t.replace(k, v)
    return t.encode("ascii", "ignore").decode()


def _cut(t: str, n: int) -> str:
    return t if len(t) <= n else t[:n].rsplit(" ", 1)[0].rstrip(" ,;:(") + ".."


def to_sms(b: dict) -> str:
    """Formatted signal, plain ASCII (GSM-7) so it stays within two SMS segments (<= 320 characters)."""
    a = b["decide"][0]
    obs = _tactical_obs(b) or b["observe"]
    hot = ", ".join(f"{d['name'].split(' (')[0]} {d['p_now']:.2f}" for d in _hot(b))
    tag = "NOTIONAL" + ("/SYNTHETIC DRILL" if b["synthetic"] else "")
    head = f"{PRECEDENCE[b['rating']]} - CW/{b['code']} - DTG {b['dtg']}\nTHREAT {b['rating']} {b['trend'].upper()} - CONF {b['confidence']}"
    act = f"ACT {_owner(a)}: {a['short']} NLT {_nlt(b, a['timeline'])}"
    hotl = f"WATCH {hot}" if hot else ""
    tail = f"ACK REQD - {tag}"
    room = 320 - sum(len(_ascii(x)) + 1 for x in (head, hotl, act, tail) if x) - 5
    sit = "SIT " + _cut(_ascii(obs[0]["text"]), max(room, 40))
    return "\n".join(_ascii(x) for x in (head, sit, hotl, act, tail) if x)[:320]


def to_whatsapp(b: dict) -> str:
    """Five-paragraph signal: situation, hot areas, assessment, actions (who / what / by when), escalation triggers."""
    obs = _tactical_obs(b) or b["observe"]
    tag = "NOTIONAL" + (" · SYNTHETIC DRILL" if b["synthetic"] else "")
    L = [f"*{PRECEDENCE[b['rating']]} · CONFLICT WATCH SITREP*",
         f"FROM: CW Ops Cell   TO: Cdr {b['code']}",
         f"DTG: {b['dtg']}   UNCLAS · {tag}",
         "",
         f"{RAG_EMOJI[b['rating']]} *THREAT {b['rating']} {b['arrow']} {b['trend'].upper()}* · CONFIDENCE {b['confidence']}",
         "",
         "*1. SITUATION*"]
    L += [f"• {o['text']} _[{o['tag']}, {o['window']}]_" for o in obs[:3]]
    hot = _hot(b)
    if hot:
        L += ["", "*2. WATCH AREAS* (escalation probability, nowcast)"]
        L += [f"• {'◆ ' if d.get('synthetic') else ''}{d['name']} ({d['iso']}) — {d['p_now']:.2f}" for d in hot]
    L += ["", "*3. ASSESSMENT*"] + [f"• {x['why']} ({x['pts']:+d})" for x in sorted(b["orient"]["points"], key=lambda x: -abs(x["pts"]))[:2]]
    L += ["", "*4. ACTIONS* (who · what · by when)"]
    L += [f"A{a['rank']}. *{_owner(a)}* · {a['short'][0].upper() + a['short'][1:]} · *NLT {_nlt(b, a['timeline'])}* ({a['timeline']})"
          for a in b["decide"]]
    L += ["", "*5. ESCALATE IF*"] + [f"A{a['rank']}. {a['trigger']}" for a in b["decide"]]
    L += ["", "*ACK:* reply ACK-" + b["code"] + ". Full brief: Ops Console ▸ Theatre.",
          f"_UNCLAS · {tag} · competition data._"]
    return "\n".join(L)


def to_markdown(b: dict) -> str:
    o = "\n".join(f"{i}. {x['text']} *({x['window']}, {x['source']}, {x['tag']})*" for i, x in enumerate(b["observe"], 1))
    r = "\n".join(f"- {p['pts']:+d}  {p['why']}" for p in b["orient"]["points"])
    d = "\n".join(f"| {a['rank']} | {a['kind']} | {a['text']} | {a['owner']} | {a['timeline']} | {a['trigger']} |"
                  for a in b["decide"])
    cav = "\n".join(f"- {c}" for c in b["caveats"])
    return f"""# {b['theatre']} (NOTIONAL): daily brief {b['dtg']}

**BLUF:** {b['bluf']}

## OBSERVE: top changes in the AOR
{o}

## ORIENT: {b['rating']} {b['arrow']} ({b['trend']}), confidence {b['confidence']}
{r}

{b['orient']['model_why']} {b['confidence_why']}

## DECIDE and ACT
| # | Line | Action | Owner | Timeline | Trigger to escalate |
|---|---|---|---|---|---|
{d}

{cav}
"""


def to_email_html(b: dict) -> str:
    T = C.THEME
    col = C.RAG_COLORS[b["rating"]]
    o = "".join(f"<li>{x['text']} <i style='color:#888'>({x['window']}, {x['tag']})</i></li>" for x in b["observe"])
    a = "".join(f"<tr><td>{x['rank']}</td><td><b>{x['kind']}</b><br>{x['text']}</td><td>{x['owner']}</td>"
                f"<td>{x['timeline']}</td><td>{x['trigger']}</td></tr>" for x in b["decide"])
    return f"""<div style="font-family:Calibri,Arial;max-width:760px;background:{T['bg']};color:#fff;padding:18px;border-radius:10px">
<div style="color:{T['amber']};letter-spacing:3px;font-weight:700;font-size:12px">DATA ANALYTICS COMPETITION 2026 · CONFLICT WATCH</div>
<h2 style="margin:4px 0">{b['theatre']} (notional) · {b['dtg']}</h2>
<div style="border-left:6px solid {col};padding:6px 12px;background:{T['panel']}"><b style="color:{col}">{b['rating']} {b['arrow']}</b>
 · confidence {b['confidence']}<br><b>BLUF:</b> {b['bluf']}</div>
<h3>OBSERVE</h3><ol>{o}</ol><h3>DECIDE / ACT</h3>
<table border="1" cellpadding="5" style="border-collapse:collapse;border-color:{T['border']};font-size:13px">
<tr><th>#</th><th>Action</th><th>Owner</th><th>When</th><th>Trigger</th></tr>{a}</table>
<p style="color:{T['text3']};font-size:11px">{' '.join(b['caveats'])} UNCLASSIFIED - COMPETITION DATA ONLY.</p></div>"""


# ---------------------------------------------------------------------------
# OODA: how the layer shortens each stage (shared by the dashboard, deck and report)
# ---------------------------------------------------------------------------
OODA = [
    dict(stage="OBSERVE", today="Monthly / annual datasets (UCDP lags ~6 weeks) plus agency reports collated by hand "
                                "each morning", today_h=(24, 48),
         cw="Automatic ingest of GDELT (<= 24 h), market closes and the model watch-list, filtered to the AOR; top-5 "
            "changes ranked", cw_h=(0.5, 1), how="Data latency: 43 days (UCDP) -> under 1 day (GDELT)"),
    dict(stage="ORIENT", today="Staff fuse sources at the weekly int conference; threat level argued, not scored",
         today_h=(24, 48), cw="RAG, trend arrow, confidence and the drivers computed in seconds; J2 reviews in 30 min",
         cw_h=(0.5, 1), how="Same scoring rules every day; drivers shown, so the review is about judgement, not arithmetic"),
    dict(stage="DECIDE", today="Options built at the weekly ops/int conference", today_h=(24, 96),
         cw="Three ranked actions from a playbook, ready for the 0700 commander's update", cw_h=(1, 2),
         how="Options pre-built and ranked; the commander chooses, staff do not start from a blank page"),
    dict(stage="ACT", today="Orders drafted and passed down after the decision", today_h=(24, 48),
         cw="Each action already has an owner, a timeline and a trigger; FLASH reaches the owner on ingest",
         cw_h=(2, 24), how="Pre-agreed triggers turn the next escalation into a drill, not a new decision"),
]


def ooda_totals() -> dict:
    t0 = sum(x["today_h"][0] for x in OODA), sum(x["today_h"][1] for x in OODA)
    t1 = sum(x["cw_h"][0] for x in OODA), sum(x["cw_h"][1] for x in OODA)
    return dict(today_days=(t0[0] / 24, t0[1] / 24), cw_hours=t1)


# ---------------------------------------------------------------------------
# Run (writes outputs/theatre/)
# ---------------------------------------------------------------------------
def run(end: str | None = None, days: int = 7) -> dict:
    import time
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    I = load_inputs()
    e = pd.Timestamp(end) if end else latest_date(I)
    H = build_history(I, e, days)
    secs = round(time.time() - t0, 1)
    (OUT / "aor_notional.geojson").write_text(json.dumps(aor_geojson(), indent=1))
    # v2: no synthetic LAC incidents are written or shown
    inbox = []
    for k in ROLES:
        for b in H["briefs"][k]:
            inbox.append(dict(code=k, date=b["date"], dtg=b["dtg"], kind="DAILY BRIEF", priority="ROUTINE",
                              rating=b["rating"], arrow=b["arrow"], subject=f"{k} daily brief {b['dtg']}: {b['rating']} {b['arrow']}",
                              text=b["bluf"], channels=["in-app", "email", "SMS", "WhatsApp"]))
    for f in H["flashes"]:
        for k in (f["code"], "CDS"):
            inbox.append(dict(code=k, date=f["date"], dtg=f["dtg"], kind="FLASH", priority="FLASH", rating=None,
                              arrow=None, subject=f"FLASH {f['code']}: {f['kind']}", text=f["text"],
                              channels=["in-app", "SMS", "WhatsApp"]))
    inbox = sorted(inbox, key=lambda m: (m["date"], m["kind"] != "FLASH"), reverse=True)
    meta = dict(generated_utc=pd.Timestamp.now(tz="UTC").isoformat(timespec="seconds"), data_end=str(e.date()),
                brief_dtg=dtg(e), schedule="Daily 0600 IST (0030 UTC)", build_seconds=secs, days=days,
                ucdp_end=C.PANEL_END, ucdp_lag_days=int((e - pd.Timestamp(C.PANEL_END)).days),
                flash_threshold=FLASH_P, alert_threshold=ALERT_P, notional=NOTIONAL, synthetic="",
                n_flash=len(H["flashes"]), ooda=OODA, ooda_totals=ooda_totals())
    out = dict(meta=meta, dates=H["dates"], briefs=H["briefs"], flashes=H["flashes"], inbox=inbox)
    (OUT / "briefs.json").write_text(json.dumps(out, indent=1, default=str, ensure_ascii=False), encoding="utf-8")
    # compact copy for the Ops site console (web/public/data/theatre.json; inlined into the single-file build)
    web = dict(meta=meta, dates=H["dates"], flashes=H["flashes"], inbox=inbox[:60], aor=aor_geojson(),
               briefs={k: [{kk: v for kk, v in b.items() if kk not in ("gdelt", "econ", "ucdp_week")} for b in H["briefs"][k]]
                       for k in ROLES},
               theatres={k: dict(name=theatre(k)["name"], short=theatre(k)["short"], front=theatre(k)["front"],
                                 color=theatre(k)["color"], sectors=theatre(k)["sectors"], cases=theatre(k)["cases"],
                                 context=theatre(k)["context_cases"]) for k in ROLES},
               sms={k: to_sms(H["briefs"][k][-1]) for k in ROLES},
               whatsapp={k: to_whatsapp(H["briefs"][k][-1]) for k in ROLES})
    wd = C.ROOT / "web" / "public" / "data"
    if wd.exists():
        (wd / "theatre.json").write_text(json.dumps(web, default=str, ensure_ascii=False, separators=(",", ":")),
                                         encoding="utf-8")
    for k in ROLES:
        for b in H["briefs"][k]:
            p = OUT / "briefs" / b["date"]
            p.mkdir(parents=True, exist_ok=True)
            (p / f"{k}.md").write_text(to_markdown(b), encoding="utf-8")
            (p / f"{k}_email.html").write_text(to_email_html(b), encoding="utf-8")
    return out


def send_email(b: dict, to: list[str]) -> str:
    """Send one brief by SMTP using the CW_SMTP_* environment variables. Returns a status line."""
    import os
    import smtplib
    from email.message import EmailMessage
    host = os.environ.get("CW_SMTP_HOST")
    if not host:
        return "Not sent: CW_SMTP_HOST is not set (demo mode)."
    m = EmailMessage()
    m["Subject"] = f"[CONFLICT WATCH] {b['code']} daily brief {b['dtg']}: {b['rating']} {b['arrow']} (NOTIONAL)"
    m["From"] = os.environ.get("CW_MAIL_FROM", os.environ.get("CW_SMTP_USER", "conflict-watch@localhost"))
    m["To"] = ", ".join(to)
    m.set_content(to_markdown(b))
    m.add_alternative(to_email_html(b), subtype="html")
    with smtplib.SMTP(host, int(os.environ.get("CW_SMTP_PORT", "587")), timeout=30) as s:
        s.starttls()
        if os.environ.get("CW_SMTP_USER"):
            s.login(os.environ["CW_SMTP_USER"], os.environ.get("CW_SMTP_PASS", ""))
        s.send_message(m)
    return f"Sent to {len(to)} recipient(s)."
