"""Escalation-warning variants (transfer learning study). Usage:
    python scripts/ew_variants.py 2023,2024,2025   # back-test: used to choose (see preregistration.json)
    python scripts/ew_variants.py 2026             # holdout: run once, after the choice was written
Writes outputs/tables/ew_variants_<years>.json
"""
import sys, json, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np, pandas as pd, lightgbm as lgb
from sklearn.metrics import roc_auc_score, average_precision_score
from src import config as C, models as M
from src.global_ew import build_global_admin1
am = pd.read_parquet(C.PROCESSED / "admin1_month.parquet")
g = build_global_admin1()
f = M.escalation_frame(pd.concat([am, g], ignore_index=True)); f = f[f.escalation.notna()]
case = f.conflict_case.isin(C.CASES)
print("rows case", case.sum(), "global", (~case).sum(), "global escal rate", f[~case].escalation.mean().round(3), "case", f[case].escalation.mean().round(3))
def run(years, variant):
    res = []
    for Y in years:
        cut = pd.Timestamp(f"{Y-1}-12-01")
        tr = f[f.target_month <= cut]
        if variant["global"] is False: tr = tr[tr.conflict_case.isin(C.CASES)]
        elif variant.get("since"): tr = tr[tr.conflict_case.isin(C.CASES) | (tr.target_month >= variant["since"])]
        w = np.where(tr.conflict_case.isin(C.CASES), variant.get("w", 1.0), 1.0)
        te = f[case & (f.target_month > cut) & (f.target_month < f"{Y+1}-01-01")]
        clf = lgb.LGBMClassifier(**{**M.LGB_PARAMS, **M.EW_PARAMS, **variant.get("params", {})}).fit(tr[M.EW_FEATURES], tr.escalation.astype(int), sample_weight=w)
        p = clf.predict_proba(te[M.EW_FEATURES])[:, 1]; t = te.assign(p=p)
        p10 = t.groupby("target_month").apply(lambda d: d.nlargest(10, "p").escalation.mean()).mean()
        res.append(dict(year=Y, auc=roc_auc_score(te.escalation, p), pr=average_precision_score(te.escalation, p), p10=p10))
    return pd.DataFrame(res)
V = {"A cases_only": {"global": False},
     "B global all": {"global": True},
     "C global since 2005": {"global": True, "since": pd.Timestamp("2005-01-01")},
     "D global, case weight 5": {"global": True, "w": 5.0},
     "E global, more trees": {"global": True, "params": dict(n_estimators=400, num_leaves=15, min_child_samples=200)},
     "F global, more trees, case w5": {"global": True, "w": 5.0, "params": dict(n_estimators=400, num_leaves=15, min_child_samples=200)},
     "G cases_only, more trees": {"global": False, "params": dict(n_estimators=400, num_leaves=15, min_child_samples=200)}}
years = tuple(int(y) for y in sys.argv[1].split(","))
out = {}
for k, v in V.items():
    r = run(years, v); out[k] = r.round(4).to_dict("records")
    print(f"{k:28s} AUC {r.auc.mean():.3f}  PR {r.pr.mean():.3f}  P@10 {r.p10.mean():.3f}   per-year PR {list(r.pr.round(3))}")
json.dump(out, open(C.TAB_DIR / f"ew_variants_{sys.argv[1].replace(',', '_')}.json", "w"), indent=1)
