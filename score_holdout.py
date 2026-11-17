"""Score the forecasts and watch-list frozen in this submission against new UCDP events.

    python score_holdout.py --events new_events.csv     # same columns as conflict_events.csv
    python score_holdout.py --selftest                  # builds a synthetic month and checks the scorer

Nothing is refitted.  The frozen outputs are:
  * data/processed/forecast_future.parquet   ensemble forecast + 80% band, Oct-Dec 2026
  * data/processed/early_warning_live.parquet escalation probability per area for Oct 2026
New events are cleaned with the same rules as the pipeline (FATA -> KP, blank admin1 bucket,
blank country -> INTL/XXX, multi-month records split by day) before scoring.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from src import config as C  # noqa: E402

PANEL_END = pd.Timestamp(C.PANEL_END)
LAST_MONTH = PANEL_END.to_period("M").to_timestamp()


def clean_new(e: pd.DataFrame) -> pd.DataFrame:
    e = e.copy()
    for c in ("date_start", "date_end"):
        e[c] = pd.to_datetime(e[c])
    e = e.drop_duplicates("event_id")
    e = e[e.conflict_case.isin(C.CASES)]
    e["country_iso3"] = e.location_iso3.fillna("XXX")
    if "source_location_precision" in e:
        e.loc[e.location_iso3.isna() & (e.source_location_precision == 7), "country_iso3"] = "INTL"
    e["admin1"] = e.admin1_name.fillna("(country-level / unspecified)")
    e.loc[e.admin1.eq("Federally Administered Tribal Areas"), "admin1"] = "Khyber Pakhtunkwa province"
    e["admin1_key"] = e.country_iso3 + " | " + e.admin1
    # uniform-day allocation across months; keep months after the submission's data window
    rows = []
    for r in e.itertuples(index=False):
        days = pd.date_range(r.date_start, max(r.date_end, r.date_start), freq="D")
        per = days.to_period("M").value_counts(sort=False)
        for p, n in per.items():
            rows.append((r.conflict_case, r.admin1_key, p.to_timestamp(), r.deaths_best * n / len(days)))
    a = pd.DataFrame(rows, columns=["conflict_case", "admin1_key", "month", "deaths"])
    return a[a.month > PANEL_END]


def score(alloc: pd.DataFrame) -> dict:
    fut = pd.read_parquet(C.PROCESSED / "forecast_future.parquet")
    fut = fut[fut.model == "ensemble"]
    cm = pd.read_parquet(C.PROCESSED / "case_month.parquet")
    last = cm[cm.month == LAST_MONTH].set_index("conflict_case").deaths
    act = alloc.groupby(["conflict_case", "month"]).deaths.sum()
    out = {"forecast": [], "watch_list": None}
    for r in fut.itertuples(index=False):
        m = pd.Timestamp(r.target_month)
        if not (alloc.month == m).any():
            continue
        y = float(act.get((r.conflict_case, m), 0.0))
        out["forecast"].append(dict(
            conflict=r.conflict_case, month=f"{m:%b %Y}", actual=round(y), forecast=round(r.pred),
            band80=[round(r.pi80_lo), round(r.pi80_hi)], inside_band=bool(r.pi80_lo <= y <= r.pi80_hi),
            abs_error=round(abs(r.pred - y)), naive_abs_error=round(abs(last[r.conflict_case] - y))))
    f = pd.DataFrame(out["forecast"])
    if len(f):
        out["forecast_summary"] = dict(months=int(f.month.nunique()), coverage80=float(f.inside_band.mean()),
                                       mae=float(f.abs_error.mean()), mae_naive=float(f.naive_abs_error.mean()),
                                       reduction_vs_naive=float(1 - f.abs_error.sum() / max(f.naive_abs_error.sum(), 1e-9)))
    # watch-list: frozen Oct 2026 probabilities vs what happened
    live = pd.read_parquet(C.PROCESSED / "early_warning_live.parquet")
    tm = LAST_MONTH + pd.DateOffset(months=1)
    if (alloc.month == tm).any():
        a1 = alloc[alloc.month == tm].groupby("admin1_key").deaths.sum()
        w = live.assign(next_deaths=live.admin1_key.map(a1).fillna(0.0))
        w["escalated"] = ((w.next_deaths >= C.ESCALATION_MIN_DEATHS) &
                          (w.next_deaths >= C.ESCALATION_RATIO * w.base3)).astype(int)
        top = w.nlargest(10, "p_escalation")
        out["watch_list"] = dict(
            month=f"{tm:%b %Y}", areas=int(len(w)), escalated=int(w.escalated.sum()),
            base_rate=float(w.escalated.mean()), top10_hits=int(top.escalated.sum()),
            top10=[dict(area=r.admin1, conflict=r.conflict_case, p=round(float(r.p_escalation), 3),
                        deaths=round(float(r.next_deaths)), escalated=bool(r.escalated)) for r in top.itertuples()],
            roc_auc=float(roc_auc_score(w.escalated, w.p_escalation)) if w.escalated.nunique() == 2 else None)
    return out


def selftest() -> dict:
    """Shift the last observed month forward by one and score it: checks the plumbing, not skill."""
    e = pd.read_csv(C.RAW_DIR / "conflict_events.csv", encoding="utf-8-sig", parse_dates=["date_start", "date_end"])
    sep = e[(e.date_start >= LAST_MONTH) & (e.date_end <= PANEL_END)].copy()
    for c in ("date_start", "date_end"):
        sep[c] = sep[c] + pd.DateOffset(months=1)
    res = score(clean_new(sep))
    assert res["forecast"], "no forecast rows scored"
    assert res["watch_list"] and res["watch_list"]["areas"] > 100, "watch-list not scored"
    assert all(r["month"] == "Oct 2026" for r in res["forecast"])
    print("selftest OK: synthetic Oct 2026 scored for", len(res["forecast"]), "conflicts and",
          res["watch_list"]["areas"], "areas")
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--events", help="CSV of new UCDP events (same columns as conflict_events.csv)")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--out", help="write the result as JSON here")
    a = ap.parse_args()
    if a.selftest:
        res = selftest()
    elif a.events:
        res = score(clean_new(pd.read_csv(a.events, encoding="utf-8-sig")))
    else:
        ap.error("give --events FILE or --selftest")
    txt = json.dumps(res, indent=2, default=str)
    if a.out:
        Path(a.out).write_text(txt)
    print(txt[:4000])
