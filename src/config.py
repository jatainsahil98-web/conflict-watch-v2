"""Central configuration: paths, constants and case metadata.

Every notebook, the pipeline script and the dashboard import from here so that
paths and modelling choices are defined exactly once.
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]          # .../submission
PROCESSED = ROOT / "data" / "processed"
FIG_DIR = ROOT / "outputs" / "figures"
TAB_DIR = ROOT / "outputs" / "tables"
for _p in (PROCESSED, FIG_DIR, TAB_DIR):
    _p.mkdir(parents=True, exist_ok=True)


def _find_raw_dir() -> Path:
    """Locate the official 'for participants/data' folder.

    Order: $CONFLICT_DATA_DIR, then the copy bundled in this repository
    (data/raw/for participants/data), then any 'for participants/data' folder
    under the parent of the submission folder (the layout the dataset ships in).
    """
    env = os.environ.get("CONFLICT_DATA_DIR")
    if env:
        return Path(env)
    bundled = ROOT / "data" / "raw" / "for participants" / "data"
    if (bundled / "conflict_events.csv").exists():
        return bundled
    for dirpath, dirnames, _ in os.walk(ROOT.parent, followlinks=True):
        if dirpath.count(os.sep) - str(ROOT.parent).count(os.sep) > 6:
            dirnames[:] = []
            continue
        cand = Path(dirpath)
        if cand.name == "data" and cand.parent.name == "for participants" and (cand / "conflict_events.csv").exists():
            return cand
    raise FileNotFoundError(
        "Could not find the official data. Set CONFLICT_DATA_DIR to the folder "
        "containing conflict_events.csv."
    )


RAW_DIR = _find_raw_dir()
DOC_DIR = RAW_DIR.parent / "documentation"

# --- Time windows -----------------------------------------------------------
PANEL_START = "2014-01-01"
PANEL_END = "2026-09-30"            # last day covered by the event extract
TRAIN_END = "2025-12-31"            # model training cut-off (GED 26.1, final)
HOLDOUT_START = "2026-01-01"        # withheld test window (UCDP Candidate, provisional)
FORECAST_MONTHS = 3                 # forward forecast Oct-Dec 2026 for the dashboard

CASES = ["Russia–Ukraine", "Israel–Hamas", "Afghanistan–Pakistan", "US–Iran"]
CASE_SHORT = {
    "Russia–Ukraine": "RU-UA",
    "Israel–Hamas": "IL-HAM",
    "Afghanistan–Pakistan": "AF-PK",
    "US–Iran": "US-IR",
}
# Palette taken from the team's jury-deck theme (dark navy, amber/cyan/red/teal accents)
THEME = dict(bg="#07131F", panel="#0F2236", panel2="#16304A", border="#2B4763", muted="#5E7B99",
             text="#FFFFFF", text2="#D5DEE8", text3="#9FB2C6", amber="#F0B03A", red="#FF4D5E",
             cyan="#4FD6E8", teal="#35C2A6", violet="#A794FF", amber_bg="#2A2008")
CASE_COLORS = {
    "Russia–Ukraine": THEME["cyan"],
    "Israel–Hamas": THEME["amber"],
    "Afghanistan–Pakistan": THEME["teal"],
    "US–Iran": THEME["red"],
}
RAG_COLORS = {"RED": THEME["red"], "AMBER": THEME["amber"], "GREEN": THEME["teal"]}
VIOLENCE_TYPES = {1: "State-based", 2: "Non-state", 3: "One-sided"}

# Escalation definition used by the early-warning classifier
ESCALATION_RATIO = 1.5      # next-month deaths >= 1.5 x trailing-3-month mean ...
ESCALATION_MIN_DEATHS = 10  # ... and at least this many deaths

RANDOM_STATE = 42

# India-relevant geography (used in the India-impact analysis).  These are
# domain annotations, not fields in the source data.
INDIA_PROXIMATE_ADMIN1 = {
    # Pakistan provinces / areas adjoining India or the Line of Control
    "Azad Jammu & Kashmir": "Adjoins LoC (J&K)",
    "Gilgit-Baltistan": "Adjoins LoC / Ladakh",
    "Punjab province": "Borders Indian Punjab / Rajasthan",
    "Sindh province": "Borders Gujarat / Rajasthan",
}
GULF_ISO3 = ["ARE", "SAU", "KWT", "QAT", "BHR", "OMN"]
