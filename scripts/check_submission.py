"""Compliance gate: run it before anything is uploaded. Exit code 1 if any check fails.

    python scripts/make_submission_v2.py      # builds dist/FCE_DAC2026.zip, then runs this gate
    python scripts/check_submission.py dist/FCE_DAC2026.zip

Checks the rules in the competition instructions (Appendix B and the submission table) and our own:
report ≤ 10 pages; zip named <Team>_DAC2026.zip; team name on every product; AI declaration in the report;
same run ID everywhere; presentation main deck ≤ 12 slides; code included; no raw dataset in the zip;
no outside (non-issued) data and no synthetic content in the products.
"""
from __future__ import annotations

import io
import re
import sys
import zipfile
from pathlib import Path

from pypdf import PdfReader
from pptx import Presentation

TEAM = "FCE"
OUTSIDE = ["Brent", "Nifty", "NIFTY", "Yahoo", "MOEX", "rouble", "Sensex", "VIX", "OSINT", "9M diaspora", "~9M", "9 million"]
SYNTH = ["SYNTHETIC", "synthetic drill", "Northern Theatre", "LAC incidents"]
RAW = ["conflict_events.csv", "war_terror_violence", "gdelt_focus", "middle east type of conflict", "event_sources.csv",
       "bilateral_displacement", "unhcr_demographics", "country_year_context.csv", "displacement_reference",
       "country_month_panel", "country_summary_panel", ".parquet"]


def main(zpath: str) -> int:
    z = zipfile.ZipFile(zpath)
    names = z.namelist()
    res = []

    def ok(name, cond, detail=""):
        res.append((bool(cond), name, detail))

    ok("zip named <Team>_DAC2026.zip", Path(zpath).name == f"{TEAM}_DAC2026.zip", Path(zpath).name)
    rep = [n for n in names if n.endswith(".pdf") and "Report" in n]
    deck = [n for n in names if n.endswith(".pptx")]
    site = [n for n in names if n.endswith("Ops.html")]
    ok("one report PDF, one .pptx, one site file", len(rep) == 1 and len(deck) == 1 and len(site) == 1, f"{rep} {deck} {site}")
    rtext = dtext = stext = ""
    if rep:
        r = PdfReader(io.BytesIO(z.read(rep[0])))
        rtext = "\n".join(p.extract_text() or "" for p in r.pages)
        ok("report ≤ 10 pages", len(r.pages) <= 10, f"{len(r.pages)} pages")
        ok("AI tools declared in the report", "AI tools declaration" in rtext)
    if deck:
        p = Presentation(io.BytesIO(z.read(deck[0])))
        slides = ["\n".join(sh.text_frame.text for sh in s.shapes if sh.has_text_frame) for s in p.slides]
        dtext = "\n".join(slides)
        main_n = sum(1 for s in slides if "BACKUP" not in s)
        ok("main deck ≤ 12 slides (rest marked BACKUP)", main_n <= 12, f"{main_n} main, {len(slides) - main_n} backup")
    if site:
        stext = z.read(site[0]).decode("utf-8", "ignore")
    for label, txt in (("report", rtext), ("deck", dtext), ("site", stext)):
        ok(f"team name '{TEAM}' on the {label}", TEAM in txt)
    runs = {label: set(re.findall(r"CW-[0-9A-F]{8}", txt)) for label, txt in (("report", rtext), ("deck", dtext), ("site", stext))}
    allr = set().union(*runs.values())
    ok("one run ID across report, deck and site", len(allr) == 1 and all(runs.values()), str(runs))
    for label, txt in (("report", rtext), ("deck", dtext)):
        hits = [w for w in OUTSIDE if w in txt]
        ok(f"no outside-data terms in the {label}", not hits, ", ".join(hits))
        hits = [w for w in SYNTH if w.lower() in txt.lower()]
        ok(f"no synthetic content in the {label}", not hits, ", ".join(hits))
    ok("site data free of outside-data terms", not any(w in stext for w in ["Yahoo", "Brent", "Nifty", "MOEX ISS", "9M diaspora"]))
    ok("code included (pipeline, models, site source)", all(any(n.endswith(f) for n in names) for f in
                                                               ("run_pipeline.py", "src/models.py", "web/src/main.ts", "requirements.txt")))
    raw = [n for n in names if any(k in n for k in RAW)]
    ok("no raw dataset in the zip", not raw, ", ".join(raw[:5]))
    ok("zip under 100 MB", Path(zpath).stat().st_size < 100e6, f"{Path(zpath).stat().st_size / 1e6:.1f} MB")
    width = max(len(n) for _, n, _ in res)
    for good, name, detail in res:
        print(f"{'PASS' if good else 'FAIL'}  {name:<{width}}  {detail if not good or 'pages' in detail or 'main' in detail else ''}")
    bad = sum(1 for g, _, _ in res if not g)
    print(f"\n{len(res) - bad}/{len(res)} checks passed" + ("" if not bad else " — DO NOT UPLOAD"))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else f"dist/{TEAM}_DAC2026.zip"))
