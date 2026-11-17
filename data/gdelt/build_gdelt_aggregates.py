"""Build compact GDELT aggregates for the conflict-watch analysis.

Reads the two raw GDELT focus CSVs (~5.5 GB, 13.5M events) with DuckDB (streams the
CSV out-of-core, far faster than pandas chunks; Excel cannot hold >1,048,576 rows)
and writes small CSV + parquet tables to this folder.

Date used: DATEADDED (the day GDELT ingested the report). SQLDATE is the coded event
date and is back-dated by up to years for ~0.7% of rows, so it is unsuitable as a
daily time axis.

Conflict cases are assigned by actor dyad (either direction, CAMEO country codes):
  RU-UA       : RUS <-> UKR
  ISR-HAMAS   : ISR <-> PSE, or ISR <-> any actor with KnownGroupCode HMS
  AF-PAK      : AFG <-> PAK
  US-IRAN     : USA <-> IRN
A looser "theatre" view (an actor of the pair + action located in the theatre)
is also given for RU-UA (UP) and ISR-HAMAS (GZ/WE/IS).
"""
import duckdb, os, time

HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.dirname(HERE)
FILES = [D + r"\4. gdelt_focus_feb_apr_2026-001.csv", D + r"\3. gdelt_focus_3gb_from_2026-002.csv"]
OUT = HERE

con = duckdb.connect()
con.execute("SET threads=6; SET memory_limit='6GB'")
t0 = time.time()
src = " UNION ALL ".join(f"SELECT * FROM read_csv('{f}', all_varchar=true, header=true, parallel=true)" for f in FILES)
con.execute(f"""
CREATE TABLE ev AS
WITH raw AS ({src})
SELECT
  strptime(DATEADDED, '%Y%m%d')::DATE                    AS date,
  Actor1CountryCode a1, Actor2CountryCode a2,
  Actor1KnownGroupCode g1, Actor2KnownGroupCode g2,
  ActionGeo_CountryCode geo,
  focus_country_name                                     AS country,
  TRY_CAST(QuadClass AS INT)                             AS quad,
  TRY_CAST(EventRootCode AS INT)                         AS root,
  TRY_CAST(GoldsteinScale AS DOUBLE)                     AS goldstein,
  TRY_CAST(NumMentions AS INT)                           AS mentions,
  TRY_CAST(NumSources AS INT)                            AS sources,
  TRY_CAST(NumArticles AS INT)                           AS articles,
  TRY_CAST(AvgTone AS DOUBLE)                            AS tone
FROM raw
""")
print("loaded", con.execute("select count(*) from ev").fetchone(), round(time.time() - t0, 1), "s")

con.execute("""
CREATE TABLE ev2 AS SELECT *,
  CASE
    WHEN (a1='RUS' AND a2='UKR') OR (a1='UKR' AND a2='RUS') THEN 'RU-UA'
    WHEN (a1='ISR' AND (a2='PSE' OR g2='HMS')) OR (a2='ISR' AND (a1='PSE' OR g1='HMS')) THEN 'ISR-HAMAS'
    WHEN (a1='AFG' AND a2='PAK') OR (a1='PAK' AND a2='AFG') THEN 'AF-PAK'
    WHEN (a1='USA' AND a2='IRN') OR (a1='IRN' AND a2='USA') THEN 'US-IRAN'
  END AS case_dyad,
  CASE
    WHEN (a1 IN ('RUS','UKR') OR a2 IN ('RUS','UKR')) AND geo='UP' THEN 'RU-UA'
    WHEN (a1 IN ('ISR','PSE') OR a2 IN ('ISR','PSE') OR g1='HMS' OR g2='HMS') AND geo IN ('GZ','WE','IS') THEN 'ISR-HAMAS'
  END AS case_theatre
FROM ev
""")

# Shared metric block. Article-weighted Goldstein/tone so one syndicated story != many.
M = """
  count(*)                                         AS events,
  sum(articles)                                    AS articles,
  sum(mentions)                                    AS mentions,
  count(*) FILTER (WHERE quad=1)                   AS verbal_coop,
  count(*) FILTER (WHERE quad=2)                   AS material_coop,
  count(*) FILTER (WHERE quad=3)                   AS verbal_conflict,
  count(*) FILTER (WHERE quad=4)                   AS material_conflict,
  count(*) FILTER (WHERE root IN (18,19,20))       AS violent_events,      -- assault, fight, mass violence
  count(*) FILTER (WHERE root=13)                  AS threat_events,
  count(*) FILTER (WHERE root=15)                  AS force_posture_events,
  sum(articles) FILTER (WHERE quad IN (3,4))       AS conflict_articles,
  sum(articles) FILTER (WHERE root IN (18,19,20))  AS violent_articles,
  round(avg(goldstein), 4)                         AS goldstein_mean,
  round(sum(goldstein*articles)/nullif(sum(articles),0), 4) AS goldstein_wmean,
  round(avg(tone), 4)                              AS tone_mean,
  round(sum(tone*articles)/nullif(sum(articles),0), 4)      AS tone_wmean,
  round(count(*) FILTER (WHERE quad IN (3,4)) / count(*)::DOUBLE, 4) AS conflict_share,
  round(count(*) FILTER (WHERE quad=4) / count(*)::DOUBLE, 4)        AS material_conflict_share
"""

def save(name, sql):
    con.execute(f"CREATE OR REPLACE TABLE t AS {sql}")
    n = con.execute("select count(*) from t").fetchone()[0]
    con.execute(f"COPY t TO '{OUT}\\{name}.csv' (HEADER)")
    con.execute(f"COPY t TO '{OUT}\\{name}.parquet' (FORMAT parquet)")
    print(f"{name}: {n} rows")

save("gdelt_case_daily", f"SELECT case_dyad AS case_id, date, {M} FROM ev2 WHERE case_dyad IS NOT NULL GROUP BY ALL ORDER BY 1,2")
save("gdelt_case_weekly", f"SELECT case_dyad AS case_id, date_trunc('week', date)::DATE AS week_start, {M} FROM ev2 WHERE case_dyad IS NOT NULL GROUP BY ALL ORDER BY 1,2")
save("gdelt_case_monthly", f"SELECT case_dyad AS case_id, strftime(date,'%Y-%m') AS year_month, {M} FROM ev2 WHERE case_dyad IS NOT NULL GROUP BY ALL ORDER BY 1,2")
save("gdelt_theatre_daily", f"SELECT case_theatre AS case_id, date, {M} FROM ev2 WHERE case_theatre IS NOT NULL GROUP BY ALL ORDER BY 1,2")
save("gdelt_country_daily", f"SELECT country, date, {M} FROM ev2 GROUP BY ALL ORDER BY 1,2")
save("gdelt_country_month", f"SELECT country, strftime(date,'%Y-%m') AS year_month, {M} FROM ev2 GROUP BY ALL ORDER BY 1,2")
save("gdelt_case_rootcode_monthly", """SELECT case_dyad AS case_id, strftime(date,'%Y-%m') AS year_month, root AS event_root_code,
    count(*) AS events, sum(articles) AS articles, round(avg(goldstein),3) AS goldstein_mean, round(avg(tone),3) AS tone_mean
    FROM ev2 WHERE case_dyad IS NOT NULL GROUP BY ALL ORDER BY 1,2,3""")
save("gdelt_country_rootcode_monthly", """SELECT country, strftime(date,'%Y-%m') AS year_month, root AS event_root_code,
    count(*) AS events, sum(articles) AS articles FROM ev2 GROUP BY ALL ORDER BY 1,2,3""")
print("done", round(time.time() - t0, 1), "s")
