"""Step 5: Northern-theatre hook. Turns non-fatal LAC / LoC indicators into a weekly stress index per sector and a
RAG level, so the NTC view can run on real data once they exist. Without data it says so and changes nothing.
Index per sector-week = sum(count x severity weight); z-score against the sector's own previous 26 weeks.
RED: z >= 3 in any sector, or z >= 2 in two sectors; AMBER: z >= 2 in one sector; else GREEN."""
import sys, json, glob
import numpy as np, pandas as pd
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; LAC = ROOT / "data/lac"
W = {1: 1.0, 2: 2.5, 3: 6.0}
def load():
    fs = [f for f in glob.glob(str(LAC / "*.csv")) if not f.endswith("template.csv")]
    if not fs: return None
    d = pd.concat([pd.read_csv(f, parse_dates=["date"]) for f in fs], ignore_index=True)
    d["w"] = d["count"] * d["severity"].map(W).fillna(1.0); return d
def index(d):
    wk = d.set_index("date").groupby(["front", "sector"]).resample("W-MON")["w"].sum().reset_index()
    out = []
    for (f, s), g in wk.groupby(["front", "sector"]):
        g = g.set_index("date")["w"].asfreq("W-MON", fill_value=0)
        m, sd = g.rolling(26, min_periods=8).mean().shift(1), g.rolling(26, min_periods=8).std().shift(1)
        out.append(pd.DataFrame({"front": f, "sector": s, "stress": g, "z": ((g - m) / sd.replace(0, np.nan)).fillna(0)}))
    return pd.concat(out).reset_index()
def rag(latest):
    z = latest["z"].to_numpy()
    return "RED" if (z >= 3).any() or (z >= 2).sum() >= 2 else "AMBER" if (z >= 2).any() else "GREEN"
if __name__ == "__main__":
    d = load()
    if d is None: print(json.dumps({"status": "no LAC/LoC indicator data yet", "how": str(LAC / "README.md")})); sys.exit(0)
    I = index(d); last = I[I["date"] == I["date"].max()]
    res = {"week": str(I["date"].max().date()), "rating": rag(last), "sectors": last[["front", "sector", "stress", "z"]].round(2).to_dict("records")}
    (ROOT / "outputs/v3/lac_index.json").write_text(json.dumps(res, indent=1)); print(json.dumps(res, indent=1))
