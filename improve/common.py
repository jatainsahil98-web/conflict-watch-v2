"""Shared data for the v3 improvement experiments (run locally; the issued data are not in the repo).

- World monthly series: every conflict in the world file 1989-2025 (final counts; no source dates exist for it).
- Four wars 2014-Sep 2026: as-known vintages from the event-source file (an event counts once its first report is out),
  so each forecast at the end of month t sees only what was known that day. Targets are final counts.
- Reporting completeness: at time t, how much of a month's final count is usually known at age 0/1/2 months, measured
  only on months that were already 12-36 months old at t (no look-ahead).
"""
from functools import lru_cache
import numpy as np, pandas as pd
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/extra/6. war_terror_violence_200k.csv"
PROC = ROOT / "data/processed"
CM = pd.period_range("2014-01", "2026-09", freq="M")
WM = pd.period_range("1989-01", "2025-12", freq="M")

@lru_cache(None)
def world():
    W = pd.read_csv(RAW, usecols=["date_start", "conflict_name", "country", "deaths_best", "latitude", "longitude"])
    W["m"] = pd.to_datetime(W["date_start"]).dt.to_period("M")
    return W

@lru_cache(None)
def world_series():
    W = world(); P = W.groupby(["conflict_name", "m"])["deaths_best"].sum().unstack(fill_value=0).reindex(columns=WM, fill_value=0)
    return P[P.sum(axis=1) >= 25]

@lru_cache(None)
def wars_final():
    C = pd.read_parquet(PROC / "case_month.parquet")[["conflict_case", "month", "deaths"]]
    C["m"] = pd.to_datetime(C["month"]).dt.to_period("M")
    return C.pivot_table(index="conflict_case", columns="m", values="deaths", aggfunc="sum").reindex(columns=CM, fill_value=0).fillna(0)

@lru_cache(None)
def vintages():
    EV = pd.read_parquet(PROC / "events.parquet")[["event_id", "conflict_case", "deaths_best"]]
    SR = pd.read_parquet(PROC / "sources.parquet")[["event_id", "published_date"]]
    FP = SR.groupby("event_id")["published_date"].min().rename("fp").reset_index()
    AL = pd.read_parquet(PROC / "alloc.parquet").merge(EV, on="event_id").merge(FP, on="event_id", how="left")
    AL["m"] = pd.to_datetime(AL["month"]).dt.to_period("M"); AL["fpm"] = pd.to_datetime(AL["fp"]).dt.to_period("M").fillna(AL["m"])
    AL["d"] = AL["deaths_best"] * AL["share"]
    out = {}
    for case, g in AL.groupby("conflict_case"):
        pm = np.array([CM.get_loc(x) if x in CM else -1 for x in g["m"]])
        pf = np.array([CM.get_loc(x) if x in CM else (len(CM) if x > CM[-1] else 0) for x in g["fpm"]])
        d = g["d"].to_numpy(); V = np.zeros((len(CM), len(CM)))
        for t in range(len(CM)):
            k = (pf <= t) & (pm >= 0) & (pm <= t)
            V[t] = np.bincount(pm[k], weights=d[k], minlength=len(CM))
        out[case] = V
    return out

def completeness(V, t):
    """Share of a month's count known at age 0, 1, 2 months, judged at time t from months aged 12-36 at t."""
    res = []
    for a in range(3):
        r = [V[m + a][m] / V[t][m] for m in range(max(0, t - 36), t - 11) if V[t][m] >= 10]
        res.append(float(np.clip(np.median(r), 0.05, 1.0)) if len(r) >= 6 else 1.0)
    return res

def _rows(s_by_t, n, idx, sid, war, final):
    l_final = np.log1p(np.clip(final, 0, None)); rows = []
    for t in range(12, n - 1):
        s, comp = s_by_t(t)
        lk = np.log1p(np.clip(s, 0, None)); lags = lk[t - 11:t + 1][::-1]
        adj = np.array([np.log1p(max(s[t - a], 0) / comp[a]) for a in range(3)])
        m3, m6, m12 = lk[t - 2:t + 1].mean(), lk[t - 5:t + 1].mean(), lk[t - 11:t + 1].mean()
        nz = np.nonzero(s[:t + 1])[0]; since = t - nz[-1] if len(nz) else 99
        rows.append(dict(sid=sid, war=war, t=idx[t], tgt_m=idx[t + 1], y=l_final[t + 1], base=m3, base_adj=adj.mean(),
                         **{f"lag{k}": lags[k] for k in range(12)}, m3=m3, m6=m6, m12=m12, mx12=lags.max(), sd12=lags.std(),
                         since=min(since, 99), mom=lags[0] - m3, acc=lags[0] - lags[1], peak=lags[0] - lags.max(),
                         nz12=(lags > 0).sum(), moy=idx[t + 1].month,
                         comp0=comp[0], comp1=comp[1], comp2=comp[2], adj0=adj[0], adj1=adj[1], adj2=adj[2], adjm=adj.mean() - m3))
    return rows

@lru_cache(None)
def monthly_frame():
    import os
    cache = os.environ.get("CW_FRAME_CACHE")            # optional: path to a pickled frame from an earlier run
    if cache and os.path.exists(cache): return pd.read_pickle(cache)
    R = []
    for name, row in world_series().iterrows():
        s = row.to_numpy(float); R += _rows(lambda t, s=s: (s[:t + 1], [1.0, 1.0, 1.0]), len(s), WM, name, 0, s)
    V = vintages(); F = wars_final()
    for name, row in F.iterrows():
        fin = row.to_numpy(float); Vw = V[name]
        R += _rows(lambda t, Vw=Vw: (Vw[t][:t + 1], completeness(Vw, t)), len(fin), CM, name, 1, fin)
    D = pd.DataFrame(R)
    D = D[(D["war"] == 1) | (D["mx12"] > 0) | (D["y"] > 0)].reset_index(drop=True)
    D["dy"] = D["y"] - D["base"]; D["dy_adj"] = D["y"] - D["base_adj"]
    return D

BASE_FE = [f"lag{k}" for k in range(12)] + ["m3", "m6", "m12", "mx12", "sd12", "since", "mom", "acc", "peak", "nz12", "moy"]
COMP_FE = ["comp0", "comp1", "comp2", "adj0", "adj1", "adj2", "adjm"]

def split(D, year=None, test=False):
    """Validation fold: train on targets up to Sep of the year before (3-month embargo), score the 4 wars in `year`.
    Test: train on targets up to Sep 2025, score Jan-Sep 2026 (walk-forward with as-known features, no refit)."""
    emb = pd.Period("2025-09" if test else f"{year - 1}-09", "M")
    tr = D[D["tgt_m"] <= emb]
    te = D[(D["war"] == 1) & ((D["tgt_m"] >= pd.Period("2026-01", "M")) & (D["tgt_m"] <= pd.Period("2026-09", "M")) if test else (D["tgt_m"].dt.year == year))]
    return tr, te

rmsle = lambda p, y: float(np.sqrt(np.mean((np.clip(p, 0, None) - y) ** 2)))
