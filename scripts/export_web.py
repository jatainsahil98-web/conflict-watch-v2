"""Export the frozen pipeline outputs to compact JSON for the Conflict Watch website and console.

Reads only outputs/tables, data/processed (aggregated panels) and models/. Never writes event rows or
source-reference rows. Every headline number is asserted against the submitted report/deck values;
the export FAILS if the run differs.

    python scripts/export_web.py            # writes web/public/data/*
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from src import config as C  # noqa: E402
from geo_match import match, A1  # noqa: E402

TB, PR = ROOT / "outputs" / "tables", ROOT / "data" / "processed"
OUT = ROOT / "web" / "public" / "data"
OUT.mkdir(parents=True, exist_ok=True)
CASES = list(C.CASES)
SLUG = {"Russia–Ukraine": "ruua", "Israel–Hamas": "ilh", "Afghanistan–Pakistan": "afpak", "US–Iran": "usir"}
SHORT = {"Russia–Ukraine": "RU–UA", "Israel–Hamas": "IL–Hamas", "Afghanistan–Pakistan": "Af–Pak", "US–Iran": "US–Iran"}
t = lambda f: pd.read_csv(TB / f)
FAILS: list[str] = []


def check(name, got, want, tol=0.0):
    ok = abs(got - want) <= tol if isinstance(want, (int, float)) else got == want
    if not ok:
        FAILS.append(f"{name}: got {got!r}, expected {want!r}")
    return got


def r(x, n=0):
    return None if x is None or (isinstance(x, float) and np.isnan(x)) else (round(float(x), n) if n else int(round(float(x))))


def dump(name, obj):
    p = OUT / name
    p.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":"), default=str))
    return p


# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------
ov = t("insight_case_overview.csv").set_index("conflict_case")
sc = t("forecast_scores.csv")
rm = t("forecast_rmsle.csv")
abl = t("ablation_lgb.csv")
ewr = t("early_warning_scores.csv")
rag = t("rag_scorecard.csv")
stats = t("insight_stats.csv").iloc[0]
fg = t("insight_front_geography.csv")
att = t("insight_attrition.csv")
ie = t("insight_india_exposure.csv")
ih = t("insight_india_hosted.csv")
dp = t("insight_demographics_profile.csv")
ip = t("insight_indian_press.csv").set_index("conflict_case")
ts = t("insight_theatre_spread.csv")
gp = t("insight_geo_precision.csv")
se = t("insight_seasonality.csv")
media = t("insight_media.csv")
disp = t("insight_displacement.csv")
unrwa = t("insight_unrwa.csv")
afprov = t("insight_afpak_provinces.csv")
shap_c = t("shap_lgb_case.csv")
shap_e = t("shap_early_warning.csv")
dq = t("data_quality_log.csv")
summary = json.loads((TB / "run_summary.json").read_text())
cm = pd.read_parquet(PR / "case_month.parquet")
am = pd.read_parquet(PR / "admin1_month.parquet")
preds = pd.read_parquet(PR / "forecast_preds.parquet")
future = pd.read_parquet(PR / "forecast_future.parquet")
ewp = pd.read_parquet(PR / "early_warning_preds.parquet")
live = pd.read_parquet(PR / "early_warning_live.parquet")
ev = pd.read_parquet(PR / "events.parquet")

# ---------------------------------------------------------------------------
# Run ID: hash of the result tables (src/robustness.run_id), shared with the report, deck and dashboard
# ---------------------------------------------------------------------------
RUN_ID = (TB / "run_id.txt").read_text().strip()

# ---------------------------------------------------------------------------
# Scorecard
# ---------------------------------------------------------------------------
fut = future[future.model == "ensemble"].copy()
fut["target_month"] = pd.to_datetime(fut.target_month)
WANT_RAG = {"Russia–Ukraine": ("RED", 6780, 3316, 16708, 7, 1, 4), "Israel–Hamas": ("GREEN", 128, 62, 317, -4, 0, 1),
            "Afghanistan–Pakistan": ("AMBER", 318, 155, 786, 12, 2, 2), "US–Iran": ("GREEN", 26, 12, 66, -78, 0, 1)}
WANT_FWD = {("Russia–Ukraine", 2): (6765, 3071, 30447), ("Afghanistan–Pakistan", 3): (291, 132, 1313)}
scorecard = []
for row in rag.itertuples():
    c = row.conflict_case
    w = WANT_RAG[c]
    top = [dict(name=a.split(" (")[0], p=int(a.split("(")[1].rstrip("%)")) / 100) for a in row.top_areas.split("; ")]
    trend_pct = r((row.trend_ratio - 1) * 100)
    check(f"{c} rating", row.rating, w[0])
    check(f"{c} forecast", r(row.forecast_next), w[1])
    check(f"{c} pi80", (r(row.pi80_lo), r(row.pi80_hi)), (w[2], w[3]))
    check(f"{c} trend", trend_pct, w[4])
    check(f"{c} hotspots", int(row.hotspots), w[5])
    check(f"{c} points", int(row.score), w[6])
    f = fut[fut.conflict_case == c].sort_values("h")
    fwd = [dict(month=m.strftime("%b %Y"), pred=r(p), lo=r(lo), hi=r(hi), lo95=r(l95), hi95=r(h95))
           for m, p, lo, hi, l95, h95 in zip(f.target_month, f.pred, f.pi80_lo, f.pi80_hi, f.pi95_lo, f.pi95_hi)]
    for (cc, h), v in WANT_FWD.items():
        if cc == c:
            check(f"{c} fwd h{h}", (fwd[h - 1]["pred"], fwd[h - 1]["lo"], fwd[h - 1]["hi"]), v)
    lv = live[(live.conflict_case == c) & (~live.admin1.str.startswith("("))]
    scorecard.append(dict(
        id=SLUG[c], name=c, short=SHORT[c], rating=row.rating, points=int(row.score),
        forecast=r(row.forecast_next), lo=r(row.pi80_lo), hi=r(row.pi80_hi), month="Oct 2026",
        trend_pct=trend_pct, trend_ratio=r(row.trend_ratio, 4), last6=r(row.last6_mean),
        hotspots=int(row.hotspots), peak12=r(row.peak_last12), top=top,
        countries_now=int(row.countries_this_year), countries_prev=int(row.countries_last_year),
        p_areas=[r(p, 4) for p in lv.p_escalation.values],
        pts=dict(intensity=int(row.pts_intensity), trend=int(row.pts_trend), hotspots=int(row.pts_hotspots),
                 spread=int(row.pts_spread), volatility=int(row.pts_volatility)),
        forward=fwd))

# ---------------------------------------------------------------------------
# Intensity / overview
# ---------------------------------------------------------------------------
WANT_OV = {"Russia–Ukraine": (447452, 270529, 782980, "Mar 2022", 27245, 64453, 7, 4),
           "Israel–Hamas": (67933, 64292, 71893, "Oct 2023", 11211, 1191, 49, 9),
           "Afghanistan–Pakistan": (31082, 28784, 39746, "Feb 2017", 762, 2767, 20, 2),
           "US–Iran": (7929, 6878, 8742, "Mar 2026", 2825, 3965, 36, 15)}
SIG = {"Russia–Ukraine": ("ATTRITION", "Sustained attrition: 4–11k deaths a month since 2023"),
       "Israel–Hamas": ("DECLINE", "De-escalating: about 130 a month in 2026, after 2,474 in Jul 2025"),
       "Afghanistan–Pakistan": ("CREEP", "Creeping escalation: rising every year since 2021"),
       "US–Iran": ("SPIKES", "Spikes, then direct war in Feb–Mar 2026")}
overview = []
for c in CASES:
    o = ov.loc[c]
    w = WANT_OV[c]
    vals = (int(o.deaths_best), int(o.deaths_low), int(o.deaths_high), o.peak_month, int(o.peak_month_deaths),
            int(o.deaths_2026_ytd), r(o.civilian_share * 100), int(o.countries_affected))
    check(f"{c} overview", vals, w)
    overview.append(dict(id=SLUG[c], name=c, short=SHORT[c], deaths=vals[0], low=vals[1], high=vals[2],
                         peak_month=vals[3], peak=vals[4], ytd26=vals[5], civ_pct=vals[6], countries=vals[7],
                         events=int(o.events), signature=SIG[c][0], signature_text=SIG[c][1]))

# ---------------------------------------------------------------------------
# Military lens
# ---------------------------------------------------------------------------
fg_p = fg.pivot_table(index="area", columns="year", values="share")
don22, don26 = r(fg_p.loc["Donetsk oblast", 2022] * 100), r(fg_p.loc["Donetsk oblast", 2026] * 100)
check("Donetsk share", (don22, don26), (55, 30))
gpr = gp[gp.conflict_case == "Russia–Ukraine"].set_index("year").share_deaths_country_level
check("fog of war", (r(gpr[2022] * 100), r(gpr[2026] * 100)), (30, 92))
ru_att = att[(att.conflict_case == "Russia–Ukraine")].set_index("year")
check("attrition 2022", (int(ru_att.loc[2022, "deaths_side_a"]), int(ru_att.loc[2022, "deaths_side_b"])), (41929, 21844))
check("ratios", tuple(r(ru_att.loc[y, "ratio_a_to_b"], 1) for y in (2022, 2025, 2026)), (1.9, 5.5, 10.5))
us_att = att[(att.conflict_case == "US–Iran")].set_index("year")
iran26 = int(us_att.loc[2026, "deaths_side_b"]) if us_att.loc[2026, "side_b_name"].startswith("Government of Iran") else int(us_att.loc[2026, "deaths_side_a"])
coal26 = int(us_att.loc[2026, "deaths_side_a"]) if us_att.loc[2026, "side_b_name"].startswith("Government of Iran") else int(us_att.loc[2026, "deaths_side_b"])
check("US–Iran recorded losses", (iran26, coal26), (1274, 11))
rus_in = ev[(ev.conflict_case == "Russia–Ukraine") & (ev.country_iso3 == "RUS")].groupby(ev.month.dt.year).deaths_best.sum()
check("deaths inside Russia peak", (int(rus_in.idxmax()), int(rus_in.max())), (2024, 10358))
ses = se.set_index(["conflict_case", "moy"]).index_pct
check("RU-UA seasonality", tuple(r(ses[("Russia–Ukraine", m)]) for m in (5, 7, 12, 1)), (35, 25, -27, -34))

# Af–Pak interstate dyad (monthly, aggregated)
dy = ev[(ev.conflict_case == "Afghanistan–Pakistan") & ev.ucdp_dyad_name.str.contains("Government of Afghanistan")
        & ev.ucdp_dyad_name.str.contains("Government of Pakistan")]
dym = dy.groupby(dy.month.dt.strftime("%Y-%m")).deaths_best.sum()
check("Af–Pak dyad", tuple(int(dym.get(m, 0)) for m in ("2025-10", "2026-02", "2026-03", "2026-04")), (131, 172, 411, 68))
# FATA harmonisation: raw labels vs harmonised (yearly deaths, aggregated)
pk = ev[ev.country_iso3 == "PAK"].copy()
pk["year"] = pk.month.dt.year
raw_lab = pk.admin1_name.fillna("")
pk["raw"] = np.where(raw_lab.str.contains("Federally Administered|FATA", case=False), "FATA",
                     np.where(raw_lab.str.contains("Khyber", case=False), "KP", "other"))
pk["harm"] = np.where(pk.admin1.fillna("").str.contains("Khyber", case=False), "KP", "other")
fata = dict(years=list(range(2014, 2027)),
            raw_fata=[int(pk[(pk.raw == "FATA") & (pk.year == y)].deaths_best.sum()) for y in range(2014, 2027)],
            raw_kp=[int(pk[(pk.raw == "KP") & (pk.year == y)].deaths_best.sum()) for y in range(2014, 2027)],
            harm_kp=[int(pk[(pk.harm == "KP") & (pk.year == y)].deaths_best.sum()) for y in range(2014, 2027)])
afp = afprov[afprov.admin1.isin(["Khyber Pakhtunkwa province", "Balochistan province"])]
afpak_prov = {a: {int(y): int(d) for y, d in zip(g.year, g.deaths)} for a, g in afp.groupby("admin1")}
kp = afpak_prov.get("Khyber Pakhtunkwa province", {})
check("KP rising since 2021", all(kp.get(y + 1, 0) > kp.get(y, 0) for y in range(2021, 2025)), True)

military = dict(
    donetsk=[don22, don26],
    rising={a.replace(" oblast", ""): r(fg_p.loc[a, 2026] * 100) for a in
            ["Zaporizhzhya oblast", "Dnipropetrovsk oblast", "Sumy oblast", "Belgorod oblast"]},
    russia_inside_peak=dict(year=2024, deaths=int(rus_in.max())),
    russia_inside={int(k): int(v) for k, v in rus_in.items()},
    fog={int(y): r(v * 100) for y, v in gpr.items()},
    fog_all={SLUG[c]: {int(y): r(v, 3) for y, v in g.set_index("year").share_deaths_country_level.items()}
             for c, g in gp.groupby("conflict_case")},
    attrition=[dict(year=int(y), russia=int(row.deaths_side_a), ukraine=int(row.deaths_side_b),
                    ratio=r(row.ratio_a_to_b, 1)) for y, row in ru_att.iterrows() if y >= 2014],
    usir_2026=dict(iran=iran26, coalition=coal26),
    caveat="Recorded deaths: an upper bound of reporting, not a verified exchange ratio.",
    afpak_dyad={k: int(v) for k, v in dym.items()},
    fata=fata, afpak_prov=afpak_prov,
    seasonality={SLUG[c]: [r(ses.get((c, m), np.nan), 1) for m in range(1, 13)] for c in CASES},
)

# Front shares (RU–UA areas by year)
front = {a.replace(" oblast", "").replace(" Special Republican city", ""): {int(y): r(v, 4) for y, v in row.items() if not np.isnan(v)}
         for a, row in fg_p.iterrows()}

# ---------------------------------------------------------------------------
# India exposure
# ---------------------------------------------------------------------------
usir_ts = ts[ts.conflict_case == "US–Iran"].set_index("year").countries
g26 = ie[ie.year == 2026]
gulf26 = g26[g26.india_tag.str.startswith("Gulf")]
hz26 = g26[g26.india_tag.str.startswith("Iran")]
yem25 = ie[(ie.year == 2025) & ie.india_tag.str.startswith("Yemen")].deaths.sum()
pakprox = ie[ie.india_tag.str.startswith("Pakistan")].groupby("year").deaths.sum()
ihp = ih.pivot_table(index="year", columns="origin_iso3", values="total_international")
gulf_states = sorted(ev[(ev.conflict_case == "US–Iran") & (ev.month.dt.year == 2026)
                        & ev.country_iso3.isin(["ARE", "SAU", "QAT", "KWT", "BHR", "OMN"])].country_iso3.unique())
lka = ev[(ev.conflict_case == "US–Iran") & (ev.country_iso3 == "LKA") | ((ev.conflict_case == "US–Iran") & ev.ucdp_location_name.fillna("").str.contains("Sri Lanka"))]
lka_d = lka.groupby(lka.date_start.astype(str).str[:10]).deaths_best.sum()
india = dict(
    usir_countries=[int(usir_ts[2025]), int(usir_ts[2026])],
    gulf_states=len(gulf_states), gulf_list=gulf_states,
    gulf_events=int(gulf26.events.sum()), gulf_deaths=int(gulf26.deaths.sum()),
    hormuz_deaths=int(hz26.deaths.sum()), srilanka=dict(date="2026-03-04", deaths=int(lka_d.get("2026-03-04", 0))),
    yemen_2025=int(yem25), pak_india_adjoining={int(k): int(v) for k, v in pakprox.items()},
    afghans_in_india=[int(ihp["AFG"][2021]), int(ihp["AFG"][2025])],
    russians_in_india=[int(ihp["RUS"][2015]), int(ihp["RUS"][2025])],
    hosted={c: {int(y): r(v) for y, v in ihp[c].dropna().items()} for c in ihp.columns},
    exposure=[dict(tag=row.india_tag, conflict=row.conflict_case, year=int(row.year), events=int(row.events),
                   deaths=int(row.deaths)) for row in ie.itertuples()],
    domain=dict(diaspora="~9M Indians in the Gulf", precedents="Op Ganga (2022), Op Kaveri (2023), Op Ajay (2023)"),
)
check("US–Iran countries", tuple(india["usir_countries"]), (4, 14))
check("Gulf states struck", (india["gulf_states"], india["gulf_events"], india["gulf_deaths"]), (5, 25, 37))
check("Hormuz/Chabahar deaths", india["hormuz_deaths"], 299)
check("Sri Lanka 4 Mar 2026", india["srilanka"]["deaths"], 104)
check("Yemen 2025", india["yemen_2025"], 945)
check("Pakistan adjoining India", (int(pakprox[2022]), int(pakprox[2025])), (2, 52))
check("Afghans in India", tuple(india["afghans_in_india"]), (16247, 8377))
check("Russians in India", tuple(india["russians_in_india"]), (5, 329))

# ---------------------------------------------------------------------------
# Media (AGI)
# ---------------------------------------------------------------------------
check("media elasticities", (r(stats.media_elasticity_events, 2), r(stats.media_elasticity_deaths, 2), r(stats.media_r2, 2)), (0.96, 0.01, 0.96))
check("AGI lead", (r(stats.media_lead_coef, 3), r(stats.media_lead_p, 2)), (-0.047, 0.50))
rp100 = {}
for c in CASES:
    m = media[media.conflict_case == c]
    rp100[SLUG[c]] = r(m.refs_per_100_deaths.median())  # median month
check("refs per 100 deaths", tuple(rp100[SLUG[c]] for c in ["Israel–Hamas", "Russia–Ukraine", "Afghanistan–Pakistan", "US–Iran"]), (150, 54, 40, 35))
check("Indian outlets Af–Pak", r(ip.loc["Afghanistan–Pakistan", "events_covered_share"] * 100), 17)
agi_pts = [dict(c=SLUG[row.conflict_case], m=row.month[:7], d=r(row.deaths), e=r(row.n_events), s=r(row.n_sources),
                a=r(row.agi, 3)) for row in media.itertuples()]
media_out = dict(el_events=r(stats.media_elasticity_events, 2), el_deaths=r(stats.media_elasticity_deaths, 2),
                 r2=r(stats.media_r2, 2), n=int(stats.media_n), lead_coef=r(stats.media_lead_coef, 3),
                 lead_p=r(stats.media_lead_p, 2), refs_per_100=rp100,
                 indian_share={SLUG[c]: r(ip.loc[c, "events_covered_share"], 4) for c in CASES}, points=agi_pts)

# ---------------------------------------------------------------------------
# Displacement
# ---------------------------------------------------------------------------
dsp = disp.set_index(["iso3", "year"])
ukr = dsp.loc[("UKR", 2025)]
dpl = dp.sort_values("year").groupby("origin_iso3").tail(1).set_index("origin_iso3")
check("Ukraine displaced", (round(ukr.refugees / 1e6, 1), round(ukr.idps / 1e6, 1)), (5.2, 3.7))
check("WC shares", (r(dpl.loc["UKR", "women_children_share"] * 100), r(dpl.loc["AFG", "women_children_share"] * 100),
                    r(dpl.loc["AFG", "under5_share"] * 100)), (72, 63, 10))
check("Afg refugees", (round(dsp.loc[("AFG", 2024)].refugees / 1e6, 1), round(dsp.loc[("AFG", 2025)].refugees / 1e6, 1)), (5.8, 2.7))
check("link spearman", (r(stats.link_spearman, 2), r(stats.link_p, 2)), (0.10, 0.18))
displacement = dict(
    ukr=dict(refugees=int(ukr.refugees), idps=int(ukr.idps), wc=r(dpl.loc["UKR", "women_children_share"], 3),
             total=int(ukr.refugees + ukr.idps)),
    afg=dict(wc=r(dpl.loc["AFG", "women_children_share"], 3), u5=r(dpl.loc["AFG", "under5_share"], 3),
             ref24=int(dsp.loc[("AFG", 2024)].refugees), ref25=int(dsp.loc[("AFG", 2025)].refugees),
             oip25=int(dsp.loc[("AFG", 2025)].oip)),
    pse=dict(idmc=2.0e6, unrwa=int(unrwa[(unrwa.reporting_iso3 == "PSE")].sort_values("year").people.iloc[-1])
             if (unrwa.reporting_iso3 == "PSE").any() else None),
    series={iso: [dict(year=int(y), refugees=r(g.refugees), idps=r(g.idps), oip=r(g.oip), asylum=r(g.asylum_seekers))
                  for y, g in d.set_index("year").iterrows()] for iso, d in disp.groupby("iso3")},
    demographics={iso: [dict(year=int(row.year), wc=r(row.women_children_share, 3), u5=r(row.under5_share, 3))
                        for row in d.itertuples()] for iso, d in dp.groupby("origin_iso3")},
    unrwa=[dict(iso=row.reporting_iso3, name=row.reporting_name, year=int(row.year), people=int(row.people))
           for row in unrwa.itertuples()],
    link=dict(spearman=r(stats.link_spearman, 2), p=r(stats.link_p, 2), n=int(stats.link_n)),
)

# ---------------------------------------------------------------------------
# Forecasting
# ---------------------------------------------------------------------------
MODEL_LABELS = {"ensemble": "Ensemble", "naive": "Naive (no change)", "snaive": "Seasonal naive", "ma3": "3-month mean",
                "ets": "ETS (damped, log)", "sarima": "SARIMA", "lgb_case": "LightGBM-Δ (global)",
                "lgb_admin1": "LightGBM bottom-up (Tweedie)"}
lb = rm.assign(set=np.where(rm.fold == 2026, "hold", "bt")).groupby(["model", "track", "set"]).RMSLE.mean()
leader = [dict(model=m, label=MODEL_LABELS.get(m, m), A_bt=r(lb.get((m, "A", "bt")), 3), A_hold=r(lb.get((m, "A", "hold")), 3),
               B_bt=r(lb.get((m, "B", "bt")), 3), B_hold=r(lb.get((m, "B", "hold")), 3)) for m in MODEL_LABELS]
L = {d["model"]: d for d in leader}
check("RMSLE ensemble", (L["ensemble"]["A_bt"], L["ensemble"]["A_hold"], L["ensemble"]["B_bt"], L["ensemble"]["B_hold"]),
      (0.839, 0.845, 1.142, 1.169))
hold = sc[sc.fold == 2026]
hA = hold[hold.track == "A"]
naive_mae = hA[hA.model == "naive"].set_index("conflict_case").MAE
ens_mae = hA[hA.model == "ensemble"].set_index("conflict_case").MAE
mae_red = {SLUG[c]: r((1 - ens_mae[c] / naive_mae[c]) * 100) for c in CASES}
pooled = r((1 - ens_mae.sum() / naive_mae.sum()) * 100)
check("MAE vs naive", (pooled, mae_red["ruua"], mae_red["ilh"], mae_red["usir"], mae_red["afpak"]), (29, 30, 55, 31, 4))
mape_ru = r(hA[(hA.model == "ensemble") & (hA.conflict_case == "Russia–Ukraine")].MAPE.iloc[0])
check("RU–UA MAPE", mape_ru, 9)
e = preds[preds.model == "ensemble"]
e26 = e[e.fold == 2026].copy()
inside = (e26.actual >= e26.pi80_lo) & (e26.actual <= e26.pi80_hi)
cov = dict(all=r(inside.mean() * 100), A=r(inside[e26.track == "A"].mean() * 100), B=r(inside[e26.track == "B"].mean() * 100))
check("coverage", (cov["all"], cov["A"], cov["B"]), (83, 81, 86))
# direction of change (Track A): sign(pred - last actual) == sign(actual - last actual)
eA = e26[e26.track == "A"].copy()
eA["target_month"] = pd.to_datetime(eA.target_month)
last = cm.set_index(["conflict_case", "month"]).deaths
eA["prev"] = [last.get((c, m - pd.DateOffset(months=1)), np.nan) for c, m in zip(eA.conflict_case, eA.target_month)]
dir_ok = r((np.sign(eA.pred - eA.prev) == np.sign(eA.actual - eA.prev)).mean() * 100)
check("direction correct", dir_ok, 72)
abl_rows = [dict(variant=row[0], A=r(row[1], 3), B=r(row[2], 3)) for row in abl.itertuples(index=False)]
holdout_paths = []
for c in CASES:
    for tr in ("A", "B"):
        g = e26[(e26.conflict_case == c) & (e26.track == tr)].copy()
        g["target_month"] = pd.to_datetime(g.target_month)
        g = g.sort_values("target_month")
        holdout_paths.append(dict(c=SLUG[c], track=tr, months=[m.strftime("%Y-%m") for m in g.target_month],
                                  pred=[r(v) for v in g.pred], actual=[r(v) for v in g.actual],
                                  lo=[r(v) for v in g.pi80_lo], hi=[r(v) for v in g.pi80_hi]))
SHAP_NAMES = {"accel": "Acceleration (last month vs month before)", "y_l0": "Deaths last month", "y_l1": "Deaths 2 months ago",
              "y_l2": "Deaths 3 months ago", "y_l3": "Deaths 4 months ago", "y_rm3": "3-month average", "y_rm6": "6-month average",
              "y_rm12": "12-month average", "y_ewm": "Smoothed recent level", "y_max12": "Worst month in last year",
              "y_rstd6": "Volatility (6 months)", "momentum_3v12": "Momentum (3 vs 12 months)", "zero_streak": "Months of quiet",
              "cum_active_months": "Months active so far", "case_cat": "Which conflict", "h": "Months ahead",
              "y_l6": "Deaths 7 months ago", "y_l11": "Deaths a year ago", "y_l12": "Deaths 13 months ago",
              "cty_y_l0": "Country deaths last month", "cty_y_rm3": "Country 3-month average", "n_events_rm3": "Events (3-month avg)",
              "n_sources_rm3": "Media sources (3-month avg)", "n_outlets_rm3": "Outlets (3-month avg)", "civ_share_rm3": "Civilian share",
              "case_y_l0": "Whole-conflict deaths last month", "case_momentum": "Whole-conflict momentum", "moy": "Month of year",
              "n_admin1_rm3": "Active areas (3-month avg)", "hhi_rm3": "Concentration of violence",
              "outside_core_share_rm3": "Share outside core theatre", "uncert_index_rm3": "Reporting uncertainty"}
shap = dict(forecast=[dict(f=row.feature, label=SHAP_NAMES.get(row.feature, row.feature.replace("_", " ")), v=r(row.mean_abs_shap, 4))
                      for row in shap_c.head(12).itertuples()],
            warning=[dict(f=row.feature, label=SHAP_NAMES.get(row.feature, row.feature.replace("_", " ")), v=r(row.mean_abs_shap, 4))
                     for row in shap_e.head(12).itertuples()])
forecasting = dict(members=summary["ensemble_members"], leaderboard=leader, mae_vs_naive=mae_red, mae_pooled=pooled,
                   mape_ruua=mape_ru, coverage=cov, direction=dir_ok, ablation=abl_rows, shap=shap,
                   holdout_rmsle=summary["holdout_rmsle"])

# ---------------------------------------------------------------------------
# Early warning
# ---------------------------------------------------------------------------
ew26 = ewr[ewr.year == 2026].set_index("model")
lg = ew26.loc["LightGBM classifier"]
rule = ew26.loc["Rule: rank by last month's deaths"]
logit = ew26.loc["Logistic regression (5 signals)"]
lift = r(lg.precision_at_10 / lg.base_rate, 1)
check("EW holdout", (r(lg.ROC_AUC, 3), r(lg.PR_AUC, 3), r(lg.Brier, 3), r(lg.precision_at_10 * 100, 1), r(lg.recall_at_20 * 100, 1)),
      (0.798, 0.146, 0.037, 16.7, 37.9))
check("EW lift", (lift, r(lg.precision_at_10 / rule.precision_at_10, 1), r(rule.ROC_AUC, 3), r(logit.ROC_AUC, 3)), (4.1, 3.8, 0.727, 0.746))
bt_auc = ewr[(ewr.model == "LightGBM classifier") & (ewr.year < 2026)].ROC_AUC
check("EW backtest range", (r(bt_auc.min(), 2), r(bt_auc.max(), 2)), (0.82, 0.91))
w26 = ewp[ewp.fold == 2026].copy()
w26["target_month"] = pd.to_datetime(w26.target_month)
mar = w26[w26.target_month == "2026-03-01"].sort_values("p_lgb", ascending=False).head(10)
check("replay Mar 2026 hits", int(mar.escalation.sum()), 5)
warning = dict(auc=r(lg.ROC_AUC, 3), pr_auc=r(lg.PR_AUC, 3), brier=r(lg.Brier, 3), p10=r(lg.precision_at_10, 3),
               r20=r(lg.recall_at_20, 3), base=r(lg.base_rate, 3), lift=lift, lift_rule=r(lg.precision_at_10 / rule.precision_at_10, 1),
               rule_auc=r(rule.ROC_AUC, 3), logit_auc=r(logit.ROC_AUC, 3), bt_auc=[r(bt_auc.min(), 2), r(bt_auc.max(), 2)],
               n=int(lg.n), positives=int(lg.positives), areas=int(len(live)),
               countries=int(live.country_iso3.nunique()),
               scores=[dict(model=row.model, year=int(row.year), auc=r(row.ROC_AUC, 3), p10=r(row.precision_at_10, 3))
                       for row in ewr.itertuples()])
check("EW area count", warning["areas"], 222)
check("EW countries", warning["countries"], 22)

# ---------------------------------------------------------------------------
# What-if grid (exact Python engine, precomputed so the browser reproduces it bit-for-bit)
# ---------------------------------------------------------------------------
import joblib  # noqa: E402
from src import models as M  # noqa: E402
import warnings  # noqa: E402
warnings.filterwarnings("ignore")
art = joblib.load(ROOT / "models" / "models.joblib")
import os  # noqa: E402
SHOCKS, KS = ([0, 30], [3]) if os.environ.get("QUICK") else (list(range(-50, 101, 10)), list(range(1, 7)))
grid = {}
for c in CASES:
    grid[SLUG[c]] = {}
    for k in KS:
        for s in SHOCKS:
            o = M.scenario_forecast(cm, c, s, k, art["m_case_full"], art["members"], art["conformal"])
            grid[SLUG[c]][f"{s}|{k}"] = [[r(p), r(lo), r(hi)] for p, lo, hi in zip(o.pred, o.pi80_lo, o.pi80_hi)]
    print("what-if grid", c, "done")
w30 = grid["afpak"]["30|3"][0][0]
check("what-if Af–Pak +30%x3", w30, 359, tol=1)
check("what-if baseline = scorecard", tuple(grid[SLUG[c]]["0|3"][0][0] for c in CASES), tuple(WANT_RAG[c][1] for c in CASES), tol=1)
hist_tail = {SLUG[c]: [dict(m=m.strftime("%Y-%m"), d=r(d)) for m, d in
                       cm[cm.conflict_case == c].sort_values("month").tail(12)[["month", "deaths"]].itertuples(index=False)]
             for c in CASES}
whatif = dict(shocks=SHOCKS, ks=KS, months=["Oct 2026", "Nov 2026", "Dec 2026"], grid=grid, history=hist_tail,
              note="Precomputed with the frozen Python ensemble (3-month mean + ETS refit + LightGBM-Δ) for every slider "
                   "position, so the browser shows exactly what the submitted model says.")

# ---------------------------------------------------------------------------
# Monthly series per conflict
# ---------------------------------------------------------------------------
monthly = {}
for c in CASES:
    g = cm[cm.conflict_case == c].sort_values("month")
    monthly[SLUG[c]] = dict(months=[m.strftime("%Y-%m") for m in g.month], deaths=[r(v) for v in g.deaths],
                            low=[r(v) for v in g.deaths_low], high=[r(v) for v in g.deaths_high],
                            events=[int(v) for v in g.n_events], civ=[r(v, 3) for v in g.civ_share.fillna(0)],
                            countries=[int(v) for v in g.n_countries])

# ---------------------------------------------------------------------------
# Areas (222) + geometry
# ---------------------------------------------------------------------------
geo = match(live)
DISPLAY = {"Gilgit-Baltistan": "Gilgit-Baltistan (PoK)", "Azad Jammu & Kashmir": "Muzaffarabad region (PoK)"}
months_all = sorted(am.month.unique())
mlab = [pd.Timestamp(m).strftime("%Y-%m") for m in months_all]
amp = am.pivot_table(index=["conflict_case", "admin1_key"], columns="month", values="deaths", aggfunc="sum").reindex(columns=months_all).fillna(0)
amc = am.drop_duplicates("admin1_key").set_index("admin1_key")
w26p = w26.pivot_table(index=["conflict_case", "admin1_key"], columns="target_month", values="p_lgb")
w26e = w26.pivot_table(index=["conflict_case", "admin1_key"], columns="target_month", values="escalation")
ew_months = [pd.Timestamp(m).strftime("%Y-%m") for m in w26p.columns]
areas, poly_ids = [], {}
for i, row in enumerate(live.sort_values("p_escalation", ascending=False).itertuples()):
    g = geo.get(row.admin1_key)
    name = DISPLAY.get(row.admin1, row.admin1.replace(" province", "").replace(" oblast", "").replace(" governorate", ""))
    a = dict(id=f"{SLUG[row.conflict_case]}:{row.admin1_key}", key=row.admin1_key, c=SLUG[row.conflict_case], iso=row.country_iso3, name=name,
             lon=r(g["lon"], 2) if g else None, lat=r(g["lat"], 2) if g else None, poly=g["poly"] if g else None,
             unloc=row.admin1.startswith("("),
             p=r(row.p_escalation, 4), last=r(row.deaths),
             d=[r(v) for v in amp.loc[(row.conflict_case, row.admin1_key)].values] if (row.conflict_case, row.admin1_key) in amp.index else [],
             pm=[r(v, 4) if not np.isnan(v) else None for v in w26p.loc[(row.conflict_case, row.admin1_key)].values] if (row.conflict_case, row.admin1_key) in w26p.index else [],
             esc=[int(v) if not np.isnan(v) else None for v in w26e.loc[(row.conflict_case, row.admin1_key)].values] if (row.conflict_case, row.admin1_key) in w26e.index else [])
    areas.append(a)
# admin-1 polygons used by at least one area; tag with area id and strip unused ones
used = {}
for a in areas:
    if a["poly"] is not None:
        used.setdefault(a["poly"], []).append(a["id"])
feats = []
for pi, ids in used.items():
    f = A1["features"][pi]
    feats.append(dict(type="Feature", geometry=f["geometry"],
                      properties=dict(ids=ids, name=f["properties"]["name_en"] or f["properties"]["name"], iso=f["properties"]["adm0_a3"])))
for a in areas:
    a.pop("poly")
areas_out = dict(months=mlab, ew_months=ew_months, areas=areas)

# events grid (admin-1 centroid × year, deaths summed; no event rows)
evy = am.assign(year=pd.to_datetime(am.month).dt.year).groupby(["conflict_case", "admin1_key", "year"]).deaths.sum().reset_index()
pts = []
for row in evy[evy.deaths > 0].itertuples():
    g = geo.get(row.admin1_key)
    if g:
        pts.append([SLUG[row.conflict_case], round(g["lon"], 2), round(g["lat"], 2), int(row.year), r(row.deaths)])

# ---------------------------------------------------------------------------
# Facts
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# GDELT (new, labelled results; does not change the submitted models)
# ---------------------------------------------------------------------------
_gd = json.loads((TB / "gdelt_summary.json").read_text())
_gdd = pd.read_csv(ROOT / "data" / "gdelt" / "gdelt_case_daily.csv", parse_dates=["date"])
_gdd["case"] = _gdd.case_id.map({"RU-UA": "Russia–Ukraine", "ISR-HAMAS": "Israel–Hamas", "AF-PAK": "Afghanistan–Pakistan", "US-IRAN": "US–Iran"})
_gdd["week"] = _gdd.date.dt.to_period("W-SUN").dt.start_time
_gwk = _gdd.groupby(["case", "week"]).agg(v=("violent_events", "sum"), t=("threat_events", "sum"), n=("date", "nunique")).reset_index()
_gwk = _gwk[_gwk.n >= 4]
_uw = pd.read_parquet(C.PROCESSED / "gdelt_weekly.parquet")
gdelt_out = dict(
    coverage=_gd["coverage"], caveat=_gd["caveat"],
    rho_change={SLUG[k]: r(v["rho_change"], 2) for k, v in _gd["monthly"]["by_case"].items()},
    articles_per_death={SLUG[k]: int(round(v["articles_per_death"])) for k, v in _gd["monthly"]["by_case"].items()},
    pooled_r=r(_gd["monthly"]["pooled_change_r"], 2), lead_p=r(_gd["weekly"]["lead_p"], 2),
    nowcast_coef=r(_gd["weekly"]["nowcast_coef"], 2), oos_gain_nowcast=r(_gd["weekly"]["oos_gain_nowcast"], 2),
    oos_gain_lead=r(_gd["weekly"]["oos_gain_lead"], 2), oos_weeks=_gd["weekly"]["oos_weeks"],
    signals=[dict(c=SLUG[x["case"]], m=x["month"], days=x["days"], v=r(x["violent_pd"], 1), t=r(x["threats_pd"], 1),
                  ch=None if pd.isna(x["violent_change_vs_prev"]) else r(x["violent_change_vs_prev"], 3), flag=x["flag"],
                  tracks=bool(x["gdelt_tracks_ucdp"])) for x in _gd["signals"]],
    weekly={SLUG[c]: dict(weeks=[f"{w:%Y-%m-%d}" for w in g.week], v=[r(a / b, 1) for a, b in zip(g.v, g.n)],
                          t=[r(a / b, 1) for a, b in zip(g.t, g.n)],
                          ucdp=[None if w > pd.Timestamp("2026-09-21") else
                                r(float(_uw[(_uw.case == c) & (_uw.week == f"{w:%Y-%m-%d}")].ucdp_deaths.sum()), 0) for w in g.week])
            for c, g in _gwk.groupby("case")},
)
check("GDELT US–Iran rho", (gdelt_out["rho_change"]["usir"], gdelt_out["lead_p"]), (0.86, 0.55))

# ---------------------------------------------------------------------------
# Version 2 (issued data only): fast clock, reporting completeness, India's own front, sealed claims
# ---------------------------------------------------------------------------
_tw = json.loads((TB / "tripwire_summary.json").read_text())
_ta = t("tripwire_alerts.csv")
_cp = t("completeness.csv")
_in = json.loads((TB / "india_front.json").read_text())
_sl = json.loads((TB / "sealed_predictions.json").read_text())
_pr = json.loads((TB / "preregistration.json").read_text())
CASE_SLUG = {"Russia–Ukraine": "ruua", "Israel–Hamas": "ilh", "Afghanistan–Pakistan": "afpak", "US–Iran": "usir"}
v2_out = dict(
    tripwire=dict(episodes=_tw["red_episodes"], confirmed=_tw["red_confirmed"], p=r(_tw["p_value"], 3),
                  chance=r(_tw["perm_mean_hits"], 1), window=_tw["window"], rules=_tw["rules"],
                  caught={CASE_SLUG[k]: v for k, v in _tw["by_case"].items()},
                  alerts=[dict(c=CASE_SLUG[x.case], d=str(x.date), light=x.light, ok=bool(x.confirmed),
                               lead=None if pd.isna(x.lead_days) else int(x.lead_days)) for x in _ta.itertuples()],
                  latest=[dict(c=CASE_SLUG[x["case"]], d=x["date"], ratio=x["ratio"], red=bool(x["red"])) for x in _tw["latest"]]),
    completeness={CASE_SLUG[c]: dict(days=g.days.tolist(), share=g.share_known.tolist()) for c, g in _cp.groupby("case")},
    india=dict(note=_in["note"], triggers=_in["triggers"], yearly=_in["yearly_recent"]),
    sealed=dict(sha=_sl["sha256"], on=_sl["sealed_on"]),
    prereg=dict(sha=_pr["sha256"], rule=_pr["rule"], variant=_pr["decision"]["variant"]),
)
check("v2 tripwire confirmed", (v2_out["tripwire"]["confirmed"], v2_out["tripwire"]["episodes"]), (4, 5))
check("v2 RU-UA known at 90 days", v2_out["completeness"]["ruua"]["share"][3], 0.401, 0.01)

AI_DECL = ("AI tools declaration: the team used Anthropic's Claude (an AI assistant) to help write and debug code, "
           "draft text and design visuals. All analysis choices, numbers and conclusions were checked by the team, "
           "and every number is generated by the pipeline from the official competition data.")
facts = dict(
    run_id=RUN_ID, data_as_of="2026-09-30", exported=dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    competition="Data Analytics Competition 2026",
    team=["Maj Shivam Mehta", "Capt Siddharth Sangwan", "Capt Sahil Singh"], team_name="FCE",
    tagline="Four wars, three warning signals, one exposed neighbour: open data can tell India where to look next month.",
    ai_declaration=AI_DECL,
    rules=dict(int_hi=1000, int_lo=100, trend_up=20, trend_dn=-20, hot_p=0.15, hot_hi=3, hot_lo=1, vol=1000,
               red_fc=1000, red_pts=5, amber_pts=2),
    scorecard=scorecard, overview=overview, military=military, india=india, media=media_out,
    displacement=displacement, forecasting=forecasting, warning=warning, gdelt=gdelt_out, v2=v2_out,
    recommendations=[
        dict(line="SENSE", action="Task ISR and analysts on the monthly watch-list; run the daily GDELT tripwire for a change of state",
             lead="DIA / Service int", when="Now / 90 days", trigger="warning", why="Top-10 watch-list is 3.5× better than random (AUC 0.795)"),
        dict(line="WARN", action="Af–Pak dyad and KP/Balochistan hotspots as standing LoC I&W. Publish the RAG monthly",
             lead="HQ IDS, N & W Comds", when="Now", trigger="afpak", why="Interstate clashes peaked at 411 deaths (Mar 2026); 2 Af–Pak hotspots"),
        dict(line="SHIELD", action="Gulf NEO plans current while US–Iran is AMBER. Belligerent-movement picture in the IOR",
             lead="HQ IDS, Navy, IAF, MEA", when="Now / 90 days", trigger="india", why="US–Iran reached 14 countries, 5 Gulf states and Sri Lankan waters"),
        dict(line="SUSTAIN", action="Buffer and indigenise spares (Russian- and Israeli-origin). HADR kits for women, children, under-fives",
             lead="MoD, DPSUs, NDMA", when="6–12 months", trigger="displacement", why="RU–UA RED at 6,780/month; 72% of Ukrainian refugees are women or children"),
    ],
    end_state=["1-month warning lead", "Top-10 areas tasked monthly", "0 Indians stranded", "RAG brief every month"],
    limits=["UCDP records only reported deaths.", "2026 is provisional Candidate data.",
            "92% of 2026 RU–UA deaths have no sub-national location.",
            "The US–Iran dyad treats Israel and the US as one actor.",
            "Displacement cannot be attributed to single events.", "World Bank data ends in 2025.",
            "Decisions to start wars are not forecastable from death counts."],
    sources="UCDP GED 26.1 and Candidate 26.01.26.09, UNHCR, IDMC, UNRWA, World Bank, Natural Earth (India point of view)",
    licence="UCDP data CC BY 4.0; Natural Earth public domain",
)

if FAILS:
    print("\nEXPORT FAILED – numbers differ from the submitted report/deck:")
    for f in FAILS:
        print("  ✗", f)
    sys.exit(1)

files = {
    "facts.json": facts, "monthly_conflict.json": monthly, "areas.json": areas_out,
    "admin1.geojson": dict(type="FeatureCollection", features=feats), "events_points.json": pts,
    "front_shares.json": front, "leaderboard.json": dict(leaderboard=leader, ablation=abl_rows),
    "holdout_paths.json": holdout_paths, "whatif.json": whatif,
    "dq_log.json": json.loads(dq.to_json(orient="records")),
}
for n, o in files.items():
    dump(n, o)
(OUT / "world_ind.geojson").write_text((ROOT / "assets/web/world_ind.json").read_text())
manifest = {}
for p in sorted(OUT.glob("*")):
    if p.name == "manifest.json":
        continue
    b = p.read_bytes()
    manifest[p.name] = dict(bytes=len(b), sha256=hashlib.sha256(b).hexdigest())
    assert len(b) < 5e6, f"{p.name} too large"
    for bad in ("event_id", "publisher", "source_headline", "source_url"):
        assert f"\"{bad}\":" not in b.decode("utf-8", "ignore"), f"raw column {bad} found in {p.name}"
dump("manifest.json", dict(run_id=RUN_ID, files=manifest))
print(f"OK – all asserts passed. run_id={RUN_ID}")
for k, v in manifest.items():
    print(f"  {k:24s} {v['bytes'] / 1024:8.1f} KB")
