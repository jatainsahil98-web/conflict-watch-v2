"""Match the 222 UCDP admin-1 areas to Natural Earth admin-1 polygons (by name, within country)."""
import json, re, difflib, unicodedata
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
A1 = json.loads((ROOT / "assets/web/admin1.json").read_text())

STOP = r"\b(province|oblast|governorate|district|region|krai|kray|republic|of|the|muhafazah|emirate|city|ostan|territory|capital|municipality|raion|autonomous|federal|okrug|governorate)\b"

def norm(s):
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower().replace("'", "").replace("’", "")
    s = re.sub(STOP, " ", s)
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()

# Manual fixes: UCDP name -> NE name (same country)
MANUAL = {
    ("PAK", "Khyber Pakhtunkwa province"): "K.P.", ("PAK", "Balochistan province"): "Baluchistan",
    ("PAK", "Sindh province"): "Sind", ("PAK", "Islamabad Capital territory"): "F.C.T.",
    ("PAK", "Punjab province"): "Punjab",
}
# Cross-country fixes: (UCDP iso, UCDP name) -> (NE iso, NE name)
CROSS = {
    ("UKR", "Kyiv Special Republican city"): ("UKR", "Kiev City"), ("UKR", "Kyiv oblast"): ("UKR", "Kiev"),
    ("UKR", "Autonomous Republic of Crimea"): ("RUS", "Crimea"),
    ("UKR", "Sevastopol City State Administration"): ("RUS", "Sevastopol"),
    ("INTL", "Odessa oblast"): ("UKR", "Odessa"), ("LKA", "Western province"): ("LKA", "Colombo"),
    ("LBN", "Baalbek-Hermel province"): ("LBN", "Beqaa"), ("RUS", "Moscow gorod"): ("RUS", "Moskva"),
    ("IRQ", "Wāsiţ province"): ("IRQ", "Wasit"), ("BHR", "Al ‘Āşimah governorate"): ("BHR", "Al Manāmah"),
    ("YEM", "Şan‘ā’ governorate"): ("YEM", "Sana'a"),
}
# Points without a polygon (PoK areas are drawn inside India's outline, never as Pakistan polygons)
POINTS = {
    "Gilgit-Baltistan": (74.6, 35.9), "Azad Jammu & Kashmir": (73.8, 34.0),
    "Gaza Strip": (34.39, 31.43), "West Bank": (35.25, 31.95),
}

def match(live):
    idx = {}
    for i, f in enumerate(A1["features"]):
        p = f["properties"]
        names = [p.get("name"), p.get("name_en"), p.get("woe_name"), p.get("gn_name")] + (p.get("name_alt") or "").split("|")
        for n in names:
            if n:
                idx.setdefault(p["adm0_a3"], {}).setdefault(norm(n), i)
    out = {}
    for r in live.itertuples():
        key = r.admin1_key
        if r.admin1 in POINTS:
            out[key] = dict(poly=None, lon=POINTS[r.admin1][0], lat=POINTS[r.admin1][1]); continue
        cands = idx.get(r.country_iso3, {})
        m = None
        if (r.country_iso3, r.admin1) in CROSS:
            ci, cn = CROSS[(r.country_iso3, r.admin1)]
            m = idx.get(ci, {}).get(norm(cn))
        if (r.country_iso3, r.admin1) in MANUAL:
            m = cands.get(norm(MANUAL[(r.country_iso3, r.admin1)]))
        if m is None:
            m = cands.get(norm(r.admin1))
        if m is None and cands:
            c = difflib.get_close_matches(norm(r.admin1), list(cands), n=1, cutoff=0.72)
            m = cands[c[0]] if c else None
        if m is None:
            out[key] = None; continue
        p = A1["features"][m]["properties"]
        out[key] = dict(poly=m, lon=p["longitude"], lat=p["latitude"], ne=p["name"])
    return out

if __name__ == "__main__":
    live = pd.read_parquet(ROOT / "data/processed/early_warning_live.parquet")
    m = match(live)
    bad = live[[m[k] is None for k in live.admin1_key]]
    print("matched", len(live) - len(bad), "of", len(live))
    print(bad[["country_iso3", "admin1"]].to_string())
    for k, v in m.items():
        if v and v.get("ne"):
            a = live.drop_duplicates("admin1_key").set_index("admin1_key").admin1[k]
            if norm(a)[:4] != norm(v["ne"])[:4]: print("CHECK", a, "->", v["ne"])
