"""2027 outlook per war and per theatre (analogue method).

Question: given where each war stands at the end of the data (Sep 2026), what did conflicts in the same
situation do over the following calendar year? We answer it from the issued world file (117 countries,
1989-2025): for every conflict-month we record the recent level (mean of the last 6 months), the momentum
(last 3 months vs last 12), and the total deaths in months +4..+15 (the 'calendar 2027' window seen from
end-September). The ratio of that total to 12x the recent level, for conflicts in the same level band and
momentum class, gives the range. This is a scenario range from history, not a validated forecast: our models
were only tested 1-3 months ahead.

Writes web/public/data/outlook2027.json and outputs/tables/outlook_2027.csv.
"""
import json, numpy as np, pandas as pd
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
W = pd.read_csv(ROOT / "data/raw/extra/6. war_terror_violence_200k.csv", usecols=["date_start", "conflict_name", "country", "deaths_best"])
W["m"] = pd.to_datetime(W["date_start"]).dt.to_period("M")
W = W[(W["m"] >= pd.Period("1989-01", "M")) & (W["m"] <= pd.Period("2025-12", "M"))]
months = pd.period_range("1989-01", "2025-12", freq="M")
P = W.groupby(["conflict_name", "m"])["deaths_best"].sum().unstack(fill_value=0).reindex(columns=months, fill_value=0)
A = P.to_numpy(float)
rows = []
for i in range(A.shape[0]):
    s = A[i]; cs = np.concatenate([[0], np.cumsum(s)])
    for t in range(11, len(s) - 15):
        r6 = (cs[t + 1] - cs[t - 5]) / 6
        if r6 < 1: continue
        r3 = (cs[t + 1] - cs[t - 2]) / 3; r12 = (cs[t + 1] - cs[t - 11]) / 12
        y = cs[t + 16] - cs[t + 4]
        qs = [cs[t + 4 + 3 * j + 3] - cs[t + 4 + 3 * j] for j in range(4)]  # Q1..Q4 of the 2027 window
        rows.append((i, r6, r3 / max(r12, 1e-9), y, *qs))
H = pd.DataFrame(rows, columns=["cid", "r6", "mom", "y", "q1", "q2", "q3", "q4"])
H["ratio"] = H["y"] / (12 * H["r6"])
band_edges = [1, 10, 100, 1000, np.inf]; band_lab = ["1-9", "10-99", "100-999", "1,000+"]
H["band"] = pd.cut(H["r6"], band_edges, right=False, labels=band_lab)
H["momc"] = np.select([H["mom"] >= 1.25, H["mom"] <= 0.8], ["rising", "falling"], "flat")

SEAS = pd.read_csv(ROOT / "outputs/tables/insight_seasonality.csv")
C = pd.read_parquet(ROOT / "data/processed/case_month.parquet")[["conflict_case", "month", "deaths"]]
C["month"] = pd.to_datetime(C["month"])
facts = json.loads((ROOT / "web/public/data/facts.json").read_text())
sc = {s["name"]: s for s in facts["scorecard"]}
out = {}
for case, g in C.groupby("conflict_case"):
    g = g.set_index("month")["deaths"].sort_index()
    r6 = g["2026-04":"2026-09"].mean()
    # Momentum: our model's October forecast against the recent 6-month level (the scorecard trend). The raw last 3 months
    # are too incomplete to use (only ~24% of a month's RU-UA deaths are known at month-end), the model corrects for that.
    mom = float(sc[case]["trend_ratio"]); momc = "rising" if mom >= 1.25 else "falling" if mom <= 0.8 else "flat"
    band = band_lab[np.searchsorted(band_edges, r6, side="right") - 1]
    sel = H[(H["band"] == band) & (H["momc"] == momc)]
    basis = f"level {band} deaths/month, {momc}"
    if sel["cid"].nunique() < 15:
        sel = H[H["band"] == band]; basis = f"level {band} deaths/month (all momentum)"
    q = sel["ratio"].quantile([.1, .25, .5, .75, .9]).to_dict()
    base = 12 * r6
    out[case] = dict(
        recent_month=round(float(r6)), last12=int(round(g["2025-10":"2026-09"].sum())), cal2025=int(round(g["2025"].sum())),
        ytd2026=int(round(g["2026"].sum())), momentum=round(float(mom), 2), momentum_class=momc, band=band, basis=basis,
        n_cases=int(sel["cid"].nunique()), n_obs=int(len(sel)),
        y2027=dict(p10=int(round(base * q[.1])), p25=int(round(base * q[.25])), p50=int(round(base * q[.5])), p75=int(round(base * q[.75])), p90=int(round(base * q[.9]))),
        month2027_p50=int(round(base * q[.5] / 12)),
        p_up=round(float((sel["ratio"] >= 1.5).mean()), 2), p_down=round(float((sel["ratio"] <= 0.5).mean()), 2),
        p_quiet=round(float((sel["y"] < 25).mean()), 2),
        rating_now=sc.get(case, {}).get("rating"), oct_forecast=sc.get(case, {}).get("forecast"))
    quarters = {}
    SE = SEAS[SEAS["conflict_case"] == case].set_index("moy")["index_pct"] / 100  # this war's own seasonality, 2014-2026
    for j in range(1, 5):
        sf = 1 + float(SE.reindex([3 * j - 2, 3 * j - 1, 3 * j]).fillna(0).mean()) if len(SE) else 1.0
        sf = min(1.2, max(0.8, sf))  # cap: one-off events (e.g. Oct 2023) must not pass for a season
        rq = sel[f"q{j}"] / (3 * sel["r6"]); qq = rq.quantile([.1, .5, .9]).to_dict(); b3 = 3 * r6 * sf
        mp = b3 * qq[.5] / 3
        lv = "RED" if mp >= 1000 else "AMBER" if mp >= 100 else "GREEN"
        pu = float((rq >= 1.5).mean())
        if lv == "GREEN" and pu >= 0.30: lv = "AMBER"
        quarters[f"Q{j}"] = dict(season_factor=round(sf, 3), p10=int(round(b3 * qq[.1])), p50=int(round(b3 * qq[.5])), p90=int(round(b3 * qq[.9])), month_p50=int(round(mp)), p_up=round(pu, 2), level=lv)
    out[case]["quarters"] = quarters
    m = out[case]["month2027_p50"]
    lvl = "RED" if m >= 1000 else "AMBER" if m >= 100 else "GREEN"
    if lvl == "GREEN" and out[case]["p_up"] >= 0.30: lvl = "AMBER"
    out[case]["level2027"] = lvl
# Out-of-time check: build the ranges on 1989-2009 and score the 80% range on 2010-2024 conflict-months.
Hm = H.assign(yr=[months[11 + 0].year for _ in range(len(H))]) if False else None
rows2 = []
for i in range(A.shape[0]):
    s = A[i]; cs = np.concatenate([[0], np.cumsum(s)])
    for t in range(11, len(s) - 15):
        r6 = (cs[t + 1] - cs[t - 5]) / 6
        if r6 < 1: continue
        r3 = (cs[t + 1] - cs[t - 2]) / 3; r12 = (cs[t + 1] - cs[t - 11]) / 12
        rows2.append((months[t].year, r6, r3 / max(r12, 1e-9), (cs[t + 16] - cs[t + 4]) / (12 * r6)))
H2 = pd.DataFrame(rows2, columns=["yr", "r6", "mom", "ratio"])
H2["band"] = pd.cut(H2["r6"], band_edges, right=False, labels=band_lab)
H2["momc"] = np.select([H2["mom"] >= 1.25, H2["mom"] <= 0.8], ["rising", "falling"], "flat")
tr, te = H2[H2["yr"] <= 2009], H2[H2["yr"] >= 2010]
Q = tr.groupby(["band", "momc"], observed=True)["ratio"].quantile([.1, .9]).unstack()
te = te.join(Q, on=["band", "momc"]).dropna(subset=[0.1, 0.9])
cover = float(((te["ratio"] >= te[0.1]) & (te["ratio"] <= te[0.9])).mean())
print("out-of-time 80% coverage 2010-2024:", round(cover, 3), "n", len(te))
meta = dict(oot_coverage=round(cover, 2), oot_n=int(len(te)), method="Analogue: conflicts in the world file (117 countries, 1989-2025) at the same recent level and momentum; deaths in the 12 months from month +4 to +15 after the last data month, relative to 12x the recent 6-month level. Quarters are also scaled by each war's own month-of-year pattern (2014-2026), capped at ±20%.",
            caveat="Scenario range from history, not a validated forecast. The models were tested only 1-3 months ahead. Shocks (a new war, a ceasefire, a decision to strike) are not in this range; the daily news tripwire is the guard for those.",
            data_end="2026-09", window="Jan-Dec 2027 (months +4 to +15 after Sep 2026)", n_conflicts=int(H["cid"].nunique()), n_obs=int(len(H)))
(ROOT / "web/public/data/outlook2027.json").write_text(json.dumps(dict(meta=meta, cases=out), ensure_ascii=False, indent=1))
pd.DataFrame(out).T.to_csv(ROOT / "outputs/tables/outlook_2027.csv")
print(json.dumps(meta, indent=1)); print(json.dumps(out, indent=1, ensure_ascii=False))
