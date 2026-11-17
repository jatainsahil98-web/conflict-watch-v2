"""How strong is the evidence?  Uncertainty on the headline results.

Reads the frozen predictions written by models.run_all / early_warning_all and adds:
  * moving-block bootstrap intervals for the MAE reduction vs the naive rule (per conflict, pooled)
  * one-sided Diebold-Mariano tests (Harvey-Leybourne-Newbold small-sample correction)
  * 80% band coverage per conflict
  * the same gain across all five folds
  * a late-data test: forecast month t from data to t-2 with the same frozen method
  * area-resampled bootstrap intervals for the early-warning metrics, and a calibration table
  * the run ID: a hash of the result tables, printed on the report, the deck and the dashboard

Outputs: outputs/tables/robustness.json, outputs/tables/ew_calibration.csv, outputs/tables/run_id.txt
"""
from __future__ import annotations

import hashlib
import json

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.metrics import average_precision_score, roc_auc_score

from . import config as C
from . import models as M
from .features import make_supervised

B = 5000
BLOCK = 3
LEVEL = 0.90


def _lo_hi(x):
    a = (1 - LEVEL) / 2 * 100
    return [float(np.percentile(x, a)), float(np.percentile(x, 100 - a))]


def _block_idx(rng, n, block=None):
    block = block or BLOCK
    starts = rng.integers(0, n - block + 1, size=int(np.ceil(n / block)))
    return np.concatenate([np.arange(s, s + block) for s in starts])[:n]


def _pairs(preds: pd.DataFrame, folds, model="ensemble", base="naive", track="A"):
    p = preds[(preds.track == track) & preds.fold.isin(folds)]
    k = ["fold", "conflict_case", "target_month"]
    e = p[p.model == model].set_index(k)
    n = p[p.model == base].set_index(k).reindex(e.index)
    d = pd.DataFrame(dict(ae=(e.pred - e.actual).abs(), an=(n.pred - n.actual).abs(), actual=e.actual,
                          lo=e.get("pi80_lo"), hi=e.get("pi80_hi"))).reset_index()
    return d


def _reduction(d):
    return 1 - d.ae.sum() / d.an.sum()


def mae_bootstrap(d: pd.DataFrame, seed=C.RANDOM_STATE):
    """Resample blocks of months (all conflicts move together), within each fold."""
    rng = np.random.default_rng(seed)
    d = d.assign(period=d.fold.astype(str) + "|" + d.target_month.astype(str))
    periods = sorted(d.period.unique())
    by_p = {p: g for p, g in d.groupby("period")}
    out = np.empty(B)
    for b in range(B):
        idx = _block_idx(rng, len(periods))
        s = pd.concat([by_p[periods[i]] for i in idx])
        out[b] = _reduction(s)
    return out


def diebold_mariano(e1, e2, h=1):
    """H0: equal accuracy; H1: model 1 (e1) more accurate.  Loss = absolute error."""
    d = np.asarray(e2) - np.asarray(e1)
    n = len(d)
    if n < 3 or np.allclose(d, 0):
        return float("nan")
    dbar = d.mean()
    gam = [np.mean((d[k:] - dbar) * (d[:n - k] - dbar)) for k in range(h)]
    var = (gam[0] + 2 * sum(gam[1:])) / n
    if var <= 0:
        return float("nan")
    dm = dbar / np.sqrt(var)
    hln = np.sqrt((n + 1 - 2 * h + h * (h - 1) / n) / n)
    return float(1 - stats.t.cdf(dm * hln, df=n - 1))


# ---------------------------------------------------------------------------
# Late data: forecast t from data to t-2 (same frozen method as Track A)
# ---------------------------------------------------------------------------
def late_data(cm: pd.DataFrame, members, folds) -> pd.DataFrame:
    sup_c = M._prep_case(make_supervised(cm, ["conflict_case"], horizons=(2,)))
    full = M._prep_case(make_supervised(cm, ["conflict_case"], horizons=range(1, M.H_MAX + 1)))
    feats = M.CASE_FEATURES + ["case_cat"]
    rows = []
    for Y in folds:
        cutoff = pd.Timestamp(f"{Y - 1}-12-01")
        months = pd.date_range(f"{Y}-01-01", f"{Y}-09-01", freq="MS")
        tr = full[(full.target_month <= cutoff) & full.target_y.notna() & (full.month >= "2014-12-01")]
        m_case = M.fit_lgb(tr, feats, "delta", **M.LGB_CASE_PARAMS)
        f = sup_c[sup_c.target_month.isin(months)]
        lg = f.assign(pred=np.expm1(m_case.predict(f[feats])).clip(0))[["conflict_case", "target_month", "pred"]]
        for case in C.CASES:
            s = cm[cm.conflict_case == case].set_index("month").deaths.asfreq("MS")
            ylog = np.log1p(s)
            ets = M._fit_ets(ylog[:cutoff])
            for t in months:
                o = t - pd.DateOffset(months=2)
                ets_o = M._ets_filter(ets, ylog[:o])
                p = dict(naive=s[o], ma3=s[o - pd.DateOffset(months=2):o].mean(),
                         ets=float(np.expm1(ets_o.forecast(2).iloc[-1])),
                         lgb_case=float(lg[(lg.conflict_case == case) & (lg.target_month == t)].pred.iloc[0]))
                ens = float(np.expm1(np.mean([np.log1p(max(p[k], 0)) for k in members])))
                rows.append(dict(fold=Y, conflict_case=case, target_month=t, actual=s[t], ens=ens, naive=p["naive"]))
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Early warning: area-resampled intervals and calibration
# ---------------------------------------------------------------------------
def _p_at_10(te, col="p_lgb"):
    return te.groupby("target_month").apply(lambda g: g.nlargest(10, col).escalation.mean(),
                                            include_groups=False).mean()


def ew_bootstrap(te: pd.DataFrame, seed=C.RANDOM_STATE, n_boot=1000):
    rng = np.random.default_rng(seed)
    areas = te.admin1_key.unique()
    by_a = {a: g for a, g in te.groupby("admin1_key")}
    auc, pr, p10, lift = [], [], [], []
    for _ in range(n_boot):
        pick = rng.choice(areas, size=len(areas), replace=True)
        s = pd.concat([by_a[a] for a in pick])
        if s.escalation.nunique() < 2:
            continue
        auc.append(roc_auc_score(s.escalation, s.p_lgb))
        pr.append(average_precision_score(s.escalation, s.p_lgb))
        k = _p_at_10(s)
        p10.append(k)
        lift.append(k / s.escalation.mean())
    return dict(auc=_lo_hi(auc), pr_auc=_lo_hi(pr), p10=_lo_hi(p10), lift=_lo_hi(lift))


def calibration(te: pd.DataFrame) -> pd.DataFrame:
    b = pd.cut(te.p_lgb, [-0.001, 0.02, 0.05, 0.1, 0.15, 0.25, 1.0])
    t = te.groupby(b, observed=True).agg(areas=("p_lgb", "size"), mean_pred=("p_lgb", "mean"),
                                         escalated=("escalation", "mean")).reset_index()
    t["band"] = t.p_lgb.astype(str)
    return t[["band", "areas", "mean_pred", "escalated"]]


# ---------------------------------------------------------------------------
def run_id() -> str:
    """Hash of every result table (CSV) in outputs/tables, in name order."""
    h = hashlib.sha256()
    for f in sorted(C.TAB_DIR.glob("*.csv")):
        if f.name in ("ew_calibration.csv",):
            continue
        h.update(f.name.encode()); h.update(f.read_bytes())
    return "CW-" + h.hexdigest()[:8].upper()


def run(cm: pd.DataFrame | None = None, save: bool = True) -> dict:
    preds = pd.read_parquet(C.PROCESSED / "forecast_preds.parquet")
    te_all = pd.read_parquet(C.PROCESSED / "early_warning_preds.parquet")
    members = pd.read_csv(C.TAB_DIR / "ensemble_members.csv").member.tolist()
    if cm is None:
        cm = pd.read_parquet(C.PROCESSED / "case_month.parquet")
    folds_all = M.BACKTEST_YEARS + [M.HOLDOUT_YEAR]

    d26 = _pairs(preds, [M.HOLDOUT_YEAR])
    res = dict(level=LEVEL, n_boot=B, block_months=BLOCK, by_conflict={})
    for case, g in d26.groupby("conflict_case"):
        bs = mae_bootstrap(g)
        res["by_conflict"][case] = dict(
            mae_ens=float(g.ae.mean()), mae_naive=float(g.an.mean()), reduction=float(_reduction(g)),
            ci=_lo_hi(bs), p_positive=float((bs > 0).mean()),
            dm_p=diebold_mariano(g.ae.values, g.an.values),
            coverage80=float(((g.actual >= g.lo) & (g.actual <= g.hi)).mean()))
    bs = mae_bootstrap(d26)
    order = d26.sort_values(["target_month", "conflict_case"])
    res["pooled"] = dict(reduction=float(_reduction(d26)), ci=_lo_hi(bs), p_positive=float((bs > 0).mean()),
                         dm_p=diebold_mariano(order.ae.values / order.an.mean(), order.an.values / order.an.mean()),
                         coverage80=float(((d26.actual >= d26.lo) & (d26.actual <= d26.hi)).mean()))
    dall = _pairs(preds, folds_all)
    bsa = mae_bootstrap(dall)
    res["all_folds"] = dict(months=int(dall.groupby("fold").target_month.nunique().sum()),
                            reduction=float(_reduction(dall)), ci=_lo_hi(bsa))

    late = late_data(cm, members, folds_all)
    r = lambda x: float(1 - (x.ens - x.actual).abs().sum() / (x.naive - x.actual).abs().sum())
    res["late_data"] = dict(holdout=r(late[late.fold == M.HOLDOUT_YEAR]),
                            backtest=r(late[late.fold.isin(M.BACKTEST_YEARS)]))

    te = te_all[te_all.fold == M.HOLDOUT_YEAR]
    res["early_warning"] = ew_bootstrap(te)
    cal = calibration(te)
    hi = te[te.p_lgb >= 0.15]
    res["early_warning"]["top_band"] = dict(threshold=0.15, mean_pred=float(hi.p_lgb.mean()),
                                            escalated=float(hi.escalation.mean()), n=int(len(hi)))
    if save:
        cal.to_csv(C.TAB_DIR / "ew_calibration.csv", index=False)
        (C.TAB_DIR / "robustness.json").write_text(json.dumps(res, indent=2))
        rid = run_id()
        (C.TAB_DIR / "run_id.txt").write_text(rid + "\n")
        res["run_id"] = rid
    return res


if __name__ == "__main__":
    out = run()
    print(json.dumps(out, indent=2)[:3000])
