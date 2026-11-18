"""Step 4: calibrated country watch-list with neighbour spill-over and two alert tiers.
Escalation (as in the deck): next month's deaths >= 1.5x the last-3-month mean and >= 10. 117 countries, world file.
Validation 2022-2024 (yearly refits, 3-month embargo) is where the calibrator and the ACT threshold are fitted;
test = all of 2025, model frozen at Sep-2024 targets, opened once.
"""
import sys, json, time, warnings
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
import common as c
import lightgbm as lgb
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import average_precision_score, roc_auc_score, brier_score_loss
OUT = c.ROOT / "outputs/v3"

def frame():
    W = c.world(); W = W[(W["m"] >= c.WM[0]) & (W["m"] <= c.WM[-1])]
    dm = W.groupby(["country", "m"])["deaths_best"].sum().unstack(fill_value=0).reindex(columns=c.WM, fill_value=0)
    ev = W.groupby(["country", "m"]).size().unstack(fill_value=0).reindex(index=dm.index, columns=c.WM, fill_value=0)
    cen = W.groupby("country")[["latitude", "longitude"]].median()
    lat, lon = np.radians(cen["latitude"].to_numpy()), np.radians(cen["longitude"].to_numpy())
    dist = 6371 * np.arccos(np.clip(np.sin(lat)[:, None] * np.sin(lat) + np.cos(lat)[:, None] * np.cos(lat) * np.cos(lon[:, None] - lon), -1, 1))
    NB = (dist < 1500) & (dist > 0)                                   # neighbours: centroids within 1,500 km
    X = dm.to_numpy(float); E = ev.to_numpy(float); L = np.log1p(X); n, T = X.shape
    cs = np.concatenate([np.zeros((n, 1)), np.cumsum(X, 1)], 1)
    mean3 = lambda t: (cs[:, t + 1] - cs[:, t - 2]) / 3
    esc = np.zeros((n, T), bool)
    for t in range(3, T - 1): esc[:, t + 1] = (X[:, t + 1] >= 1.5 * mean3(t)) & (X[:, t + 1] >= 10)
    rows = []
    for t in range(24, T - 1):
        m3 = mean3(t); lg = L[:, t - 11:t + 1][:, ::-1]
        nb_d1 = np.log1p(NB @ X[:, t]); nb_d3 = np.log1p(NB @ (cs[:, t + 1] - cs[:, t - 2]))
        nb_esc = NB @ esc[:, t].astype(float); nb_esc3 = NB @ esc[:, t - 2:t + 1].sum(1)
        nb_trend = np.log1p(NB @ X[:, t]) - np.log1p(NB @ (cs[:, t + 1] - cs[:, t - 11]) / 12)
        nz = np.array([t - np.nonzero(X[i, :t + 1])[0][-1] if X[i, :t + 1].any() else 99 for i in range(n)])
        d = pd.DataFrame({f"lag{k}": lg[:, k] for k in range(12)})
        d = d.assign(country=dm.index, t=c.WM[t], tgt=c.WM[t + 1], y=esc[:, t + 1].astype(int),
                     m3=np.log1p(m3), m12=L[:, t - 11:t + 1].mean(1), mx12=lg.max(1), sd12=lg.std(1), mom=lg[:, 0] - np.log1p(m3),
                     since=np.minimum(nz, 99), ev1=np.log1p(E[:, t]), ev3=np.log1p(E[:, t - 2:t + 1].sum(1)), esc_last=esc[:, t].astype(int),
                     esc12=esc[:, t - 11:t + 1].sum(1), moy=c.WM[t + 1].month,
                     nb_d1=nb_d1, nb_d3=nb_d3, nb_esc=nb_esc, nb_esc3=nb_esc3, nb_trend=nb_trend, nb_n=NB.sum(1))
        rows.append(d)
    return pd.concat(rows, ignore_index=True)

BASE = [f"lag{k}" for k in range(12)] + ["m3", "m12", "mx12", "sd12", "mom", "since", "ev1", "ev3", "esc_last", "esc12", "moy"]
NBF = ["nb_d1", "nb_d3", "nb_esc", "nb_esc3", "nb_trend", "nb_n"]
def fit_pred(tr, te, FE):
    m = lgb.LGBMClassifier(n_estimators=500, num_leaves=15, learning_rate=0.03, min_child_samples=50, subsample=0.8, subsample_freq=1, colsample_bytree=0.8, verbose=-1, random_state=0)
    m.fit(tr[FE], tr["y"]); return m.predict_proba(te[FE])[:, 1]
def split(D, year):
    tr = D[D["tgt"] <= pd.Period(f"{year - 1}-09", "M")]; te = D[D["tgt"].dt.year == year]; return tr, te
def ece(p, y, b=10):
    q = np.clip((p * b).astype(int), 0, b - 1); return float(sum(abs(p[q == i].mean() - y[q == i].mean()) * (q == i).mean() for i in range(b) if (q == i).any()))
def metrics(p, y, watch, act):
    def at(th): k = p >= th; return dict(flagged_per_month=round(k.sum() / 12, 1), recall=round(float(y[k].sum() / y.sum()), 3), precision=round(float(y[k].mean()) if k.any() else 0, 3))
    return dict(pr_auc=round(average_precision_score(y, p), 3), roc_auc=round(roc_auc_score(y, p), 3), brier=round(brier_score_loss(y, p), 4),
                ece=round(ece(p, y), 4), base_rate=round(float(y.mean()), 4), watch=at(watch), act=at(act))

if __name__ == "__main__":
    t0 = time.time(); import os
    D = frame(); print("rows", len(D), f"{time.time() - t0:.0f}s", file=sys.stderr)
    res = {}
    for name, FE in {"v2 baseline (own history)": BASE, "v3 (+ neighbour spill-over)": BASE + NBF}.items():
        V = [(fit_pred(*split(D, y), FE), split(D, y)[1]["y"].to_numpy()) for y in (2022, 2023, 2024)]
        pv = np.concatenate([v[0] for v in V]); yv = np.concatenate([v[1] for v in V])
        iso = IsotonicRegression(out_of_bounds="clip", y_min=0, y_max=1).fit(pv, yv)
        # thresholds fitted on validation: WATCH = recall >= 75% (raw score); ACT = calibrated precision >= 40%
        ths = np.unique(np.quantile(pv, np.linspace(0.5, 0.999, 400)))
        watch_raw = max([th for th in ths if (yv[pv >= th].sum() / yv.sum()) >= 0.75] or [0.13])
        cal_v = iso.predict(pv); cths = np.unique(cal_v)
        act = min([th for th in cths if (cal_v >= th).sum() >= 20 and yv[cal_v >= th].mean() >= 0.40] or [0.5])
        tr, te = split(D, 2025); pt = fit_pred(tr, te, FE); yt = te["y"].to_numpy(); ct = iso.predict(pt)
        res[name] = {"validation_raw": metrics(pv, yv, watch_raw, 1.1), "test_raw": metrics(pt, yt, watch_raw, 1.1),
                     "test_calibrated": metrics(ct, yt, float(iso.predict([watch_raw])[0]), act), "watch_threshold_raw": float(watch_raw), "act_threshold_calibrated": float(act)}
        if "v3" in name:
            out = te[["country", "tgt", "y"]].assign(p_raw=pt, p_cal=ct); out["tgt"] = out["tgt"].astype(str); out.to_csv(OUT / "watchlist_test2025.csv", index=False)
            bins = pd.cut(ct, [0, .05, .1, .2, .3, .5, 1.0], include_lowest=True)
            rel = pd.DataFrame({"pred": ct, "obs": yt}).groupby(bins, observed=False).agg(n=("obs", "size"), predicted=("pred", "mean"), observed=("obs", "mean")).round(3).reset_index()
            rel.columns = ["bin", "n", "predicted", "observed"]; rel["bin"] = rel["bin"].astype(str); res["reliability_test_v3"] = rel.to_dict("records")
        print(name, json.dumps(res[name]["test_calibrated"]), file=sys.stderr)
    (OUT / "watchlist_results.json").write_text(json.dumps(res, indent=1, default=str))
