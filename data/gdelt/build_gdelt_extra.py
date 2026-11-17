"""Extra GDELT aggregates (same DATEADDED axis as build_gdelt_aggregates.py).
(1) gdelt_iran_pair_daily: date x pair (IRN-USA, IRN-ISR, IRN-USA_OR_ISR), actor dyad either direction.
(2) gdelt_actiongeo_daily: date x ActionGeo_CountryCode for selected FIPS codes.
"""
import duckdb, os
HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.dirname(HERE)
OUT = os.path.join(D, "laptop_data"); os.makedirs(OUT, exist_ok=True)
FILES = [D + r"\4. gdelt_focus_feb_apr_2026-001.csv", D + r"\3. gdelt_focus_3gb_from_2026-002.csv"]
con = duckdb.connect(); con.execute("SET threads=6; SET memory_limit='6GB'")
src = " UNION ALL ".join(f"SELECT * FROM read_csv('{f}', all_varchar=true, header=true, parallel=true)" for f in FILES)
con.execute(f"""CREATE TABLE ev AS WITH raw AS ({src}) SELECT
  strptime(DATEADDED,'%Y%m%d')::DATE date, Actor1CountryCode a1, Actor2CountryCode a2, ActionGeo_CountryCode geo,
  TRY_CAST(QuadClass AS INT) quad, TRY_CAST(EventRootCode AS INT) root, TRY_CAST(GoldsteinScale AS DOUBLE) goldstein,
  TRY_CAST(NumArticles AS INT) articles, TRY_CAST(AvgTone AS DOUBLE) tone FROM raw""")
M = """count(*) events, sum(articles) articles,
  count(*) FILTER (WHERE quad=4) material_conflict, count(*) FILTER (WHERE root IN (18,19,20)) violent_events,
  round(avg(goldstein),4) goldstein_mean, round(sum(goldstein*articles)/nullif(sum(articles),0),4) goldstein_wmean,
  round(avg(tone),4) tone_mean, round(sum(tone*articles)/nullif(sum(articles),0),4) tone_wmean"""
def save(name, sql):
    con.execute(f"CREATE OR REPLACE TABLE t AS {sql}")
    con.execute(f"COPY t TO '{OUT}\\{name}.csv' (HEADER)")
    print(name, con.execute("select count(*), min(date), max(date) from t").fetchall())
save("gdelt_iran_pair_daily", f"""
  WITH p AS (
    SELECT *, 'IRN-USA' pair FROM ev WHERE (a1='IRN' AND a2='USA') OR (a1='USA' AND a2='IRN')
    UNION ALL SELECT *, 'IRN-ISR' FROM ev WHERE (a1='IRN' AND a2='ISR') OR (a1='ISR' AND a2='IRN')
    UNION ALL SELECT *, 'IRN-USA_OR_ISR' FROM ev WHERE (a1='IRN' AND a2 IN ('USA','ISR')) OR (a2='IRN' AND a1 IN ('USA','ISR')))
  SELECT date, pair, {M} FROM p GROUP BY ALL ORDER BY 1,2""")
save("gdelt_actiongeo_daily", f"""SELECT date, geo AS actiongeo_country_code, {M},
  count(*) FILTER (WHERE quad IN (3,4)) conflict_events
  FROM ev WHERE geo IN ('KU','SA','AE','QA','BA','MU','IZ','IR','CE','IN','PK','AF','IS','GZ','WE','UP','RS')
  GROUP BY ALL ORDER BY 1,2""")
