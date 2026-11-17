"""Generate the five numbered analysis notebooks (then execute them with nbconvert).

    python notebooks/build_notebooks.py
    jupyter nbconvert --to notebook --execute --inplace notebooks/0*.ipynb

Each notebook re-runs its stage from the source CSVs via the functions in src/,
so a reviewer can verify every number independently of the pipeline script.
"""
from pathlib import Path

import nbformat as nbf

HERE = Path(__file__).parent

SETUP = """import sys, warnings
from pathlib import Path
ROOT = Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()
sys.path.insert(0, str(ROOT))
warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
import plotly.io as pio
pio.renderers.default = "plotly_mimetype+notebook_connected"
pd.set_option("display.max_columns", 40); pd.set_option("display.width", 200)
pd.set_option("display.float_format", lambda v: f"{v:,.3f}")
from src import config as C, viz"""


def md(s):
    return nbf.v4.new_markdown_cell(s.strip())


def code(s):
    return nbf.v4.new_code_cell(s.strip())


def write(name, cells):
    nb = nbf.v4.new_notebook()
    nb.cells = cells
    nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
    nbf.write(nb, HERE / name)


# ---------------------------------------------------------------------------
write("01_data_cleaning.ipynb", [
    md("""
# 01 · Problem framing, data audit and cleaning
**Data Analytics Competition 2026 · Conflict analytics: Russia–Ukraine, Israel–Hamas, Afghanistan–Pakistan, US–Iran**

### The question we chose
> **When and where will conflict deaths rise next, and what does that mean for the Indian Armed Forces and for humanitarian planning?**

We break this down into five sub-questions that the rest of the notebooks answer:

| # | Question | Notebook | Why a commander cares |
|---|---|---|---|
| Q1 | How intense is each conflict, and how is it changing (tempo, lethality, geography, seasonality)? | 03 | Threat picture |
| Q2 | How are the wars being fought: attrition by side, type of violence, front-line shift, cross-border spread? | 03 | Lessons for force design |
| Q3 | Can we forecast monthly deaths 1–9 months ahead better than simple rules, on data the model has never seen (Jan–Sep 2026)? | 04 | Planning horizon |
| Q4 | Can we warn, a month ahead, which sub-national areas will escalate? | 05 | Indications & warning (I&W) |
| Q5 | What does all this mean for India: western front, Gulf diaspora and energy, Indian Ocean, defence supply, refugees? | 03, report | Policy relevance |

### Data
Official competition package only (UCDP GED 26.1 + Candidate 26.01.26.09 events, UNHCR, IDMC, UNRWA, World Bank).
The top-level files in the parent folder belong to a different package and are **not** used.

This notebook loads the six tables, runs **36 documented checks**, fixes what can be fixed, flags what cannot,
and writes the cleaned tables to `data/processed/`. Source files are never modified.
"""),
    code(SETUP),
    md("## 1. Raw tables at a glance"),
    code("""raw = {n: pd.read_csv(C.RAW_DIR / f"{n}.csv", encoding="utf-8-sig") for n in
       ["conflict_events", "event_sources", "bilateral_displacement_stocks", "unhcr_demographics",
        "displacement_reference_stocks", "country_year_context"]}
pd.DataFrame({n: {"rows": len(d), "columns": d.shape[1], "missing cells": int(d.isna().sum().sum())}
              for n, d in raw.items()}).T"""),
    code("""ev = raw["conflict_events"]
print("Events by case and year")
pd.crosstab(ev.conflict_case, ev.event_year, margins=True)"""),
    code("""print("Missing values in conflict_events:"); print(ev.isna().sum()[ev.isna().sum() > 0])
ev[["deaths_best", "deaths_low", "deaths_high", "source_count"]].describe(percentiles=[.5, .9, .99, .999]).T"""),
    md("""## 2. Run the cleaning stage
`src/cleaning.py` implements every rule below. Key decisions:

* **Out-of-order estimates** (low > best or best > high, 692 rows): raw values kept; corrected band
  `deaths_low_c = min(low, best, high)`, `deaths_high_c = max(...)`. We widen the band rather than move `best`,
  because `best` reconciles exactly with the four component fields (validated).
* **Multi-month events** (731 rows, incl. front-wide monthly aggregates): deaths are spread over calendar months
  in proportion to the days in the date range, instead of stacking them on the start month.
* **Provisional 2026 Candidate data**: flagged and used *only* as the withheld test set.
* **FATA → Khyber Pakhtunkhwa**: Pakistan merged FATA into KP in 2018; without harmonising, the sub-national panel
  shows a fake collapse in FATA and a fake surge in KP.
* **Publisher names**: 'ITAR-TASS'/'Tass', 'UA Losses'/'UALosses', 'Source:' prefixes etc. normalised.
* **Missing geography**: blank `location_iso3` → `INTL` (waters/airspace) or `XXX` (ambiguous code 666); blank admin1 →
  explicit "country-level" bucket so the deaths are not lost.
* **World Bank gaps**: interpolated within economy; used with a one-year lag so 2026 needs no extrapolation.
"""),
    code("""from src import cleaning
out = cleaning.run()
dq = out["dq_log"]
print(f"{len(dq)} checks logged; {int((dq.rows_affected > 0).sum())} found issues")
dq[["id", "table", "check", "category", "rows_affected", "pct_affected", "action"]]"""),
    code("viz.fig_dq_summary(dq)"),
    md("## 3. Spot-checks of the fixes"),
    code("""e = out["events"]
print("Out-of-order examples (raw vs corrected):")
e.loc[e.flag_estimate_order, ["event_id", "deaths_low", "deaths_best", "deaths_high", "deaths_low_c", "deaths_high_c"]].head()"""),
    code("""al = out["alloc"]
x = e.loc[e.flag_multi_month].nlargest(1, "deaths_best")[["event_id", "date_start", "date_end", "deaths_best"]]
print(x.to_string(index=False))
al[al.event_id == x.event_id.iloc[0]].assign(deaths=lambda d: d.share * x.deaths_best.iloc[0])"""),
    code("""# allocation conserves deaths (except the logged October share after the window)
alloc_tot = al.merge(e[["event_id", "deaths_best"]]).eval("share*deaths_best").sum()
print(f"events total {e.deaths_best.sum():,.1f}  vs  allocated total {alloc_tot:,.1f}")"""),
    code("""s = out["sources"]
print(f"{s.publisher.nunique():,} raw publisher labels -> {s.publisher_norm.nunique():,} normalised outlets")
s.groupby("publisher_norm").size().nlargest(15).rename("references").to_frame()"""),
    md("""## 4. A finding from cleaning itself: the *fog of war* in the data
Most Russia–Ukraine deaths since 2024 are recorded as country-level aggregates (often memorial-database counts),
not as located incidents. By 2026, **over 90%** of RU–UA deaths have no sub-national location.
Consequence for our method: front-line geography is measured with **located, discrete events**, not deaths, and
sub-national forecasts are evaluated with that limit stated."""),
    code("""from src import insights
gp = insights.geo_precision_trend(e)
display(gp[gp.conflict_case == "Russia–Ukraine"].round(3))
viz.fig_fog_of_war(gp)"""),
    md("""## 5. Summary
* 36 checks, 0 key or arithmetic failures, 692 out-of-order estimate rows repaired (flagged),
  731 multi-month records disaggregated, 4,644 provisional rows isolated for testing.
* Cleaned tables are in `data/processed/*.parquet`; the full log is `outputs/tables/data_quality_log.csv`.

Next: `02_feature_engineering.ipynb`."""),
])

# ---------------------------------------------------------------------------
write("02_feature_engineering.ipynb", [
    md("""
# 02 · Feature engineering
Two monthly panels are built from the cleaned events:

* **Conflict level** – 4 cases × 153 months (Jan 2014 – Sep 2026).
* **Sub-national level** – 222 (case, country, first-level area) series × 153 months, zero-filled.

Every model feature is computed so that it is **known at the end of the forecast-origin month** (no look-ahead),
and annual context (displacement, World Bank) enters with a **one-year lag**.
"""),
    code(SETUP),
    code("""from src import features
ft = features.run()
cm, am = ft["case_month"], ft["admin1_month"]
print("conflict-month panel", cm.shape, "| sub-national panel", am.shape)
cm[cm.conflict_case == "US–Iran"].tail(6)[["month", "deaths", "n_events", "n_admin1", "hhi", "outside_core_share",
                                         "civ_share", "uncert_index", "n_outlets", "y_rm3", "momentum_3v12"]]"""),
    md("## Feature dictionary"),
    code("""pd.DataFrame(list(features.FEATURE_DICTIONARY.items()), columns=["feature", "meaning"])"""),
    md("""### Feature families and the military/analytic idea behind each
| Family | Examples | Idea |
|---|---|---|
| Intensity memory | lags, rolling means, EWM, 12-month peak | Wars have inertia; the best predictor of next month is a smoothed recent level |
| Momentum | `momentum_3v12`, `accel` | Escalation shows up as short-term intensity running above the long-term norm |
| Tempo | events/month, references/month | Operational tempo (number of engagements) vs lethality |
| Fog of war | `uncert_index`, `agg_share`, `lowprec_share` | How much the reporting picture is degraded |
| Character of violence | civilian share, state/one-sided share, focal share | Shift from battlefield to punitive violence |
| Geography | active areas, HHI concentration, share outside core theatre | Front widening and horizontal escalation |
| Seasonality | target-month sine/cosine, same-month-last-year | Campaigning seasons, weather |
| Context (lag 1y) | IDPs, refugees, GDP growth, inflation | Structural stress |
| Hierarchy (sub-national) | conflict-level intensity, area's share of the conflict | Areas inherit their war's tempo |
"""),
    code("""from src.features import make_supervised
sup = make_supervised(cm, ["conflict_case"], horizons=(1,))
num = ["target_y", "y_l0", "y_rm3", "y_rm12", "momentum_3v12", "log_events_rm3", "log_sources_rm3", "civ_share_rm3",
       "uncert_index_rm3", "n_admin1_rm3", "hhi_rm3", "outside_core_share_rm3", "zero_streak", "y_seasonal"]
corr = sup[num].corr(method="spearman")["target_y"].drop("target_y").sort_values()
corr.rename("Spearman correlation with next month's log deaths").to_frame()"""),
    code("""import plotly.graph_objects as go
c = sup[num].corr(method="spearman")
go.Figure(go.Heatmap(z=c.values, x=c.columns, y=c.index, zmid=0, colorscale="RdBu_r")).update_layout(
    title="Feature correlation (Spearman)", height=650)"""),
    md("""### Leakage checks
* Target month > origin month for every row (asserted below).
* Annual context for year *Y* comes from *Y − 1*.
* 2026 rows are never in a training set for evaluated models (enforced in `src/models.py`)."""),
    code("""sup_h = make_supervised(cm, ["conflict_case"], horizons=range(1, 10))
assert (sup_h.target_month > sup_h.month).all()
ctx = features.build_country_year_context()
print("context years available:", ctx.year.min(), "-", ctx.year.max(), "| used with +1 year lag")
print("rows with 2026 targets:", int((sup_h.target_month >= "2026-01-01").sum()), "(test only)")"""),
])

# ---------------------------------------------------------------------------
write("03_eda_military_india.ipynb", [
    md("""
# 03 · Exploratory analysis: intensity, how the wars are fought, displacement, media, and India
Each section ends with **So what** – the actionable implication. Points that rely on knowledge outside this
dataset are labelled **[Domain]**; everything else is computed here.
"""),
    code(SETUP),
    code("""from src import insights
from src.cleaning import load
e = load("events"); s = load("sources")
cm = pd.read_parquet(C.PROCESSED / "case_month.parquet")
I = insights.run()
I["case_overview"].set_index("conflict_case").T"""),
    md("## 1. Intensity and tempo"),
    code("viz.fig_monthly_deaths(cm)"),
    code("viz.fig_case_small_multiples(cm)"),
    code("viz.fig_violence_mix(I['violence_mix'])"),
    md("""**Reading.** Russia–Ukraine dominates absolute deaths (≈447k recorded, 2014–Sep 2026) and has held a
5–11k/month plateau since 2023. Israel–Hamas peaked in Oct 2023 and has fallen to ~130/month during 2026.
Afghanistan–Pakistan is lower-intensity but **rising since 2021**. US–Iran went from proxy and coalition strikes
to a direct state-on-state war in Feb–Mar 2026 (peak month of the case).

**So what.** Threat is not one number: RU–UA is a *sustained attrition* problem, US–Iran a *spike* problem,
Af–Pak a *creeping* problem. Each needs a different warning indicator (level, shock, trend)."""),
    md("## 2. How the wars are being fought (military lens)"),
    md("### 2a. Attrition by side (focal dyads)"),
    code("""att = I["attrition"]
display(att[att.year >= 2022].round(2))
viz.fig_attrition(att)"""),
    md("""**Reading.** UCDP *records* Russian fatalities outnumbering Ukrainian ones by a widening margin
(about 2:1 in 2022–23 to about 10:1 in 2026). **Caveat:** these are recorded, source-dependent figures. Ukrainian
memorial and OSINT databases document Russian losses more systematically than the reverse, so the ratio is an
upper bound of reporting, not a verified exchange ratio.

**So what [Domain].** A defender with ISR-cued precision fires and drones can impose disproportionate attrition.
That lesson matters for India's force design on both fronts."""),
    md("### 2b. Front-line geography: the front widens rather than moves"),
    code("""fg = I["front_geography"]
display(fg.pivot(index="area", columns="year", values="share").mul(100).round(1).fillna(0))
viz.fig_front_geography(fg)"""),
    md("""**Reading.** Donetsk's share of geolocated events falls from about 55% (2022) to 30% (2026), while
Zaporizhzhia, Dnipropetrovsk, Sumy and Russia's Belgorod and Kursk grow. Violence is spreading **along and across**
the line rather than moving with a breakthrough.

**So what.** Static, wide fronts favour long-range strike, counter-drone and logistics depth. Warning systems
should track the *spread* of activity (number of active areas, concentration), which we feed into the models."""),
    code("viz.fig_theatre_spread(I['theatre_spread'])"),
    code("viz.fig_country_map(I['country_deaths'])"),
    md("""### 2c. Afghanistan–Pakistan: a second, state-on-state front opens"""),
    code("""display(I["afpak_provinces"].pivot_table(index=["country_iso3", "admin1"], columns="year", values="deaths",
                                           aggfunc="sum").fillna(0).astype(int))
viz.fig_afpak(I["afpak_provinces"])"""),
    code("viz.fig_afpak_interstate(e)"),
    md("""**Reading.** TTP-led violence has concentrated in **Khyber Pakhtunkhwa** (FATA merged), rising every year
since 2021. Since Oct 2025 the **Afghan and Pakistani governments have fought each other directly**: 131 deaths in
Oct 2025 and a peak of 411 in Mar 2026.

**So what (India).** Pakistan now faces active hostilities on its western border. **[Domain]** That stretches its
army and may reduce its capacity on the eastern front, or raise the incentive for diversionary activity along
the LoC. Either way, India needs closer watch on the western front, not less."""),
    md("### 2d. Campaign seasons"),
    code("viz.fig_seasonality(I['seasonality'])"),
    md("""**Reading.** RU–UA deaths run about 15–35% above trend in **May–August** and about 25–35% below in **Dec–Jan**
(the summer campaigning season versus winter and the *rasputitsa*). Af–Pak peaks in **Sep–Oct**.

**So what.** Seasonal priors are a cheap, explainable addition to warning; our models use them."""),
    md("## 3. Media attention vs deaths (original index)"),
    code("""md_, st = I["media"], I["stats"]["media"]
print({k: round(float(v), 3) for k, v in st.items()})
viz.fig_media_scatter(md_)"""),
    code("viz.fig_media_gap(md_)"),
    code("I['indian_press']"),
    md("""**Reading.** Once the number of incidents is known, **deaths add essentially nothing** to how many references
a month receives (elasticity ≈ 0.01 vs ≈ 0.96 for events). One mass-casualty strike counts as one story.
The attention gap does **not** lead next month's escalation (p ≈ 0.5), so media volume is not a warning signal.
Indian outlets (PTI) appear in **17% of Af–Pak events** and almost none of the other three theatres.

**So what (India).** India's open-source picture of West Asia and Europe depends almost entirely on foreign
reporting. Building indigenous OSINT coverage of the Gulf and Iran is a cheap capability gain."""),
    md("## 4. Displacement and humanitarian planning"),
    code("viz.fig_displacement(I['displacement'])"),
    code("""display(I["demographics_profile"].sort_values("year").groupby("origin_iso3").tail(1).round(3))
viz.fig_demographics(I["demographics_profile"])"""),
    code("""lk, st2 = I["displacement_link"], I["stats"]["displacement_link"]
print({k: round(float(v), 3) for k, v in st2.items()})"""),
    md("""**Reading.** Ukraine: about 5.2M refugees and 3.7M IDPs at end-2025; **72%** of Ukrainian refugees with recorded
sex and age are women or children. Afghanistan: 63% women and children, 10% under five. At country-year level,
deaths explain little of the *change* in displaced stocks (Spearman ≈ 0.1): displacement responds to the
onset of war and to access, not to the monthly death count.

**So what.** HADR planning should key on **war onset and spread** (our early-warning flags), and stock
paediatric and maternal supplies. Displacement cannot be attributed to single events (README caveat)."""),
    md("## 5. India impact (data-derived parts)"),
    code("""ie = I["india_exposure"]
display(ie[ie.year >= 2024].pivot_table(index="india_tag", columns="year", values=["events", "deaths"], aggfunc="sum").fillna(0))
viz.fig_india_exposure(ie)"""),
    code("""display(I["india_hosted"].pivot_table(index="origin_name", columns="year", values="total_international"))
viz.fig_india_hosted(I["india_hosted"])"""),
    code("""ic = I["india_context"]
ic.pivot(index="year", columns="iso3", values="consumer_inflation_annual_pct").round(1)"""),
    md("""**Data-derived**
* In 2026 the US–Iran war hit **six Gulf states** (25 events, 37 deaths), **Iran's Hormuz/Chabahar coast** (61 events,
  299 deaths) and reached the **Indian Ocean**: a strike off Sri Lanka's west coast killed **104** on 4 Mar 2026.
* Yemen and the Red Sea approaches: 945 deaths in 2025.
* Pakistan areas adjoining India or the LoC (Punjab, Sindh, AJK, Gilgit-Baltistan): low but rising
  (2 deaths in 2022, 52 in 2025).
* India hosts about 8.4k Afghans (falling) and a fast-growing number of **Russian asylum seekers (5 → 329, 2015–25)**.

**[Domain] reasoning (not from this dataset)**
* About 9 million Indians live in the Gulf, so evacuation contingencies are needed (cf. Op Ganga 2022, Op Kaveri 2023, Op Ajay 2023).
* A large share of India's crude and LPG imports transit Hormuz. The Chabahar port and the INSTC corridor run
  through the 2026 strike zone.
* Russia remains India's largest legacy arms supplier and Israel a key supplier of UAVs, missiles and sensors.
  Both suppliers are at war, which risks spares and delivery delays.
"""),
])

# ---------------------------------------------------------------------------
write("04_forecasting.ipynb", [
    md("""
# 04 · Forecasting monthly deaths, tested on withheld 2026 data

### Protocol (identical for every fold)
Models are fitted **once** on data up to December *Y − 1* and then **frozen**. Two questions are scored on Jan–Sep of year *Y*:

* **Track A – operational, 1 month ahead.** Each month the frozen model receives the newly observed month (no
  refit) and forecasts the next one. This is how an early-warning cell would use it.
* **Track B – strategic, 1–9 months ahead** from a single origin (Dec *Y − 1*), using nothing from year *Y*.

**Back-test folds** *Y* = 2022, 2023, 2024, 2025 are used for **all** design choices: features, the ablation,
ensemble membership and interval calibration. **2026 (provisional UCDP Candidate)** is the withheld test set,
scored once at the end.

### Models
| Model | Why it is here |
|---|---|
| Naive, seasonal naive, 3-month moving average | Benchmarks any model must beat |
| ETS (damped Holt, log) | Strong classical smoother for level shifts |
| SARIMA (AIC-selected per series, log) | Classical autocorrelation and seasonality |
| **LightGBM-Δ** (global, all four conflicts) | Learns the *change* in log deaths from 18 dynamic features; the Δ-target removes the tree-ceiling problem |
| LightGBM bottom-up (Tweedie, 222 sub-national series, summed) | Answers *where*, and gives a hierarchical forecast |
| **Ensemble** | Log-space mean of members chosen on the back-test |

Metrics: MAE, RMSE, MAPE (actual > 0), sMAPE, MASE, and **RMSLE**, which is our selection metric because the four
series differ by three orders of magnitude.
"""),
    code(SETUP),
    code("""from src import models as M
cm = pd.read_parquet(C.PROCESSED / "case_month.parquet")
am = pd.read_parquet(C.PROCESSED / "admin1_month.parquet")
fc = M.run_all(cm, am)          # 5 folds x 7 models (+ ensemble), ~1 minute
print("Ensemble members chosen on 2022-25 back-test:", fc["members"])"""),
    md("## 1. Design choices justified by ablation (back-test folds only)"),
    code("""abl = M.ablation(cm)
abl"""),
    md("""**Reading.** A plain LightGBM on the log *level* (A) is the **worst** ML option: trees cannot predict beyond
the range seen in training, so a model fitted before Feb 2022 can never forecast the invasion's death toll.
Predicting the **change** (B–E) fixes this. A compact feature set with robust loss (E) generalises best, because
four conflict series cannot support 40 features. Raw-count Tweedie (F) is poor at conflict level."""),
    md("## 2. Ensemble selection (back-test only)"),
    code("fc['ensemble_table'].head(10)"),
    md("## 3. Results"),
    code("""r = fc["rmsle"]
tab = r.assign(set=np.where(r.fold == 2026, "2026 holdout", "back-test")).groupby(["track", "model", "set"]).RMSLE.mean().unstack().round(3)
tab.sort_values(("2026 holdout") if False else "2026 holdout")"""),
    code("viz.fig_model_compare(fc['rmsle'])"),
    code("""sc = fc["scores"]
hold = sc[sc.fold == 2026]
for metric in ["MAE", "RMSE", "MAPE", "MASE"]:
    print(f"\\n2026 holdout - {metric} (Track A, 1 month ahead)")
    display(hold[hold.track == "A"].pivot_table(index="model", columns="conflict_case", values=metric).round(1))"""),
    code("""base = hold[(hold.track == "A") & (hold.model == "naive")].set_index("conflict_case").MAE
ens = hold[(hold.track == "A") & (hold.model == "ensemble")].set_index("conflict_case").MAE
(1 - ens / base).mul(100).round(1).rename("% MAE reduction vs naive, 2026, 1-month ahead").to_frame()"""),
    md("## 4. Forecast vs actual on the withheld months"),
    code("""for case in C.CASES:
    viz.fig_forecast_case(cm, fc["preds"], case, track="A", future=fc["future"]).show()"""),
    code("""for case in C.CASES:
    viz.fig_forecast_case(cm, fc["preds"], case, track="B").show()"""),
    md("## 5. Prediction intervals and reliability"),
    code("""p = fc["preds"]; e = p[p.model == "ensemble"]
cov = e.groupby(["fold", "track"]).apply(lambda g: pd.Series({
    "coverage_80": ((g.actual >= g.pi80_lo) & (g.actual <= g.pi80_hi)).mean(),
    "coverage_95": ((g.actual >= g.pi95_lo) & (g.actual <= g.pi95_hi)).mean(), "n": len(g)}))
cov.round(2)"""),
    code("""# directional reliability: did the forecast get the direction of change right (vs last observed month)?
a = e[e.track == "A"].sort_values(["conflict_case", "target_month"]).copy()
last = cm.set_index(["conflict_case", "month"]).deaths
a["last"] = [last.get((c, t - pd.DateOffset(months=1)), np.nan) for c, t in zip(a.conflict_case, a.target_month)]
a["dir_ok"] = np.sign(a.pred - a["last"]) == np.sign(a.actual - a["last"])
a.groupby("fold").dir_ok.mean().round(2).rename("direction accuracy (Track A)").to_frame()"""),
    code("""bias = e.groupby(["fold", "conflict_case"]).apply(lambda g: np.median(np.log1p(g.pred) - np.log1p(g.actual)))
bias.unstack().round(2)"""),
    md("""**Reading.**
* The 80% conformal intervals cover about **80–86%** of 2026 outcomes (target 80%), so they are well calibrated.
  The 95% upper tail is very wide by design: the back-test includes the 2022 invasion and the 2026 Gulf war, and
  that **outbreak risk** is real.
* Error is largest for US–Iran, whose 2026 war began with no build-up in the data. No model trained on monthly death
  counts can anticipate a decision to go to war, which is why we pair the forecast with sub-national escalation
  warning (notebook 05) and state this limit plainly.
* 2026 Candidate data are provisional and are usually revised **up**; the holdout error includes that revision noise."""),
    md("## 6. What drives the forecast (TreeSHAP)"),
    code("""from src.features import make_supervised
sup = M._prep_case(make_supervised(cm, ["conflict_case"], horizons=range(1, 10)))
X = sup[(sup.month >= "2015-01-01") & sup.target_y.notna()][M.CASE_FEATURES + ["case_cat"]]
imp = M.shap_importance(fc["models_by_fold"][2026][0], X)
display(imp.head(12))
viz.fig_shap(imp)"""),
    md("## 7. Forward forecast, Oct–Dec 2026 (all data, refitted)"),
    code("""f = fc["future"]
f[f.model == "ensemble"][["conflict_case", "target_month", "pred", "pi80_lo", "pi80_hi"]].round(0)"""),
])

# ---------------------------------------------------------------------------
write("05_early_warning_scorecard.ipynb", [
    md("""
# 05 · Sub-national escalation warning, threat scorecard and what-if scenarios
**Target:** an area *escalates* next month if its deaths are ≥ 10 **and** ≥ 1.5 × its trailing 3-month mean.
That is about 2–4% of area-months, a rare-event problem, so we report ROC-AUC, PR-AUC, Brier score and the
operational **precision of a top-10 watch-list** each month.

Folds: train on target months up to Dec *Y − 1*, test on Jan–Sep *Y*, for *Y* = 2023–2026. Features and
hyper-parameters were chosen on 2023–2025; 2026 is the withheld year.
"""),
    code(SETUP),
    code("""from src import models as M
am = pd.read_parquet(C.PROCESSED / "admin1_month.parquet")
cm = pd.read_parquet(C.PROCESSED / "case_month.parquet")
ew = M.early_warning_all(am)
ew["report"].round(3)"""),
    code("viz.fig_ew_curves(ew['preds'], fold=2026)"),
    code("""rep = ew["report"]; r26 = rep[rep.year == 2026].set_index("model")
lift = r26.precision_at_10 / r26.base_rate
lift.round(1).rename("lift of top-10 watch-list over random (2026)").to_frame()"""),
    code("""imp = M.shap_importance(ew["models"][2026], ew["preds"][ew["preds"].fold == 2026][M.EW_FEATURES])
viz.fig_shap(imp, title="What drives the escalation warning (mean |SHAP|)")"""),
    md("""**Reading.** On the withheld 2026 months the classifier ranks escalating areas with ROC-AUC ≈ 0.80, against
0.73 for the rule-of-thumb 'watch last month's deadliest areas'. Its top-10 list is about **3.5× better than random**.
The strongest signals are the area's own smoothed intensity, the *whole conflict's* tempo and how many areas are
active (spread), and the country's momentum: escalation is contagious within a theatre.

**So what.** This is an **I&W tasking tool**: it ranks where to point ISR and analysts next month. It is not a
prediction of decisions to go to war."""),
    md("## Live watch-list (scored on Sep 2026, for Oct 2026)"),
    code("""live = ew["live"]
live[~live.admin1.str.startswith("(")].head(15)[["conflict_case", "country_iso3", "admin1", "deaths", "base3",
                                                 "momentum_3v12", "p_escalation"]].round(3)"""),
    md("## Threat scorecard (RAG)"),
    code("""from src import insights
fut = pd.read_parquet(C.PROCESSED / "forecast_future.parquet")
th = insights.theatre_spread(insights.load("events"))
rag = M.rag_scorecard(cm, fut, live, th)
display(rag.round(2))
viz.fig_rag(rag)"""),
    md("""Rules (transparent, from model outputs only): **intensity** of the next-month forecast, **trend** against
the last 6 months, number of **hotspot** areas with escalation probability ≥ 15%, **spread** to more countries
than last year, and **volatility** (a ≥ 1,000-death month in the last year). RED = active high-intensity war or ≥ 5
points; AMBER = 2–4; GREEN ≤ 1."""),
    md("## What-if scenario: 'If Af–Pak violence rises 30% for three months, what does the model say?'"),
    code("""import joblib
art = joblib.load(C.ROOT / "models" / "models.joblib")
q = art["conformal"]
for shock in (0, 30, 100):
    sc = M.scenario_forecast(cm, "Afghanistan–Pakistan", shock, 3, art["m_case_full"], art["members"], q)
    print(f"shock {shock:+d}%:", sc[["target_month", "pred", "pi80_lo", "pi80_hi"]].round(0).to_dict("records"))"""),
])
print("notebooks written")
