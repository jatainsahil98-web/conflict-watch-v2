"""The six supplementary issued files (D7–D12): audit them, then use them to test, widen or explain D1.

File IDs follow the report (D1–D6 are the official participant package in data/raw/for participants):
  D7  4. gdelt_focus_feb_apr_2026.csv      } reduced on the laptop to the daily tables in data/gdelt/
  D8  3. gdelt_focus_3gb_from_2026.csv     } (13,507,238 raw rows; raw files are 5.7 GB and not committed)
  D9  5. middle east type of conflict.xlsx (ACLED-style, admin1 x week x event type)
  D10 6. war_terror_violence_200k.csv       (UCDP GED events 1989–2025, capped at 200,000 rows)
  D11 1. country_month_panel_with_middle_east.csv (pre-joined UCDP + GDELT + ME panel)
  D12 2. country_summary_panel_with_middle_east.csv (pre-joined country totals)

Rules: providers are never joined on event IDs (except D1 <-> D10, which are both UCDP GED); the only
cross-provider keys are country (or state pair) and day, week, month or year. Pre-joined panels (D11, D12)
are audited before use, not trusted.

Output: outputs/tables/extra_sources.json (+ extra_sources_checks.csv).
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy import stats

from . import config as C

XDIR = C.ROOT / "data" / "raw" / "extra"
GDIR = C.ROOT / "data" / "gdelt"
F = dict(D9="5. middle east type of conflict.xlsx", D10="6. war_terror_violence_200k.csv",
         D11="1. country_month_panel_with_middle_east.csv", D12="2. country_summary_panel_with_middle_east.csv")
GULF = ["Bahrain", "Kuwait", "Oman", "Qatar", "Saudi Arabia", "United Arab Emirates"]
VIOLENT = ["Battles", "Explosions/Remote violence", "Violence against civilians"]
WAR_2026 = pd.Timestamp("2026-02-28")     # US–Israel strikes on Iran begin
WAR_2025 = pd.Timestamp("2025-06-13")     # Israel–Iran twelve-day war begins
ISO = {"Afghanistan": "AFG", "Pakistan": "PAK", "Russia": "RUS", "Ukraine": "UKR", "Iran": "IRN", "Israel": "ISR",
       "United States": "USA"}


def _me() -> pd.DataFrame:
    cache = C.PROCESSED / "me_weekly.parquet"
    src = XDIR / F["D9"]
    if cache.exists() and cache.stat().st_mtime >= src.stat().st_mtime:
        return pd.read_parquet(cache)
    m = pd.read_excel(src)
    m.to_parquet(cache, index=False)
    return m


def _half(d: pd.Series) -> pd.Series:
    return d.dt.year.astype(str) + np.where(d.dt.month <= 6, "H1", "H2")


# ---------------------------------------------------------------------------------------------------- D10
def d10(events: pd.DataFrame) -> dict:
    d = pd.read_csv(XDIR / F["D10"], low_memory=False)
    e25 = events[events.event_year <= 2025]
    hit = e25.event_id.isin(set(d.id))
    j = e25[hit].merge(d[["id", "deaths_best"]], left_on="event_id", right_on="id", suffixes=("", "_d10"))
    f = d[d.country_group == "Focus country"]
    cy = (f.groupby(["country", "year"]).deaths_best.sum().unstack(fill_value=0)
          .reindex(columns=range(int(d.year.min()), int(d.year.max()) + 1), fill_value=0))
    a, b = cy.values[:, :-1], cy.values[:, 1:]
    hi, quiet = a >= 10_000, a < 25
    afg = d[(d.country == "Afghanistan") & d.year.between(2014, 2025)].deaths_best.sum()
    ap = e25[(e25.conflict_case == "Afghanistan–Pakistan") & (e25.country_iso3 == "AFG")].deaths_best.sum()
    ru = cy.loc["Ukraine"] if "Ukraine" in cy.index else None
    return dict(rows=int(len(d)), rows_stated=209_787, years=[int(d.year.min()), int(d.year.max())],
                focus_countries=sorted(f.country.unique().tolist()),
                d1_events_found=float(hit.mean()), d1_events_2014_25=int(len(e25)),
                deaths_identical=float((j.deaths_best == j.deaths_best_d10).mean()),
                persist_10k=dict(n=int(hi.sum()), share_next_ge_1k=float((b[hi] >= 1000).mean())),
                quiet_to_1k=dict(n=int(quiet.sum()), share=float((b[quiet] >= 1000).mean())),
                afpak_case_share_of_afghanistan=float(ap / afg),
                ukraine_years_ge_10k=[int(y) for y in ru.index if ru[y] >= 10_000] if ru is not None else [])


# ---------------------------------------------------------------------------------------------------- D9
def _strat(m: pd.DataFrame, country: str, onset: pd.Timestamp) -> dict:
    s = m[(m.COUNTRY == country) & (m.EVENT_TYPE == "Strategic developments")].groupby("WEEK").EVENTS.sum()
    s = s.reindex(pd.date_range(m.WEEK.min(), m.WEEK.max(), freq="7D"), fill_value=0)
    pre = s[(s.index < onset) & (s.index >= onset - pd.Timedelta(days=28))]
    base = s[(s.index < onset - pd.Timedelta(days=28)) & (s.index >= onset - pd.Timedelta(days=28 + 364))]
    return dict(pre4=int(pre.sum()), base4_mean=float(base.mean() * 4), ratio=float(pre.sum() / max(base.mean() * 4, 1e-9)))


def d9(m: pd.DataFrame, cm: pd.DataFrame) -> dict:
    m = m.copy()
    m["h"] = _half(m.WEEK)
    m["month"] = m.WEEK.dt.to_period("M").dt.to_timestamp()
    ir = m[m.COUNTRY == "Iran"]
    unrest = ir[ir.EVENT_TYPE.isin(["Protests", "Riots"]) & (ir.month >= "2025-12-01") & (ir.month <= "2026-01-01")]
    g = m[m.COUNTRY.isin(GULF) & m.EVENT_TYPE.isin(VIOLENT)].groupby("h").EVENTS.sum()
    io = m[(m.COUNTRY == "Indian Ocean") & m.EVENT_TYPE.isin(VIOLENT)].groupby("h").EVENTS.sum()
    # second-provider check on magnitude: Israel + Palestine vs D1 Israel–Hamas case, monthly
    ip = m[m.COUNTRY.isin(["Israel", "Palestine"])].groupby("month").FATALITIES.sum()
    u = cm[cm.conflict_case == "Israel–Hamas"].set_index("month").deaths
    k = ip.index.intersection(u.index)
    k = k[(k >= "2016-01-01") & (k <= "2026-06-01")]
    ctx = pd.read_parquet(C.PROCESSED / "context.parquet")
    infl = ctx[(ctx.iso3 == "IRN") & (ctx.year == 2025)].consumer_inflation_annual_pct
    return dict(rows=int(len(m)), weeks=[str(m.WEEK.min().date()), str(m.WEEK.max().date())],
                iran_inflation_2025_d6=float(infl.iloc[0]) if len(infl) else None,
                countries=int(m.COUNTRY.nunique()),
                iran_unrest_deaths_dec25_jan26=int(unrest.FATALITIES.sum()),
                iran_strategic_pre_2026=_strat(m, "Iran", WAR_2026), iran_strategic_pre_2025=_strat(m, "Iran", WAR_2025),
                gulf_violent_events=dict(H1_2025=int(g.get("2025H1", 0)), H1_2026=int(g.get("2026H1", 0))),
                indian_ocean_violent_events=dict(H1_2025=int(io.get("2025H1", 0)), H1_2026=int(io.get("2026H1", 0))),
                israel_palestine_rho=float(stats.spearmanr(ip[k], u[k])[0]), israel_palestine_months=int(len(k)))


# ---------------------------------------------------------------------------------------------------- D11
def d11() -> dict:
    p = pd.read_csv(XDIR / F["D11"])
    d = pd.read_csv(XDIR / F["D10"], usecols=["country", "date_start", "deaths_best"], low_memory=False)
    d["ym"] = d.date_start.str[:7]
    long = d.groupby(["country", "ym"]).deaths_best.sum()
    q = p[p.ucdp_events > 0].set_index(["country", "year_month"]).ucdp_deaths_best
    k = q.index.intersection(long.index)
    dd = pd.read_csv(XDIR / F["D10"], usecols=["country_group", "date_start", "date_end"], low_memory=False)
    dd = dd[dd.country_group == "Focus country"]
    multi = int((dd.date_start.str[:7] != dd.date_end.str[:7]).sum())
    iran = p[(p.country == "Iran") & (p.year_month >= "2016-01")]
    ir26 = p[(p.country == "Iran") & p.year_month.between("2026-02", "2026-04")]
    return dict(rows=int(len(p)), latest_ucdp_month=str(p[p.ucdp_events > 0].year_month.max()),
                iran_ucdp_deaths_feb_apr_2026=int(ir26.ucdp_deaths_best.sum()),
                gdelt_months_before_feb2026=int(((p.gdelt_events > 0) & (p.year_month < "2026-02")).sum()),
                gdelt_months_span=[str(p[p.gdelt_events > 0].year_month.min()), str(p[p.gdelt_events > 0].year_month.max())],
                ucdp_match_share=float((q[k] == long[k]).mean()), ucdp_country_months=int(len(k)),
                multi_month_records_stacked=multi,
                iran_ucdp_vs_protests_rho=float(stats.spearmanr(iran.ucdp_deaths_best, iran.me_protests)[0]))


# ---------------------------------------------------------------------------------------------------- D12
def d12(events: pd.DataFrame) -> dict:
    s = pd.read_csv(XDIR / F["D12"]).set_index("country")
    d = pd.read_csv(XDIR / F["D10"], usecols=["country", "id"], low_memory=False)
    e = events[(events.date_start >= "2026-02-01") & (events.date_start < "2026-05-01")]
    per = {}
    for c, iso in ISO.items():
        deaths = e[e.country_iso3 == iso].deaths_best.sum()
        per[c] = dict(gdelt_events=int(s.loc[c, "gdelt_feb_apr_2026_events"]), d1_deaths=int(deaths),
                      events_per_death=float(s.loc[c, "gdelt_feb_apr_2026_events"] / max(deaths, 1)))
    cnt = d.groupby("country").id.count()
    match = all(int(s.loc[c, "ucdp_events"]) == int(cnt.get(c, 0)) for c in ISO)
    return dict(rows=int(len(s)), media_per_death_feb_apr_2026=per, ucdp_event_totals_match_d10=bool(match))


# ---------------------------------------------------------------------------------------------------- D7 / D8
def gdelt_checks(events: pd.DataFrame) -> dict:
    from . import gdelt as G
    g = G._daily()
    out = {}
    # (a) pre-war volume and character, Iran vs US/Israel (pair table if the laptop built it; else USA<->IRN)
    pair_f = GDIR / "gdelt_iran_pair_daily.csv"
    if pair_f.exists():
        pp = pd.read_csv(pair_f, parse_dates=["date"])
        x = pp[pp.pair == "IRN-USA_OR_ISR"]
        src = "Iran vs the US or Israel"
    else:
        x = g[g.case_id == "US-IRAN"]
        src = "US–Iran dyad (case table)"
    x = x.set_index("date").sort_index()
    base, last = x["2026-02-01":"2026-02-20"], x["2026-02-21":"2026-02-27"]
    out["prewar"] = dict(source=src, base_days=int(len(base)), last_days=int(len(last)),
                         events_per_day=[float(base.events.mean()), float(last.events.mean())],
                         events_p=float(stats.ttest_ind(base.events, last.events).pvalue),
                         goldstein=[float(base.goldstein_mean.mean()), float(last.goldstein_mean.mean())],
                         goldstein_p=float(stats.ttest_ind(base.goldstein_mean, last.goldstein_mean).pvalue),
                         goldstein_w=[float(base.goldstein_wmean.mean()), float(last.goldstein_wmean.mean())])
    # (b) weekly lead test, each conflict separately
    wk = G._rate(g, "week")
    wk = wk[wk.days >= 5]
    w = wk.merge(G.weekly_ucdp(events), on=["case", "week"], how="left").fillna({"ucdp_deaths": 0})
    w = w[w.week <= G.LAST_UCDP + pd.offsets.MonthEnd(0) - pd.Timedelta(days=6)].sort_values(["case", "week"])
    w["lv"], w["lu"] = np.log1p(w.violent_pd), np.log1p(w.ucdp_deaths)
    w["lu1"], w["lv1"] = w.groupby("case").lu.shift(), w.groupby("case").lv.shift()
    pv = {c: float(smf.ols("lu ~ lu1 + lv1", data=gg.dropna(subset=["lu1", "lv1"])).fit().pvalues["lv1"])
          for c, gg in w.groupby("case")}
    out["weekly_lead_p_by_case"] = pv
    out["weekly_lead_p_min"] = min(pv.values())
    # (c) located spread to the Gulf (needs the ActionGeo table from the laptop)
    geo_f = GDIR / "gdelt_actiongeo_daily.csv"
    if geo_f.exists():
        ge = pd.read_csv(geo_f, parse_dates=["date"])
        col = "conflict_events" if "conflict_events" in ge else "events"
        cal = pd.date_range("2026-02-01", "2026-04-30")          # absent day = no located report
        ku = ge[ge.actiongeo_country_code == "KU"].set_index("date")[col].reindex(cal, fill_value=0)
        out["kuwait_conflict_per_day"] = [float(ku["2026-02-01":"2026-02-27"].mean()), float(ku["2026-02-28":"2026-03-31"].mean())]
        ce = ge[ge.actiongeo_country_code == "CE"].set_index("date")[col]
        out["sri_lanka_peak_day"] = str(ce["2026-02-15":"2026-03-31"].idxmax().date())
    return out


def gdelt_october(cm: pd.DataFrame) -> dict:
    """Does GDELT's Oct 2026 direction (vs Sep) agree with our Oct forecast direction (vs Sep actual)?"""
    sig = pd.read_csv(C.TAB_DIR / "gdelt_signals.csv")
    fut = pd.read_parquet(C.PROCESSED / "forecast_future.parquet")
    res = {}
    for c in C.CASES:
        s = sig[sig.case == c].set_index("month")
        if "2026-10" not in s.index or "2026-09" not in s.index:
            continue
        gd = s.loc["2026-10", "violent_pd"] / s.loc["2026-09", "violent_pd"] - 1
        sep = cm[(cm.conflict_case == c) & (cm.month == "2026-09-01")].deaths.iloc[0]
        f = fut[(fut.conflict_case == c)].sort_values("target_month").pred.iloc[0]
        fc = f / max(sep, 1) - 1
        res[c] = dict(gdelt_change=float(gd), forecast_change=float(fc), agree=bool(np.sign(gd) == np.sign(fc)))
    return dict(by_case=res, agree=int(sum(v["agree"] for v in res.values())), of=len(res))


def run(cm: pd.DataFrame | None = None, events: pd.DataFrame | None = None, save: bool = True) -> dict:
    if cm is None:
        cm = pd.read_parquet(C.PROCESSED / "case_month.parquet")
    if events is None:
        events = pd.read_parquet(C.PROCESSED / "events.parquet")
    out = dict(D9=d9(_me(), cm), D10=d10(events), D11=d11(), D12=d12(events), GDELT=gdelt_checks(events),
               GDELT_OCT=gdelt_october(cm))
    if save:
        (C.TAB_DIR / "extra_sources.json").write_text(json.dumps(out, indent=2, default=str))
        # flat copy so the run ID (a hash of the CSV tables) covers these results too
        flat = pd.json_normalize(out, sep=".").T.reset_index()
        flat.columns = ["key", "value"]
        flat["value"] = flat.value.map(lambda v: round(v, 6) if isinstance(v, float) else v).astype(str)
        flat.to_csv(C.TAB_DIR / "extra_sources_checks.csv", index=False)
    return out


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, default=str))
