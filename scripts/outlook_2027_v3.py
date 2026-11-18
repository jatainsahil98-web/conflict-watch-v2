"""2027 outlook, v3: quantile LightGBM trained on 12-15-month-ahead outcomes of every conflict in the world file
(improve/longhorizon.py, back-tested 2010-2024), replacing the analogue table. Writes web/public/data/outlook2027.json.
Features for the four wars come from their issued monthly series to Sep 2026 (already including late reports)."""
import sys, json
import numpy as np, pandas as pd
from math import erf, sqrt, log
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "improve"))
import common as c, longhorizon as lh
D = lh.build()
BT = json.loads((ROOT / "outputs/v3/longhorizon_backtest.json").read_text())
F = c.wars_final(); V = c.vintages(); t = len(c.CM) - 1
facts = json.loads((ROOT / "web/public/data/facts.json").read_text()); sc = {s["name"]: s for s in facts["scorecard"]}
SEAS = pd.read_csv(ROOT / "outputs/tables/insight_seasonality.csv")
def season(case, k):
    if k == "Y": return 1.0
    j = int(k[1]); SE = SEAS[SEAS["conflict_case"] == case].set_index("moy")["index_pct"] / 100
    return min(1.2, max(0.8, 1 + float(SE.reindex([3 * j - 2, 3 * j - 1, 3 * j]).fillna(0).mean()))) if len(SE) else 1.0
models = {k: [lh.qmodel(D, f"y_{k}", q) for q in lh.QS] for k in lh.WINS}
Phi = lambda z: 0.5 * (1 + erf(z / sqrt(2)))
out = {}
for case, row in F.iterrows():
    # The issued monthly counts already include reports published after Sep 2026 (the file was compiled later), so they
    # are used as they are: dividing them again by the month-end completeness would double-count late reports.
    s = row.to_numpy(float).copy(); comp = c.completeness(V[case], t)
    d, r6 = lh.feats_one(s, t); X = pd.DataFrame([d])[lh.FE]
    res = {}
    for k, (a, b) in lh.WINS.items():
        q = np.sort([m.predict(X)[0] for m in models[k]]); n = b - a
        tot = lambda z: max(0.0, float(np.expm1(z + np.log1p(n * r6))))
        sf = season(case, k); p10, p50, p90 = tot(q[0]) * sf, tot(q[1]) * sf, tot(q[2]) * sf
        sd = max((q[2] - q[0]) / 2.563, 1e-3)                       # spread of log ratio, from the 10-90% quantiles
        thr_up = np.log1p(1.5 * n * r6) - np.log1p(n * r6); thr_dn = np.log1p(0.5 * n * r6) - np.log1p(n * r6)
        p_up = 1 - Phi((thr_up - q[1]) / sd); p_dn = Phi((thr_dn - q[1]) / sd)
        mp = p50 / n; lv = "RED" if mp >= 1000 else "AMBER" if mp >= 100 else "GREEN"
        if lv == "GREEN" and p_up >= 0.30: lv = "AMBER"
        res[k] = dict(season_factor=round(sf, 3), p10=int(round(p10)), p50=int(round(p50)), p90=int(round(p90)), month_p50=int(round(mp)), p_up=round(p_up, 2), p_down=round(p_dn, 2), level=lv)
    g = row.to_numpy(float); Y = res.pop("Y")
    out[case] = dict(recent_month=round(float(r6)), last12=int(round(g[-12:].sum())), cal2025=int(round(g[-21:-9].sum())), ytd2026=int(round(g[-9:].sum())),
                     y2027={k: Y[k] for k in ("p10", "p50", "p90")}, month2027_p50=Y["month_p50"],
                     p_up=Y["p_up"], p_down=Y["p_down"], p_quiet=None, level2027=Y["level"], quarters=res,
                     rating_now=sc.get(case, {}).get("rating"), oct_forecast=sc.get(case, {}).get("forecast"))
cov_y = BT["Y"]["quantile_lgbm"]["coverage80"]; cov_q = np.mean([BT[q]["quantile_lgbm"]["coverage80"] for q in ("Q1", "Q2", "Q3", "Q4")])
meta = dict(method="v3: quantile LightGBM trained on what every conflict in the world file (117 countries, 1989-2025) did 4-15 months later, from its own history, using the issued monthly counts to Sep 2026.",
            footnote=f"Level = middle case of a 10-90% range from a quantile model trained on 117 countries, 1989-2025, for the whole year or each quarter of 2027 (quarters scaled by each war's month-of-year pattern, capped at ±20%). A restart in any one quarter makes the year's middle case larger than the four quarters added up. Back-tested 2010-2024: the range held {round(cov_y * 100)}% (year) and {round(cov_q * 100)}% (quarters), with about half the typical error of the analogue table used before. Not a validated forecast of these wars. Chains are our analysis.",
            caveat="Planning range, not a validated forecast: a decision to strike, a ceasefire or a new war can move it.",
            data_end="2026-09", window="Jan-Dec 2027 (months +4 to +15 after Sep 2026)", oot_coverage=round(cov_y, 2), oot_coverage_quarters=round(float(cov_q), 2),
            backtest={k: BT[k] for k in BT})
(ROOT / "web/public/data/outlook2027.json").write_text(json.dumps(dict(meta=meta, cases=out), ensure_ascii=False, indent=1))
for k, v in out.items(): print(k, v["level2027"], v["y2027"], {q: (x["p50"], x["level"]) for q, x in v["quarters"].items()})
