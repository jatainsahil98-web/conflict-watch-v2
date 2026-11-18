"""Step 2: better monthly forecast. Pre-register -> validate (2023-25) -> choose by rule -> freeze -> open 2026 test once.
Run: python improve/monthly.py validate   then   python improve/monthly.py test
"""
import sys, json, hashlib, time, warnings
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
import common as c
OUT = c.ROOT / "outputs/v3"; OUT.mkdir(parents=True, exist_ok=True)
import lightgbm as lgb, xgboost as xgb
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.linear_model import Ridge

def wts(tr): return np.where(tr["war"] == 1, 5.0, 1.0)
def LGB(obj, target="dy", fe="base"):
    def f(tr, te, FE):
        m = lgb.LGBMRegressor(objective=obj, n_estimators=600, num_leaves=15, learning_rate=0.03, min_child_samples=40, subsample=0.8, subsample_freq=1, colsample_bytree=0.8, verbose=-1, random_state=0)
        if target == "y": m.fit(tr[FE], tr["y"], sample_weight=wts(tr)); return m.predict(te[FE])
        b = "base" if target == "dy" else "base_adj"; m.fit(tr[FE], tr[target], sample_weight=wts(tr)); return te[b].to_numpy() + m.predict(te[FE])
    return f
def XGB(tr, te, FE):
    m = xgb.XGBRegressor(n_estimators=600, max_depth=4, learning_rate=0.03, subsample=0.8, colsample_bytree=0.8, objective="reg:pseudohubererror", n_jobs=2, random_state=0)
    m.fit(tr[FE], tr["dy"], sample_weight=wts(tr)); return te["base"].to_numpy() + m.predict(te[FE])
def ET(tr, te, FE):
    m = ExtraTreesRegressor(300, min_samples_leaf=20, max_features=0.6, n_jobs=2, random_state=0)
    m.fit(tr[FE], tr["dy"], sample_weight=wts(tr)); return te["base"].to_numpy() + m.predict(te[FE])
def RID(tr, te, FE):
    m = Ridge(alpha=3.0); m.fit(tr[FE], tr["dy"], sample_weight=wts(tr)); return te["base"].to_numpy() + m.predict(te[FE])

SINGLE = {"lgb_l1": LGB("l1"), "lgb_huber": LGB("huber"), "lgb_level": LGB("l1", "y"), "lgb_huber_nowcast": LGB("huber", "dy_adj"),
          "xgb": XGB, "extratrees": ET, "ridge": RID}
FEATSETS = {"base": c.BASE_FE, "comp": c.BASE_FE + c.COMP_FE}
ENSEMBLES = {"tree4": ["lgb_huber", "lgb_level", "xgb", "extratrees"], "tree4+ridge": ["lgb_huber", "lgb_level", "xgb", "extratrees", "ridge"],
             "tree3_nowcast": ["lgb_huber_nowcast", "lgb_level", "extratrees"]}
PREREG = {
    "written": "before any v3 score was seen",
    "target": "log1p(final deaths next month), four wars, one month ahead, features as known on the day",
    "validation": "refit once per year 2023, 2024, 2025 with 3-month embargo; pooled RMSLE over 36 war-months",
    "test": "frozen at Sep-2025 targets, Jan-Sep 2026 walk-forward, opened once",
    "baseline": "lgb_l1 with base features (the v2 recipe)",
    "candidates": [f"{m}|{f}" for f in FEATSETS for m in list(SINGLE) + list(ENSEMBLES)],
    "rule": "choose the candidate with the lowest pooled validation RMSLE among those that (a) beat the baseline by >= 3% "
            "and (b) are not worse than the baseline by more than 10% on any single war's validation RMSLE; "
            "if none qualifies, keep the baseline. Ensembles are equal-weight means (no weights fitted on validation).",
}

def run(key):
    D = c.monthly_frame(); tr, te = c.split(D, *( (None, True) if key == "test" else (key,) ))
    out = {}
    for fs, FE in FEATSETS.items():
        for m, f in SINGLE.items():
            t0 = time.time(); out[f"{m}|{fs}"] = np.clip(f(tr, te, FE), 0, None); print(key, m, fs, f"{time.time() - t0:.0f}s", file=sys.stderr)
        for e, mem in ENSEMBLES.items(): out[f"{e}|{fs}"] = np.mean([out[f"{x}|{fs}"] for x in mem], axis=0)
    return out, te[["sid", "tgt_m", "y", "base"]].reset_index(drop=True)

def score(P, T):
    y = T["y"].to_numpy(); res = {}
    for k, p in P.items():
        res[k] = {"pooled": c.rmsle(p, y), **{w: c.rmsle(p[T["sid"] == w], y[T["sid"] == w]) for w in sorted(T["sid"].unique())}}
    res["rule_3m"] = {"pooled": c.rmsle(T["base"].to_numpy(), y), **{w: c.rmsle(T["base"][T["sid"] == w].to_numpy(), y[T["sid"] == w]) for w in sorted(T["sid"].unique())}}
    return res

if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "validate":
        pr = json.dumps(PREREG, indent=1, sort_keys=True); h = hashlib.sha256(pr.encode()).hexdigest()
        (OUT / "prereg_monthly.json").write_text(pr); (OUT / "prereg_monthly.sha256").write_text(h + "\n"); print("prereg", h)
        Ps, Ts = [], []
        for y in (2023, 2024, 2025): P, T = run(y); Ps.append(P); Ts.append(T)
        P = {k: np.concatenate([p[k] for p in Ps]) for k in Ps[0]}; T = pd.concat(Ts, ignore_index=True)
        S = score(P, T); base = S["lgb_l1|base"]; ok = []
        for k, s in S.items():
            if k in ("lgb_l1|base", "rule_3m"): continue
            better = s["pooled"] <= base["pooled"] * 0.97
            robust = all(s[w] <= base[w] * 1.10 for w in base if w != "pooled")
            if better and robust: ok.append((s["pooled"], k))
        choice = min(ok)[1] if ok else "lgb_l1|base"
        frz = {"prereg_sha256": h, "choice": choice, "validation": S, "qualified": sorted(ok)}
        fz = json.dumps(frz, indent=1, sort_keys=True, default=float); (OUT / "freeze_monthly.json").write_text(fz)
        (OUT / "freeze_monthly.sha256").write_text(hashlib.sha256(fz.encode()).hexdigest() + "\n")
        print("CHOICE", choice); [print(f"{k:34s} {v['pooled']:.3f}") for k, v in sorted(S.items(), key=lambda x: x[1]["pooled"])]
    elif mode == "test":
        flag = OUT / "test_opened_monthly.flag"
        if flag.exists(): sys.exit("test already opened once: refusing to run again")
        frz = json.loads((OUT / "freeze_monthly.json").read_text())
        assert hashlib.sha256((OUT / "freeze_monthly.json").read_text().encode()).hexdigest() == (OUT / "freeze_monthly.sha256").read_text().strip()
        flag.write_text(time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
        P, T = run("test"); S = score(P, T)
        (OUT / "test_monthly.json").write_text(json.dumps({"choice": frz["choice"], "test": S}, indent=1, default=float))
        T.assign(pred_choice=P[frz["choice"]], pred_baseline=P["lgb_l1|base"]).to_csv(OUT / "test_monthly_preds.csv", index=False)
        ch, b = S[frz["choice"]], S["lgb_l1|base"]
        print("CHOICE", frz["choice"], f"test {ch['pooled']:.3f} vs baseline {b['pooled']:.3f} ({100 * (ch['pooled'] / b['pooled'] - 1):+.1f}%) vs 3m rule {S['rule_3m']['pooled']:.3f}")
        for w in [k for k in ch if k != "pooled"]: print(f"  {w:22s} choice {ch[w]:.3f}  baseline {b[w]:.3f}  rule {S['rule_3m'][w]:.3f}")
