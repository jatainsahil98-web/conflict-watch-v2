# Conflict Watch v2 — Team FCE

**When and where will conflict deaths rise next, and what does it mean for India?**
Lt Gen MS Sodhi Medal Data Analytics Competition 2026 · Maj Shivam Mehta · Capt Siddharth Sangwan · Capt Sahil Singh

v2 applies the lessons from the competition review: issued data only, a ≤10-page report, a 12-slide main deck,
a pre-registered and transfer-learned escalation warning, a GDELT tripwire tested against chance, India's own front,
sealed forecasts, and a compliance gate. See `WHAT_CHANGED_v2.md`. Run ID `CW-F6C2C2CC`.

The issued dataset is **not** in this repository. Put the files in `data/raw/` (layout below), then:

```bash
pip install -r requirements.txt
python run_pipeline.py                 # every table, model and figure (~3-4 min)
python scripts/export_web.py           # site data; stops if a headline number drifts
python scripts/build_site.py           # single-file offline site -> app/static/conflictwatch.html
python report/make_report_figs.py && python report/build_report_v2.py && node report/to_pdf_v2.js
python deck/build_deck_v2.py
python scripts/make_submission_v2.py   # dist/FCE_DAC2026.zip + 17-check compliance gate
```

---

# CONFLICT WATCH – Data Analytics Competition 2026

**When and where will conflict deaths rise next, and what does it mean for India?**
Russia–Ukraine · Israel–Hamas · Afghanistan–Pakistan · US–Iran

Team: Maj Shivam Mehta · Capt Siddharth Sangwan · Capt Sahil Singh · UNCLASSIFIED: open-source data only

**Live dashboard:** https://conflictmonitor2026.streamlit.app

---

## What is in this folder

| Path | What it is |
|---|---|
| `report/Conflict_Watch_Report.pdf` | Full analysis report: method, results, assumptions and limitations (10 pages + appendices); footer carries the run ID |
| `deck/` | Presentation deck (PPTX with Morph transitions and automatic build-ins via `deck/hud.py`; static PDF), commander's brief, Q&A prep sheet, demo-video script |
| `app/app.py` | Hosted app: opens on the Ops site; classic 15-page Streamlit dashboard in *Analyst dashboard* mode (pages 14–15: theatre daily brief, brief history and OODA loop) |
| `web/`, `scripts/export_web.py` | Ops site source (Vite + TypeScript + ECharts + d3-geo) and its data export with asserts |
| `notebooks/01–05` | Executed notebooks: cleaning, features, EDA (military + India), forecasting, early warning |
| `src/` | All pipeline code: `cleaning`, `features`, `insights`, `models`, `viz`, `config` |
| `run_pipeline.py` | One command that reproduces every table, model and figure |
| `score_holdout.py` | Scores the frozen Oct–Dec 2026 forecasts and watch-list against new UCDP events, with no refit (`--events FILE`, `--selftest`) |
| `src/robustness.py` | Evidence strength: month-block bootstrap, Diebold–Mariano, late-data test, warning calibration → `outputs/tables/robustness.json` |
| `src/gdelt.py`, `data/gdelt/` | GDELT media-coded events (Feb–12 Nov 2026) as compact aggregates plus the script that built them; compared with UCDP as **new, separately labelled** results |
| `src/econ.py`, `data/econ/` | Economic front: event study of stock indices, currencies, Brent, gas, wheat and shipping around each war shock (day 0 from UCDP deaths), India panel, reserves, political-crisis timeline and a claims check. Public data (Yahoo Finance, MOEX ISS, World Bank, GPR index) with the fetch scripts; **separately labelled** from the competition data |
| `src/theatre.py`, `src/theatre_viz.py`, `scripts/daily_briefs.py` | **Theatre commander layer (NOTIONAL).** Three illustrative theatre AORs (WTC, NTC, MTC) as GeoJSON plus linked conflicts, a demo login (WTC/NTC/MTC/CDS) that filters the whole dashboard, an auto-generated 0600 IST brief in OODA form with BLUF, FLASH alerts, inbox and e-mail/SMS/WhatsApp previews, and 7 days of history. LAC data are **SYNTHETIC** (seeded) because no issued file covers the LAC. Writes `outputs/theatre/` only, so the run ID is unchanged |
| `outputs/tables/run_id.txt` | Run ID (hash of every result table) printed on the report, deck, dashboard and Ops site |
| `outputs/tables/` | Every number quoted anywhere, as CSV (incl. `data_quality_log.csv`) |
| `outputs/figures/` | 46 figures as PNG and interactive HTML |
| `models/models.joblib` | Fitted forecaster, ensemble members, conformal intervals and early-warning classifier |

## Data

All **twelve issued files** (D1–D12) are used. The six files of the participant package (D1–D6) are bundled under
`data/raw/for participants/` (`data/*.csv` and `documentation/`): UCDP GED 26.1 + Candidate 26.01.26.09,
source references, UNHCR bilateral and demographics, IDMC/UNRWA reference stocks and World Bank context.
The supplementary files are in `data/raw/extra/`: the Middle East (ACLED-style) sheet (D9), the UCDP 1989–2025 file
(D10) and the two pre-joined panels (D11, D12). The two GDELT files (D7, D8; 5.7 GB) are reduced to daily tables
in `data/gdelt/`, with the scripts that built them. `src/extra_sources.py` audits and uses D7–D12.
Licences and attributions are in `data/raw/for participants/documentation/Sources_and_Licenses.md`
(UCDP data are CC BY 4.0). Source files are read-only and are never modified.

To use a copy stored elsewhere:

```bash
export CONFLICT_DATA_DIR="/path/to/for participants/data"
```

## Run it

```bash
pip install -r requirements-dev.txt   # or requirements.txt for the dashboard only

python run_pipeline.py            # about 2.5 min: clean → features → insights → models → scorecard → figures
streamlit run app/app.py          # dashboard at http://localhost:8501
jupyter lab notebooks/            # 01–05, each re-runs its stage with commentary

python report/build_report.py     # rebuild the report (Markdown + HTML) from the output tables
NODE_PATH=$(npm root -g) node report/to_pdf.js   # optional HTML → PDF (needs Node + Playwright)
python deck/build_deck.py         # rebuild the slide deck
```

The dashboard needs the outputs of `run_pipeline.py` (already included). It makes no internet calls.
Its maps use a bundled Natural Earth outline (`assets/world_lowres.geojson`).

## Ops site (story website + ops console)

The hosted app opens on the **Ops site**, which has three levels of depth:

1. **Commander view** (landing screen, one screen, no scrolling): four status tiles, the India exposure map, the
   orders for the month and the top-10 watch-list. Select any tile, marker or order for its evidence sheet.
2. **Briefing** (scroll story): nine chapters by default; `FULL EVIDENCE` (key `E`) adds the seven supporting
   chapters, and `SHOW EVIDENCE` opens the second-level charts inside a chapter.
3. **Ops console** for staff officers (Decide: Brief, Theatre, Warning · Explore: Map, Area, Forecast, What-if ·
   Verify: Scorecard, Data quality, About), each page with a summary header.

`P` toggles presentation mode (larger text, shorter animations, 15-minute timer) for screen sharing.
The classic 15-page Streamlit dashboard is one click away in the sidebar (*Analyst dashboard*).

```bash
python scripts/export_web.py     # frozen outputs -> web/public/data; asserts every headline number (fails on any mismatch)
python scripts/build_site.py     # Vite build -> app/static/site/ (PWA, works offline) + app/static/conflictwatch.html (single file)
cd web && npm run dev            # live development server
```

* Every number comes from `web/public/data/facts.json`, generated from `outputs/tables`. The what-if simulator ships the
  exact Python ensemble output for every slider position (Af–Pak +30% × 3 months = 359, asserted).
* Maps draw India's boundary from Natural Earth's India point-of-view layer; PoK areas are shown as points inside it.
* Keys: **P** presenter mode (15-min timer, arrows jump chapters), **N** speaker notes, **Ctrl/⌘ K** command palette in the console.
* `app/static/conflictwatch.html` (served by the app and its full-screen button) and `deck/conflictwatch.html` are the
  redesigned single-file build (commander landing page: CDS / WTC / NTC / MTC). Its source is now in `web/`
  (`web/src/commander.ts`), so `python scripts/build_site.py` rebuilds it.
* `deck/conflictwatch.html` is the single-file offline backup. `DEMO_SCRIPT.md` is the 2-minute live-demo walkthrough.

## Theatre commander briefs (notional)

```bash
python scripts/daily_briefs.py              # 4 theatres x 7 days of briefs, FLASH log, inbox, outbox (.eml, SMS, WhatsApp)
python scripts/daily_briefs.py --figs       # also figures 34-38
python scripts/daily_briefs.py --send-email # real e-mail via SMTP (CW_SMTP_HOST, CW_SMTP_USER, CW_SMTP_PASS, CW_MAIL_TO_<ROLE>)
```

Schedule it at 0600 IST (0030 UTC) with Windows Task Scheduler, cron, or `.github/workflows/daily-briefs.yml`.
Scoring: 2 x monthly RAG level + daily GDELT, district and market modifiers (RED >= 6, AMBER 3-5). FLASH: a district
nowcast crossing P 0.20 or a RAG change. The district nowcast is a heuristic and is not back-tested. The OODA timings
(4-10 days -> 4-28 hours) are a DOMAIN estimate; data latency (43 d -> <1 d) and build time (~2 s) are measured.

## Method in one paragraph

36 data-quality checks are logged and acted on. Examples: out-of-order estimates are repaired in new columns,
multi-month records are spread across months by day, FATA is harmonised into Khyber Pakhtunkhwa, and publishers are
normalised. The data become two monthly panels: 4 conflicts and 222 sub-national area series, from Jan 2014 to Sep 2026.
Seven forecasters are compared: naive, seasonal naive, 3-month mean, ETS, SARIMA, a global LightGBM on the *change* in
log deaths, and a bottom-up Tweedie LightGBM. They are scored with a walk-forward back-test (2022–2025) and **2026 is
the withheld test set**. The ensemble (3-month mean + ETS + LightGBM-Δ) is chosen on the back-test only. Split-conformal
intervals cover 83% of 2026 outcomes at 80%. A sub-national escalation classifier (ROC-AUC 0.79 on 2026, top-10
precision 3.5× the base rate) feeds a transparent Red/Amber/Green threat scorecard and a what-if simulator.

## Reproducibility notes

* Random seed fixed (`random_state = 42`); LightGBM runs deterministically on CPU.
* All design choices (features, ensemble members, interval bands, classifier features) were made on the
  2022–2025 back-test folds. 2026 was scored once.
* Every figure and number in the report and deck is read from `outputs/tables/`.
* The run ID (`outputs/tables/run_id.txt`) is a SHA-256 hash of those tables. If the ID on the deck, report, dashboard
  and Ops site match, they show the same run.
* GDELT does not change the submitted models: it tracks UCDP only in spike wars, adds nothing a week ahead and
  did not beat persistence out of sample. It is used to watch Oct–Nov 2026, past UCDP's Sep 2026 end.
