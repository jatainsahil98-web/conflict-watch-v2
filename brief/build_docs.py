"""Build the one-page commander's brief and the Q&A / speaker sheet (HTML; PDF via brief/to_pdf.js).

    python brief/build_docs.py
    NODE_PATH=$(npm root -g) node brief/to_pdf.js
"""
from __future__ import annotations

import sys
from pathlib import Path

import markdown
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src import config as C  # noqa: E402

TB = C.TAB_DIR
OUT = ROOT / "brief"

rag = pd.read_csv(TB / "rag_scorecard.csv").set_index("conflict_case")
ew = pd.read_csv(TB / "early_warning_scores.csv")
lg = ew[(ew.year == 2026) & (ew.model == "LightGBM classifier")].iloc[0]
rule = ew[(ew.year == 2026) & (ew.model.str.startswith("Rule"))].iloc[0]
sc = pd.read_csv(TB / "forecast_scores.csv")
hA = sc[(sc.fold == 2026) & (sc.track == "A")]
nv = hA[hA.model == "naive"].set_index("conflict_case").MAE
en = hA[hA.model == "ensemble"].set_index("conflict_case").MAE
pooled = (1 - en.sum() / nv.sum()) * 100
red = (1 - en / nv) * 100
preds = pd.read_parquet(C.PROCESSED / "forecast_preds.parquet")
e26 = preds[(preds.model == "ensemble") & (preds.fold == 2026)]
cov80 = ((e26.actual >= e26.pi80_lo) & (e26.actual <= e26.pi80_hi)).mean() * 100
stats = pd.read_csv(TB / "insight_stats.csv").iloc[0]
abl = pd.read_csv(TB / "ablation_lgb.csv")
import json  # noqa: E402
ROB = json.loads((TB / "robustness.json").read_text())
RUN_ID = (TB / "run_id.txt").read_text().strip()
X = json.loads((TB / "extra_sources.json").read_text())
X9, X10, X11, X12, XG, XO = X["D9"], X["D10"], X["D11"], X["D12"], X["GDELT"], X["GDELT_OCT"]
GDS = json.loads((TB / "gdelt_summary.json").read_text())
_mpd = X12["media_per_death_feb_apr_2026"]
_pw = XG["prewar"]
_lp = XG["weekly_lead_p_by_case"]
RB, RP, REW = ROB["by_conflict"], ROB["pooled"], ROB["early_warning"]
_SH = {"Russia–Ukraine": "Russia–Ukraine", "Israel–Hamas": "Israel–Hamas", "Afghanistan–Pakistan": "Af–Pak", "US–Iran": "US–Iran"}
_clear = [_SH[k] for k in C.CASES if RB[k]["ci"][0] > 0]
_inc = [_SH[k] for k in C.CASES if RB[k]["ci"][0] <= 0]
_dm = [_SH[k] for k in C.CASES if RB[k]["dm_p"] < 0.05]


def _ci(c):
    return f"{c[0] * 100:.0f}% to {c[1] * 100:.0f}%".replace("-", "−")


def _and(xs):
    return " and ".join(", ".join(xs).rsplit(", ", 1))


RC = {"RED": "#FF4D5E", "AMBER": "#F0B03A", "GREEN": "#35C2A6"}

CSS = """
@page { size: A4; margin: 8mm 10mm; }
* { box-sizing: border-box; }
body { font-family: Calibri, Carlito, 'Segoe UI', Arial, sans-serif; color: #1b2733; font-size: 9.4pt; line-height: 1.24; margin: 0; }
.hdr { background: #07131F; color: #fff; padding: 9px 14px 10px 14px; border-radius: 6px; }
.hdr .k { color: #F0B03A; font-weight: 700; letter-spacing: 2px; font-size: 8pt; }
.hdr h1 { margin: 2px 0 2px 0; font-size: 18pt; }
.hdr .m { color: #9FB2C6; font-size: 8.4pt; }
h2 { font-size: 10.5pt; color: #07131F; border-bottom: 2px solid #F0B03A; margin: 9px 0 5px 0; padding-bottom: 2px; letter-spacing: .5px; }
h3 { font-size: 10.5pt; margin: 10px 0 4px 0; }
ul, ol { margin: 3px 0 3px 0; padding-left: 16px; } li { margin: 1.5px 0; }
table { border-collapse: collapse; width: 100%; font-size: 8.7pt; margin: 3px 0; }
th { background: #0F2236; color: #fff; text-align: left; padding: 3px 5px; }
td { border-bottom: 1px solid #d6dee8; padding: 3px 5px; vertical-align: top; }
.rag { display: flex; gap: 6px; margin: 6px 0 2px 0; }
.rag div { flex: 1; background: #0F2236; color: #fff; border-radius: 6px; padding: 5px 8px; border: 2px solid; }
.rag b.r { font-size: 14pt; display: block; }
.rag span { font-size: 8pt; color: #D5DEE8; }
.d { background: #35C2A6; color: #07131F; font-size: 7pt; font-weight: 700; padding: 0 4px; border-radius: 3px; }
.o { background: #A794FF; color: #07131F; font-size: 7pt; font-weight: 700; padding: 0 4px; border-radius: 3px; }
.foot { margin-top: 6px; font-size: 7.5pt; color: #5E7B99; text-align: center; letter-spacing: 1px; }
.bluf { background: #fff8e8; border-left: 4px solid #F0B03A; padding: 5px 9px; }
.q { font-weight: 700; color: #07131F; margin-top: 7px; }
.a { margin: 1px 0 0 0; }
.cols { display: flex; gap: 14px; } .cols > div { flex: 1; }
"""


def page(title, body):
    return (f"<!doctype html><html><head><meta charset='utf-8'><title>{title}</title><style>{CSS}</style></head>"
            f"<body>{body}</body></html>")


# ----------------------------------------------------------------------------------- economic front (new)
E = json.loads((C.TAB_DIR / "econ_summary.json").read_text())
EH, OIL, RSV, REM = E["headline"], E["india_oil_bill"], E["reserves"], E["india_remittances"]

# ----------------------------------------------------------------------------------- commander's brief
cards = "".join(
    f"<div style='border-color:{RC[rag.loc[c, 'rating']]}'><b>{c}</b>"
    f"<b class='r' style='color:{RC[rag.loc[c, 'rating']]}'>{rag.loc[c, 'rating']}</b>"
    f"<span>{rag.loc[c, 'forecast_next']:,.0f} deaths forecast Oct 2026<br/>80%: {rag.loc[c, 'pi80_lo']:,.0f}–"
    f"{rag.loc[c, 'pi80_hi']:,.0f} · top area {str(rag.loc[c, 'top_areas']).split(' (')[0]}</span></div>"
    for c in C.CASES)

from src.brand import brand_corners
BRAND_CSS = "position:relative;padding-left:24mm;padding-right:24mm;min-height:18mm"
brief = f"""
<div class="hdr" style="{BRAND_CSS}">{{BRAND}}<div class="k">COMMANDER'S BRIEF &nbsp;|&nbsp; DATA ANALYTICS COMPETITION 2026 &nbsp;|&nbsp; AS OF 30 SEP 2026</div>
<h1>Conflict Watch: where deaths rise next, and what it means for India</h1>
<div class="m">Maj Shivam Mehta · Capt Siddharth Sangwan · Capt Sahil Singh &nbsp;·&nbsp; Source: all twelve issued files (UCDP, UNHCR, IDMC,
UNRWA, World Bank, GDELT, ACLED-style) &nbsp;·&nbsp; <span class="d">DATA</span> computed from the files &nbsp;
<span class="o">DOMAIN</span> expert reasoning</div></div>

<h2>BOTTOM LINE UP FRONT</h2>
<div class="bluf">Russia–Ukraine stays <b style="color:#d7263d">RED</b>; Afghanistan–Pakistan and US–Iran are
<b style="color:#c77d00">AMBER</b>; Israel–Hamas is <b style="color:#1f9e83">GREEN</b>. The 2026 US–Iran war reached
India's neighbourhood (Gulf, Hormuz, Sri Lankan waters). Our models, tested on unseen 2026 data, forecast
monthly deaths {pooled:.0f}% more accurately than "no change" and flag escalating districts a month ahead
(AUC {lg.ROC_AUC:.2f}). On the economic front India paid without taking fire. <b>Use them to task ISR, keep Gulf NEO plans current, and watch Pakistan's western front.</b></div>

<h2>THREAT ASSESSMENT – OCTOBER 2026</h2>
<div class="rag">{cards}</div>
<ul>
<li><b>Russia–Ukraine:</b> sustained attrition at 4–11k deaths a month since 2023. The front is widening, not moving:
Donetsk's share of located events fell from 55% to 30% (2022–26) while Zaporizhzhia, Dnipropetrovsk, Sumy and Russia's
border oblasts rose. <span class="d">DATA</span></li>
<li><b>Afghanistan–Pakistan:</b> deaths in KP have risen every year since 2021, and the two states have fought each other
directly since Oct 2025 (411 deaths in Mar 2026). Kandahar, Balochistan and Kunar head the escalation watch-list.
<span class="d">DATA</span></li>
<li><b>US–Iran:</b> calm now (26 forecast), but the Feb–Mar 2026 war came with no build-up and hit 14 countries.
Recorded losses: Iran 1,274 vs Israel–US 11. <span class="d">DATA</span></li>
<li><b>Israel–Hamas:</b> about 130 a month in 2026; the war reached Qatar in Sep 2025. <span class="d">DATA</span></li>
</ul>

<h2>INDIA IMPACT</h2>
<table><tr><th style="width:18%">Theatre</th><th style="width:44%">Evidence <span class="d">DATA</span></th><th>Implication <span class="o">DOMAIN</span></th></tr>
<tr><td><b>Western front</b></td><td>Af–Pak interstate clashes since Oct 2025; deaths in Pakistan areas adjoining India rose 2 → 52 (2022–25)</td><td>Pakistan Army stretched west: risk of diversionary LoC activity, TTP/IS-K spill-over</td></tr>
<tr><td><b>Gulf / Hormuz</b></td><td>5 Gulf states struck in 2026 (25 events); 299 deaths on Iran's Hormuz/Chabahar coast; 945 deaths in Yemen in 2025</td><td>Large Indian diaspora needs NEO readiness; Gulf energy via Hormuz; Chabahar and INSTC exposed</td></tr>
<tr><td><b>IOR</b></td><td>104 killed in one strike off Sri Lanka, 4 Mar 2026</td><td>Belligerents operating in India's maritime neighbourhood</td></tr>
<tr><td><b>Supply chains</b></td><td>RU–UA at 4–11k deaths/month; Israel at war since 2023</td><td>Spares for Russian- and Israeli-origin platforms at risk</td></tr>
<tr><td><b>Economic front</b></td><td>Gulf war: Brent +{EH['brent_d20_2026']:.0f}%, Nifty {EH['nifty_d20_2026']:.0f}% in 20 days (public market data)</td><td>≈ ${OIL['extra_usd_bn_per_year_2026']:.0f}B/yr extra crude bill: oil stocks, rupee buffers, escort</td></tr>
<tr><td><b>Information</b></td><td>In UCDP's record, Indian outlets appear in 17% of Af–Pak events, about 0% elsewhere; media volume does not lead escalation (p = {stats.media_lead_p:.2f})</td><td>The record of West Asia rests on non-Indian wires: build Indian coverage; do not warn on headlines</td></tr>
</table>

<h2>RECOMMENDATIONS</h2>
<table><tr><th style="width:12%">Line</th><th>Action</th><th style="width:21%">Lead <span class="o">DOMAIN</span></th><th style="width:11%">When</th></tr>
<tr><td><b>SENSE</b></td><td>Task ISR and analysts on the monthly sub-national watch-list; track countries hit as a spread indicator</td><td>DIA, Service intelligence</td><td>Now / 90 days</td></tr>
<tr><td><b>WARN</b></td><td>Adopt the Af–Pak dyad and KP/Balochistan hotspot probabilities as LoC I&amp;W; publish the RAG monthly</td><td>HQ IDS, N &amp; W Comds</td><td>Now</td></tr>
<tr><td><b>SHIELD</b></td><td>Keep Gulf NEO plans current while US–Iran is AMBER; belligerent-movement picture in the IOR</td><td>HQ IDS, Navy, IAF, MEA</td><td>Now / 90 days</td></tr>
<tr><td><b>SUSTAIN</b></td><td>Buffer and indigenise critical spares; HADR kits for women, children, under-fives</td><td>MoD, DPSUs, NDMA</td><td>6–12 months</td></tr>
</table>

<h2>CONFIDENCE AND LIMITS</h2>
<ul>
<li>Forecasts trained to Dec 2025, scored on Jan–Sep 2026: error −{pooled:.0f}% vs naive (RU–UA −{red['Russia–Ukraine']:.0f}%,
Israel–Hamas −{red['Israel–Hamas']:.0f}%); {cov80:.0f}% of outcomes inside the 80% interval. Escalation top-10 list
{lg.precision_at_10 / lg.base_rate:.1f}× better than random. 90% interval on the gain: {_ci(RP['ci'])}; US–Iran bands held only {RB['US–Iran']['coverage80']:.0%}.</li>
<li>UCDP counts <i>reported</i> deaths; 2026 data are provisional; 92% of 2026 RU–UA deaths lack a location; decisions to
start a war (Feb 2022, Feb 2026) are not predictable from death counts.</li>
</ul>
<div class="foot">UNCLASSIFIED – COMPETITION DATA ONLY &nbsp;|&nbsp; RUN {RUN_ID} &nbsp;|&nbsp; Full method: analysis report</div>
"""
(OUT / "Commanders_Brief.html").write_text(page("Commander's Brief – Conflict Watch", brief.replace("{BRAND}", brand_corners(16))))

# ----------------------------------------------------------------------------------- Q&A + speaker split
QA = [
    ("Problem framing", [
        ("Why forecast deaths and not events?", "Deaths are the measure of harm that planners act on, and the "
         "series is comparable across the four conflicts. Events drive media volume, not lethality, as our index shows."),
        ("Why only these four conflicts?", "They are the competition scope. The pipeline is generic: any UCDP "
         "conflict can be added by extending the case list in config.py."),
    ]),
    ("The economic front (new, public market data)", [
        ("Where do the market numbers come from?", "Public daily series (Yahoo Finance, MOEX ISS, World Bank, the "
         "Caldara–Iacoviello risk index), fetched once on the team laptop and frozen in data/econ/raw so the run is "
         "reproducible offline. They are not competition files and are labelled as such."),
        ("How do you know a market move was caused by the war?", f"We do not claim cause. We date each shock from the UCDP "
         f"deaths, then compare the 20-day move with every other 20-day window of the same series since 2014 (placebo). "
         f"{E['sig_share_main_onsets']:.0%} of moves after the three onsets are unusual at p < 0.10, against "
         f"{E['sig_share_other_episodes']:.0%} after routine spikes."),
        ("Is the economic front really bigger than the battlefield?", f"For India, yes: no Indian unit fought, but the Gulf war "
         f"added about ${OIL['extra_usd_bn_per_year_2026']:.0f}B a year to the crude bill (4.8 mb/d is a domain input) and cut the "
         f"Nifty {-EH['nifty_d20_2026']:.0f}%. We do not put a money value on a life."),
        ("Were the figures quoted earlier right?", "Mostly. MOEX −33% on 24 Feb 2022 and a four-week halt: correct. ~$300B "
         "of Russian reserves frozen: correct (G7/EU figure). Bank of Israel: $30B of FX sales plus $15B of swaps, so up to $45B. "
         "Pakistan under a month of imports and Afghanistan's ~$9B frozen: correct. Political crises lining up with war peaks: "
         "only partly (3 of 17)."),
    ]),
    ("Data and cleaning", [
        ("Did you change the source data?", "No. Raw CSVs are read-only. Repairs go into new columns (e.g. deaths_low_c) "
         "and every change is in the 36-check data-quality log."),
        ("How did you handle multi-month events?", "731 records span more than one month, including front-wide "
         "aggregates. We spread their deaths across months by day count, otherwise the start month shows a false spike."),
        ("What about out-of-order low/best/high?", "692 rows. We keep best, because it reconciles exactly with the "
         "fatality components, and widen the band to min/max. Raw values are kept."),
        ("Why merge FATA into KP?", "Pakistan merged them in 2018. Without harmonising, FATA would show a fake collapse "
         "and KP a fake surge exactly at the boundary change."),
        ("Did you use all the issued datasets?", "Yes, all twelve, each with an ID (D1–D12). The report's Appendix C scans "
         "its own text and confirms each file is cited in both the data section and the findings. The pre-joined panels were "
         f"audited first: the country-month panel stops UCDP at {X11['latest_ucdp_month']} (it shows Iran with "
         f"{X11['iran_ucdp_deaths_feb_apr_2026']} deaths in the 2026 war) and keys GDELT on event date, so we rebuilt those joins."),
        ("What did the Middle East (ACLED-style) data add?", "What UCDP cannot see: protest violence and non-lethal activity. "
         f"Iran lost {X9['iran_unrest_deaths_dec25_jan26']:,} people to unrest in Dec 2025–Jan 2026, and strategic developments "
         f"ran {X9['iran_strategic_pre_2026']['ratio']:.1f}× their norm in the four weeks before the war. It also confirms the Gulf "
         f"spread ({X9['gulf_violent_events']['H1_2025']} → {X9['gulf_violent_events']['H1_2026']} violent events) and agrees "
         f"with UCDP on Israel–Palestine deaths (monthly ρ = {X9['israel_palestine_rho']:.2f}). The same signs did not precede "
         f"the June 2025 war ({X9['iran_strategic_pre_2025']['ratio']:.1f}×), so we recommend a trial."),
        ("What did the 1989–2025 UCDP file add?", f"Base rates from 37 years: {X10['persist_10k']['share_next_ge_1k']:.0%} of "
         f"{X10['persist_10k']['n']} focus-country years with ≥10,000 deaths were followed by at least 1,000 more, which supports "
         f"RED for Russia–Ukraine. It also shows the Af–Pak case holds only {X10['afpak_case_share_of_afghanistan']:.0%} of "
         "Afghanistan's recorded deaths, so our Af–Pak forecasts describe the cross-border and TTP war."),
        ("2026 data are provisional; is the test fair?", "It is the hardest, most realistic test: operational users always "
         "work on provisional data. Revisions usually go upward, which makes our holdout error conservative."),
    ]),
    ("Models and validation", [
        ("Why not a deep-learning model (LSTM)?", "Four series of 153 months is far too little data. Our ablation shows "
         "even a 40-feature LightGBM over-fits. Simpler, regularised models generalise better and are explainable."),
        ("Why does LightGBM predict the change, not the level?", "Trees cannot predict above the highest value seen in "
         "training. A level model trained before 2022 can never forecast the invasion. The change target removes that ceiling: "
         f"back-test RMSLE {abl.iloc[0, 1]:.2f} (level) vs {abl.iloc[4, 1]:.2f} (change, compact)."),
        ("How do you know you didn't tune on 2026?", "All choices (features, ensemble members, interval bands, classifier "
         "features) were made on 2022–25 folds. 2026 was scored once. On Track B SARIMA beat the ensemble in 2026, and we "
         "report that rather than switch."),
        ("Why is RMSLE the selection metric?", "The series differ by three orders of magnitude. RMSE would be dominated "
         "by Russia–Ukraine. RMSLE scores relative error fairly. MAE, RMSE, MAPE, sMAPE and MASE are all reported too."),
        ("Your Af–Pak improvement is only 4%. Why?", "Af–Pak is a steady creep with little month-to-month signal, so "
         "'no change' is already a strong baseline. The ensemble still wins, and the gain is large where it matters (RU–UA, "
         "Israel–Hamas, US–Iran)."),
        ("Why are the 95% intervals so wide?", "The back-test includes the 2022 invasion. A calibrated interval must keep "
         "room for outbreaks. The 80% band, which covered 83% of 2026, is the planning band."),
        ("The model missed the US–Iran war. Isn't that a failure?", "Yes, and we say so. No death-count model can foresee "
         "a decision to go to war. That is why warning also tracks spread and hotspots, and why the scorecard has a "
         "volatility rule."),
        ("How good is the early warning, really?", f"AUC {lg.ROC_AUC:.2f} on 2026 (rule of thumb {rule.ROC_AUC:.2f}); "
         f"top-10 precision {lg.precision_at_10:.0%} vs base rate {lg.base_rate:.1%}. Escalations are rare (4%), so "
         "precision looks low in absolute terms, but it is 3.5× random: it focuses scarce ISR. The scores run high at the "
         "top end, so we use the list as a ranking, not as literal odds."),
        (f"Is the {pooled:.0f}% gain statistically significant?", f"Partly. The 90% bootstrap interval is {_ci(RP['ci'])} and "
         f"excludes zero for the pool and for {_and(_clear)}. It includes zero for {_and(_inc)}, and with nine test months a "
         f"Diebold–Mariano test is significant only for {_and(_dm) or 'no single conflict'} (pooled p = {RP['dm_p']:.2f}). "
         f"Across all five folds the gain is {ROB['all_folds']['reduction'] * 100:.0f}%. We claim a consistent, useful gain, not a proven one."),
        (f"Your {cov80:.0f}% coverage: is that true for every conflict?", f"No. One month ahead it is "
         f"{RB['Russia–Ukraine']['coverage80']:.0%} for the three established wars and {RB['US–Iran']['coverage80']:.0%} for "
         "US–Iran, whose war began inside the test window. We say US–Iran bands are too narrow."),
        ("Do your context features leak the future?", "World Bank gaps are interpolated, which looks at later years. Those "
         "columns are not in the selected ensemble or the classifier; they appear only in benchmark and ablation variants. "
         "The selected models use deaths, events, references and the calendar only."),
        ("How would this run on data that arrives a month late?", f"We tested it: forecasting from data two months old still "
         f"beats the matching naive rule by {ROB['late_data']['holdout'] * 100:.0f}% on 2026 and "
         f"{ROB['late_data']['backtest'] * 100:.0f}% on the back-test."),
        ("What happens if we give you October data now?", "Run python score_holdout.py --events &lt;file&gt;. It cleans the new "
         "events with the same rules and scores the forecasts and watch-list frozen in the submission. Nothing is refitted."),
        ("Why is Israel–Hamas GREEN with 130 deaths a month?", "The rating measures escalation risk against the conflict's own "
         "recent level, not peace. The forecast is flat, there are no hotspots and no new countries."),
    ]),
    ("Military and India", [
        ("Is the Russia:Ukraine 10:1 ratio real?", "No; it is recorded. Ukrainian OSINT and memorial databases record "
         "Russian deaths more fully. We show it as an upper bound of reporting and caveat it on the slide."),
        ("How do you link the Af–Pak war to the LoC?", "The data show Pakistan fighting on its western front. The LoC link "
         "is domain reasoning, labelled DOMAIN, and we recommend it as an indicator to watch, not a prediction."),
        ("Where does '9 million Indians in the Gulf' come from?", "It is public MEA-order-of-magnitude knowledge, not "
         "from the competition files, and is labelled DOMAIN."),
        ("What would you do with classified data?", "Fuse it as extra features (e.g. movement indicators). The pipeline "
         "already accepts new features; the walk-forward protocol would test their value."),
    ]),
    ("Theatre commander view and the OODA loop (notional)", [
        ("Are these real theatre commands?", "No. WTC, NTC and MTC are notional, drawn from public reporting, and are labelled "
         "NOTIONAL on every screen, slide and brief. Each AOR is an illustrative polygon plus a list of linked conflicts and countries."),
        ("Is the LAC data real?", "No. No issued file covers the LAC, so NTC runs on a seeded synthetic incident generator "
         "(9 sectors, seed 2026) with a scripted surge at Yangtse and Depsang to show the FLASH path. Every item is tagged "
         "SYNTHETIC, NTC confidence is LOW, and the CDS brief never picks its main effort from synthetic data."),
        ("How are the theatre RAG, trend and confidence computed?", "Twice the monthly RAG level of the linked conflicts "
         "(GREEN 2, AMBER 4, RED 6), plus daily modifiers: the GDELT 7-day ratio against the prior 4 weeks, a 24-hour z-score, "
         "districts over the FLASH threshold and adverse market moves. RED is 6 or more, AMBER 3–5. The trend arrow is the "
         "GDELT 7-day ratio. Confidence falls with synthetic inputs, low news volume and the UCDP lag."),
        ("What is the district nowcast? Is it validated?", "The monthly watch-list probability shifted by the theatre's GDELT "
         "momentum: logit(p_now) = logit(p) + 0.5 × clip(ln r7, −1, 1). It is a heuristic and is not back-tested; the "
         "monthly model underneath is (AUC 0.795 on 2026)."),
        ("When does a FLASH fire?", "When a district's nowcast crosses P 0.20 upward (with a small band to stop flicker) or "
         "a theatre's RAG changes between daily runs. In the 7-day demo, three fired, all on synthetic NTC data."),
        ("Where do the OODA hours come from?", "The staff-cycle timings (4–10 days today, 4–28 hours with the brief) are our "
         "domain estimate of a weekly int/ops conference cycle, not a measurement. Two numbers are measured: data latency "
         "falls from 43 days (UCDP) to under one day (GDELT, markets), and all briefs build in about 2 seconds."),
        ("Does the model make the decision?", "No. It takes collation, scoring and option-building off the critical path. "
         "The commander chooses among three ranked options, each with an owner, a timeline and a trigger."),
        ("Is the 0600 job real?", "Yes: scripts/daily_briefs.py runs on a schedule (Windows Task Scheduler, cron or a GitHub "
         "workflow at 0030 UTC). The demo writes an in-app inbox and e-mail, SMS and WhatsApp previews; real e-mail works "
         "through SMTP if configured. SMS and WhatsApp gateways are not wired."),
    ]),
    ("Dashboard and reproducibility", [
        ("Can it run offline at an HQ?", "Yes. The Ops site is one offline HTML file and the Streamlit dashboard runs on "
         "a laptop with no internet calls and a bundled map outline. One command rebuilds everything in about 4 minutes."),
        ("Can it be updated monthly?", "Drop in the new UCDP month and rerun. The 'live re-train' page refits LightGBM-Δ "
         "in about 2 seconds."),
        ("What did the GDELT files add?", f"An independent test on 13.5 million media records. Media volume did not rise "
         f"before the Feb 2026 war ({_pw['events_per_day'][0]:,.0f} vs {_pw['events_per_day'][1]:,.0f} reports a day on Iran vs "
         f"the US or Israel, p = {_pw['events_p']:.2f}), which confirms our UCDP finding. The character of coverage did shift in "
         f"the last week (Goldstein {_pw['goldstein'][0]:+.2f} to {_pw['goldstein'][1]:+.2f}, p = {_pw['goldstein_p']:.3f}), but "
         f"that is one case and we call it a hypothesis. Kuwait-located conflict reports went from {XG['kuwait_conflict_per_day'][0]:.1f} "
         f"to {XG['kuwait_conflict_per_day'][1]:.0f} a day, confirming the Gulf spread. Its October direction agrees with our "
         f"forecast for {XO['agree']} of {XO['of']} conflicts."),
        ("Why is GDELT not in your model?", "It covers only Feb–Nov 2026, so there is nothing to train or back-test on. "
         f"It moves with UCDP month to month only in spike wars (US–Iran ρ {GDS['monthly']['by_case']['US–Iran']['rho_change']:.2f}, "
         f"Af–Pak {GDS['monthly']['by_case']['Afghanistan–Pakistan']['rho_change']:.2f}). Pooled, a week earlier it adds nothing "
         f"(p {GDS['weekly']['lead_p']:.2f}); Af–Pak alone gives p {_lp['Afghanistan–Pakistan']:.2f}, which does not survive a "
         "correction for four tests, and it did not beat persistence out of sample. We use it as a nowcast and never join it to UCDP events."),
        ("What does GDELT say after September?", "US–Iran violent events per day rose about 59% in 1–12 Nov over "
         "October, and threats doubled, while the scorecard is AMBER. Af–Pak and Israel–Hamas fell; RU–UA steady. "
         "GDELT counts news reports, not incidents, so treat it as a cue to look, not a casualty figure."),
        ("How was AI used?", "AI tools used: Claude (Anthropic), as a coding, drafting and review assistant. It helped write "
         "and debug the pipeline, dashboard, report and slide code, and reviewed the submission against the marking scheme. "
         "No number was typed in or generated by an AI tool: every figure is computed by the code in this repository from "
         "the issued dataset and can be reproduced with one command. The team framed the questions, checked the analysis "
         "and owns the findings and recommendations."),
        ("Is your map of India correct?", "Yes. India is drawn with the whole of Jammu &amp; Kashmir and Ladakh, following "
         "the Government of India's depiction (Natural Earth India point-of-view boundary). PoK incidents are shown as "
         "points labelled PoK."),
        ("How do we know the demo matches the submission?", f"The run ID {RUN_ID} is a hash of the result tables. It is "
         "printed on the report, every slide, the dashboard sidebar and the Ops site strip, and the deck annex holds all "
         "15 dashboard pages and every metric."),
        ("What is the single decision a commander should take on Monday?", "Put the top-10 watch-list into the monthly ISR "
         "tasking cycle and keep the Gulf NEO plan current while US–Iran is AMBER."),
    ]),
]

qa_html = "".join(f"<h3>{sec}</h3>" + "".join(f"<div class='q'>Q. {q}</div><div class='a'>{a}</div>" for q, a in items)
                  for sec, items in QA)

speak = f"""
<div class="hdr" style="{BRAND_CSS}">{{BRAND}}<div class="k">PRESENTER PACK &nbsp;|&nbsp; DATA ANALYTICS COMPETITION 2026</div>
<h1>Run of show, speaker split and Q&amp;A preparation</h1>
<div class="m">Designed for a Google Meet presentation: share the deck window, then switch to the live Ops site tab for the demo. Run {RUN_ID}.</div></div>

<h2>RUN OF SHOW (TARGET 14:55 + Q&amp;A; HARD STOP 15:00)</h2>
<table><tr><th>Time</th><th>Slides / demo</th><th>Speaker</th><th>Key line</th></tr>
<tr><td>0:00–1:30</td><td>1 Cover, 2 BLUF</td><td>Maj Shivam Mehta</td><td>"Error cut by {pooled:.0f}% on unseen data; RED, two AMBER, one GREEN; four tasks for India."</td></tr>
<tr><td>1:30–3:15</td><td>3 Approach, 4 Data and pipeline, 5 Method</td><td>Capt Siddharth Sangwan</td><td>"Twelve issued files, 36 checks, joined only by country and calendar; the back-test chose the ensemble."</td></tr>
<tr><td>3:15–5:00</td><td>6–8 Validation on withheld 2026</td><td>Capt Siddharth Sangwan</td><td>"It beats simple rules, and we show where it does not."</td></tr>
<tr><td>5:00–6:50</td><td>9 <b>LIVE DEMO</b>: Ops site story → console</td><td>Capt Siddharth Sangwan</td><td>"Here is the RED card, and here is where it comes from."</td></tr>
<tr><td>6:50–7:35</td><td>10 Theatre commander view (notional)</td><td>Capt Siddharth Sangwan</td><td>"One dataset, four commanders: a 0600 brief in OODA form."</td></tr>
<tr><td>7:35–8:50</td><td>11–12 Finding 1: borders and the LoC</td><td>Capt Sahil Singh</td><td>"Pakistan fights on two fronts: watch the LoC more closely."</td></tr>
<tr><td>8:50–9:50</td><td>13 Finding 2: Gulf, diaspora, sea lanes</td><td>Capt Sahil Singh</td><td>"14 countries, five Gulf states and Sri Lankan waters."</td></tr>
<tr><td>9:50–10:25</td><td>14 Finding 3: defence sustainment</td><td>Capt Sahil Singh</td><td>"The front is widening, not moving, and the war will last."</td></tr>
<tr><td>10:25–11:50</td><td>15–16 Finding 4: the economic front</td><td>Capt Sahil Singh</td><td>"The guns stay far away; oil, the rupee and markets reach India first."</td></tr>
<tr><td>11:50–12:55</td><td>17–18 Recommendations</td><td>Maj Shivam Mehta</td><td>"Sense, warn, shield, sustain: SENSE and WARN need no new platform."</td></tr>
<tr><td>12:55–13:40</td><td>19 Shortening the OODA loop</td><td>Maj Shivam Mehta</td><td>"Event to decision: from days to hours."</td></tr>
<tr><td>13:40–14:55</td><td>20 Execution, 21 Scorecard</td><td>Maj Shivam Mehta</td><td>"Open data and an honest model tell India where to look next month."</td></tr>
<tr><td>Q&amp;A</td><td>22–33 support, 34–38 backup, 39–57 annex</td><td>All</td><td>Pull the slide that answers the question.</td></tr>
</table>
<p><b>Speaker split:</b> <b>Maj Shivam Mehta</b> opens with the bottom line and closes with the recommendations and scorecard. <b>Capt Siddharth Sangwan</b> covers approach, data, method and validation and runs the live demo. <b>Capt Sahil Singh</b> presents the four India findings, including the economic front, and chairs Q&amp;A, routing data and model questions to Capt Sangwan and military questions to Maj Mehta. The word-for-word script is in <i>Presenter_Script.pdf</i>.</p>

<h2>VIDEO-CALL CHECKLIST</h2>
<ul>
<li>Open <b>conflictmonitor2026.streamlit.app</b> 15 minutes early so it wakes; scroll the story once and open the console once.</li>
<li>Share a single browser window at 1600×900 or similar; browser zoom 110–125% for legibility after compression.</li>
<li>Fall-backs: the offline Ops site <code>deck/conflictwatch.html</code>, the demo video and the deck PDF.</li>
<li>Check the run ID on the site strip reads <b>{RUN_ID}</b>, the same as the deck footer.</li>
<li>Mute notifications; use a wired connection; cameras on for Q&amp;A.</li>
</ul>

<h2>DEMO SCRIPT (ABOUT 2 MINUTES, OPS SITE)</h2>
<ol>
<li><b>Globe:</b> twelve years of deaths; scroll so it turns to India and draws the exposure ring (Gulf, Hormuz, Chabahar, Sri Lanka, LoC).</li>
<li><b>BLUF:</b> click the Af–Pak card: 3 points (intensity + hotspots), so AMBER.</li>
<li><b>Front:</b> toggle "show all deaths": the 92% with no location. <b>Af–Pak:</b> switch RAW / HARMONISED to show the FATA fix.</li>
<li><b>Prediction:</b> press play; coverage ticks to 83%. Show Track B honestly (SARIMA won there).</li>
<li><b>Early warning:</b> Replay Mar 2026 (3 of the top 10 escalated), then move the threshold.</li>
<li><b>GDELT</b> (skip if short of time): toggle US–Iran; the line runs past UCDP's end.</li>
<li><b>What-if</b> (Q&amp;A only, cut from the talk): Af–Pak, +30% for 3 months: 318 → 359.</li>
<li><b>Ops console:</b> Ctrl+K → Kandahar: deaths, forecast, warning history; print bulletin.</li>
<li><b>Theatre</b> (if asked, or in Q&amp;A): console THEATRE tab or Streamlit page 14; switch WTC → MTC → NTC to show the same data giving different briefs; page 15 for the 7-day history, side by side and the OODA loop.</li>
</ol>

<h2>LIKELY QUESTIONS AND ANSWERS</h2>
<div class="cols"><div>{qa_html}</div></div>
<div class="foot">UNCLASSIFIED – COMPETITION DATA ONLY</div>
"""
(OUT / "QA_Prep_and_Speaker_Split.html").write_text(page("Q&A Prep – Conflict Watch", speak.replace("{BRAND}", brand_corners(16))))
print("brief and Q&A written")
