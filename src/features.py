"""Stage 2 - feature engineering.

Builds two monthly panels from the cleaned tables:

* ``case_month``   - 4 conflict cases x 153 months (Jan 2014 - Sep 2026)
* ``admin1_month`` - every (case, country, first-level area) that ever saw an
  event x 153 months, zero-filled.

and a modelling frame (``make_supervised``) in which every feature is known at
the end of the forecast-origin month t and the target is deaths in month t+h.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as C
from .cleaning import load

CORE_THEATRE = {
    "Russia–Ukraine": {"UKR"},
    "Israel–Hamas": {"PSE"},
    "Afghanistan–Pakistan": {"AFG", "PAK"},
    "US–Iran": {"IRN"},
}
# country whose displacement / macro context describes each case
CASE_CONTEXT_ISO = {
    "Russia–Ukraine": "UKR",
    "Israel–Hamas": "PSE",
    "Afghanistan–Pakistan": "AFG",
    "US–Iran": "IRN",
}
MONTHS = pd.date_range(C.PANEL_START, C.PANEL_END, freq="MS")


# ---------------------------------------------------------------------------
# Monthly aggregation
# ---------------------------------------------------------------------------
def _event_month_frame(e: pd.DataFrame, alloc: pd.DataFrame) -> pd.DataFrame:
    """Deaths at (event, month) after uniform-day allocation."""
    cols = ["event_id", "conflict_case", "country_iso3", "admin1_key", "admin1", "case_scope",
            "violence_type_code", "deaths_best", "deaths_low_c", "deaths_high_c", "deaths_civilians",
            "deaths_side_a", "deaths_side_b", "deaths_unknown_status"]
    em = alloc.merge(e[cols], on="event_id", how="left")
    for c in cols[7:]:
        em[c] = em[c] * em["share"]
    em["core"] = [iso in CORE_THEATRE[case] for case, iso in zip(em.conflict_case, em.country_iso3)]
    em["d_outside_core"] = np.where(em.core, 0.0, em.deaths_best)
    em["d_state"] = np.where(em.violence_type_code == 1, em.deaths_best, 0.0)
    em["d_nonstate"] = np.where(em.violence_type_code == 2, em.deaths_best, 0.0)
    em["d_onesided"] = np.where(em.violence_type_code == 3, em.deaths_best, 0.0)
    em["d_focal"] = np.where(em.case_scope == "Focal", em.deaths_best, 0.0)
    return em


def _start_month_counts(e: pd.DataFrame, s: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    """Event and source counts by event start month (counts are not split)."""
    g = e.groupby(keys + ["month"])
    out = pd.DataFrame({
        "n_events": g.size(),
        "n_events_clear": g.is_aggregate.apply(lambda x: (~x).sum()),
        "n_sources": g.source_count.sum(),
        "n_aggregate": g.is_aggregate.sum(),
        "n_lowprec": g.flag_low_date_precision.sum(),
        "n_provisional": g.is_provisional.sum(),
    })
    ss = s.loc[~s.flag_repeat_reference].merge(e[["event_id"] + keys + ["month"]], on="event_id",
                                               suffixes=("_src", ""))
    k2 = [k for k in keys]  # conflict_case may be duplicated by the merge
    ss = ss.loc[:, ~ss.columns.duplicated()]
    out["n_outlets"] = ss.groupby(k2 + ["month"]).publisher_norm.nunique()
    out["n_refs_unique"] = ss.groupby(k2 + ["month"]).size()
    lag = s.merge(e[["event_id"] + keys + ["month"]], on="event_id", suffixes=("_src", ""))
    lag = lag.loc[:, ~lag.columns.duplicated()]
    out["report_lag_median"] = lag.groupby(k2 + ["month"]).report_lag_days_c.median()
    return out.fillna(0)


def _complete(df: pd.DataFrame, keys: list[str], key_values: pd.DataFrame) -> pd.DataFrame:
    grid = key_values.merge(pd.DataFrame({"month": MONTHS}), how="cross")
    out = grid.merge(df, on=keys + ["month"], how="left")
    num = out.select_dtypes("number").columns
    out[num] = out[num].fillna(0)
    return out


def build_case_month(e, alloc, s) -> pd.DataFrame:
    em = _event_month_frame(e, alloc)
    keys = ["conflict_case"]
    agg = em.groupby(keys + ["month"]).agg(
        deaths=("deaths_best", "sum"), deaths_low=("deaths_low_c", "sum"),
        deaths_high=("deaths_high_c", "sum"), deaths_civ=("deaths_civilians", "sum"),
        deaths_side_a=("deaths_side_a", "sum"), deaths_side_b=("deaths_side_b", "sum"),
        deaths_unknown=("deaths_unknown_status", "sum"), d_outside_core=("d_outside_core", "sum"),
        d_state=("d_state", "sum"), d_nonstate=("d_nonstate", "sum"), d_onesided=("d_onesided", "sum"),
        d_focal=("d_focal", "sum"),
    ).reset_index()
    # geographic spread: number of active first-level areas and concentration (HHI)
    a1 = em.groupby(keys + ["month", "admin1_key"]).deaths_best.sum().reset_index()
    a1 = a1[a1.deaths_best > 0]
    tot = a1.groupby(keys + ["month"]).deaths_best.transform("sum")
    a1["sh2"] = (a1.deaths_best / tot) ** 2
    geo = a1.groupby(keys + ["month"]).agg(n_admin1=("admin1_key", "nunique"), hhi=("sh2", "sum"),
                                          n_countries=("admin1_key", lambda x: x.str[:3].nunique()))
    agg = agg.merge(geo.reset_index(), on=keys + ["month"], how="left")
    cnt = _start_month_counts(e, s, keys).reset_index()
    agg = agg.merge(cnt, on=keys + ["month"], how="outer")
    out = _complete(agg, keys, pd.DataFrame({"conflict_case": C.CASES}))
    return _derive_ratios(out)


def build_admin1_month(e, alloc, s) -> pd.DataFrame:
    em = _event_month_frame(e, alloc)
    keys = ["conflict_case", "admin1_key"]
    agg = em.groupby(keys + ["month"]).agg(
        deaths=("deaths_best", "sum"), deaths_low=("deaths_low_c", "sum"),
        deaths_high=("deaths_high_c", "sum"), deaths_civ=("deaths_civilians", "sum"),
        d_state=("d_state", "sum"), d_onesided=("d_onesided", "sum"), d_focal=("d_focal", "sum"),
    ).reset_index()
    cnt = _start_month_counts(e, s, keys).reset_index()
    agg = agg.merge(cnt, on=keys + ["month"], how="outer")
    kv = e[keys + ["country_iso3", "admin1"]].drop_duplicates(keys)
    out = _complete(agg, keys, kv)
    return _derive_ratios(out)


def _derive_ratios(p: pd.DataFrame) -> pd.DataFrame:
    p = p.copy()
    d = p.deaths.replace(0, np.nan)
    p["civ_share"] = (p.deaths_civ / d).fillna(0)
    p["uncert_index"] = ((p.deaths_high - p.deaths_low) / d).fillna(0)   # relative width of UCDP band
    p["src_per_event"] = (p.n_sources / p.n_events.replace(0, np.nan)).fillna(0)
    p["src_per_death"] = (p.n_sources / d).fillna(0)
    p["agg_share"] = (p.n_aggregate / p.n_events.replace(0, np.nan)).fillna(0)
    p["lowprec_share"] = (p.n_lowprec / p.n_events.replace(0, np.nan)).fillna(0)
    if "d_outside_core" in p:
        p["outside_core_share"] = (p.d_outside_core / d).fillna(0)
    p["state_share"] = (p.d_state / d).fillna(0)
    p["onesided_share"] = (p.d_onesided / d).fillna(0)
    p["focal_share"] = (p.d_focal / d).fillna(0)
    p["is_provisional_month"] = p.month >= pd.Timestamp(C.HOLDOUT_START)
    return p


# ---------------------------------------------------------------------------
# Annual context (displacement + World Bank), lagged one year
# ---------------------------------------------------------------------------
def build_country_year_context() -> pd.DataFrame:
    ctx = load("context")[["iso3", "year", "population_total", "gdp_growth_annual_pct",
                           "consumer_inflation_annual_pct"]]
    ref = load("reference")
    idp = (ref[ref.series_code == "IDMC_CONFLICT_IDP"]
           .rename(columns={"reporting_iso3": "iso3", "people": "idp_stock"})[["iso3", "year", "idp_stock"]])
    bil = load("bilateral")
    out_ref = (bil.groupby(["origin_iso3", "year"]).total_international.sum()
               .rename("refugees_out").reset_index().rename(columns={"origin_iso3": "iso3"}))
    cy = ctx.merge(idp, on=["iso3", "year"], how="outer").merge(out_ref, on=["iso3", "year"], how="outer")
    cy = cy.sort_values(["iso3", "year"])
    cy["displaced_total"] = cy[["idp_stock", "refugees_out"]].sum(axis=1, min_count=1)
    cy["displaced_growth"] = cy.groupby("iso3").displaced_total.pct_change(fill_method=None)
    cy["displaced_per_1k"] = 1000 * cy.displaced_total / cy.population_total
    return cy


def attach_context(panel: pd.DataFrame, iso_col: str) -> pd.DataFrame:
    """Join country-year context lagged by one year (value for year-1)."""
    cy = build_country_year_context().copy()
    cy["year"] = cy["year"] + 1                       # lag: month in year Y sees Y-1 context
    p = panel.copy()
    p["year"] = p.month.dt.year
    # 2026 months would need 2025 context (available), so no extrapolation is required.
    keep = ["iso3", "year", "population_total", "gdp_growth_annual_pct", "consumer_inflation_annual_pct",
            "idp_stock", "refugees_out", "displaced_growth", "displaced_per_1k"]
    p = p.merge(cy[keep].rename(columns={"iso3": iso_col}), on=[iso_col, "year"], how="left")
    return p.drop(columns="year")


# ---------------------------------------------------------------------------
# Supervised frame
# ---------------------------------------------------------------------------
DYN_COLS = ["n_events", "n_sources", "n_outlets", "civ_share", "uncert_index", "src_per_event",
            "agg_share", "lowprec_share", "state_share", "onesided_share", "focal_share"]


def add_dynamic_features(p: pd.DataFrame, group: list[str]) -> pd.DataFrame:
    """Features known at the end of month t (the forecast origin)."""
    p = p.sort_values(group + ["month"]).copy()
    p["y"] = np.log1p(p.deaths)
    g = p.groupby(group, sort=False)
    p["y_l0"] = p.y
    for L in (1, 2, 3, 6, 11, 12):
        p[f"y_l{L}"] = g.y.shift(L)
    for w in (3, 6, 12):
        p[f"y_rm{w}"] = g.y.transform(lambda s: s.rolling(w, min_periods=1).mean())
    p["y_rstd6"] = g.y.transform(lambda s: s.rolling(6, min_periods=2).std())
    p["y_max12"] = g.y.transform(lambda s: s.rolling(12, min_periods=1).max())
    p["y_ewm"] = g.y.transform(lambda s: s.ewm(alpha=0.5).mean())
    p["momentum_3v12"] = p.y_rm3 - p.y_rm12
    p["accel"] = p.y_l0 - p.y_l1
    # months since the last month with any deaths, and since series start of activity
    active = p.deaths > 0
    p["_grp"] = (active != g.deaths.shift().gt(0)).cumsum()
    p["zero_streak"] = np.where(active, 0, p.groupby(group + ["_grp"]).cumcount() + 1)
    p["cum_active_months"] = g.deaths.transform(lambda s: (s > 0).cumsum())
    p = p.drop(columns="_grp")
    for c in DYN_COLS:
        if c in p:
            p[f"{c}_rm3"] = g[c].transform(lambda s: s.rolling(3, min_periods=1).mean())
    p["log_events_rm3"] = np.log1p(p.n_events_rm3)
    p["log_sources_rm3"] = np.log1p(p.n_sources_rm3)
    if "n_admin1" in p:
        p["n_admin1_rm3"] = g.n_admin1.transform(lambda s: s.rolling(3, min_periods=1).mean())
        p["hhi_rm3"] = g.hhi.transform(lambda s: s.rolling(3, min_periods=1).mean())
        p["outside_core_share_rm3"] = g.outside_core_share.transform(lambda s: s.rolling(3, min_periods=1).mean())
    return p


def make_supervised(p: pd.DataFrame, group: list[str], horizons=(1,)) -> pd.DataFrame:
    """Stack (origin t, horizon h) rows with target y_{t+h} and seasonal anchor y_{t+h-12}."""
    frames = []
    g = p.groupby(group, sort=False)
    for h in horizons:
        f = p.copy()
        f["h"] = h
        f["target_month"] = f.month + pd.DateOffset(months=h)
        f["target_y"] = g.y.shift(-h)
        f["target_deaths"] = g.deaths.shift(-h)
        f["y_seasonal"] = g.y.shift(12 - h) if h <= 12 else np.nan
        f["tm_sin"] = np.sin(2 * np.pi * f.target_month.dt.month / 12)
        f["tm_cos"] = np.cos(2 * np.pi * f.target_month.dt.month / 12)
        frames.append(f)
    return pd.concat(frames, ignore_index=True)


# ---------------------------------------------------------------------------
def run(save: bool = True) -> dict:
    e, alloc, s = load("events"), load("alloc"), load("sources")
    cm = build_case_month(e, alloc, s)
    cm["context_iso3"] = cm.conflict_case.map(CASE_CONTEXT_ISO)
    cm = attach_context(cm, "context_iso3")
    cm = add_dynamic_features(cm, ["conflict_case"])

    am = build_admin1_month(e, alloc, s)
    am = attach_context(am, "country_iso3")
    am = add_dynamic_features(am, ["conflict_case", "admin1_key"])
    # case-level context for each sub-national series
    case_ctx = cm[["conflict_case", "month", "y_l0", "y_rm3", "y_rm12", "momentum_3v12", "n_admin1_rm3"]]
    case_ctx = case_ctx.rename(columns={c: f"case_{c}" for c in case_ctx.columns[2:]})
    am = am.merge(case_ctx, on=["conflict_case", "month"], how="left")
    # area's share of its case's deaths over the trailing 12 months
    am["_d12"] = am.groupby(["conflict_case", "admin1_key"]).deaths.transform(lambda s: s.rolling(12, 1).sum())
    tot = am.groupby(["conflict_case", "month"])._d12.transform("sum").replace(0, np.nan)
    am["share_of_case_12m"] = (am._d12 / tot).fillna(0)
    am = am.drop(columns="_d12")
    if save:
        cm.to_parquet(C.PROCESSED / "case_month.parquet", index=False)
        am.to_parquet(C.PROCESSED / "admin1_month.parquet", index=False)
        cy = build_country_year_context()
        cy.to_parquet(C.PROCESSED / "country_year.parquet", index=False)
    return dict(case_month=cm, admin1_month=am)


FEATURE_DICTIONARY = {
    "y_l0..y_l12": "log1p(deaths) at the origin month and its lags 1,2,3,6,11,12",
    "y_rm3/6/12": "rolling mean of log deaths over 3/6/12 months (tempo of the conflict)",
    "y_rstd6": "6-month volatility of log deaths",
    "y_max12": "peak log deaths in the last year (memory of past intensity)",
    "y_ewm": "exponentially weighted log deaths (alpha 0.5)",
    "momentum_3v12": "short-term vs long-term intensity (positive = escalating)",
    "accel": "month-on-month change in log deaths",
    "zero_streak": "consecutive months with no deaths (dormancy)",
    "cum_active_months": "number of months with deaths so far (conflict maturity)",
    "log_events_rm3": "log of events per month, 3-month mean (operational tempo)",
    "log_sources_rm3": "log of references per month, 3-month mean (media attention)",
    "n_outlets_rm3": "distinct outlets reporting (breadth of attention)",
    "src_per_event_rm3": "references per event (reporting depth)",
    "civ_share_rm3": "share of deaths that are civilians",
    "uncert_index_rm3": "(high-low)/best: relative fatality uncertainty (fog of war)",
    "agg_share_rm3": "share of events reported only as aggregates (access constraint)",
    "lowprec_share_rm3": "share of events with month-or-worse date precision",
    "state_share_rm3 / onesided_share_rm3": "violence-type mix",
    "focal_share_rm3": "share of deaths in the focal dyad",
    "n_admin1_rm3": "number of first-level areas with deaths (geographic spread)",
    "hhi_rm3": "Herfindahl concentration of deaths across areas (1 = single front)",
    "outside_core_share_rm3": "share of deaths outside the core theatre (horizontal escalation)",
    "y_seasonal": "log deaths 12 months before the target month",
    "tm_sin/tm_cos": "target calendar month (seasonality, e.g. campaigning season)",
    "h": "forecast horizon in months",
    "idp_stock, refugees_out, displaced_growth, displaced_per_1k": "displacement context, previous year",
    "gdp_growth, inflation, population": "World Bank context, previous year",
    "case_* (admin1 model)": "intensity of the whole conflict the area belongs to",
    "share_of_case_12m (admin1 model)": "area's share of its conflict's deaths in the last 12 months",
}
