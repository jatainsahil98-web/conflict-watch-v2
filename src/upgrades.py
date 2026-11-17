"""Version 2 additions (issued data only). Each one answers a lesson from the competition review.

1. tripwire()      Fast clock: a daily GDELT (D7, D8) alert for a change of conflict state, tested against
                   UCDP-recorded escalation days with a permutation test. Rules are fixed in RULES below
                   and were not tuned on the outcome.
2. completeness()  How much of a month's deaths is known k days after the event, from the date of the
                   last source report (D2). Explains why the latest months look low.
3. india_front()   India's own front from D10 (UCDP GED 1989-2025): mass-casualty attacks in J&K and the
                   India-Pakistan state fighting that followed.
4. seal()          SHA-256 of the forward forecasts and watch-list, so they can be scored later.

Outputs (outputs/tables): tripwire_alerts.csv, tripwire_summary.json, completeness.csv, india_front.csv,
india_front.json, sealed_predictions.json
"""
from __future__ import annotations

import hashlib
import json

import numpy as np
import pandas as pd

from . import config as C

GDIR = C.ROOT / "data" / "gdelt"
CASE = {"RU-UA": "Russia–Ukraine", "ISR-HAMAS": "Israel–Hamas", "AF-PAK": "Afghanistan–Pakistan", "US-IRAN": "US–Iran"}
RULES = dict(
    red_ratio=4.0, red_window=14, red_min=100,      # violent events/day >= 4x trailing 14-day median and >= 100
    amber_ratio=4.0, amber_window=28, amber_min=40,  # force-posture events (7-day sum) >= 4x trailing 28-day median
    esc_ratio=3.0, esc_window=28, esc_min=20,        # UCDP escalation day: deaths > max(20, 3x trailing 28-day mean)
    tolerance_days=3, n_perm=20000, seed=C.RANDOM_STATE)


# ---------------------------------------------------------------------------
def _ucdp_daily(e: pd.DataFrame) -> pd.DataFrame:
    """Deaths per case-day from precisely dated events (single-day, not aggregates)."""
    d = e[(e.span_days <= 1) & (~e.is_aggregate.astype(bool))]
    d = d.groupby(["conflict_case", "date_start"]).deaths_best.sum().rename("deaths").reset_index()
    out = []
    for case, g in d.groupby("conflict_case"):
        idx = pd.date_range("2025-10-01", C.PANEL_END, freq="D")
        s = g.set_index("date_start").deaths.reindex(idx, fill_value=0)
        base = s.shift(1).rolling(RULES["esc_window"], min_periods=7).mean()
        esc = (s > np.maximum(RULES["esc_min"], RULES["esc_ratio"] * base.fillna(0)))
        out.append(pd.DataFrame({"case": case, "date": idx, "deaths": s.values, "escalation": esc.values}))
    return pd.concat(out, ignore_index=True)


def _alerts(g: pd.DataFrame) -> pd.DataFrame:
    out = []
    for case, x in g.groupby("case"):
        x = x.set_index("date").sort_index()
        idx = pd.date_range(x.index.min(), x.index.max(), freq="D")
        x = x.reindex(idx)                                      # GDELT gap 1-16 May 2026 stays missing
        v, p = x.violent_events, x.force_posture_events
        med = v.shift(1).rolling(RULES["red_window"], min_periods=7).median()
        red = (v >= RULES["red_ratio"] * med) & (v >= RULES["red_min"])
        p7 = p.rolling(7, min_periods=5).sum()
        pmed = p7.shift(7).rolling(RULES["amber_window"], min_periods=14).median()
        amber = (p7 >= RULES["amber_ratio"] * pmed) & (p7 >= RULES["amber_min"])
        out.append(pd.DataFrame({"case": case, "date": idx, "violent": v.values, "ratio": (v / med).values,
                                 "red": red.fillna(False).values, "amber": amber.fillna(False).values}))
    return pd.concat(out, ignore_index=True)


def _episodes(days: pd.Series) -> list:
    """Consecutive alert days form one episode; return the first day of each."""
    days = sorted(days)
    eps, last = [], None
    for d in days:
        if last is None or (d - last).days > 1:
            eps.append(d)
        last = d
    return eps


def tripwire(e: pd.DataFrame) -> dict:
    g = pd.read_csv(GDIR / "gdelt_case_daily.csv", parse_dates=["date"])
    g["case"] = g.case_id.map(CASE)
    a = _alerts(g)
    u = _ucdp_daily(e)
    tol = pd.Timedelta(days=RULES["tolerance_days"])
    lo, hi = pd.Timestamp("2026-02-01"), pd.Timestamp(C.PANEL_END)     # both clocks run
    rng = np.random.default_rng(RULES["seed"])
    rows, hits_total, eps_total, perm_hits = [], 0, 0, np.zeros(RULES["n_perm"])
    for case in C.CASES:
        aa = a[(a.case == case) & a.date.between(lo, hi)]
        uu = u[(u.case == case) & u.date.between(lo, hi)]
        esc_days = set(uu.date[uu.escalation])
        eps = _episodes(aa.date[aa.red])
        valid_days = aa.date[aa.violent.notna()].tolist()
        def hit(d):
            return any(abs((x - d).days) <= tol.days for x in esc_days)
        h = [hit(d) for d in eps]
        hits_total += sum(h); eps_total += len(eps)
        for d, ok in zip(eps, h):
            rows.append(dict(case=case, date=d.date(), light="RED", confirmed=ok))
        for d in _episodes(aa.date[aa.amber]):
            nxt = [x for x in esc_days if 0 <= (x - d).days <= 21]
            rows.append(dict(case=case, date=d.date(), light="AMBER", confirmed=bool(nxt),
                             lead_days=min((x - d).days for x in nxt) if nxt else None))
        # permutation: same number of episodes on random covered days
        if eps and valid_days:
            arr = np.array(valid_days, dtype="datetime64[D]")
            esc = np.array(sorted(esc_days), dtype="datetime64[D]") if esc_days else np.array([], dtype="datetime64[D]")
            for i in range(RULES["n_perm"]):
                pick = rng.choice(arr, size=len(eps), replace=False)
                if len(esc):
                    dd = np.abs((pick[:, None] - esc[None, :]).astype(int)).min(axis=1)
                    perm_hits[i] += (dd <= tol.days).sum()
    p = float((perm_hits >= hits_total).mean()) if eps_total else None
    al = pd.DataFrame(rows)
    al.to_csv(C.TAB_DIR / "tripwire_alerts.csv", index=False)
    caught = {}
    for case in C.CASES:
        uu = u[(u.case == case) & u.date.between(lo, hi)]
        reds = set(a[(a.case == case) & a.red].date)
        esc = uu.date[uu.escalation]
        caught[case] = dict(escalation_days=int(len(esc)),
                            caught=int(sum(any(abs((r - d).days) <= tol.days for r in reds) for d in esc)))
    summ = dict(rules=RULES, window=[str(lo.date()), str(hi.date())], red_episodes=eps_total,
                red_confirmed=hits_total, p_value=p, perm_mean_hits=float(perm_hits.mean()), by_case=caught,
                latest=a.sort_values("date").groupby("case").tail(1)[["case", "date", "ratio", "red"]]
                .assign(date=lambda x: x.date.dt.date.astype(str)).round(2).to_dict("records"))
    (C.TAB_DIR / "tripwire_summary.json").write_text(json.dumps(summ, indent=1, default=str))
    return summ


# ---------------------------------------------------------------------------
def completeness(e: pd.DataFrame, s: pd.DataFrame) -> pd.DataFrame:
    """Share of deaths whose last source report was published within k days of the event's end (2022-2025)."""
    last = s.groupby("event_id").published_date.max().rename("last_pub")
    x = e[(e.event_year >= 2022) & (e.event_year <= 2025)].merge(last, left_on="event_id", right_index=True)
    x["lag"] = (pd.to_datetime(x.last_pub) - pd.to_datetime(x.date_end)).dt.days.clip(lower=0)
    rows = []
    for case, g in x.groupby("conflict_case"):
        tot = g.deaths_best.sum()
        for k in (7, 30, 60, 90, 180, 365, 730):
            rows.append(dict(case=case, days=k, share_known=round(float(g.deaths_best[g.lag <= k].sum() / tot), 3)))
    out = pd.DataFrame(rows)
    out.to_csv(C.TAB_DIR / "completeness.csv", index=False)
    return out


# ---------------------------------------------------------------------------
D10 = C.ROOT / "data" / "raw" / "extra" / "6. war_terror_violence_200k.csv"


def india_front() -> dict:
    d = pd.read_csv(D10, usecols=["country", "adm_1", "date_start", "dyad_name", "side_a", "side_b",
                                  "deaths_best", "deaths_civilians", "violence_category"], parse_dates=["date_start"])
    ind = d[d.country == "India"].copy()
    jk = ind[ind.adm_1.fillna("").str.contains("Jammu|Kashmir", case=False)]
    state = d[d.dyad_name.fillna("").str.contains("Government of India - Government of Pakistan")]
    yearly = pd.DataFrame({
        "jk_deaths": jk.groupby(jk.date_start.dt.year).deaths_best.sum(),
        "india_all_deaths": ind.groupby(ind.date_start.dt.year).deaths_best.sum(),
        "ind_pak_state_deaths": state.groupby(state.date_start.dt.year).deaths_best.sum()}).fillna(0).astype(int)
    big = jk[jk.date_start >= "2014-01-01"].groupby(["date_start", "adm_1"]).agg(
        deaths=("deaths_best", "sum"), civilians=("deaths_civilians", "sum")).reset_index()
    big = big[big.deaths >= 15].sort_values("date_start")
    rows = []
    for _, r in big.iterrows():
        t0 = r.date_start
        before = state[(state.date_start < t0) & (state.date_start >= t0 - pd.Timedelta(days=45))].deaths_best.sum()
        after = state[(state.date_start > t0) & (state.date_start <= t0 + pd.Timedelta(days=45))]
        first = after.date_start.min()
        rows.append(dict(date=t0.date(), area=r.adm_1, deaths=int(r.deaths), civilians=int(r.civilians),
                         state_deaths_45d_before=int(before), state_deaths_45d_after=int(after.deaths_best.sum()),
                         days_to_state_fighting=(first - t0).days if pd.notna(first) else None))
    trig = pd.DataFrame(rows)
    trig.to_csv(C.TAB_DIR / "india_front.csv", index=False)
    yearly.to_csv(C.TAB_DIR / "india_front_yearly.csv")
    j = dict(records_india=int(len(ind)), note="D10 keeps the deadlier records outside the focus countries, so India figures are a floor.",
             triggers=trig.to_dict("records"), yearly_recent=yearly.loc[2014:].reset_index()
             .rename(columns={"date_start": "year"}).to_dict("records"))
    (C.TAB_DIR / "india_front.json").write_text(json.dumps(j, indent=1, default=str))
    return j


# ---------------------------------------------------------------------------
def seal() -> dict:
    fut = pd.read_parquet(C.PROCESSED / "forecast_future.parquet")
    live = pd.read_parquet(C.PROCESSED / "early_warning_live.parquet").head(20)
    claims = dict(forecast=fut.round(1).astype(str).to_dict("records"),
                  watchlist=live[["conflict_case", "admin1", "p_escalation"]].round(4).astype(str).to_dict("records"))
    blob = json.dumps(claims, sort_keys=True).encode()
    out = dict(sha256=hashlib.sha256(blob).hexdigest(), sealed_on=str(pd.Timestamp.now(tz="Asia/Kolkata").date()),
               how_to_check="Recompute sha256 of json.dumps(claims, sort_keys=True) and compare; score against UCDP when Oct-Dec 2026 is released.",
               claims=claims)
    (C.TAB_DIR / "sealed_predictions.json").write_text(json.dumps(out, indent=1))
    return out


def run(e: pd.DataFrame | None = None, s: pd.DataFrame | None = None) -> dict:
    e = pd.read_parquet(C.PROCESSED / "events.parquet") if e is None else e
    s = pd.read_parquet(C.PROCESSED / "sources.parquet") if s is None else s
    return dict(tripwire=tripwire(e), completeness=completeness(e, s), india=india_front(), sealed=seal())
