# Conflict EW v3: model improvements (after the competition)

Done after the 17 Nov 2026 submission, on the team's v2 repo. Every result below was produced the way the deck
demands: choices made on validation (2023–25), written down and hashed **before** the test, and the test
(Jan–Sep 2026 for forecasts, all of 2025 for the watch-list) opened **once**. Code is in `improve/` and
`scripts/`; results in `outputs/v3/`. The issued dataset is not in the repo, so the scripts run only where it is.

> These experiments rebuild the recipe in a simplified setting. Our v2 baseline scores 1.47 / 1.75 here,
> not the deck's 1.26 / 1.40, so compare rows **within** each table, not with the deck.

## Summary

| Step | What we tried | Result on the sealed test | Verdict |
|---|---|---|---|
| 2 Monthly forecast | 21 candidates (7 models × 2 feature sets + 3 equal-weight averages); pre-registered rule | Chosen model **−7.9%** error vs the v2 recipe (1.612 vs 1.750); Russia–Ukraine error halved (1.30 → 0.64) | **Adopt**, with a caveat on Israel–Hamas |
| 3 Ranges | Global width (v2), per-band widths, conformalised quantile regression | Per-band: ~25% narrower ranges for the three steady wars at 78–89% coverage; CQR: 86% overall but much wider | **Adopt per-band** for steady wars; onsets stay uncovered |
| 4 Watch-list | Neighbour spill-over, isotonic calibration, two alert tiers | Spill-over **did not help** (PR-AUC 0.31 vs 0.34); raw scores already calibrated (ECE 0.009); new **ACT tier**: ~3.5 countries/month at **41% precision** | **Adopt two tiers**, drop spill-over |
| 1 Onset tripwire | Learned logistic model on daily GDELT vs the fixed rules | Learned model **worse** out of sample (ROC 0.30 vs 0.50); fixed rules kept | **Not adopted**: 4 wars × 8 months is too little |
| 6 2027 outlook | Quantile LightGBM on 4–15-month outcomes vs the analogue table | Back-test 2010–24: **19–24% lower loss**, about half the typical error, ranges ~25% narrower, coverage 76–80% | **Adopted** on the v2 site |
| 5 LAC hook | Indicator format, weekly sector stress index, RAG | Ready; no data yet (self-test on generated data turns RED on a surge) | Ready for data |
| 7 Monthly cycle | `monthly_cycle.py forecast / score`, scorebook, track record | October 2026 forecasts written and hashed; scored as data arrive | Running |

## Step 2: monthly forecast

Pre-registration `outputs/v3/prereg_monthly.json`, SHA-256 `612b65cc…f577`. Rule: lowest pooled validation RMSLE
among candidates that beat the v2 recipe by ≥ 3% **and** are not more than 10% worse on any single war.
Freeze `freeze_monthly.json`, SHA-256 `74d7071b…732b`; test flag written on first run.

| Model (RMSLE, lower is better) | Validation 2023–25 | Test Jan–Sep 2026 | Af–Pak | IL–Hamas | RU–UA | US–Iran |
|---|---|---|---|---|---|---|
| v2 recipe (LightGBM, L1, change target) | 1.468 | 1.750 | 0.59 | 0.21 | 1.30 | 3.19 |
| **Chosen: LightGBM, Huber, nowcast target, completeness features** | **1.314** | **1.612** | 0.56 | 0.85 | **0.64** | 2.99 |
| Equal-weight average of 4 tree models, completeness features (not chosen) | 1.358 | 1.540 | 0.56 | 0.59 | 0.53 | 2.93 |
| 3-month average (rule) | 1.455 | 1.753 | 0.62 | 0.17 | 1.19 | 3.23 |

What made the difference: **reporting completeness**. The model is told how much of the last three months is
usually known at month-end (measured only on older months, so no look-ahead) and forecasts from the corrected level.
That halved the Russia–Ukraine error, where recent months are the least complete.

Honest notes: the chosen model is worse than the v2 recipe on Israel–Hamas (0.85 vs 0.21) in 2026; a 4-tree
average would have scored better on the test (1.540), but the rule picked by validation and we keep that choice.
US–Iran (a war started by decision) stays the largest error for every model.

## Step 3: ranges (80%)

| Method | Coverage on test | Mean width | Af–Pak | IL–Hamas | RU–UA | US–Iran |
|---|---|---|---|---|---|---|
| v2: one global width | 78% | ×3.4 either way | 100% | 89% | 100% | 22% |
| Per intensity band | 72% | ×3.0 | 89% (×2.6) | 78% (×2.6) | 89% (×2.7) | 33% |
| Conformalised quantile regression | 86% | ×5.7 | 89% | 100% | 89% | 67% (×12.7) |

Per-band ranges are about a quarter narrower for the steady wars at similar coverage; the onset war is only covered
by a very wide range. The monthly cycle uses per-band widths and says so.

## Step 4: watch-list (117 countries, test = all of 2025)

| | PR-AUC | ROC-AUC | Calibration error | WATCH tier | ACT tier |
|---|---|---|---|---|---|
| v2 features | **0.336** | 0.885 | 0.009 | ~24/month, recall 76%, precision 24% | – |
| + neighbour spill-over | 0.313 | 0.878 | 0.013 | ~23/month, recall 69% | – |
| v2 features, calibrated, two tiers | 0.309 | 0.883 | 0.012 | ~26/month, recall 80%, precision 23% | **~3.5/month, precision 41%**, recall 19% |

The ACT threshold was fixed on validation (calibrated precision ≥ 40%) and held on the test. A short ACT list of
about 3–4 countries a month, right four times in ten, is the answer to "four in five alerts are false".

## Step 1: onset tripwire

856 war-days (Feb–Sep 2026), leave-one-war-out. Target: a casualty escalation day within 14 days.
Fixed rules (site): PR-AUC 0.40, ROC 0.50, precision 42% on alert days. Learned logistic: PR-AUC 0.30, ROC 0.30.
With four wars and eight months, a learned model cannot generalise to a war it has not seen. It needs GDELT for all
country pairs over several years, which the issued files do not contain. The fixed rules stay.

## Step 6: 2027 outlook

| Back-test 2010–2024 (28,960 conflict-months) | Pinball loss | Median error (log) | 80% range width | Coverage |
|---|---|---|---|---|
| Analogue table (old site) – year | 0.514 | 1.42 | 5.77 | 83% |
| **Quantile LightGBM – year** | **0.415** | **1.06** | **4.23** | 76% |
| Analogue table – quarters | 0.43 | 1.15–1.25 | ~4.6 | 82% |
| **Quantile LightGBM – quarters** | **0.33** | **0.46–0.57** | **~3.4** | 79% |

New 2027 middle cases (v2 site): Af–Pak ~2.3k (AMBER), IL–Hamas ~1.3k (AMBER), RU–UA ~87k (RED, close to its current
pace, where the analogue table said 36k), US–Iran ~1.1k for the year (AMBER) but tens per quarter: a restart in
any one quarter makes the year larger than the four quiet quarters added up.

## Steps 5 and 7

- `data/lac/README.md`, `template.csv`, `improve/lac.py`: drop non-fatal LAC / LoC indicators in and the Northern
  view can run on real data. Nothing is shipped but the template.
- `scripts/monthly_cycle.py forecast` refits the chosen model, forecasts next month with per-band ranges, hashes each
  forecast and appends it to `outputs/v3/scorebook.csv`; `score` fills in actuals as they arrive and writes
  `track_record.json`. October 2026: Af–Pak 325 (124–845), IL–Hamas 119 (45–311), RU–UA 8,195 (3,064–21,919),
  US–Iran 16 (3–76).

## What would move the needle next

1. GDELT (or similar) for every country pair over several years, so the onset model can learn.
2. Real non-fatal LAC / LoC indicators in `data/lac/`.
3. Re-run Step 2 inside the full deck pipeline and confirm the gain on Oct–Dec 2026 as it arrives (the scorebook does this).
