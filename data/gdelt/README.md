# GDELT aggregates (Feb–Nov 2026)

Built by `build_gdelt_aggregates.py` from the two raw GDELT focus files
(`gdelt_focus_feb_apr_2026.csv`, `gdelt_focus_3gb_from_2026.csv`; 13,507,238 events, no ID overlap).
Raw files are not included. Each table is given as CSV and parquet.

## Coverage
- Date axis = `DATEADDED` (day GDELT ingested the report). `SQLDATE` is back-dated for ~0.7% of rows.
- Covered: 2026-02-01 to 2026-04-30 and 2026-05-17 to 2026-11-12.
- **Gap 2026-05-01 to 05-16** (not in either file), so May and Nov are partial months.
  Use daily/weekly rates, or normalise monthly counts by days covered, before comparing months.

## Conflict cases (actor dyad, either direction, CAMEO codes)
| case_id | rule |
|---|---|
| RU-UA | RUS ↔ UKR |
| ISR-HAMAS | ISR ↔ PSE, or ISR ↔ actor with KnownGroupCode HMS |
| AF-PAK | AFG ↔ PAK |
| US-IRAN | USA ↔ IRN |

`gdelt_theatre_daily` is a looser view: RU-UA = a RUS/UKR actor with action in Ukraine (UP);
ISR-HAMAS = an ISR/PSE/HMS actor with action in Gaza, West Bank or Israel (GZ/WE/IS).

## Tables
| file | grain |
|---|---|
| gdelt_case_daily | case_id × date |
| gdelt_case_weekly | case_id × week_start (Monday) |
| gdelt_case_monthly | case_id × year_month |
| gdelt_theatre_daily | theatre case × date |
| gdelt_country_daily | focus country × date (all events for the 7 focus countries) |
| gdelt_country_month | focus country × year_month, joins to `country_month_panel` on country + year_month |
| gdelt_case_rootcode_monthly | case × month × CAMEO EventRootCode (long) |
| gdelt_country_rootcode_monthly | country × month × CAMEO EventRootCode (long) |

## Metrics
events, articles, mentions; QuadClass counts (verbal_coop, material_coop, verbal_conflict,
material_conflict); violent_events (root 18 assault, 19 fight, 20 mass violence); threat_events (13);
force_posture_events (15); conflict_articles, violent_articles; goldstein_mean / goldstein_wmean
(article-weighted); tone_mean / tone_wmean; conflict_share (QuadClass 3+4 / all);
material_conflict_share.

## Caveats
GDELT is media-coded news volume, not ground truth: one GDELT row is not one incident, and US
counts are inflated by coverage bias. Treat it as a narrative / attention signal and compare with
UCDP fatalities (country + year_month), never join on event IDs.
