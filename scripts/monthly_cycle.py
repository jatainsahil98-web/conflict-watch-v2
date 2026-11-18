"""Step 7: run the system month after month, with the same discipline as the competition test.

  python scripts/monthly_cycle.py forecast   # after a new month of data: refit the v3 model, forecast next month
                                             # with 80% ranges, hash the forecast and add it to the scorebook
  python scripts/monthly_cycle.py score      # when that month's counts arrive: score every open forecast
                                             # (RMSLE, inside-range) and update the running track record

Model = the Step-2 choice frozen in outputs/v3/freeze_monthly.json (LightGBM, Huber loss, nowcast target,
completeness features); ranges = per-intensity-band widths from outputs/v3/ranges_results.json.
A forecast, once written, is never edited: scoring only appends.
"""
import sys, json, hashlib, time
import numpy as np, pandas as pd
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "improve"))
import common as c
import lightgbm as lgb
OUT = ROOT / "outputs/v3"; BOOK = OUT / "scorebook.csv"
FE = c.BASE_FE + c.COMP_FE

def latest_rows():
    """Feature rows at the last data month for each war (as known at its end)."""
    V = c.vintages(); F = c.wars_final(); t = len(c.CM) - 1; rows = []
    for w, row in F.iterrows():
        s = np.clip(V[w][t][:t + 1], 0, None); comp = c.completeness(V[w], t)
        # same feature code as training: reuse common._rows on a series padded by one dummy month
        fin = np.append(row.to_numpy(float), 0.0); idx = c.CM.append(pd.period_range(c.CM[-1] + 1, periods=1, freq="M"))
        r = c._rows(lambda tt: (np.clip(V[w][min(tt, t)][:tt + 1], 0, None), c.completeness(V[w], min(tt, t))), len(fin), idx, w, 1, fin)[-1]
        rows.append(r)
    return pd.DataFrame(rows)

def forecast():
    frz = json.loads((OUT / "freeze_monthly.json").read_text()); assert frz["choice"] == "lgb_huber_nowcast|comp"
    widths = json.loads((OUT / "ranges_results.json").read_text())["widths"]["B"]
    D = c.monthly_frame(); X = latest_rows()
    m = lgb.LGBMRegressor(objective="huber", n_estimators=600, num_leaves=15, learning_rate=0.03, min_child_samples=40, subsample=0.8, subsample_freq=1, colsample_bytree=0.8, verbose=-1, random_state=0)
    m.fit(D[FE], D["dy_adj"], sample_weight=np.where(D["war"] == 1, 5.0, 1.0))
    p = np.clip(X["base_adj"].to_numpy() + m.predict(X[FE]), 0, None)
    band = np.digitize(X["base_adj"].to_numpy(), np.log1p([10, 100, 1000])); w = np.array([float(widths[str(b)]) for b in band])
    made = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    new = pd.DataFrame({"made": made, "model": frz["choice"], "war": X["sid"], "target_month": X["tgt_m"].astype(str),
                        "forecast": np.round(np.expm1(p)).astype(int), "lo80": np.round(np.expm1(np.clip(p - w, 0, None))).astype(int),
                        "hi80": np.round(np.expm1(p + w)).astype(int), "actual": np.nan, "rmsle": np.nan, "inside": np.nan})
    new["hash"] = [hashlib.sha256(json.dumps(r, sort_keys=True, default=str).encode()).hexdigest()[:16] for r in new.drop(columns=["actual", "rmsle", "inside"]).to_dict("records")]
    book = pd.concat([pd.read_csv(BOOK), new], ignore_index=True) if BOOK.exists() else new
    book = book.drop_duplicates(subset=["war", "target_month", "model"], keep="first")   # a forecast is never replaced
    book.to_csv(BOOK, index=False); print(new[["war", "target_month", "forecast", "lo80", "hi80", "hash"]].to_string(index=False))

def score():
    if not BOOK.exists(): sys.exit("no scorebook yet")
    book = pd.read_csv(BOOK); F = c.wars_final(); n = 0
    for i, r in book[book["actual"].isna()].iterrows():
        m = pd.Period(r["target_month"], "M")
        if m in F.columns and m <= c.CM[-1] and m > pd.Period(r["made"][:7], "M") - 1:
            a = float(F.loc[r["war"], m]); book.loc[i, ["actual", "rmsle", "inside"]] = [a, abs(np.log1p(a) - np.log1p(r["forecast"])), float(r["lo80"] <= a <= r["hi80"])]; n += 1
    book.to_csv(BOOK, index=False); s = book.dropna(subset=["actual"])
    rec = {"scored": int(len(s)), "rmsle": round(float(np.sqrt((s["rmsle"] ** 2).mean())), 3) if len(s) else None, "inside80": round(float(s["inside"].mean()), 3) if len(s) else None}
    (OUT / "track_record.json").write_text(json.dumps(rec, indent=1)); print(f"scored {n} new; track record {rec}")

if __name__ == "__main__":
    {"forecast": forecast, "score": score}[sys.argv[1]]()
