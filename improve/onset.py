"""Step 1: learned daily tripwire from GDELT news vs the fixed rules on the site.
Target: a casualty escalation day (deaths >= 3x the previous 14-day mean and >= 20, the RED confirmation used in the
deck) within the next 14 days. Rows: war-days Feb-Sep 2026 (GDELT starts 1 Feb; casualties end 30 Sep).
Evaluation: leave-one-war-out (train on three wars, score the fourth) so no war is scored on itself.
Small sample (four wars, eight months): read the results as direction, not proof.
"""
import sys, json, warnings
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
import common as c
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.metrics import average_precision_score, roc_auc_score
OUT = c.ROOT / "outputs/v3"
MAP = {"AF-PAK": "Afghanistan–Pakistan", "ISR-HAMAS": "Israel–Hamas", "RU-UA": "Russia–Ukraine", "US-IRAN": "US–Iran"}
G = pd.read_csv(c.ROOT / "data/gdelt/gdelt_case_daily.csv", parse_dates=["date"]); G["war"] = G["case_id"].map(MAP)
E = pd.read_parquet(c.PROC / "events.parquet")[["conflict_case", "date_start", "deaths_best"]]
E["date"] = pd.to_datetime(E["date_start"]).dt.normalize()
cas = E.groupby(["conflict_case", "date"])["deaths_best"].sum()
rows = []
for w, g in G.groupby("war"):
    g = g.set_index("date").sort_index().asfreq("D").fillna(0)
    d = cas.get(w, pd.Series(dtype=float)).reindex(pd.date_range("2025-12-01", "2026-09-30"), fill_value=0)
    prev = d.rolling(14).mean().shift(1); escd = ((d >= 3 * prev) & (d >= 20)).astype(int)
    fut = escd[::-1].rolling(14, min_periods=1).max()[::-1].shift(-1)          # any escalation day in t+1..t+14
    f = pd.DataFrame(index=g.index)
    for col in ["force_posture_events", "threat_events", "violent_events", "material_conflict", "events", "violent_articles"]:
        x = g[col]; m = x.rolling(14).mean().shift(1); s = x.rolling(14).std().shift(1)
        f[f"z_{col}"] = ((x - m) / s.replace(0, np.nan)).fillna(0).clip(-5, 10)
        f[f"r7_{col}"] = np.log1p(x.rolling(7).sum()) - np.log1p(x.rolling(28).sum() / 4)
    f["tone"] = g["tone_wmean"]; f["d_tone"] = g["tone_wmean"] - g["tone_wmean"].rolling(14).mean().shift(1)
    f["goldstein"] = g["goldstein_wmean"]; f["cas_7"] = np.log1p(d.reindex(f.index).rolling(7).sum().shift(1)).fillna(0)
    f["rule_posture"] = (f["z_force_posture_events"] + f["z_threat_events"] >= 3).astype(int)
    med = g["violent_events"].rolling(14).median().shift(1); f["rule_red"] = ((g["violent_events"] >= 4 * med) & (g["violent_events"] >= 100)).astype(int)
    f["y"] = fut.reindex(f.index); f["war"] = w
    rows.append(f[(f.index >= "2026-02-15") & (f.index <= "2026-09-16")])
D = pd.concat(rows).dropna(subset=["y"]); D["y"] = D["y"].astype(int)
D = D.replace([np.inf, -np.inf], np.nan).fillna(0)
FE = [x for x in D.columns if x.startswith(("z_", "r7_")) or x in ("tone", "d_tone", "goldstein", "cas_7")]
res, P = {}, pd.Series(index=D.index, dtype=float)
oof = np.zeros(len(D))
for w in D["war"].unique():
    tr, te = D["war"] != w, D["war"] == w
    m = make_pipeline(StandardScaler(), LogisticRegression(C=0.3, class_weight="balanced", max_iter=2000)).fit(D.loc[tr, FE], D.loc[tr, "y"])
    oof[te.to_numpy()] = m.predict_proba(D.loc[te, FE])[:, 1]
D["p_learned"] = oof; D["p_rules"] = np.maximum(D["rule_posture"], D["rule_red"])
y = D["y"].to_numpy()
def sc(p): return dict(pr_auc=round(float(average_precision_score(y, p)), 3), roc_auc=round(float(roc_auc_score(y, p)), 3))
res["base_rate"] = round(float(y.mean()), 3); res["n_days"] = int(len(D))
res["fixed_rules (site)"] = sc(D["p_rules"].to_numpy()); res["learned_logistic"] = sc(D["p_learned"].to_numpy())
res["blend (max of rules and learned)"] = sc(np.maximum(D["p_rules"], D["p_learned"]).to_numpy())
th = float(np.quantile(D["p_learned"], 0.85))
def alerts(col, t): k = D[col] >= t; return dict(alert_days=int(k.sum()), precision=round(float(D.loc[k, "y"].mean()), 3) if k.any() else 0, recall=round(float(D.loc[k, "y"].sum() / D["y"].sum()), 3))
res["at_alert_level"] = {"fixed_rules": alerts("p_rules", 1), "learned (top 15% of days)": alerts("p_learned", th)}
ui = D[D["war"] == "US–Iran"]
res["us_iran_onset"] = {"first_learned_alert_before_28_Feb": str(ui[(ui["p_learned"] >= th) & (ui.index < "2026-02-28")].index.min()),
                        "first_rule_alert_before_28_Feb": str(ui[(ui["p_rules"] == 1) & (ui.index < "2026-02-28")].index.min())}
(OUT / "onset_results.json").write_text(json.dumps(res, indent=1))
print(json.dumps(res, indent=1))
