"""Reproduce every number, table, model and figure in the submission.

    python run_pipeline.py            # full run (about 3-4 minutes on a laptop)
    python run_pipeline.py --no-figs  # skip static PNG export

Stages: 1 clean -> 2 features -> 3 insights -> 4 forecasting + early warning (trained with the D10
world areas) -> 5 scorecard + v2 additions -> 6 figures. Issued competition data only: the earlier
market-data module (src/econ.py) is no longer run.  Outputs: data/processed, outputs/tables, outputs/figures,
models/.
"""
from __future__ import annotations

import argparse
import json
import time

import joblib
import numpy as np
import pandas as pd

from src import cleaning, config as C, extra_sources, features, gdelt, insights, models as M, robustness, upgrades, viz

MODEL_DIR = C.ROOT / "models"
MODEL_DIR.mkdir(exist_ok=True)


def main(figs: bool = True):
    t0 = time.time()
    np.random.seed(C.RANDOM_STATE)
    print("[1/6] Cleaning ...")
    cl = cleaning.run()
    print(f"      {len(cl['dq_log'])} data-quality checks logged")
    print("[2/6] Features ...")
    ft = features.run()
    cm, am = ft["case_month"], ft["admin1_month"]
    print(f"      case-month {cm.shape}, admin1-month {am.shape}")
    print("[3/6] Insights ...")
    ins = insights.run()
    print("[4/6] Forecasting (5 folds x 7 models) ...")
    fc = M.run_all(cm, am)
    abl = M.ablation(cm)
    abl.to_csv(C.TAB_DIR / "ablation_lgb.csv")
    # explainability of the 2026-fold LightGBM-Δ (fitted on <= 2025)
    from src.features import make_supervised
    sup = M._prep_case(make_supervised(cm, ["conflict_case"], horizons=range(1, M.H_MAX + 1)))
    X = sup[(sup.month >= "2015-01-01") & sup.target_y.notna()][M.CASE_FEATURES + ["case_cat"]]
    shap_case = M.shap_importance(fc["models_by_fold"][2026][0], X)
    shap_case.to_csv(C.TAB_DIR / "shap_lgb_case.csv", index=False)
    print("      early warning ...")
    ew = M.early_warning_all(am)
    shap_ew = M.shap_importance(ew["models"][2026], ew["preds"][ew["preds"].fold == 2026][M.EW_FEATURES])
    shap_ew.to_csv(C.TAB_DIR / "shap_early_warning.csv", index=False)
    print("[5/6] Scorecard ...")
    rag = M.rag_scorecard(cm, fc["future"], ew["live"], ins["theatre_spread"])
    rag.to_csv(C.TAB_DIR / "rag_scorecard.csv", index=False)
    print("      GDELT vs UCDP (new, labelled; does not change the models) ...")
    gdelt.run(cm)
    extra_sources.run(cm)
    print("      v2: fast-clock tripwire, reporting completeness, India front, sealed claims ...")
    v2 = upgrades.run(cl["events"], cl["sources"]) if "sources" in cl else upgrades.run()
    print("      evidence strength (bootstrap, Diebold-Mariano, late data, calibration) ...")
    rob = robustness.run(cm)
    joblib.dump(dict(m_case_full=fc["m_case_full"], members=fc["members"], conformal=fc["conformal"],
                     ew_full=ew["clf_full"]), MODEL_DIR / "models.joblib")

    summary = dict(
        ensemble_members=fc["members"],
        holdout_rmsle=fc["rmsle"][fc["rmsle"].fold == 2026].groupby(["track", "model"]).RMSLE.mean().round(3)
        .unstack(0).to_dict(),
        early_warning_2026=ew["report"][ew["report"].year == 2026].round(3).to_dict("records"),
        rag=rag[["conflict_case", "rating", "score", "forecast_next"]].round(0).to_dict("records"),
        robustness=rob,
        runtime_s=round(time.time() - t0, 1),
    )
    (C.TAB_DIR / "run_summary.json").write_text(json.dumps(summary, indent=2, default=str))

    print("      theatre commander briefs (new, notional; writes outputs/theatre/, not outputs/tables/) ...")
    from src import theatre
    tb = theatre.run()
    if figs:
        print("[6/6] Figures ...")
        export_figures(cl, cm, ins, fc, ew, rag, shap_case, shap_ew)
        from src import theatre_viz
        theatre_viz.export_figures(tb)
    print(f"Done in {time.time() - t0:.0f}s")
    return summary


def export_figures(cl, cm, ins, fc, ew, rag, shap_case, shap_ew):
    e = cl["events"]
    viz.save(viz.fig_monthly_deaths(cm), "01_monthly_deaths")
    viz.save(viz.fig_case_small_multiples(cm), "02_case_small_multiples")
    viz.save(viz.fig_dq_summary(cl["dq_log"]), "03_data_quality", height=760)
    viz.save(viz.fig_fog_of_war(ins["geo_precision"]), "04_fog_of_war")
    viz.save(viz.fig_front_geography(ins["front_geography"]), "05_front_geography")
    viz.save(viz.fig_attrition(ins["attrition"]), "06_attrition_ru_ua")
    viz.save(viz.fig_theatre_spread(ins["theatre_spread"]), "07_theatre_spread")
    viz.save(viz.fig_country_map(ins["country_deaths"]), "08_country_map", width=1150, height=640)
    viz.save(viz.fig_afpak(ins["afpak_provinces"]), "09_afpak_provinces")
    viz.save(viz.fig_afpak_interstate(e), "10_afpak_interstate")
    viz.save(viz.fig_seasonality(ins["seasonality"]), "11_seasonality")
    viz.save(viz.fig_violence_mix(ins["violence_mix"]), "12_violence_mix")
    viz.save(viz.fig_media_scatter(ins["media"]), "13_media_scatter")
    viz.save(viz.fig_media_gap(ins["media"]), "14_media_gap")
    viz.save(viz.fig_displacement(ins["displacement"]), "15_displacement")
    viz.save(viz.fig_demographics(ins["demographics_profile"]), "16_demographics")
    viz.save(viz.fig_india_exposure(ins["india_exposure"]), "17_india_exposure")
    viz.save(viz.fig_india_hosted(ins["india_hosted"]), "18_india_hosted")
    for case in C.CASES:
        tag = C.CASE_SHORT[case]
        viz.save(viz.fig_forecast_case(cm, fc["preds"], case, track="A", future=fc["future"]), f"19_forecast_A_{tag}")
        viz.save(viz.fig_forecast_case(cm, fc["preds"], case, track="B"), f"20_forecast_B_{tag}")
    viz.save(viz.fig_model_compare(fc["rmsle"]), "21_model_compare")
    viz.save(viz.fig_shap(shap_case), "22_shap_forecast")
    viz.save(viz.fig_shap(shap_ew, title="What drives the escalation warning (mean |SHAP|)"), "23_shap_early_warning")
    viz.save(viz.fig_ew_curves(ew["preds"]), "24_early_warning_curves")
    viz.save(viz.fig_gdelt_vs_ucdp(pd.read_csv(gdelt.GDIR / "gdelt_case_daily.csv"),
                                   pd.read_parquet(C.PROCESSED / "gdelt_weekly.parquet")), "27_gdelt_vs_ucdp", height=620)
    viz.save(viz.fig_gdelt_lags(pd.read_csv(C.TAB_DIR / "gdelt_weekly_lags.csv")), "28_gdelt_lags", width=900)
    viz.save(viz.fig_ew_calibration(pd.read_csv(C.TAB_DIR / "ew_calibration.csv")), "26_ew_calibration", width=900)
    viz.save(viz.fig_rag(rag), "25_rag_scorecard", height=260)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-figs", action="store_true")
    a = ap.parse_args()
    main(figs=not a.no_figs)
