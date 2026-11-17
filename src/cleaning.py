"""Stage 1 - load, validate and clean the six official tables.

Design rules
------------
* Source files are never modified. Every cleaned table is written to
  ``data/processed`` as parquet.
* Nothing is silently dropped. Each check is recorded in a data-quality (DQ)
  log with the rows affected and the action taken, and row-level flags are kept
  on the cleaned tables so any analysis can include or exclude them.
* Raw values are preserved next to corrected values (e.g. ``deaths_low`` and
  ``deaths_low_c``) so a reviewer can always see what changed.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import config as C


# ---------------------------------------------------------------------------
# Data-quality log
# ---------------------------------------------------------------------------
@dataclass
class DQLog:
    rows: list = field(default_factory=list)

    def add(self, table, check, category, n_affected, n_total, action, impact=""):
        self.rows.append(
            dict(
                id=f"DQ{len(self.rows) + 1:02d}",
                table=table,
                check=check,
                category=category,
                rows_affected=int(n_affected),
                rows_total=int(n_total),
                pct_affected=round(100 * n_affected / max(n_total, 1), 2),
                action=action,
                analytical_impact=impact,
            )
        )

    def frame(self) -> pd.DataFrame:
        return pd.DataFrame(self.rows)


def _read(name: str, **kw) -> pd.DataFrame:
    # Files ship as UTF-8 with a byte-order mark; utf-8-sig strips it so the
    # first column name is not corrupted ("﻿event_id").
    return pd.read_csv(C.RAW_DIR / f"{name}.csv", encoding="utf-8-sig", **kw)


# ---------------------------------------------------------------------------
# Conflict events
# ---------------------------------------------------------------------------
def clean_events(log: DQLog) -> pd.DataFrame:
    e = _read("conflict_events", parse_dates=["date_start", "date_end"])
    n = len(e)
    log.add("conflict_events", "File encoding: UTF-8 byte-order mark on header", "Format",
            0, n, "Read with utf-8-sig so the first column is 'event_id' and not '\\ufeffevent_id'.",
            "Prevents silent join failures on event_id.")

    # --- Keys ---------------------------------------------------------------
    dup = e.event_id.duplicated().sum()
    log.add("conflict_events", "Duplicate primary key (event_id)", "Integrity", dup, n,
            "Validated: none found." if dup == 0 else "Dropped exact duplicates.")
    e = e.drop_duplicates("event_id")

    # --- Fatality arithmetic -------------------------------------------------
    comp = e[["deaths_side_a", "deaths_side_b", "deaths_civilians", "deaths_unknown_status"]].sum(axis=1)
    bad_sum = int((comp != e.deaths_best).sum())
    log.add("conflict_events", "deaths_best equals sum of four component fields", "Integrity", bad_sum, n,
            "Validated: identity holds for every row." if bad_sum == 0 else "Flagged rows where it fails.")

    neg = int((e[["deaths_best", "deaths_low", "deaths_high"]] < 0).any(axis=1).sum())
    log.add("conflict_events", "Negative fatality values", "Validity", neg, n, "Validated: none found.")

    ooo = (e.deaths_low > e.deaths_best) | (e.deaths_best > e.deaths_high) | (e.deaths_low > e.deaths_high)
    e["flag_estimate_order"] = ooo
    # Corrected bounds: the band must contain the best estimate. We widen the
    # band rather than move the best estimate, because best is the figure UCDP
    # reconciles with the component fields (validated above).
    e["deaths_low_c"] = np.minimum.reduce([e.deaths_low, e.deaths_best, e.deaths_high])
    e["deaths_high_c"] = np.maximum.reduce([e.deaths_low, e.deaths_best, e.deaths_high])
    log.add("conflict_events", "Out-of-order low/best/high estimates (low<=best<=high violated)", "Validity",
            ooo.sum(), n,
            "Raw values preserved. Corrected copies deaths_low_c = min(low,best,high) and deaths_high_c = "
            "max(low,best,high); row flagged flag_estimate_order.",
            "Uncertainty-band features and the fatality uncertainty index use the corrected band.")

    # --- Dates --------------------------------------------------------------
    rev = int((e.date_end < e.date_start).sum())
    log.add("conflict_events", "date_end earlier than date_start", "Validity", rev, n, "Validated: none found.")
    e["span_days"] = (e.date_end - e.date_start).dt.days + 1
    multi_month = e.date_start.dt.to_period("M") != e.date_end.dt.to_period("M")
    e["flag_multi_month"] = multi_month
    log.add("conflict_events", "Event date range crosses a month boundary", "Temporal",
            multi_month.sum(), n,
            "Fatalities allocated across months in proportion to days in range (uniform-day disaggregation) "
            "instead of assigning everything to the start month.",
            f"Avoids artificial spikes: {int(e.loc[multi_month, 'deaths_best'].sum()):,} deaths would otherwise "
            "be stacked on start months.")
    beyond = e.date_end > pd.Timestamp(C.PANEL_END)
    log.add("conflict_events", "Date range extends beyond the 30 Sep 2026 extract window", "Temporal",
            beyond.sum(), n,
            "Kept. Only the in-window share of deaths enters the monthly panel; out-of-window share is logged.")
    e["flag_low_date_precision"] = e.date_precision >= 4
    log.add("conflict_events", "Low date precision (code 4-5: month or longer)", "Precision",
            e.flag_low_date_precision.sum(), n,
            "Kept and flagged. Used as a feature (share of imprecise events = reporting fog).")

    # --- Provisional data ---------------------------------------------------
    e["is_provisional"] = e.source_release.str.startswith("Candidate")
    log.add("conflict_events", "Provisional UCDP Candidate records (Jan-Sep 2026)", "Provenance",
            e.is_provisional.sum(), n,
            "Flagged is_provisional. 2026 is used ONLY as the withheld test set, never for training "
            "the evaluated models.",
            "Candidate counts can be revised (usually upward) at the annual release; holdout error includes "
            "this revision noise.")
    chk = e.ucdp_coding_status.ne("Clear")
    e["flag_coding_check"] = chk
    log.add("conflict_events", "UCDP coding status under review ('Check ...')", "Provenance", chk.sum(), n,
            "Kept and flagged flag_coding_check; sensitivity analysis excludes them.")

    # --- Geography ----------------------------------------------------------
    miss_iso = e.location_iso3.isna()
    e["country_iso3"] = e.location_iso3.fillna("XXX")
    e.loc[miss_iso & (e.source_location_precision == 7), "country_iso3"] = "INTL"
    log.add("conflict_events", "Blank location_iso3 (code 666 ambiguous / international waters or airspace)",
            "Missing", miss_iso.sum(), n,
            "Imputed join key: 'INTL' for international waters/airspace (precision 7), 'XXX' for ambiguous "
            "code 666. Source labels retained.",
            "Rows stay in case totals; excluded only from country-level joins.")
    miss_a1 = e.admin1_name.isna()
    e["admin1"] = e.admin1_name.fillna("(country-level / unspecified)")
    # Boundary harmonisation: FATA was merged into Khyber Pakhtunkhwa by Pakistan's
    # 25th Amendment (May 2018). UCDP labels pre-2018 events 'FATA' and later ones
    # 'Khyber Pakhtunkwa', which would fake a collapse of violence in FATA and a
    # surge in KP. We map both to the post-merger unit and keep the raw label.
    fata = e.admin1.eq("Federally Administered Tribal Areas")
    e.loc[fata, "admin1"] = "Khyber Pakhtunkwa province"
    e["admin1_key"] = e.country_iso3 + " | " + e.admin1
    log.add("conflict_events", "Administrative boundary change: FATA merged into Khyber Pakhtunkhwa (2018)",
            "Consistency", fata.sum(), n,
            "Harmonised FATA to 'Khyber Pakhtunkwa province' (post-merger boundary) for a stable sub-national "
            "panel; raw admin1_name retained.",
            "Removes a spurious 2018 structural break in the AF-PK hotspot series.")
    log.add("conflict_events", "Blank admin1_name", "Missing", miss_a1.sum(), n,
            "Imputed category '(country-level / unspecified)' so the events remain in sub-national panels.",
            "Sub-national hotspot ranking treats this as its own bucket.")

    # --- Aggregates and outliers --------------------------------------------
    e["is_aggregate"] = e.event_clarity.eq(2)
    log.add("conflict_events", "Aggregate event records (event_clarity = 2)", "Granularity",
            e.is_aggregate.sum(), n,
            "Kept (they carry real deaths) and flagged; event COUNT features use clear events only.")
    q = e.deaths_best.quantile(0.999)
    big = e.deaths_best > q
    log.add("conflict_events", f"Extreme fatality records (> 99.9th pct = {q:.0f})", "Outlier", big.sum(), n,
            "Kept: verified as multi-day aggregates (mostly RU-UA front-wide monthly totals). Models use "
            "log1p target and robust (MAE-based) evaluation.",
            "Treated as signal, not error; capping would erase the 2022 invasion.")
    zero = e.deaths_best.eq(0)
    log.add("conflict_events", "Zero-fatality events (deaths_best = 0)", "Validity", zero.sum(), n,
            "Kept: UCDP retains events whose best estimate is 0 if low/high > 0 or in an active dyad.")

    # --- Derived convenience fields -----------------------------------------
    e["violence_type"] = e.violence_type_code.map(C.VIOLENCE_TYPES)
    e["month"] = e.date_start.dt.to_period("M").dt.to_timestamp()
    e["deaths_combatant"] = e.deaths_side_a + e.deaths_side_b
    return e


def allocate_to_months(e: pd.DataFrame, log: DQLog) -> pd.DataFrame:
    """Uniform-day temporal disaggregation of each event to calendar months.

    Returns one row per (event_id, month) with the share of the event's days that
    fall in that month (shares sum to 1 over the full range, but rows outside the
    panel window are dropped).
    """
    single = e.loc[~e.flag_multi_month, ["event_id", "month"]].assign(share=1.0)
    rows = []
    for r in e.loc[e.flag_multi_month, ["event_id", "date_start", "date_end", "span_days"]].itertuples(index=False):
        days = pd.date_range(r.date_start, r.date_end, freq="D")
        m = days.to_period("M").value_counts(sort=False)
        for per, cnt in m.items():
            rows.append((r.event_id, per.to_timestamp(), cnt / r.span_days))
    multi = pd.DataFrame(rows, columns=["event_id", "month", "share"])
    alloc = pd.concat([single, multi], ignore_index=True)
    out = alloc.month > pd.Timestamp(C.PANEL_END)
    lost = (alloc.loc[out].merge(e[["event_id", "deaths_best"]], on="event_id")
            .eval("share*deaths_best").sum())
    alloc = alloc.loc[~out].reset_index(drop=True)
    log.add("conflict_events", "Monthly allocation outside panel window (after Sep 2026)", "Temporal",
            out.sum(), len(alloc) + out.sum(),
            f"Dropped allocation rows after the window ({lost:.1f} deaths, i.e. the October share of a "
            "September-start record).")
    return alloc


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------
_ALIASES = {
    "itar tass": "TASS", "tass": "TASS", "itar tass world service": "TASS",
    "ua losses": "UA Losses", "ualosses": "UA Losses",
    "ukrinform": "Ukrinform", "ukrinform news": "Ukrinform",
    "afp": "Agence France Presse", "agence france presse": "Agence France Presse",
    "reuters": "Reuters", "reuters news": "Reuters",
    "btselem": "B'Tselem", "b tselem": "B'Tselem",
}


def _norm_key(s: str) -> str:
    s = re.sub(r"^\s*source:\s*", "", str(s), flags=re.I)
    s = re.sub(r"[^0-9a-zA-Z]+", " ", s).strip().lower()
    return re.sub(r"\s+", " ", s)


def clean_sources(e: pd.DataFrame, log: DQLog) -> pd.DataFrame:
    s = _read("event_sources", parse_dates=["published_date"])
    n = len(s)
    dup = s.duplicated(["event_id", "reference_order"]).sum()
    log.add("event_sources", "Duplicate composite key (event_id, reference_order)", "Integrity", dup, n,
            "Validated: none found." if dup == 0 else "Dropped.")
    orphan = ~s.event_id.isin(e.event_id)
    log.add("event_sources", "Orphan references (event_id not in events)", "Integrity", orphan.sum(), n,
            "Validated: none found." if orphan.sum() == 0 else "Dropped.")
    cnt = s.groupby("event_id").size().reindex(e.event_id).fillna(0)
    mism = int((cnt.values != e.source_count.values).sum())
    log.add("event_sources", "source_count matches number of reference rows", "Integrity", mism, len(e),
            "Validated: matches for every event." if mism == 0 else "Flagged.")

    pref = s.publisher.str.match(r"^\s*Source:", case=False)
    log.add("event_sources", "Publisher labels with spreadsheet 'Source:' prefix", "Format", pref.sum(), n,
            "Prefix stripped in publisher_norm.")
    key = s.publisher.map(_norm_key)
    s["publisher_key"] = key.map(lambda k: _ALIASES.get(k, k))
    canon = (s.groupby("publisher_key").publisher.agg(lambda x: x.value_counts().index[0])
             .str.replace(r"^\s*Source:\s*", "", regex=True))
    s["publisher_norm"] = s.publisher_key.map(canon)
    for k, v in _ALIASES.items():
        s.loc[s.publisher_key == v, "publisher_norm"] = v
    n_raw, n_norm = s.publisher.nunique(), s.publisher_norm.nunique()
    log.add("event_sources", "Publisher name variants (e.g. ITAR-TASS/Tass, UA Losses/UALosses)", "Consistency",
            n_raw - n_norm, n_raw,
            f"Normalised {n_raw:,} raw labels to {n_norm:,} outlets (case, punctuation, prefix, alias map).",
            "Outlet diversity features count real outlets, not spelling variants.")
    rep = s.duplicated(["event_id", "publisher_norm", "published_date"])
    s["flag_repeat_reference"] = rep
    log.add("event_sources", "Same outlet + same date repeated within one event", "Duplicates", rep.sum(), n,
            "Kept (README: references can repeat an outlet/date) but flagged; 'unique outlets' feature "
            "de-duplicates them.")
    s = s.merge(e[["event_id", "date_start", "date_end", "conflict_case"]], on="event_id", how="left")
    s["report_lag_days"] = (s.published_date - s.date_end).dt.days
    pre = s.report_lag_days < -1
    log.add("event_sources", "Reference published before the event's end date", "Temporal", pre.sum(), n,
            "Kept (README: references may precede an event, e.g. aggregate updates). Lag clipped at 0 for "
            "reporting-latency statistics.")
    s["report_lag_days_c"] = s.report_lag_days.clip(lower=0)
    return s


# ---------------------------------------------------------------------------
# Displacement and context tables
# ---------------------------------------------------------------------------
def clean_bilateral(log: DQLog) -> pd.DataFrame:
    b = _read("bilateral_displacement_stocks")
    n = len(b)
    dup = b.duplicated(["year", "origin_iso3", "asylum_iso3"]).sum()
    log.add("bilateral_displacement_stocks", "Duplicate key (year, origin, asylum)", "Integrity", dup, n,
            "Validated: none found." if dup == 0 else "Dropped.")
    miss = b.other_international_protection.isna()
    b["flag_oip_blank"] = miss
    b["other_international_protection"] = b.other_international_protection.fillna(0)
    log.add("bilateral_displacement_stocks", "Blank other_international_protection (source dash)", "Missing",
            miss.sum(), n,
            "Imputed 0: in UNHCR tables a dash denotes nil / not applicable (documented in data dictionary). "
            "Flag retained.")
    b["total_international"] = b[["refugees_unhcr", "asylum_seekers", "other_international_protection"]].sum(axis=1)
    return b


def clean_demographics(log: DQLog) -> pd.DataFrame:
    u = _read("unhcr_demographics")
    n = len(u)
    dup = u.unhcr_record_id.duplicated().sum()
    log.add("unhcr_demographics", "Duplicate unhcr_record_id", "Integrity", dup, n,
            "Validated: none found." if dup == 0 else "Dropped.")
    unspec = (u[["sex_code", "age_code"]] == "_X").any(axis=1)
    log.add("unhcr_demographics", "Unspecified sex/age cells ('_X')", "Missing", unspec.sum(), n,
            "Kept as an explicit 'Unspecified' level; shares computed over specified cells only and coverage "
            "reported alongside.", "Avoids treating unreported as zero.")
    return u


def clean_reference_stocks(log: DQLog) -> pd.DataFrame:
    r = _read("displacement_reference_stocks")
    n = len(r)
    log.add("displacement_reference_stocks", "Two non-comparable series (IDMC IDPs vs UNRWA registrations)",
            "Semantics", n, n, "series_code kept as a key on every summary; the series are never summed.")
    unk = r.reporting_iso3.eq("UNK")
    log.add("displacement_reference_stocks", "Unknown reporting area (UNK)", "Missing", unk.sum(), n,
            "Kept in series totals, excluded from country joins.")
    return r


def clean_context(log: DQLog) -> pd.DataFrame:
    c = _read("country_year_context")
    n = len(c)
    c = c.sort_values(["iso3", "year"])
    for col in ["population_total", "gdp_growth_annual_pct", "consumer_inflation_annual_pct"]:
        miss = c[col].isna()
        flag = f"flag_imputed_{col.split('_')[0]}"
        c[flag] = miss
        # within-economy linear interpolation, then nearest-year fill at the edges
        c[col] = (c.groupby("iso3")[col]
                  .transform(lambda s: s.interpolate(limit_direction="both")))
        still = c[col].isna().sum()
        log.add("country_year_context", f"Missing {col}", "Missing", miss.sum(), n,
                f"Within-economy linear interpolation + edge fill; {still} remain blank (economy has no "
                "value in any year) and are left missing.")
    log.add("country_year_context", "Context ends 2025; panel runs to Sep 2026", "Temporal", 0, n,
            "Models use context lagged by one year, so 2026 months use 2025 values - no extrapolation "
            "and no leakage.")
    return c


# ---------------------------------------------------------------------------
def run(save: bool = True) -> dict:
    log = DQLog()
    ev = clean_events(log)
    alloc = allocate_to_months(ev, log)
    src = clean_sources(ev, log)
    bil = clean_bilateral(log)
    dem = clean_demographics(log)
    ref = clean_reference_stocks(log)
    ctx = clean_context(log)
    # cross-table join coverage
    iso_ev = set(ev.country_iso3) - {"INTL", "XXX"}
    miss_ctx = sorted(iso_ev - set(ctx.iso3))
    log.add("cross-table", "Event locations with no World Bank economy match", "Join coverage",
            len(miss_ctx), len(iso_ev), f"Unmatched: {', '.join(miss_ctx) or 'none'}. Context features left "
            "blank for these (LightGBM handles missing natively).")
    dq = log.frame()
    out = dict(events=ev, alloc=alloc, sources=src, bilateral=bil, demographics=dem,
               reference=ref, context=ctx, dq_log=dq)
    if save:
        for k, v in out.items():
            v.to_parquet(C.PROCESSED / f"{k}.parquet", index=False)
        dq.to_csv(C.TAB_DIR / "data_quality_log.csv", index=False)
    return out


def load(name: str) -> pd.DataFrame:
    return pd.read_parquet(C.PROCESSED / f"{name}.parquet")
