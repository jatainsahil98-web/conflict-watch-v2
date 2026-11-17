# Conflict Watch v2 (Team FCE) — what changed and why

Run ID: CW-F6C2C2CC (rebuilds identically). Local branch `fce-v2` — NOT pushed (the GitHub repo is public).

## Lessons applied
| Lesson | What v2 does |
|---|---|
| 1 Compliance gate | `scripts/check_submission.py`: 17 checks (≤10 pages, zip name, FCE on every product, one run ID, AI declaration, ≤12 main slides, code in, no raw data, no outside data, no synthetic). All pass. |
| 2 One source of truth | One branch, one run ID, one packager (`scripts/make_submission_v2.py` → `dist/FCE_DAC2026.zip`). |
| 3 Issued data only | Market module (Brent, Nifty, rupee, MOEX…) removed from pipeline, report, deck and site. "~9M diaspora" and "OSINT" removed. |
| 4 Validation over polish | Pre-registered model choice (hash in `preregistration.json`), sealed Oct–Dec forecasts (hash in `sealed_predictions.json`), permutation test for the tripwire. |
| 5 Use all the data | Escalation classifier now also trains on 1,450 areas in 110 other countries from D10 (transfer learning). GDELT daily tripwire. Reporting-lag completeness curve from D2. |
| 6 India's own front | J&K attacks with 15+ deaths vs India–Pakistan state fighting (D10): after Uri, Pulwama, Pahalgam, state fighting followed in 11–15 days. |
| 7 Deck | 12 main slides (15 min) + 6 backup; Deduction → Action on every finding slide. |
| 8 No synthetic data | Northern (LAC) view removed; views are now CDS, WTC, MTC. |

## Results that changed
| | v1 (submitted) | v2 |
|---|---|---|
| Forecast error vs "no change" (2026) | −29% | −29% (unchanged) |
| Escalation warning, 2026 ROC-AUC / PR-AUC / top-10 precision | 0.795 / 0.133 / 14.4% | 0.798 / 0.146 / 16.7% |
| Top-10 lift vs chance | 3.5× | 4.1× |
| News tripwire | — | 4 of 5 RED alerts confirmed, p = 0.018; US–Iran RED on day 0 (28 Feb), AMBER 3 days before |
| RU–UA deaths known 90 days after the event | — | 40% (the 2026 "decline" is late reporting) |
| Oct 2026 ratings | RU–UA RED · Af–Pak AMBER · US–Iran AMBER · IL–Hamas GREEN | RU–UA RED · Af–Pak AMBER · **US–Iran GREEN** · IL–Hamas GREEN |
| Report | 36 pages | 5 pages |

**US–Iran moves AMBER → GREEN.** The calibrated warning model now puts no US–Iran area above the 15% hotspot line, so its score drops from 2 to 1. The forecast is unchanged (26 deaths). The report says plainly that the monthly model cannot forecast an onset, and the daily tripwire guards US–Iran.

**Disclosure.** Calibration (Platt, fitted on 2023–25 only) was added after seeing the 2026 reliability table; the variant choice was not changed. This is recorded in `preregistration.json`.

## Not rebuilt
Commander's Brief, Q&A sheet and demo videos (not required by the rules).
