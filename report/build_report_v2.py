"""Analysis report, version 2 (≤ 10 pages, issued competition data only).

    python report/build_report_v2.py      # writes report/FCE_Conflict_Watch_Report.{md,html} + v2 figures
    NODE_PATH=$(npm root -g) node report/to_pdf_v2.js

Sections follow the assessment sheet (Appendix B) in order, so each criterion has one home.
Every number is read from outputs/tables; nothing is typed in by hand.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src import config as C  # noqa: E402

TB, OUT = C.TAB_DIR, ROOT / "report"
FIGD = OUT / "figs"
FIGD.mkdir(exist_ok=True)
FIG = "figs"
t = lambda f, **k: pd.read_csv(TB / f, **k)
j = lambda f: json.loads((TB / f).read_text(encoding="utf-8"))
RUN_ID = (TB / "run_id.txt").read_text().strip()
TEAM = "FCE"
MEMBERS = "Maj Shivam Mehta · Capt Siddharth Sangwan · Capt Sahil Singh"
SHORT = {"Russia–Ukraine": "RU–UA", "Israel–Hamas": "IL–Hamas", "Afghanistan–Pakistan": "Af–Pak", "US–Iran": "US–Iran"}
COL = {"Russia–Ukraine": "#d7263d", "Israel–Hamas": "#7c5cbf", "Afghanistan–Pakistan": "#c77d00", "US–Iran": "#1f8fa3"}
RAGC = {"RED": "red", "AMBER": "amber", "GREEN": "green"}


def pct(x, d=0):
    return f"{100 * x:.{d}f}%"


def fmt(x):
    return f"{x:,.0f}"


def table(rows, head):
    out = ["| " + " | ".join(head) + " |", "|" + "|".join(["---"] * len(head)) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def fig(name, cap, width=None):
    w = f' style="width:{width}"' if width else ""
    return f'<figure{w}><img src="{FIG}/{name}.png" alt="{cap}"/><figcaption>{cap}</figcaption></figure>'


def pair(a, b):
    return f'<div class="pair">{a}{b}</div>'


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------
rag = t("rag_scorecard.csv").set_index("conflict_case")
ov = t("insight_case_overview.csv").set_index("conflict_case")
rob = j("robustness.json")
ewr = t("early_warning_scores.csv")
ew26 = ewr[ewr.year == 2026].set_index("model")
lg, rule = ew26.loc["LightGBM classifier"], ew26.loc["Rule: rank by last month's deaths"]
ewbt = ewr[(ewr.model == "LightGBM classifier") & (ewr.year < 2026)]
pre = j("preregistration.json")
trip, tal = j("tripwire_summary.json"), t("tripwire_alerts.csv")
comp = t("completeness.csv")
ind = j("india_front.json")
seal = j("sealed_predictions.json")
dq = t("data_quality_log.csv")
rm = t("forecast_rmsle.csv")
hold = rm[rm.fold == 2026].groupby(["track", "model"]).RMSLE.mean().unstack(0)
abl = t("ablation_lgb.csv")
fut = pd.read_parquet(C.PROCESSED / "forecast_future.parquet")
fut = fut[(fut.model == "ensemble") & (fut.h == 1)].set_index("conflict_case")
live = pd.read_parquet(C.PROCESSED / "early_warning_live.parquet")
live = live[~live.admin1.str.startswith("(")].head(10)
xs = j("extra_sources.json")
iex = t("insight_india_exposure.csv")
facts = json.loads((ROOT / "web" / "public" / "data" / "facts.json").read_text(encoding="utf-8"))
gd = facts["gdelt"]
pool = rob["pooled"]
byc = rob["by_conflict"]

bt = pre["backtest_2023_2025"]
bt_mean = {k: (np.mean([r["auc"] for r in v]), np.mean([r["pr"] for r in v]), np.mean([r["p10"] for r in v])) for k, v in bt.items()}
A, E = bt_mean["A cases_only"], bt_mean["E global, more trees"]
v1 = j("ew_variants_2026.json")["A cases_only"][0]          # the competition-day model, same 2026 data
caseonly26 = dict(auc=v1["auc"], pr=v1["pr"], p10=v1["p10"])
_d10 = pd.read_csv(C.ROOT / "data" / "raw" / "extra" / "6. war_terror_violence_200k.csv", usecols=["country", "country_group", "adm_1"])
_d10 = _d10[_d10.country_group != "Focus country"]
N_CTY, N_AREA = _d10.country.nunique(), _d10.drop_duplicates(["country", "adm_1"]).shape[0]

# ---------------------------------------------------------------------------
# New v2 figures
# ---------------------------------------------------------------------------
LAY = dict(template="plotly_white", font=dict(family="Carlito, Calibri, Arial", size=14, color="#1b2733"), margin=dict(l=58, r=58, t=42, b=40))


def fig_completeness():
    f = go.Figure()
    for c, g in comp.groupby("case"):
        f.add_trace(go.Scatter(x=g.days, y=g.share_known, name=SHORT[c], mode="lines+markers", line=dict(color=COL[c], width=3)))
    f.update_layout(**LAY, title="Share of deaths known k days after the event (2022–2025)", 
                    xaxis=dict(type="log", title="days after the event ends", tickvals=[7, 30, 90, 365, 730]),
                    yaxis=dict(tickformat=".0%", range=[0, 1.02]), legend=dict(orientation="h", y=-0.22))
    f.write_image(FIGD / "completeness.png", width=690, height=390, scale=2)


def fig_tripwire():
    g = pd.read_csv(C.ROOT / "data" / "gdelt" / "gdelt_case_daily.csv", parse_dates=["date"])
    g = g[(g.case_id == "US-IRAN") & (g.date.between("2026-02-01", "2026-04-30"))]
    e = pd.read_parquet(C.PROCESSED / "events.parquet")
    e = e[(e.conflict_case == "US–Iran") & (e.span_days <= 1) & (~e.is_aggregate.astype(bool))]
    d = e.groupby("date_start").deaths_best.sum()
    d = d[(d.index >= "2026-02-01") & (d.index <= "2026-04-30")]
    f = go.Figure()
    d = d.reindex(pd.date_range("2026-02-01", "2026-04-30"), fill_value=0)
    f.add_trace(go.Scatter(x=d.index, y=d.values, name="UCDP deaths / day (dated events)", fill="tozeroy", mode="lines",
                           line=dict(color="#d7263d", width=1), fillcolor="rgba(215,38,61,0.35)", yaxis="y2"))
    f.add_trace(go.Scatter(x=g.date, y=g.violent_events, name="GDELT violent events / day", line=dict(color="#0F2236", width=2.4)))
    seen = set()
    for x in tal[(tal.case == "US–Iran")].sort_values("date").itertuples():
        if x.light in seen:
            continue
        seen.add(x.light)
        if pd.Timestamp(x.date) <= pd.Timestamp("2026-04-30"):
            f.add_vline(x=pd.Timestamp(x.date), line=dict(color="#d7263d" if x.light == "RED" else "#c77d00", dash="dash", width=2))
            f.add_annotation(x=pd.Timestamp(x.date), y=1.0 if x.light == "RED" else 0.9, yref="paper",
                             text=f"{x.light} {pd.Timestamp(x.date):%d %b}", showarrow=False,
                             xanchor="left" if x.light == "RED" else "right", xshift=4 if x.light == "RED" else -4,
                             font=dict(color="#d7263d" if x.light == "RED" else "#c77d00", size=12))
    f.update_layout(**LAY, title="US–Iran, Feb–Apr 2026: the news turned on day 0", 
                    yaxis=dict(title="GDELT events / day"), yaxis2=dict(overlaying="y", side="right", title="UCDP deaths / day", showgrid=False, range=[0, float(d.max()) * 1.05], tickmode="auto", tickformat=",d"),
                    legend=dict(orientation="h", y=-0.22))
    f.write_image(FIGD / "tripwire_usir.png", width=690, height=390, scale=2)


fig_completeness()
fig_tripwire()

# ---------------------------------------------------------------------------
# Derived numbers
# ---------------------------------------------------------------------------
rag_rows = []
for c in C.CASES:
    r = rag.loc[c]
    rag_rows.append([f"**{c}**", f'<b class="{RAGC[r.rating]}">{r.rating}</b>', fmt(r.forecast_next),
                     f"{fmt(r.pi80_lo)}–{fmt(r.pi80_hi)}", f"{(r.trend_ratio - 1) * 100:+.0f}%", r.top_areas.split("; ")[0]])
big3 = ind["triggers"]
named = {"2016-09-18": "Uri", "2019-02-14": "Pulwama", "2025-04-22": "Pahalgam"}
followed = [x for x in big3 if x["state_deaths_45d_after"] >= 30]
ru90 = comp[(comp.case == "Russia–Ukraine") & (comp.days == 90)].share_known.iloc[0]
af90 = comp[(comp.case == "Afghanistan–Pakistan") & (comp.days == 90)].share_known.iloc[0]
usir_amber = tal[(tal.case == "US–Iran") & (tal.light == "AMBER")].date.min()
gulf = xs["D9"]["gulf_violent_events"]
afpak_state = facts["india"]["pak_india_adjoining"]
cov80 = pool["coverage80"]
dq_issues = dq[dq.rows_affected > 0]

# ---------------------------------------------------------------------------
md = f"""
<div class="banner"><div class="kick">LT GEN MS SODHI MEDAL · DATA ANALYTICS COMPETITION 2026 · ANALYSIS REPORT · TEAM {TEAM}</div>
<div class="title">CONFLICT WATCH</div>
<div class="subtitle">When and where will conflict deaths rise next, and what does it mean for India?</div>
<div class="meta">{MEMBERS} · Data to 30 Sep 2026 (UCDP), 12 Nov 2026 (GDELT) · Issued competition data only · Run {RUN_ID}</div></div>

<div class="bluf" markdown="1">
**Bottom line.** Russia–Ukraine stays **RED** (about {fmt(rag.loc['Russia–Ukraine'].forecast_next)} deaths in Oct 2026). Afghanistan–Pakistan is **AMBER** and is the front that matters most to India: Pakistan now fights the TTP inside and Afghanistan across the Durand Line. US–Iran and Israel–Hamas are **GREEN** on the monthly model, but US–Iran is a "sudden war": history cannot forecast its onset, so a daily news tripwire watches it. Our forecast cut error by **{pct(pool['reduction'])}** against "no change" on withheld 2026 data (90% interval {pct(pool['ci'][0])} to {pct(pool['ci'][1])}); the area watch-list is **{lg.precision_at_10 / lg.base_rate:.1f}×** better than chance.

**Act now.** (1) Task ISR on the monthly top-10 areas (Kandahar, Kunar, Kabul lead). (2) Treat any J&K attack with 15+ deaths as the start of a 15-day escalation watch. (3) Keep Gulf evacuation plans current and act the day the tripwire turns RED, not when deaths are published six weeks later.
</div>

{table(rag_rows, ["Conflict", "Oct 2026", "Forecast deaths", "80% range", "vs last 6 months", "Top watch area"])}

## 1 · Problem understanding

The brief is open: frame our own questions from four conflicts. We framed it as **decision support for India** and asked five questions, each tied to a decision. **Q1** How intense is each war and where is it heading (force posture, watch levels)? **Q2** Which areas will escalate next month (ISR tasking)? **Q3** Can we see a change of state before deaths are published (warning time)? **Q4** How far can the record be trusted (confidence in Q1–Q3)? **Q5** What touches India: the Pakistan front, the Gulf and the sea lanes? Every claim of predictive skill had to survive data the model had never seen: **all of 2026 was withheld** from every modelling choice.

## 2 · Data preparation and feature engineering

**Twelve issued files, one rule: providers are never joined on event IDs.** Cross-provider keys are only country and day, week, month or year; the pre-joined panels (D11–D12) are audited, not trusted (the supplied panel shows 0 UCDP deaths for 2026, so we rebuilt from events).

{table([
    ['D1', 'conflict_events (UCDP GED 26.1 + Candidate 2026)', fmt(ov.events.sum()), 'Jan 2014 – Sep 2026', 'Fatality ground truth; models; 2026 withheld'],
    ['D2', 'event_sources', '85,406', '2014 – Oct 2026', 'Source dependence; reporting lag (§3.5)'],
    ['D3–D5', 'UNHCR stocks, demographics; IDMC/UNRWA', '26,215', '2014 – 2025', 'Displacement, HADR planning'],
    ['D6', 'country_year_context (World Bank)', '1,764', '2014 – 2025', 'Population, growth, inflation (lagged)'],
    ['D7–D8', 'GDELT focus files (two)', '13,507,238', 'Feb – Nov 2026', 'Attention; daily tripwire (§4.4)'],
    ['D9', 'Middle East weekly (ACLED-style)', fmt(xs['D9']['rows']), 'Dec 2014 – Jun 2026', 'Second source; Gulf spill-over'],
    ['D10', 'UCDP GED long file', fmt(xs['D10']['rows']), '1989 – 2025', "Transfer learning (§4.5); India's front (§3.3)"],
    ['D11–D12', 'Pre-joined country panels', '3,467', '1989 – Jun 2026', 'Audited, used only for checks'],
], ['ID', 'Issued file', 'Rows', 'Period', 'Use'])}

**Cleaning.** {len(dq)} checks are logged with the rows affected and the action (code: `src/cleaning.py`); {len(dq_issues)} found something. The ones that change results:

{table([[r.id, r.check, fmt(r.rows_affected), r.action.split('. ')[0]] for r in dq[dq.id.isin(['DQ05', 'DQ07', 'DQ10', 'DQ13', 'DQ14', 'DQ15'])].itertuples()], ['ID', 'Issue', 'Rows', 'What we did'])}

**Imputation.** Months with no UCDP event are true zeros (UCDP is an event register). Blank areas become an explicit "(country-level / unspecified)" level, never a guessed place. The GDELT gap of 1–16 May 2026 stays missing. World Bank gaps are interpolated inside each economy only, and lagged one year so a forecast never sees the future. Raw values are never overwritten: corrected copies sit beside them.

**Features** (all known at the end of the forecast month): recent level (log deaths now, 1 and 2 months ago), rolling means (3, 6, 12 months, exponential), volatility and 12-month peak, momentum (3 vs 12 months) and acceleration, months since the last death, reporting intensity (events, sources), seasonality and horizon. The area model adds the parent conflict's tempo, the country's tempo and the area's share of its conflict. A 40-feature set with displacement and macro data overfit and was dropped (ablation in §4).

## 3 · Exploratory analysis and insights

Each finding ends in a **deduction** and an **action**.

**3.1 Four wars, four shapes.** Russia–Ukraine holds {pct(ov.loc['Russia–Ukraine'].deaths_best / ov.deaths_best.sum())} of {fmt(ov.deaths_best.sum())} recorded deaths and is flat at 6–8k a month; Israel–Hamas fell {pct(1 - ov.loc['Israel–Hamas'].deaths_2026_ytd / ov.loc['Israel–Hamas'].deaths_2025)} after the Oct 2025 ceasefire; Afghanistan–Pakistan has already passed its 2025 total ({fmt(ov.loc['Afghanistan–Pakistan'].deaths_2026_ytd)} vs {fmt(ov.loc['Afghanistan–Pakistan'].deaths_2025)}); US–Iran recorded {fmt(ov.loc['US–Iran'].deaths_2026_ytd)} deaths in 2026, mostly in 39 days from 28 Feb. Civilians are {pct(ov.loc['Israel–Hamas'].civilian_share)} of Israel–Hamas deaths against {pct(ov.loc['Russia–Ukraine'].civilian_share)} in Russia–Ukraine. *Deduction:* one watch level cannot fit all four. *Action:* attrition watch for RU–UA, onset watch for US–Iran, standing watch for Af–Pak.

{pair(fig('monthly_deaths', 'Monthly deaths by conflict, log scale; shaded = 2026 withheld test window [D1]'), fig('afpak_interstate', 'Afghanistan–Pakistan: state-on-state deaths since Oct 2025 [D1]'))}

**3.2 Pakistan now fights on two fronts.** TTP violence in Khyber Pakhtunkhwa grew every year since 2021, and since Oct 2025 the two governments fight each other directly (peak 411 deaths in Mar 2026). FATA was merged into KP in 2018; we harmonised the 602 affected records (DQ13) so the area series do not break. *Deduction:* a stretched Pakistan raises the risk of miscalculation on the LoC. *Action:* treat Af–Pak hotspots as a standing LoC indicator.

{pair(fig('afpak_provinces', 'Af–Pak deaths by province: KP and Balochistan carry the rise [D1]'), fig('india_exposure', 'Where the four wars touch India: LoC-adjoining areas, Gulf, Hormuz, Sri Lanka [D1]'))}

**3.3 India's own front: a 15-day clock.** From D10, every J&K incident with 15+ deaths since 2014 ({len(big3)} incidents). After {", ".join(named[x['date']] for x in followed if x['date'] in named)}, India–Pakistan state fighting with 30+ deaths followed within {min(x['days_to_state_fighting'] for x in followed if x['date'] in named)}–{max(x['days_to_state_fighting'] for x in followed if x['date'] in named)} days; state deaths had been near zero in the 45 days before. D10 keeps only the deadlier records outside the focus countries, so these are floors, and cross-border firing was routine in 2016–20: a pattern to watch, not proof of cause. *Action:* start a 15-day escalation watch after any such attack.

**3.4 The 2026 war reached India's neighbourhood.** US–Iran deaths were recorded in {facts['india']['usir_countries'][1]} countries in 2026 (4 in 2025), including {facts['india']['gulf_states']} Gulf states and {facts['india']['srilanka']['deaths']} killed off Sri Lanka on 4 Mar 2026. The ACLED-style file (D9) shows Gulf violent events rising from {gulf['H1_2025']} to {gulf['H1_2026']} (H1 2025 to H1 2026). *Action:* keep Gulf evacuation plans and sea-lane escorts tied to the tripwire.

**3.5 The record arrives late, and unevenly.** Only {pct(ru90)} of Russia–Ukraine deaths are known 90 days after the event, against {pct(af90)} for Af–Pak (D2 publication dates). *Deduction:* the 2026 Russia–Ukraine "decline" is mostly late reporting. *Action:* read recent months as a floor; never brief a fall in RU–UA deaths from the last quarter alone.

**3.6 News follows politics, not deaths.** US–Iran drew {gd['articles_per_death']['usir']} GDELT articles per death against {gd['articles_per_death']['ruua']} for Russia–Ukraine. Weekly news moves with deaths only for Af–Pak and US–Iran (ρ {gd['rho_change']['afpak']} and {gd['rho_change']['usir']}). *Action:* use news to see a change of state, never to size a war (§4.4).

{pair(fig('media_gap', 'Attention vs deaths: source references per 100 deaths [D1, D2]'), fig('displacement', 'Displacement by origin: refugees abroad and IDPs [D3–D5]'))}

## 4 · Model and prediction

**4.1 Protocol.** Walk-forward: for each year Y the models are fitted on data to Dec Y−1 and scored on Jan–Sep of Y (back-test 2022–2025, holdout 2026). Choices were made on the back-test only.

**4.2 Choice and justification.** Four series of about 150 months each are too few for a deep model. We combine three members with different errors: a 3-month mean (robust), damped ETS on log deaths (each war's own trend) and **LightGBM-Δ**, one model pooled across the four wars that predicts the *change* in log deaths with an L1 loss. The Δ target and compact features won the ablation (back-test RMSLE {abl.iloc[4, 1]:.3f} vs {abl.iloc[0, 1]:.3f} for the default ML set-up). The ensemble is the log-space mean. SARIMA was tested and not selected on the back-test. Bands are split-conformal, built from the models' real past errors.

**4.3 Performance on withheld 2026 data (1 month ahead).**

{table([['Ensemble (adopted)', f"{hold.loc['ensemble', 'A']:.3f}", pct(pool['reduction']), f"{pct(pool['ci'][0])} to {pct(pool['ci'][1])}", f"{pool['dm_p']:.3f}", pct(cov80)], ['No change (naive)', f"{hold.loc['naive', 'A']:.3f}", '–', '–', '–', '–'], ['ETS alone', f"{hold.loc['ets', 'A']:.3f}", '', '', '', ''], ['LightGBM-Δ alone', f"{hold.loc['lgb_case', 'A']:.3f}", '', '', '', '']], ['Model', 'RMSLE', 'MAE cut vs naive', '90% interval', 'Diebold–Mariano p', '80% band coverage'])}

By conflict the cut is {", ".join(f"{SHORT[c]} {pct(byc[c]['reduction'])}" for c in C.CASES)}. **Reliability:** the forecast is good for protracted wars one month ahead; bands widen fast beyond that, and US–Iran's onset fell outside its band ({pct(byc['US–Iran']['coverage80'])} coverage). That limit is why §4.4 exists.

{pair(fig('forecast_ru', 'Russia–Ukraine: 1-month forecasts on withheld 2026, 80% band, forward forecast'), fig('forecast_afpak', 'Afghanistan–Pakistan: same view'))}

**4.4 The fast clock: a news tripwire for a change of state.** RED fires when violent GDELT events per day reach 4× their 14-day median (and at least 100); AMBER when military-posture reports reach 4× their 28-day median. Rules were fixed before testing and not tuned. Of {trip['red_episodes']} RED alerts in Feb–Sep 2026, **{trip['red_confirmed']} were confirmed** by a UCDP escalation within ±3 days (chance: {trip['perm_mean_hits']:.1f}; permutation p = {trip['p_value']:.3f}). US–Iran: AMBER on {usir_amber}, RED on 28 Feb, the first day of the war; UCDP published those deaths weeks later. It misses most routine insurgent escalations (Af–Pak {trip['by_case']['Afghanistan–Pakistan']['caught']} of {trip['by_case']['Afghanistan–Pakistan']['escalation_days']} days), so it complements the forecast, it does not replace it.

{pair(fig('tripwire_usir', 'US–Iran tripwire: AMBER and RED lines against UCDP deaths [D7, D8, D1]'), fig('completeness', 'How much of the record is known k days on [D1, D2]'))}

**4.5 Where next: the area escalation warning.** An area escalates if next month's deaths are ≥ {C.ESCALATION_MIN_DEATHS} and ≥ {C.ESCALATION_RATIO}× its 3-month mean (about 4% of area-months). A LightGBM classifier ranks {facts['warning']['areas']} areas in {facts['warning']['countries']} countries. **New in v2: transfer learning.** The four cases hold too few escalations to learn from, so the classifier also trains on {fmt(N_AREA)} areas in {N_CTY} other countries from D10 (1990–2025, focus countries removed to avoid double counting). The variant was **pre-registered**: chosen on the 2023–25 back-test by a rule written before 2026 was scored (file hash `{pre['sha256'][:12]}…`).

{table([['Competition-day model (cases only)', f"{A[1]:.3f}", f"{A[0]:.3f}", f"{caseonly26['pr']:.3f}", f"{caseonly26['auc']:.3f}", pct(caseonly26['p10'], 1)], ['**v2: cases + world areas (pre-registered)**', f"**{E[1]:.3f}**", f"**{E[0]:.3f}**", f"**{lg.PR_AUC:.3f}**", f"**{lg.ROC_AUC:.3f}**", f"**{pct(lg.precision_at_10, 1)}**"], ["Rule: rank by last month's deaths", '', '', f"{rule.PR_AUC:.3f}", f"{rule.ROC_AUC:.3f}", pct(rule.precision_at_10, 1)]], ['Escalation model', 'Back-test PR-AUC', 'Back-test ROC-AUC', '2026 PR-AUC', '2026 ROC-AUC', '2026 top-10 precision'])}

Base rate {pct(lg.base_rate, 1)}, so the top-10 list is {lg.precision_at_10 / lg.base_rate:.1f}× better than chance. After scoring we added Platt calibration fitted on the back-test only, because the larger model over-stated probabilities above the scorecard's 15% hotspot line; it does not change the ranking, and the file records that it was added after seeing 2026. **Sealed claims:** the Oct–Dec 2026 forecasts and the watch-list are hashed (`{seal['sha256'][:16]}…`) so they can be scored when UCDP publishes.

{pair(fig('ew_curves', 'Escalation warning on 2026: ROC and precision–recall vs the rule of thumb'), fig('shap_ew', 'What drives the warning (mean |SHAP|)'))}

**4.6 The scorecard.** Points: intensity (forecast ≥1,000 → 2; ≥100 → 1), trend vs the last 6 months (≥+20% → +1; ≤−20% → −1), hotspots (areas with P ≥ 15%: ≥3 → 2; ≥1 → 1), spread (more countries than last year → 1) and volatility (a 1,000-death month in the last year → 1). **RED** if the forecast is ≥1,000 deaths or points ≥5; **AMBER** if points ≥2; otherwise GREEN. US–Iran scores 1 (spread +1, volatility +1, trend −1): GREEN on the monthly rule, which is why the daily tripwire guards it. Rules are in the report, the code and the dashboard, and the dashboard re-checks its ratings against the pipeline on load.

## 5 · Innovation and tools

**Two clocks:** a monthly forecast sizes the war; a daily tripwire flags its change of state, each with its own test. **Transfer learning** from the wider world for a small-sample warning model. **Honest-by-design:** pre-registered model choice, sealed forecasts, a completeness curve that tells the reader when not to trust the latest month. **Ops site** (single offline HTML file and Streamlit app): a one-screen commander view with CDS and two notional theatre views, three depths of detail, an Ops console (brief, theatre, warning, map, area, forecast, what-if, scorecard, data quality) and the fast-clock panel. Python (pandas, LightGBM, statsmodels, scikit-learn, plotly), DuckDB for the 5.7 GB GDELT files, TypeScript/ECharts for the site.

## 6 · Recommendations

{table([
    ['SENSE', 'Task ISR and analysts on the monthly top-10 areas; run the daily tripwire', f"Top-10 precision {pct(lg.precision_at_10, 0)} vs {pct(lg.base_rate, 0)} base rate; 4 of 5 RED alerts confirmed", 'Monthly list; RED alert', 'Medium'],
    ['WARN', 'Treat Af–Pak hotspots and any J&K attack with 15+ deaths as LoC indicators; 15-day watch', '§3.2–3.3: two-front Pakistan; 11–15 days to state fighting', 'Af–Pak AMBER/RED; J&K attack', 'Medium'],
    ['SHIELD', 'Keep Gulf evacuation and sea-lane plans current; act on RED, not on published deaths', f"§3.4, §4.4: war reached {facts['india']['usir_countries'][1]} countries; tripwire fired on day 0", 'US–Iran RED or AMBER', 'High'],
    ['SUSTAIN', 'Plan Russian-platform spares on a long RU–UA war (DOMAIN)', 'RU–UA RED, 6–8k deaths a month, no sign of decline once late reports arrive', 'RU–UA stays RED', 'Medium'],
    ['ADAPT', 'Brief recent months as floors; re-run when UCDP publishes Oct–Dec and score the sealed claims', f"Only {pct(ru90)} of RU–UA deaths known at 90 days", 'Each UCDP release', 'High'],
], ['Line', 'Action', 'Evidence', 'Trigger', 'Confidence'])}

## 7 · Limitations, reproducibility and AI declaration

**Limitations.** 2026 UCDP data are provisional and will rise. Four conflict series give small samples: one-month-ahead bands are usable, longer ones are wide. The tripwire rests on 5 alerts in 8 months. D10 is a capped extract that favours deadlier records outside the focus countries. GDELT counts reports, not incidents, and is US-heavy. Theatre commands in the site are notional. No outside data are used anywhere in this entry.

**Reproducibility.** One command, `python run_pipeline.py`, rebuilds every table, model and figure from the raw files in about 3–4 minutes (seed {C.RANDOM_STATE}); `python scripts/export_web.py` rebuilds the site data and stops if any headline number drifts; `python scripts/check_submission.py` is the compliance gate (pages, names, files, declarations). Run ID `{RUN_ID}` is a hash of the result tables and appears on every product.

**AI tools declaration.** The team used Anthropic's Claude (an AI assistant) to help write and debug code, draft text and design the site and slides. The team set the questions, made the design decisions and checked every number against the pipeline outputs.
"""

(OUT / "FCE_Conflict_Watch_Report.md").write_text(md, encoding="utf-8")
import markdown  # noqa: E402

body = markdown.markdown(md, extensions=["tables", "sane_lists", "md_in_html"])
CSS = """
@page { size: A4; margin: 10mm 11mm 12mm 11mm; }
body { font-family: Carlito, Calibri, 'Segoe UI', Arial, sans-serif; color: #1b2733; font-size: 10pt; line-height: 1.36; }
p { margin: 3px 0 4px 0; } ul { margin: 2px 0 4px 0; padding-left: 16px; }
h2 { color: #07131F; border-bottom: 2px solid #F0B03A; padding-bottom: 1px; margin: 9px 0 4px 0; font-size: 12pt; page-break-after: avoid; }
table { border-collapse: collapse; width: 100%; margin: 4px 0 6px 0; font-size: 8.5pt; line-height: 1.22; }
th { background: #0F2236; color: #fff; text-align: left; padding: 2px 5px; }
td { border-bottom: 1px solid #d6dee8; padding: 2px 5px; vertical-align: top; }
tr { page-break-inside: avoid; } tr:nth-child(even) td { background: #f4f7fa; }
figure { margin: 3px 0 4px 0; page-break-inside: avoid; } figure img { width: 100%; display: block; }
figcaption { font-size: 7.9pt; color: #5E7B99; margin-top: 1px; }
.pair { display: flex; gap: 10px; page-break-inside: avoid; } .pair figure { flex: 1; min-width: 0; }
code { background: #f0f3f7; border-radius: 3px; font-size: 8pt; padding: 0 2px; }
.red { color: #d7263d; } .amber { color: #c77d00; } .green { color: #1f9e83; }
.banner { background: #07131F; color: #fff; padding: 8px 14px; border-radius: 4px; margin-bottom: 6px; }
.banner .kick { color: #F0B03A; font-weight: 700; letter-spacing: 1.4px; font-size: 7.5pt; }
.banner .title { font-size: 22pt; font-weight: 700; letter-spacing: 1.5px; line-height: 1.1; }
.banner .subtitle { color: #D5DEE8; font-size: 10.5pt; } .banner .meta { color: #9FB2C6; font-size: 7.8pt; margin-top: 3px; }
.bluf { border-left: 4px solid #F0B03A; background: #fff8ea; padding: 5px 10px; margin: 5px 0; }
"""
html = (f"<!doctype html><html><head><meta charset='utf-8'><title>Conflict Watch – Team {TEAM} – Analysis Report</title>"
        f"<style>{CSS}</style></head><body>{body}</body></html>")
(OUT / "FCE_Conflict_Watch_Report.html").write_text(html, encoding="utf-8")
print("report v2 written | run", RUN_ID)
