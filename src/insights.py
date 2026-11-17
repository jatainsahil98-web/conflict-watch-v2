"""Stage 3 - analytical tables behind the EDA, military, India and humanitarian findings.

Every function returns a tidy DataFrame; notebooks plot them, the dashboard
re-uses them, and ``run()`` writes them to outputs/tables for the report.
Points that rest on domain knowledge rather than these data are kept out of
this module and labelled [Domain] in the report and deck.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf

from . import config as CFG
from .cleaning import load

UNSPEC = "(country-level / unspecified)"


# ---------------------------------------------------------------------------
# Overview
# ---------------------------------------------------------------------------
def case_overview(e: pd.DataFrame, cm: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for case, g in e.groupby("conflict_case"):
        m = cm[cm.conflict_case == case].set_index("month").deaths
        rows.append(dict(
            conflict_case=case, events=len(g), deaths_best=int(g.deaths_best.sum()),
            deaths_low=int(g.deaths_low_c.sum()), deaths_high=int(g.deaths_high_c.sum()),
            peak_month=m.idxmax().strftime("%b %Y"), peak_month_deaths=int(m.max()),
            deaths_2026_ytd=int(m["2026"].sum()), deaths_2025=int(m["2025"].sum()),
            civilian_share=g.deaths_civilians.sum() / g.deaths_best.sum(),
            deaths_per_event=g.deaths_best.sum() / len(g),
            aggregate_event_share=g.is_aggregate.mean(),
            countries_affected=g.country_iso3.nunique(),
            areas_affected=g.admin1_key.nunique(),
            first_event=g.date_start.min().strftime("%b %Y"),
        ))
    return pd.DataFrame(rows).set_index("conflict_case").loc[CFG.CASES].reset_index()


# ---------------------------------------------------------------------------
# Military lens
# ---------------------------------------------------------------------------
def attrition_by_side(e: pd.DataFrame) -> pd.DataFrame:
    """UCDP-recorded fatalities by side in each FOCAL dyad, per year."""
    f = e[e.case_scope == "Focal"].copy()
    f["year"] = f.month.dt.year
    t = (f.groupby(["conflict_case", "side_a_name", "side_b_name", "year"])
         [["deaths_side_a", "deaths_side_b", "deaths_civilians", "deaths_unknown_status"]].sum().reset_index())
    t["ratio_a_to_b"] = t.deaths_side_a / t.deaths_side_b.replace(0, np.nan)
    return t[t[["deaths_side_a", "deaths_side_b", "deaths_civilians", "deaths_unknown_status"]].sum(axis=1) > 0]


def front_geography(e: pd.DataFrame, case="Russia–Ukraine", min_share=0.03) -> pd.DataFrame:
    """Share of geolocated, discrete events by first-level area and year.

    Events (not deaths) are used because most recent RU-UA deaths come in
    country-level aggregate records with no sub-national location."""
    g = e[(e.conflict_case == case) & (e.admin1 != UNSPEC) & (~e.is_aggregate)].copy()
    g["year"] = g.month.dt.year
    t = g.groupby(["year", "country_iso3", "admin1"]).size().rename("events").reset_index()
    t["share"] = t.events / t.groupby("year").events.transform("sum")
    keep = t.groupby("admin1").share.max()
    t["area"] = np.where(t.admin1.isin(keep[keep >= min_share].index), t.admin1, "Other areas")
    return t.groupby(["year", "area"], as_index=False)[["events", "share"]].sum()


def geo_precision_trend(e: pd.DataFrame) -> pd.DataFrame:
    """'Fog of war' in the data: share of deaths with no sub-national location
    and share carried by aggregate records, by case and year."""
    e = e.assign(year=e.month.dt.year)
    rows = []
    for (case, yr), g in e.groupby(["conflict_case", "year"]):
        d = g.deaths_best.sum()
        if d == 0:
            continue
        rows.append(dict(conflict_case=case, year=yr, events=len(g), deaths=d,
                         share_deaths_country_level=g.loc[g.admin1 == UNSPEC, "deaths_best"].sum() / d,
                         share_deaths_aggregate=g.loc[g.is_aggregate, "deaths_best"].sum() / d,
                         uncertainty_index=(g.deaths_high_c.sum() - g.deaths_low_c.sum()) / d))
    return pd.DataFrame(rows)


def theatre_spread(e: pd.DataFrame) -> pd.DataFrame:
    """Horizontal escalation: countries and areas hit per case-year, deaths outside core theatre."""
    from .features import CORE_THEATRE
    e = e.assign(year=e.month.dt.year)
    e["outside_core"] = [iso not in CORE_THEATRE[c] for c, iso in zip(e.conflict_case, e.country_iso3)]
    t = e.groupby(["conflict_case", "year"]).agg(
        countries=("country_iso3", lambda x: x[~x.isin(["INTL", "XXX"])].nunique()),
        areas=("admin1_key", "nunique"), deaths=("deaths_best", "sum"),
        deaths_outside_core=("deaths_best", lambda x: x[e.loc[x.index, "outside_core"]].sum()),
    ).reset_index()
    t["outside_core_share"] = t.deaths_outside_core / t.deaths.replace(0, np.nan)
    return t


def country_deaths(e: pd.DataFrame) -> pd.DataFrame:
    e = e.assign(year=e.month.dt.year)
    return (e[~e.country_iso3.isin(["INTL", "XXX"])]
            .groupby(["conflict_case", "country_iso3", "ucdp_location_name", "year"])
            .agg(deaths=("deaths_best", "sum"), events=("event_id", "count")).reset_index())


def seasonality(cm: pd.DataFrame) -> pd.DataFrame:
    """Month-of-year index of log deaths (de-trended by 12-month mean), active years only."""
    d = cm[["conflict_case", "month", "y"]].copy()
    d["trend"] = d.groupby("conflict_case").y.transform(lambda s: s.rolling(13, center=True, min_periods=7).mean())
    d["dev"] = d.y - d.trend
    d = d[d.trend > 2]                      # months in an active phase (> ~6 deaths/month)
    d["moy"] = d.month.dt.month
    t = d.groupby(["conflict_case", "moy"]).dev.agg(["mean", "count"]).reset_index()
    t["index_pct"] = (np.exp(t["mean"]) - 1) * 100
    return t


def violence_mix(e: pd.DataFrame) -> pd.DataFrame:
    e = e.assign(year=e.month.dt.year)
    return (e.groupby(["conflict_case", "year", "violence_type"]).deaths_best.sum().rename("deaths").reset_index())


def dyad_table(e: pd.DataFrame, top=25) -> pd.DataFrame:
    return (e.groupby(["conflict_case", "case_scope", "ucdp_dyad_name"])
            .agg(events=("event_id", "count"), deaths=("deaths_best", "sum"),
                 first=("date_start", "min"), last=("date_start", "max"))
            .reset_index().sort_values("deaths", ascending=False).head(top))


def afpak_provinces(e: pd.DataFrame) -> pd.DataFrame:
    g = e[e.conflict_case == "Afghanistan–Pakistan"].assign(year=lambda d: d.month.dt.year)
    t = g.groupby(["country_iso3", "admin1", "year"]).deaths_best.sum().rename("deaths").reset_index()
    t["india_proximate"] = t.admin1.map(CFG.INDIA_PROXIMATE_ADMIN1).fillna("")
    return t


def tempo(e: pd.DataFrame) -> pd.DataFrame:
    """Operational tempo: events per month and lethality (deaths per discrete event)."""
    c = e[~e.is_aggregate].groupby(["conflict_case", "month"]).agg(
        events=("event_id", "count"), deaths=("deaths_best", "sum")).reset_index()
    c["deaths_per_event"] = c.deaths / c.events
    return c


# ---------------------------------------------------------------------------
# Media attention vs deaths (original index)
# ---------------------------------------------------------------------------
def media_attention(cm: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Attention Gap Index (AGI).

    Pooled OLS on active case-months:  log(1+references) ~ log(1+deaths) +
    log(1+events) + case fixed effects.  The residual is the attention gap:
    > 0 means a month drew more source references than its violence predicts
    (over-reported), < 0 means under-reported ('forgotten' violence).  It is a
    standardised (z-score) residual so cases are comparable.
    """
    d = cm[cm.n_events > 0].copy()
    d["lref"], d["ldeath"], d["lev"] = np.log1p(d.n_sources), np.log1p(d.deaths), np.log1p(d.n_events)
    d["case"] = d.conflict_case
    fit = smf.ols("lref ~ ldeath + lev + C(case)", data=d).fit(cov_type="HC1")
    d["agi"] = fit.resid / fit.resid.std()
    d["refs_per_100_deaths"] = 100 * d.n_sources / d.deaths.replace(0, np.nan)
    # lead-lag: does attention at t carry information about Δ log deaths at t+1?
    d = d.sort_values(["conflict_case", "month"])
    d["dy_next"] = d.groupby("conflict_case").y.shift(-1) - d.y
    ll = smf.ols("dy_next ~ agi + y + C(case)", data=d.dropna(subset=["dy_next"])).fit(cov_type="HC1")
    stats = dict(elasticity_deaths=fit.params["ldeath"], elasticity_events=fit.params["lev"],
                 r2=fit.rsquared, n=int(fit.nobs), lead_coef=ll.params["agi"], lead_p=ll.pvalues["agi"])
    return d[["conflict_case", "month", "deaths", "n_events", "n_sources", "n_outlets", "refs_per_100_deaths",
              "agi", "report_lag_median"]], stats


def outlet_mix(s: pd.DataFrame, top=12) -> pd.DataFrame:
    t = s.groupby(["conflict_case", "publisher_norm"]).size().rename("refs").reset_index()
    t["share"] = t.refs / t.groupby("conflict_case").refs.transform("sum")
    return t.sort_values(["conflict_case", "refs"], ascending=[True, False]).groupby("conflict_case").head(top)


# ---------------------------------------------------------------------------
# Displacement and humanitarian planning
# ---------------------------------------------------------------------------
FOCUS_ISO = ["UKR", "PSE", "AFG", "PAK", "IRN", "RUS", "ISR"]


def displacement_series() -> pd.DataFrame:
    cy = load("bilateral").groupby(["origin_iso3", "year"]).agg(
        refugees=("refugees_unhcr", "sum"), asylum_seekers=("asylum_seekers", "sum"),
        oip=("other_international_protection", "sum")).reset_index().rename(columns={"origin_iso3": "iso3"})
    ref = load("reference")
    idp = ref[ref.series_code == "IDMC_CONFLICT_IDP"].rename(columns={"reporting_iso3": "iso3", "people": "idps"})
    out = cy.merge(idp[["iso3", "year", "idps"]], on=["iso3", "year"], how="outer")
    return out[out.iso3.isin(FOCUS_ISO)].sort_values(["iso3", "year"])


def unrwa_series() -> pd.DataFrame:
    ref = load("reference")
    return ref[ref.series_code == "UNRWA_REGISTERED_REFUGEE"][["reporting_iso3", "reporting_name", "year", "people"]]


def deaths_displacement_link(e: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Country-year: does violence this year go with growth in the displaced stock?"""
    d = (e[~e.country_iso3.isin(["INTL", "XXX"])].assign(year=e.month.dt.year)
         .groupby(["country_iso3", "year"]).deaths_best.sum().rename("deaths").reset_index()
         .rename(columns={"country_iso3": "iso3"}))
    ds = displacement_series()
    ds["displaced"] = ds[["refugees", "asylum_seekers", "oip", "idps"]].sum(axis=1, min_count=1)
    ds["d_displaced"] = ds.groupby("iso3").displaced.diff()
    m = ds.merge(d, on=["iso3", "year"], how="left").fillna({"deaths": 0})
    m = m[m.year <= 2025].dropna(subset=["d_displaced"])
    m["ldeaths"] = np.log1p(m.deaths)
    m["sgn_lchange"] = np.sign(m.d_displaced) * np.log1p(np.abs(m.d_displaced))
    fit = smf.ols("sgn_lchange ~ ldeaths + C(iso3)", data=m).fit(cov_type="HC1")
    rho = m[["ldeaths", "sgn_lchange"]].corr(method="spearman").iloc[0, 1]
    return m, dict(coef=fit.params["ldeaths"], p=fit.pvalues["ldeaths"], spearman=rho, n=len(m))


def demographic_profile() -> pd.DataFrame:
    """Share of women and children among recorded refugees/asylum seekers, by origin (latest year)."""
    u = load("demographics")
    u = u[u.origin_iso3.isin(FOCUS_ISO)]
    sex = u[(u.sex_code != "_X") & (u.age_code != "_X")]
    rows = []
    for (iso, yr), g in sex.groupby(["origin_iso3", "year"]):
        tot = g.people.sum()
        if tot < 500:
            continue
        rows.append(dict(origin_iso3=iso, year=yr, people_specified=tot,
                         women_share=g.loc[g.sex_code == "F", "people"].sum() / tot,
                         children_share=g.loc[g.age_code.isin(["Y0T4", "Y5T11", "Y12T17"]), "people"].sum() / tot,
                         under5_share=g.loc[g.age_code == "Y0T4", "people"].sum() / tot,
                         elderly_share=g.loc[g.age_code == "Y_GE60", "people"].sum() / tot,
                         women_children_share=g.loc[(g.sex_code == "F") | g.age_code.isin(["Y0T4", "Y5T11", "Y12T17"]),
                                                    "people"].sum() / tot))
    return pd.DataFrame(rows)


def host_countries(top=8) -> pd.DataFrame:
    b = load("bilateral")
    b = b[b.origin_iso3.isin(FOCUS_ISO) & (b.year == b.year.max())]
    return (b.sort_values("total_international", ascending=False).groupby("origin_iso3").head(top)
            [["origin_iso3", "origin_name", "asylum_iso3", "asylum_name", "refugees_unhcr", "asylum_seekers",
              "total_international"]])


# ---------------------------------------------------------------------------
# India lens (data-derived parts only)
# ---------------------------------------------------------------------------
def india_hosted() -> pd.DataFrame:
    b = load("bilateral")
    return (b[b.asylum_iso3 == "IND"][["year", "origin_iso3", "origin_name", "refugees_unhcr", "asylum_seekers",
                                       "total_international"]].sort_values(["origin_iso3", "year"]))


def india_context() -> pd.DataFrame:
    c = load("context")
    return c[c.iso3.isin(["IND", "PAK", "AFG", "IRN", "ISR", "RUS", "UKR"])][
        ["iso3", "economy_name", "year", "population_total", "gdp_growth_annual_pct", "consumer_inflation_annual_pct"]]


def india_exposure_events(e: pd.DataFrame) -> pd.DataFrame:
    """Events in places that matter to India: Gulf states, Indian Ocean littoral,
    Pakistan areas adjoining India, Iran's Hormuz / Chabahar coast."""
    e = e.assign(year=e.month.dt.year)
    tags = []
    for r in e.itertuples():
        t = ""
        if r.country_iso3 in CFG.GULF_ISO3:
            t = "Gulf state (Indian diaspora / energy)"
        elif r.country_iso3 == "LKA":
            t = "Indian Ocean (Sri Lanka)"
        elif r.country_iso3 == "PAK" and r.admin1 in CFG.INDIA_PROXIMATE_ADMIN1:
            t = "Pakistan area adjoining India/LoC"
        elif r.country_iso3 == "IRN" and r.admin1 in ("Hormozgan province", "Sistan and Baluchestan province",
                                                      "Bushehr province"):
            t = "Iran: Hormuz / Chabahar coast"
        elif r.country_iso3 == "YEM":
            t = "Yemen (Red Sea / Bab el-Mandeb)"
        tags.append(t)
    e["india_tag"] = tags
    x = e[e.india_tag != ""]
    return (x.groupby(["india_tag", "conflict_case", "year"])
            .agg(events=("event_id", "count"), deaths=("deaths_best", "sum")).reset_index())


def indian_press_share(s: pd.DataFrame) -> pd.DataFrame:
    ind = ["Press Trust of India", "The Hindu", "Times of India", "Hindustan Times", "Indian Express",
           "Asian News International", "NDTV", "The Tribune", "Economic Times"]
    s = s.assign(indian=s.publisher_norm.str.contains("|".join(ind), case=False, regex=True))
    t = s.groupby("conflict_case").agg(refs=("event_id", "size"), indian_refs=("indian", "sum"),
                                       events=("event_id", "nunique")).reset_index()
    ev = s[s.indian].groupby("conflict_case").event_id.nunique().rename("events_with_indian_source")
    t = t.merge(ev, on="conflict_case", how="left").fillna(0)
    t["indian_ref_share"] = t.indian_refs / t.refs
    t["events_covered_share"] = t.events_with_indian_source / t.events
    return t


# ---------------------------------------------------------------------------
def run(save=True) -> dict:
    e, s = load("events"), load("sources")
    cm = pd.read_parquet(CFG.PROCESSED / "case_month.parquet")
    media, media_stats = media_attention(cm)
    link, link_stats = deaths_displacement_link(e)
    out = dict(
        case_overview=case_overview(e, cm), attrition=attrition_by_side(e), front_geography=front_geography(e),
        geo_precision=geo_precision_trend(e), theatre_spread=theatre_spread(e), country_deaths=country_deaths(e),
        seasonality=seasonality(cm), violence_mix=violence_mix(e), dyads=dyad_table(e),
        afpak_provinces=afpak_provinces(e), tempo=tempo(e), media=media, outlet_mix=outlet_mix(s),
        displacement=displacement_series(), unrwa=unrwa_series(), displacement_link=link,
        demographics_profile=demographic_profile(), hosts=host_countries(), india_hosted=india_hosted(),
        india_context=india_context(), india_exposure=india_exposure_events(e), indian_press=indian_press_share(s),
    )
    stats = dict(media=media_stats, displacement_link=link_stats)
    if save:
        for k, v in out.items():
            v.to_csv(CFG.TAB_DIR / f"insight_{k}.csv", index=False)
        pd.DataFrame([{**{f"media_{k}": v for k, v in media_stats.items()},
                       **{f"link_{k}": v for k, v in link_stats.items()}}]).to_csv(
            CFG.TAB_DIR / "insight_stats.csv", index=False)
    out["stats"] = stats
    return out
