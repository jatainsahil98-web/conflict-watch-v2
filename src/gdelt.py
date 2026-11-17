"""GDELT (media-coded events, Feb–Nov 2026) against UCDP (recorded deaths, to Sep 2026).

This is a NEW, separately labelled analysis. It does not change the submitted forecasting or
early-warning models; it asks three questions of the GDELT aggregates in data/gdelt/:

  1. Agreement: does GDELT's violent-event rate move with UCDP deaths, and in which wars?
  2. Lead or nowcast: does GDELT in week t-1 add to UCDP in week t-1 when predicting UCDP in week t
     (leading indicator), or only GDELT in the same week t (nowcast)?
  3. Beyond UCDP: what does GDELT say about Oct and early Nov 2026, after UCDP's Sep 2026 end?

GDELT counts media-coded reports, not incidents. Rates are per covered day because the files miss
1-16 May 2026 and stop on 12 Nov 2026.

Outputs (outputs/tables): gdelt_vs_ucdp_monthly.csv, gdelt_weekly_lags.csv, gdelt_signals.csv, gdelt_summary.json
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy import stats

from . import config as C

GDIR = C.ROOT / "data" / "gdelt"
CASE = {"RU-UA": "Russia–Ukraine", "ISR-HAMAS": "Israel–Hamas", "AF-PAK": "Afghanistan–Pakistan", "US-IRAN": "US–Iran"}
LAST_UCDP = pd.Timestamp(C.PANEL_END).to_period("M").to_timestamp()
SIGNAL_UP = 0.25   # a 25% rise in violent events per day flags a case


def _daily() -> pd.DataFrame:
    g = pd.read_csv(GDIR / "gdelt_case_daily.csv", parse_dates=["date"])
    g["case"] = g.case_id.map(CASE)
    g["month"] = g.date.dt.to_period("M").dt.to_timestamp()
    g["week"] = g.date.dt.to_period("W-SUN").dt.start_time
    return g


def _rate(g: pd.DataFrame, key: str) -> pd.DataFrame:
    a = g.groupby(["case", key]).agg(days=("date", "nunique"), violent=("violent_events", "sum"),
                                     events=("events", "sum"), articles=("articles", "sum"),
                                     threats=("threat_events", "sum"), posture=("force_posture_events", "sum"),
                                     gw=("goldstein_wmean", "mean"), tone=("tone_wmean", "mean")).reset_index()
    for c in ("violent", "events", "articles", "threats", "posture"):
        a[f"{c}_pd"] = a[c] / a.days
    return a


def monthly(g: pd.DataFrame, cm: pd.DataFrame) -> pd.DataFrame:
    m = _rate(g, "month")
    u = cm[["conflict_case", "month", "deaths", "n_events"]].rename(columns={"conflict_case": "case",
                                                                            "deaths": "ucdp_deaths",
                                                                            "n_events": "ucdp_events"})
    return m.merge(u, on=["case", "month"], how="left")


def weekly_ucdp(events: pd.DataFrame) -> pd.DataFrame:
    """Deaths in discrete, dated UCDP events (span <= 7 days, not aggregates), by start week."""
    e = events[(events.date_start >= "2026-01-26") & (events.span_days <= 7) & (~events.is_aggregate)].copy()
    e["week"] = e.date_start.dt.to_period("W-SUN").dt.start_time
    return (e.groupby(["conflict_case", "week"]).deaths_best.sum().rename("ucdp_deaths").reset_index()
            .rename(columns={"conflict_case": "case"}))


def run(cm: pd.DataFrame | None = None, events: pd.DataFrame | None = None, save: bool = True) -> dict:
    if cm is None:
        cm = pd.read_parquet(C.PROCESSED / "case_month.parquet")
    if events is None:
        events = pd.read_parquet(C.PROCESSED / "events.parquet")
    g = _daily()
    out: dict = dict(coverage=dict(start=str(g.date.min().date()), end=str(g.date.max().date()),
                                   gap="2026-05-01 to 2026-05-16", days=int(g.date.nunique()),
                                   events=int(pd.read_csv(GDIR / "gdelt_case_monthly.csv").events.sum())))

    # ---- 1. agreement, monthly (Feb–Sep 2026 overlap) -----------------------------------------
    mo = monthly(g, cm)
    ov = mo[mo.month <= LAST_UCDP].copy()
    ov["lv"], ov["ld"] = np.log1p(ov.violent_pd), np.log1p(ov.ucdp_deaths)
    ov["dlv"] = ov.groupby("case").lv.diff()
    ov["dld"] = ov.groupby("case").ld.diff()
    agree = {}
    for c in C.CASES:
        x = ov[ov.case == c]
        d = x.dropna(subset=["dlv"])
        agree[c] = dict(months=int(len(x)), rho_level=float(stats.spearmanr(x.violent_pd, x.ucdp_deaths)[0]),
                        rho_change=float(stats.spearmanr(d.dlv, d.dld)[0]),
                        articles_per_death=float(x.articles.sum() / max(x.ucdp_deaths.sum(), 1) /
                                                 (x.days.sum() / x.days.sum())))
    d = ov.dropna(subset=["dlv"])
    r = stats.pearsonr(d.dlv, d.dld)
    out["monthly"] = dict(by_case=agree, pooled_change_r=float(r[0]), pooled_change_p=float(r[1]), n=int(len(d)))

    # ---- 2. lead or nowcast, weekly ---------------------------------------------------------------
    wk = _rate(g, "week")
    wk = wk[wk.days >= 5]
    uw = weekly_ucdp(events)
    w = wk.merge(uw, on=["case", "week"], how="left").fillna({"ucdp_deaths": 0})
    w = w[w.week <= LAST_UCDP + pd.offsets.MonthEnd(0) - pd.Timedelta(days=6)].sort_values(["case", "week"])
    w["lv"], w["lu"] = np.log1p(w.violent_pd), np.log1p(w.ucdp_deaths)
    w["lu1"] = w.groupby("case").lu.shift()
    w["lv1"] = w.groupby("case").lv.shift()
    lag_rows = []
    for c, gg in w.groupby("case"):
        for L in (-2, -1, 0, 1, 2):          # L > 0: GDELT L weeks BEFORE UCDP
            x = gg.lv.shift(L)
            k = x.notna()
            lag_rows.append(dict(case=c, lag_weeks=L, spearman=float(stats.spearmanr(x[k], gg.lu[k])[0])))
    lags = pd.DataFrame(lag_rows)
    ww = w.dropna(subset=["lu1", "lv1"])
    lead = smf.ols("lu ~ lu1 + lv1 + case", data=ww).fit()
    now = smf.ols("lu ~ lu1 + lv + case", data=ww).fit()
    base = smf.ols("lu ~ lu1 + case", data=ww).fit()
    # out-of-sample, expanding window: predict week t from weeks < t
    weeks = sorted(ww.week.unique())
    oos = []
    for t in weeks[10:]:
        tr, te = ww[ww.week < t], ww[ww.week == t]
        for name, f in (("persistence+case", "lu ~ lu1 + case"), ("nowcast (GDELT same week)", "lu ~ lu1 + lv + case"),
                        ("lead (GDELT week before)", "lu ~ lu1 + lv1 + case")):
            p = smf.ols(f, data=tr).fit().predict(te)
            oos.append(pd.DataFrame(dict(model=name, case=te.case, week=te.week, err=(p - te.lu).abs())))
    oos = pd.concat(oos)
    o = oos.groupby("model").err.mean()
    out["weekly"] = dict(
        weeks=int(ww.week.nunique()), n=int(len(ww)),
        lead_coef=float(lead.params["lv1"]), lead_p=float(lead.pvalues["lv1"]),
        nowcast_coef=float(now.params["lv"]), nowcast_p=float(now.pvalues["lv"]),
        r2_base=float(base.rsquared), r2_nowcast=float(now.rsquared),
        oos_mae_log=o.round(4).to_dict(), oos_weeks=int(oos.week.nunique()),
        oos_gain_nowcast=float(1 - o["nowcast (GDELT same week)"] / o["persistence+case"]),
        oos_gain_lead=float(1 - o["lead (GDELT week before)"] / o["persistence+case"]),
        oos_by_case={c: float(1 - x[x.model.str.startswith("nowcast")].err.mean() /
                              x[x.model.str.startswith("persistence")].err.mean()) for c, x in oos.groupby("case")})

    # ---- 3. beyond UCDP: Oct and early Nov 2026 -----------------------------------------------
    sig = mo[mo.month >= LAST_UCDP][["case", "month", "days", "violent_pd", "events_pd", "articles_pd",
                                    "threats_pd", "posture_pd", "gw", "tone"]].copy()
    sig = sig.sort_values(["case", "month"])
    sig["violent_change_vs_prev"] = sig.groupby("case").violent_pd.pct_change()
    tracks = {c for c, v in agree.items() if v["rho_change"] >= 0.5}
    sig["gdelt_tracks_ucdp"] = sig.case.isin(tracks)
    sig["flag"] = np.where(sig.violent_change_vs_prev >= SIGNAL_UP, "RISING",
                           np.where(sig.violent_change_vs_prev <= -SIGNAL_UP, "FALLING", "STEADY"))
    sig.loc[sig.month == LAST_UCDP, "flag"] = "baseline (last UCDP month)"
    sig["month"] = sig.month.dt.strftime("%Y-%m")
    out["signals"] = sig.round(4).to_dict("records")
    out["tracks_ucdp"] = sorted(tracks)
    out["caveat"] = ("GDELT counts media-coded reports, not incidents; it is a narrative/attention signal and is "
                     "compared with UCDP, never joined on events. These are new results, not part of the submitted models.")

    if save:
        mo.assign(month=mo.month.dt.strftime("%Y-%m")).round(4).to_csv(C.TAB_DIR / "gdelt_vs_ucdp_monthly.csv", index=False)
        lags.round(4).to_csv(C.TAB_DIR / "gdelt_weekly_lags.csv", index=False)
        sig.round(4).to_csv(C.TAB_DIR / "gdelt_signals.csv", index=False)
        w.assign(week=w.week.dt.strftime("%Y-%m-%d"))[["case", "week", "days", "violent_pd", "ucdp_deaths"]].round(3) \
            .to_parquet(C.PROCESSED / "gdelt_weekly.parquet", index=False)
        (C.TAB_DIR / "gdelt_summary.json").write_text(json.dumps(out, indent=2, default=str))
    return out


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, default=str)[:6000])
