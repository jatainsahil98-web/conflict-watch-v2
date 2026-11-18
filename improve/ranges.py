"""Step 3: sharper, honest 80% ranges. Point model = the Step-2 choice (LightGBM Huber, nowcast target, completeness features).
A  (v2 method)  one global width: 80th percentile of |validation error| around the point forecast.
B  per-band width: the same, but separately for 4 intensity bands of the recent as-known level.
C  conformalised quantile regression (CQR): quantile LightGBM at 10% / 90%, widened by the validation
   non-conformity score per intensity band so each band holds ~80%.
Validation 2023-25 sets every width; test Jan-Sep 2026 is scored once.
"""
import sys, json, warnings
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
import common as c
import lightgbm as lgb
OUT = c.ROOT / "outputs/v3"
FE = c.BASE_FE + c.COMP_FE
W = lambda tr: np.where(tr["war"] == 1, 5.0, 1.0)
def lg(obj, **kw): return lgb.LGBMRegressor(objective=obj, n_estimators=600, num_leaves=15, learning_rate=0.03, min_child_samples=40, subsample=0.8, subsample_freq=1, colsample_bytree=0.8, verbose=-1, random_state=0, **kw)
def preds(tr, te):
    b = te["base_adj"].to_numpy()
    pt = b + lg("huber").fit(tr[FE], tr["dy_adj"], sample_weight=W(tr)).predict(te[FE])
    lo = b + lg("quantile", alpha=0.1).fit(tr[FE], tr["dy_adj"], sample_weight=W(tr)).predict(te[FE])
    hi = b + lg("quantile", alpha=0.9).fit(tr[FE], tr["dy_adj"], sample_weight=W(tr)).predict(te[FE])
    return np.clip(pt, 0, None), np.minimum(lo, hi), np.maximum(lo, hi)
band = lambda d: np.digitize(d["base_adj"].to_numpy(), np.log1p([10, 100, 1000]))
D = c.monthly_frame()
V = [(*preds(*c.split(D, y)), c.split(D, y)[1]) for y in (2023, 2024, 2025)]
pv, lv, hv = (np.concatenate([v[i] for v in V]) for i in range(3)); Tv = pd.concat([v[3] for v in V]); yv = Tv["y"].to_numpy(); bv = band(Tv)
tr, Tt = c.split(D, test=True); pt, lt, ht = preds(tr, Tt); yt = Tt["y"].to_numpy(); bt = band(Tt)
q80 = lambda r: float(np.quantile(r, 0.8 * (1 + 1 / len(r)))) if len(r) else np.nan
# A global
wA = q80(np.abs(yv - pv)); A = (np.clip(pt - wA, 0, None), pt + wA)
# B per band (fallback to global if < 12 points)
wB = {b: (q80(np.abs(yv - pv)[bv == b]) if (bv == b).sum() >= 12 else wA) for b in range(4)}
B = (np.clip(pt - np.array([wB[b] for b in bt]), 0, None), pt + np.array([wB[b] for b in bt]))
# C CQR per band
sv = np.maximum(lv - yv, yv - hv)
qC = {b: (q80(sv[bv == b]) if (bv == b).sum() >= 12 else q80(sv)) for b in range(4)}
C = (np.clip(lt - np.array([qC[b] for b in bt]), 0, None), ht + np.array([qC[b] for b in bt]))
def sc(L, H):
    inside = (yt >= L) & (yt <= H); w = H - L
    return dict(coverage=round(float(inside.mean()), 3), mean_width_log=round(float(w.mean()), 3), width_factor=round(float(np.exp(w.mean() / 2)), 2),
                per_war={s: dict(coverage=round(float(inside[Tt["sid"].to_numpy() == s].mean()), 2), width_log=round(float(w[Tt["sid"].to_numpy() == s].mean()), 2)) for s in sorted(Tt["sid"].unique())})
res = {"A_global_v2": sc(*A), "B_per_band": sc(*B), "C_cqr_per_band": sc(*C), "widths": {"A": wA, "B": wB, "C": qC}}
(OUT / "ranges_results.json").write_text(json.dumps(res, indent=1, default=float))
for k in ("A_global_v2", "B_per_band", "C_cqr_per_band"): print(k, res[k]["coverage"], res[k]["mean_width_log"], "±x", res[k]["width_factor"], res[k]["per_war"])
