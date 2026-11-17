"""Build the submission zip (dist/FCE_DAC2026.zip) and run the compliance gate.

    python scripts/make_submission_v2.py

Contents: the report PDF, the deck, the single-file Ops site, and the code needed to rebuild every
number from the issued files (raw data and derived parquet files are NOT included, per the undertaking).
"""
from __future__ import annotations

import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEAM = "FCE"
DIST = ROOT / "dist"
DIST.mkdir(exist_ok=True)
Z = DIST / f"{TEAM}_DAC2026.zip"
P = f"{TEAM}_DAC2026/"

PRODUCTS = {
    ROOT / "report" / "FCE_Conflict_Watch_Report.pdf": "FCE_Conflict_Watch_Report.pdf",
    ROOT / "deck" / "FCE_Conflict_Watch_Deck.pptx": "FCE_Conflict_Watch_Deck.pptx",
    ROOT / "app" / "static" / "conflictwatch.html": "FCE_Conflict_Watch_Ops.html",
}
CODE_DIRS = ["src", "scripts", "app", "web/src", "web/public/data", "report", "deck", "data/gdelt", "outputs/tables", "notebooks"]
CODE_FILES = ["run_pipeline.py", "score_holdout.py", "requirements.txt", "README.md", "web/package.json", "web/vite.config.ts",
              "web/tsconfig.json", "web/index.html"]
SKIP_DIRS = {"__pycache__", "node_modules", "figs_old", "shots", "assets", "earlier_versions", "dist", "static"}
SKIP_SUFFIX = {".pdf", ".pptx", ".mp4", ".png", ".gif", ".parquet", ".joblib", ".docx"}
KEEP_EXTRA = {"report/figs"}          # report figures are small and make the report rebuild self-contained
SKIP_FILES = {"src/econ.py"}           # the v1 market-data module is not part of v2 (issued data only)


def code_files():
    for d in CODE_DIRS:
        base = ROOT / d
        for f in sorted(base.rglob("*")):
            rel = f.relative_to(ROOT).as_posix()
            if f.is_dir() or rel in SKIP_FILES or any(part in SKIP_DIRS for part in f.relative_to(ROOT).parts):
                continue
            if f.suffix in SKIP_SUFFIX and not (f.suffix == ".png" and any(rel.startswith(k) for k in KEEP_EXTRA)):
                continue
            if rel.startswith("outputs/tables/econ") or "econ" in f.name and d == "outputs/tables":
                continue
            yield f, rel
    for rel in CODE_FILES:
        f = ROOT / rel
        if f.exists():
            yield f, rel


with zipfile.ZipFile(Z, "w", zipfile.ZIP_DEFLATED) as z:
    for src, name in PRODUCTS.items():
        z.write(src, P + name)
    for f, rel in code_files():
        z.write(f, P + "code/" + rel)
    z.writestr(P + "README.txt",
               "Team FCE — Conflict Watch (Lt Gen MS Sodhi Medal Data Analytics Competition 2026)\n\n"
               "FCE_Conflict_Watch_Report.pdf   analysis report (≤10 pages)\n"
               "FCE_Conflict_Watch_Deck.pptx    presentation (12 main slides + backup)\n"
               "FCE_Conflict_Watch_Ops.html     Ops site: open in any browser, works offline\n"
               "code/                           everything needed to rebuild every number\n\n"
               "Rebuild: place the issued files in code/data/raw/ (as in code/README.md), then\n"
               "  pip install -r requirements.txt\n  python run_pipeline.py\n  python scripts/export_web.py\n"
               "  python report/make_report_figs.py && python report/build_report_v2.py\n  python deck/build_deck_v2.py\n\n"
               "The raw dataset is not included. Issued competition data only.\n")
print(f"built {Z.relative_to(ROOT)} ({Z.stat().st_size / 1e6:.1f} MB, {len(zipfile.ZipFile(Z).namelist())} files)")
sys.exit(subprocess.call([sys.executable, str(ROOT / "scripts" / "check_submission.py"), str(Z)]))
