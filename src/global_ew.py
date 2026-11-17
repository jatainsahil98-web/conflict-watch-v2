"""Transfer learning for the escalation warning: learn what escalation looks like from the wider world.

The four competition cases hold about 200 first-level areas and only ~80 escalations a year, too few
to learn the shape of an escalation well. Issued file D10 (6. war_terror_violence_200k.csv, UCDP GED
1989-2025) holds 90,512 events in 110 non-focus countries and about 1,450 first-level areas. We turn
those into area-month series with exactly the same features and the same escalation label, and add
them to the TRAINING data only. Evaluation is always on the four cases.

Rules
* Focus countries (country_group == "Focus country") are dropped from D10: they are already in D1,
  so keeping them would count the same deaths twice.
* D10 is a capped extract that keeps the deadlier records outside the focus countries, so its areas
  look more violent than a random sample. That biases the training mix, not the evaluation.
* A fold for year Y trains on global target months <= Dec(Y-1), the same cutoff as the case data.
* The variant to deploy is chosen on the 2023-2025 folds only (pre-registered in
  outputs/tables/preregistration.json before 2026 is scored).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as C
from .features import add_dynamic_features

D10 = C.ROOT / "data" / "raw" / "extra" / "6. war_terror_violence_200k.csv"
GLOBAL_TAG = "Global"


def build_global_admin1() -> pd.DataFrame:
    d = pd.read_csv(D10, usecols=["country", "country_group", "adm_1", "date_start", "deaths_best"])
    d = d[d.country_group != "Focus country"].copy()
    d["month"] = pd.to_datetime(d.date_start).dt.to_period("M").dt.to_timestamp()
    d["adm_1"] = d.adm_1.fillna("(unspecified)")
    d["admin1_key"] = "G|" + d.country + "|" + d.adm_1
    agg = d.groupby(["country", "admin1_key", "adm_1", "month"]).agg(
        deaths=("deaths_best", "sum"), n_events=("deaths_best", "size")).reset_index()
    # complete each area's monthly grid from 12 months before its first event to Dec 2025
    end = pd.Timestamp("2025-12-01")
    first = agg.groupby("admin1_key").month.min()
    rows = []
    for key, m0 in first.items():
        start = max(m0 - pd.DateOffset(months=12), pd.Timestamp("1989-01-01"))
        rows.append(pd.DataFrame({"admin1_key": key, "month": pd.date_range(start, end, freq="MS")}))
    grid = pd.concat(rows, ignore_index=True)
    meta = agg[["admin1_key", "country", "adm_1"]].drop_duplicates("admin1_key")
    p = grid.merge(meta, on="admin1_key").merge(agg[["admin1_key", "month", "deaths", "n_events"]],
                                                 on=["admin1_key", "month"], how="left")
    p[["deaths", "n_events"]] = p[["deaths", "n_events"]].fillna(0)
    p["n_sources"] = np.nan
    p["conflict_case"] = GLOBAL_TAG + "|" + p.country
    p["country_iso3"] = "G|" + p.country
    p["admin1"] = p.adm_1
    p = add_dynamic_features(p, ["conflict_case", "admin1_key"])

    # the country plays the role of the "case" for the context features
    c = p.groupby(["conflict_case", "month"]).agg(deaths=("deaths", "sum"), n_events=("n_events", "sum"),
                                                  n_admin1=("deaths", lambda s: int((s > 0).sum()))).reset_index()
    c["n_sources"], c["hhi"], c["outside_core_share"] = np.nan, 0.0, 0.0
    c = add_dynamic_features(c, ["conflict_case"])
    ctx = c[["conflict_case", "month", "y_l0", "y_rm3", "y_rm12", "momentum_3v12", "n_admin1_rm3"]]
    ctx = ctx.rename(columns={k: f"case_{k}" for k in ctx.columns[2:]})
    p = p.merge(ctx, on=["conflict_case", "month"], how="left")
    p["_d12"] = p.groupby("admin1_key").deaths.transform(lambda s: s.rolling(12, 1).sum())
    tot = p.groupby(["conflict_case", "month"])._d12.transform("sum").replace(0, np.nan)
    p["share_of_case_12m"] = (p._d12 / tot).fillna(0)
    return p.drop(columns=["_d12", "adm_1", "country"])
