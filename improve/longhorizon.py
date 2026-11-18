"""Step 6: a real long-horizon model for the 2027 outlook, against the analogue table used on the site.
Rows: every active conflict-month in the world file. Features from the conflict's own history to month t.
Targets: deaths in months t+4..t+15 (the 'calendar 2027' window seen from September) and each quarter of it,
as log1p(total) - log1p(12 x recent 6-month level). Quantile LightGBM at 10/50/90%.
Back-test: fit on t <= 2009, score t in 2010-2024 (targets end by Dec 2025). Metric: pinball loss and 80% coverage.
"""
import sys, json, warnings
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
import common as c
import lightgbm as lgb
OUT = c.ROOT / "outputs/v3"
QS = (0.1, 0.5, 0.9)
WINS = {"Y": (4, 16), "Q1": (4, 7), "Q2": (7, 10), "Q3": (10, 13), "Q4": (13, 16)}

def feats_one(s, t):
    l = np.log1p(np.clip(s, 0, None)); lg = l[t - 11:t + 1][::-1]; r6 = s[t - 5:t + 1].mean()
    nz = np.nonzero(s[:t + 1])[0]
    d = {f"lag{k}": lg[k] for k in range(12)}
    d.update(r6=np.log1p(r6), m3=l[t - 2:t + 1].mean(), m12=l[t - 11:t + 1].mean(), mx12=lg.max(), sd12=lg.std(), mom=lg[0] - l[t - 2:t + 1].mean(),
             since=min(t - nz[-1], 99) if len(nz) else 99, nz12=(lg > 0).sum(), age=min(t - nz[0], 400) if len(nz) else 0,
             mx_all=np.log1p(s[:t + 1].max()), l24=l[max(0, t - 23):t + 1].mean(), moy=(t % 12) + 1)
    return d, r6

def build():
    P = c.world_series(); rows = []
    for name, row in P.iterrows():
        s = row.to_numpy(float); cs = np.concatenate([[0], np.cumsum(s)])
        for t in range(24, len(s) - 15):
            if s[t - 5:t + 1].sum() <= 0: continue
            d, r6 = feats_one(s, t)
            for k, (a, b) in WINS.items():
                tot = cs[t + b] - cs[t + a]; months = b - a
                d[f"y_{k}"] = np.log1p(tot) - np.log1p(months * r6)
            rows.append(dict(cid=name, t=c.WM[t], r6raw=r6, **d))
    return pd.DataFrame(rows)

FE = [f"lag{k}" for k in range(12)] + ["r6", "m3", "m12", "mx12", "sd12", "mom", "since", "nz12", "age", "mx_all", "l24", "moy"]
def qmodel(tr, target, q):
    m = lgb.LGBMRegressor(objective="quantile", alpha=q, n_estimators=500, num_leaves=15, learning_rate=0.03, min_child_samples=80, subsample=0.8, subsample_freq=1, colsample_bytree=0.8, verbose=-1, random_state=0)
    return m.fit(tr[FE], tr[target])
pinball = lambda y, p, q: float(np.mean(np.maximum(q * (y - p), (q - 1) * (y - p))))

def analogue_quantiles(tr, te, target):
    """The site's current method: same level band x momentum class, empirical quantiles of the ratio."""
    def keys(d):
        lv = pd.cut(np.expm1(d["r6"]), [1, 10, 100, 1000, np.inf], right=False, labels=False).fillna(0)
        mo = np.select([d["m3"] - d["m12"] >= np.log(1.25), d["m3"] - d["m12"] <= np.log(0.8)], [2, 0], 1)
        return lv.astype(int) * 3 + mo
    ktr, kte = keys(tr), keys(te); out = np.zeros((len(te), 3))
    for k in np.unique(kte):
        ys = tr.loc[ktr == k, target]; ys = ys if len(ys) >= 30 else tr[target]
        out[kte == k] = np.quantile(ys, QS)
    return out

if __name__ == "__main__":
    D = build(); print("rows", len(D), file=sys.stderr)
    tr = D[D["t"] <= pd.Period("2008-09", "M")]; te = D[(D["t"] >= pd.Period("2010-01", "M"))]
    res = {}
    for k in WINS:
        tg = f"y_{k}"; y = te[tg].to_numpy()
        Q = np.column_stack([qmodel(tr, tg, q).predict(te[FE]) for q in QS]); Q = np.sort(Q, axis=1)
        A = analogue_quantiles(tr, te, tg)
        def sc(M): return dict(pinball=round(np.mean([pinball(y, M[:, i], q) for i, q in enumerate(QS)]), 4), coverage80=round(float(np.mean((y >= M[:, 0]) & (y <= M[:, 2]))), 3),
                               median_abs_err=round(float(np.median(np.abs(y - M[:, 1]))), 3), width80=round(float(np.mean(M[:, 2] - M[:, 0])), 3))
        res[k] = {"quantile_lgbm": sc(Q), "analogue_table": sc(A), "n_test": int(len(te))}
        print(k, res[k], file=sys.stderr)
    (OUT / "longhorizon_backtest.json").write_text(json.dumps(res, indent=1))
