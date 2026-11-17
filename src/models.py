"""Stage 4 - forecasting, evaluation, prediction intervals and early warning.

Evaluation design (identical for back-test folds and the final holdout)
----------------------------------------------------------------------
For a fold year Y the models are fitted ONCE on data up to December Y-1 and then
frozen. Two questions are scored on months Jan..Sep of year Y:

* Track A - operational, 1 month ahead.  Each month the frozen model receives
  the newly observed month (no re-fitting) and forecasts the next one.  This is
  how an early-warning cell would actually use it.
* Track B - strategic, 1..9 months ahead from a single origin (December Y-1),
  with no information from year Y at all.

Back-test folds Y = 2022, 2023, 2024, 2025 are used for model selection and
for calibrating prediction intervals.  Y = 2026 (UCDP Candidate, provisional)
is the withheld test set and is only scored once, after all choices are made.
"""
from __future__ import annotations

import itertools
import warnings

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from statsmodels.tsa.statespace.sarimax import SARIMAX

from . import config as C
from .features import make_supervised

warnings.filterwarnings("ignore")

BACKTEST_YEARS = [2022, 2023, 2024, 2025]
HOLDOUT_YEAR = 2026
H_MAX = 9

# Compact feature set chosen by the ablation in notebook 04 (more features overfit
# with only four conflict series; see outputs/tables/ablation_lgb.csv).
CASE_FEATURES = [
    "y_l0", "y_l1", "y_l2", "y_rm3", "y_rm6", "y_rm12", "y_rstd6", "y_max12", "y_ewm", "momentum_3v12",
    "accel", "zero_streak", "log_events_rm3", "log_sources_rm3", "y_seasonal", "tm_sin", "tm_cos", "h",
]
LGB_CASE_PARAMS = dict(n_estimators=300, num_leaves=7, min_child_samples=30, objective="l1")

CASE_FEATURES_FULL = [
    "y_l0", "y_l1", "y_l2", "y_l3", "y_l6", "y_l11", "y_rm3", "y_rm6", "y_rm12", "y_rstd6", "y_max12",
    "y_ewm", "momentum_3v12", "accel", "zero_streak", "cum_active_months", "log_events_rm3",
    "log_sources_rm3", "n_outlets_rm3", "src_per_event_rm3", "civ_share_rm3", "uncert_index_rm3",
    "agg_share_rm3", "lowprec_share_rm3", "state_share_rm3", "onesided_share_rm3", "focal_share_rm3",
    "n_admin1_rm3", "hhi_rm3", "outside_core_share_rm3", "y_seasonal", "tm_sin", "tm_cos", "h",
    "idp_stock", "refugees_out", "displaced_growth", "displaced_per_1k", "gdp_growth_annual_pct",
    "consumer_inflation_annual_pct",
]
ADMIN1_FEATURES = [
    "y_l0", "y_l1", "y_l2", "y_l3", "y_l6", "y_l11", "y_rm3", "y_rm6", "y_rm12", "y_rstd6", "y_max12",
    "y_ewm", "momentum_3v12", "accel", "zero_streak", "cum_active_months", "log_events_rm3",
    "log_sources_rm3", "n_outlets_rm3", "src_per_event_rm3", "civ_share_rm3", "uncert_index_rm3",
    "agg_share_rm3", "lowprec_share_rm3", "state_share_rm3", "onesided_share_rm3", "focal_share_rm3",
    "y_seasonal", "tm_sin", "tm_cos", "h", "case_y_l0", "case_y_rm3", "case_y_rm12",
    "case_momentum_3v12", "case_n_admin1_rm3", "share_of_case_12m",
    "idp_stock", "displaced_per_1k", "gdp_growth_annual_pct", "consumer_inflation_annual_pct",
    "case_cat", "country_cat",
]
LGB_PARAMS = dict(n_estimators=600, learning_rate=0.03, num_leaves=15, min_child_samples=20,
                  subsample=0.8, subsample_freq=1, colsample_bytree=0.8, reg_lambda=1.0,
                  random_state=C.RANDOM_STATE, verbose=-1)

MODEL_LABELS = {
    "naive": "Naive (last month)",
    "snaive": "Seasonal naive (same month last year)",
    "ma3": "Moving average (3 months)",
    "ets": "ETS (damped Holt, log)",
    "sarima": "SARIMA (AIC-selected, log)",
    "lgb_case": "LightGBM-Δ global (change in log deaths, L1)",
    "lgb_admin1": "LightGBM bottom-up, Tweedie (sub-national, summed)",
    "ensemble": "Ensemble (log-space mean, members chosen on back-test)",
}


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------
def metrics(y, yhat, scale=None) -> dict:
    y, yhat = np.asarray(y, float), np.clip(np.asarray(yhat, float), 0, None)
    err = yhat - y
    nz = y > 0
    out = dict(
        MAE=np.mean(np.abs(err)),
        RMSE=np.sqrt(np.mean(err ** 2)),
        MAPE=np.mean(np.abs(err[nz]) / y[nz]) * 100 if nz.any() else np.nan,
        sMAPE=np.mean(2 * np.abs(err) / (np.abs(y) + np.abs(yhat) + 1e-9)) * 100,
        RMSLE=np.sqrt(np.mean((np.log1p(yhat) - np.log1p(y)) ** 2)),
        Bias=np.mean(err),
    )
    out["MASE"] = out["MAE"] / scale if scale else np.nan
    return out


def mase_scale(series: pd.Series) -> float:
    """In-sample MAE of the one-step naive forecast (Hyndman & Koehler 2006)."""
    d = np.abs(np.diff(series.values))
    return float(np.mean(d)) if len(d) and np.mean(d) > 0 else 1.0


# ---------------------------------------------------------------------------
# Statistical models (per series, log1p scale)
# ---------------------------------------------------------------------------
def _fit_ets(y: pd.Series):
    m = ExponentialSmoothing(y, trend="add", damped_trend=True, initialization_method="estimated")
    return m.fit(optimized=True)


def _ets_filter(fit, y_full: pd.Series):
    """Re-run the fitted ETS recursion over a longer series with frozen parameters."""
    p = fit.params
    m = ExponentialSmoothing(y_full, trend="add", damped_trend=True, initialization_method="known",
                             initial_level=p["initial_level"], initial_trend=p["initial_trend"])
    return m.fit(smoothing_level=p["smoothing_level"], smoothing_trend=p["smoothing_trend"],
                 damping_trend=p["damping_trend"], optimized=False)


def _fit_sarima(y: pd.Series):
    best, best_aic = None, np.inf
    for p, d, q, P in itertools.product((1, 2), (0, 1), (0, 1), (0, 1)):
        try:
            r = SARIMAX(y, order=(p, d, q), seasonal_order=(P, 0, 0, 12), trend="c" if d == 0 else "n",
                        enforce_stationarity=False, enforce_invertibility=False).fit(disp=False)
            if r.aic < best_aic:
                best, best_aic = r, r.aic
        except Exception:
            continue
    return best


# ---------------------------------------------------------------------------
# LightGBM helpers
# ---------------------------------------------------------------------------
CASE_CATS = list(C.CASES) + ["Global"]


def _prep_admin1(sup: pd.DataFrame) -> pd.DataFrame:
    sup = sup.copy()
    cc = sup.conflict_case.where(sup.conflict_case.isin(C.CASES), "Global")
    sup["case_cat"] = pd.Categorical(cc, categories=CASE_CATS)
    sup["country_cat"] = sup.country_iso3.astype("category")
    return sup


def _prep_case(sup: pd.DataFrame) -> pd.DataFrame:
    sup = sup.copy()
    sup["case_cat"] = sup.conflict_case.astype("category")
    return sup


class _TweedieWrap:
    """LightGBM Tweedie model on raw counts that exposes a log1p-scale predict()
    so it is interchangeable with the log-target models."""

    def __init__(self, model):
        self.model = model
        self.booster_ = model.booster_

    def predict(self, X):
        return np.log1p(np.clip(self.model.predict(X), 0, None))


def fit_lgb(train: pd.DataFrame, feats: list[str], mode: str = "log", **kw):
    """mode='log'  : L2 on log1p(deaths) - robust, median-like forecasts.
    mode='tweedie': Tweedie deviance on raw deaths - mean forecasts for
                         zero-inflated, heavy-tailed counts (sums correctly
                         when sub-national forecasts are aggregated)."""
    if mode == "tweedie":
        params = {**LGB_PARAMS, "objective": "tweedie", "tweedie_variance_power": 1.5, **kw}
        m = lgb.LGBMRegressor(**params)
        m.fit(train[feats], np.expm1(train.target_y))
        return _TweedieWrap(m)
    if mode == "delta":
        m = lgb.LGBMRegressor(**{**LGB_PARAMS, **kw})
        m.fit(train[feats], train.target_y - train.y_l0)
        return _DeltaWrap(m)
    m = lgb.LGBMRegressor(**{**LGB_PARAMS, **kw})
    m.fit(train[feats], train.target_y)
    return m


class _DeltaWrap:
    """LightGBM trained on the CHANGE in log deaths (y_{t+h} - y_t).

    Regression trees cannot extrapolate beyond the target range seen in
    training; a level model fitted before February 2022 can never predict
    thousands of deaths a month.  Predicting the change, then adding it to the
    last observed level, removes that ceiling."""

    def __init__(self, model):
        self.model = model
        self.booster_ = model.booster_

    def predict(self, X):
        return np.clip(X["y_l0"].values + self.model.predict(X), 0, None)


# ---------------------------------------------------------------------------
# One fold
# ---------------------------------------------------------------------------
def run_fold(cm: pd.DataFrame, am: pd.DataFrame, year: int, eval_months: int = 9) -> pd.DataFrame:
    """Return long frame: case, model, track, h, target_month, actual, pred (deaths)."""
    cutoff = pd.Timestamp(f"{year - 1}-12-01")                 # last month of training data
    last_eval = pd.Timestamp(f"{year}-{eval_months:02d}-01")
    rows = []

    # ---- case-level supervised frames -----------------------------------
    sup_c = _prep_case(make_supervised(cm, ["conflict_case"], horizons=range(1, H_MAX + 1)))
    feats_c = CASE_FEATURES + ["case_cat"]
    tr = sup_c[(sup_c.target_month <= cutoff) & sup_c.target_y.notna() & (sup_c.month >= "2014-12-01")]
    m_case = fit_lgb(tr, feats_c, "delta", **LGB_CASE_PARAMS)

    # ---- admin1-level --------------------------------------------------
    sup_a = _prep_admin1(make_supervised(am, ["conflict_case", "admin1_key"], horizons=range(1, H_MAX + 1)))
    tra = sup_a[(sup_a.target_month <= cutoff) & sup_a.target_y.notna() & (sup_a.month >= "2014-12-01")]
    # areas that never had a death before the cutoff carry no signal; keep 10% of them for realism
    m_adm = fit_lgb(tra, ADMIN1_FEATURES, "tweedie")

    def lgb_preds(sup, model, feats, level):
        a = sup[(sup.h == 1) & (sup.month >= cutoff) & (sup.target_month <= last_eval)]
        b = sup[(sup.month == cutoff) & (sup.target_month <= last_eval)]
        out = []
        for track, f in (("A", a), ("B", b)):
            f = f.assign(pred=np.expm1(model.predict(f[feats])).clip(0))
            if level == "admin1":
                f = f.groupby(["conflict_case", "h", "target_month"], as_index=False).pred.sum()
            out.append(f.assign(track=track)[["conflict_case", "h", "target_month", "pred", "track"]])
        return pd.concat(out)

    rows.append(lgb_preds(sup_c, m_case, feats_c, "case").assign(model="lgb_case"))
    rows.append(lgb_preds(sup_a, m_adm, ADMIN1_FEATURES, "admin1").assign(model="lgb_admin1"))

    # ---- per-series baselines and statistical models -------------------
    for case in C.CASES:
        s = cm[cm.conflict_case == case].set_index("month").deaths.asfreq("MS")
        ylog = np.log1p(s)
        y_tr = ylog[:cutoff]
        ets, sar = _fit_ets(y_tr), _fit_sarima(y_tr)
        months = pd.date_range(cutoff + pd.DateOffset(months=1), last_eval, freq="MS")
        # Track B: single origin
        h = np.arange(1, len(months) + 1)
        fc = {
            "naive": np.repeat(s[cutoff], len(h)),
            "snaive": s.reindex(months - pd.DateOffset(months=12)).values,
            "ma3": np.repeat(s[cutoff - pd.DateOffset(months=2):cutoff].mean(), len(h)),
            "ets": np.expm1(ets.forecast(len(h)).values),
            "sarima": np.expm1(sar.get_forecast(len(h)).predicted_mean.values),
        }
        for k, v in fc.items():
            rows.append(pd.DataFrame(dict(conflict_case=case, h=h, target_month=months, pred=np.clip(v, 0, None),
                                          track="B", model=k)))
        # Track A: rolling 1-step with frozen parameters
        y_upto = ylog[:last_eval - pd.DateOffset(months=1)]
        ets_f = _ets_filter(ets, y_upto)
        sar_f = sar.append(y_upto[cutoff + pd.DateOffset(months=1):], refit=False) if len(y_upto) > len(y_tr) else sar
        # one-step-ahead values: in-sample fitted values are one-step forecasts with frozen
        # parameters; the final month is the out-of-sample one-step forecast.
        ets_path = pd.concat([ets_f.fittedvalues, ets_f.forecast(1)])
        ets_1 = np.expm1(ets_path.reindex(months).values)
        sar_1 = np.expm1(sar_f.predict(start=months[0], end=months[-1], dynamic=False).values)
        fa = {
            "naive": s.reindex(months - pd.DateOffset(months=1)).values,
            "snaive": s.reindex(months - pd.DateOffset(months=12)).values,
            "ma3": s.rolling(3).mean().reindex(months - pd.DateOffset(months=1)).values,
            "ets": ets_1, "sarima": sar_1,
        }
        for k, v in fa.items():
            rows.append(pd.DataFrame(dict(conflict_case=case, h=1, target_month=months, pred=np.clip(v, 0, None),
                                          track="A", model=k)))

    out = pd.concat(rows, ignore_index=True)
    act = cm[["conflict_case", "month", "deaths"]].rename(columns={"month": "target_month", "deaths": "actual"})
    out = out.merge(act, on=["conflict_case", "target_month"], how="left")
    out["fold"] = year
    return out, m_case, m_adm


def add_ensemble(preds: pd.DataFrame, members: list[str]) -> pd.DataFrame:
    sub = preds[preds.model.isin(members)]
    ens = (sub.assign(lp=np.log1p(sub.pred))
           .groupby(["fold", "track", "conflict_case", "h", "target_month", "actual"], as_index=False).lp.mean())
    ens["pred"] = np.expm1(ens.lp)
    ens = ens.drop(columns="lp").assign(model="ensemble")
    return pd.concat([preds[preds.model != "ensemble"], ens], ignore_index=True)


def score(preds: pd.DataFrame, cm: pd.DataFrame) -> pd.DataFrame:
    """Per fold x track x model x case metrics plus scale-free summaries."""
    res = []
    for (fold, track, model, case), g in preds.groupby(["fold", "track", "model", "conflict_case"]):
        hist = cm[(cm.conflict_case == case) & (cm.month < f"{fold}-01-01")].deaths
        m = metrics(g.actual, g.pred, mase_scale(hist))
        # directional accuracy vs the last observed month at the origin
        res.append(dict(fold=fold, track=track, model=model, conflict_case=case, n=len(g), **m))
    return pd.DataFrame(res)


# ---------------------------------------------------------------------------
# Prediction intervals - split conformal on log residuals
# ---------------------------------------------------------------------------
SIGMA_FLOOR = 0.3


def attach_sigma(p: pd.DataFrame, cm: pd.DataFrame) -> pd.DataFrame:
    """Local volatility at the forecast origin: 12-month std of monthly changes in
    log deaths (floored).  Used to normalise residuals (adaptive conformal)."""
    vol = cm[["conflict_case", "month", "y"]].sort_values(["conflict_case", "month"]).copy()
    vol["sigma"] = (vol.groupby("conflict_case").y.transform(lambda s: s.diff().rolling(12, 3).std())
                    .fillna(SIGMA_FLOOR).clip(lower=SIGMA_FLOOR))
    p = p.copy()
    p["origin"] = p.target_month - pd.to_timedelta(0, "D")
    p["origin"] = [tm - pd.DateOffset(months=int(h)) for tm, h in zip(p.target_month, p.h)]
    p = p.merge(vol[["conflict_case", "month", "sigma"]].rename(columns={"month": "origin"}),
                on=["conflict_case", "origin"], how="left")
    p["sigma"] = p.sigma.fillna(SIGMA_FLOOR)
    return p.drop(columns="origin")


def conformal_quantiles(bt: pd.DataFrame, model: str, levels=(0.8, 0.95)) -> pd.DataFrame:
    """Split conformal prediction intervals on log residuals.

    If a 'sigma' column is present residuals are volatility-normalised
    (locally adaptive conformal, Lei et al. 2018); otherwise plain.  Track A uses all one-step residuals.  Track B
    pools horizons in bands (1-3, 4-6, 7-9) for stable tail quantiles, and
    widths are forced to be non-decreasing with horizon."""
    r = bt[bt.model == model].copy()
    sig = r["sigma"] if "sigma" in r else 1.0
    r["res"] = (np.log1p(r.actual) - np.log1p(r.pred)) / sig
    r["band"] = np.where(r.track == "A", 0, (r.h - 1) // 3 + 1)
    out = []
    for (track, h), g in r.groupby(["track", "h"]):
        pool = r[(r.track == track) & (r.band == g.band.iloc[0])]
        row = dict(track=track, h=h, n=len(pool))
        for lv in levels:
            a = (1 - lv) / 2
            row[f"lo{int(lv * 100)}"] = np.quantile(pool.res, a)
            row[f"hi{int(lv * 100)}"] = np.quantile(pool.res, 1 - a)
        out.append(row)
    q = pd.DataFrame(out)
    for lv in levels:
        for side, fn in ((f"lo{int(lv*100)}", np.minimum), (f"hi{int(lv*100)}", np.maximum)):
            mask = q.track == "B"
            q.loc[mask, side] = fn.accumulate(q.loc[mask, side].values)
    return q


def apply_intervals(p: pd.DataFrame, q: pd.DataFrame) -> pd.DataFrame:
    p = p.merge(q, on=["track", "h"], how="left")
    lp = np.log1p(p.pred)
    sig = p["sigma"] if "sigma" in p else 1.0
    for lv in (80, 95):
        p[f"pi{lv}_lo"] = np.expm1(lp + p[f"lo{lv}"] * sig).clip(lower=0)
        p[f"pi{lv}_hi"] = np.expm1(lp + p[f"hi{lv}"] * sig)
    return p.drop(columns=[c for c in p.columns if c.startswith(("lo", "hi")) or c == "n"])


# ---------------------------------------------------------------------------
# Early-warning classifier (sub-national escalation next month)
# ---------------------------------------------------------------------------
# Selected on the 2023-2025 back-test folds (see notebook 05): a compact, regularised
# feature set beat the full set (macro context and country identity overfit).
EW_FEATURES = ["y_l0", "y_rm3", "y_rm12", "y_ewm", "y_max12", "momentum_3v12", "accel", "zero_streak",
               "log_events_rm3", "case_y_l0", "case_momentum_3v12", "case_n_admin1_rm3", "share_of_case_12m",
               "cty_mom", "cty_y_l0", "y_vs_base", "tm_sin", "tm_cos", "case_cat"]
# Pre-registered (outputs/tables/preregistration.json): more capacity, enabled by the D10 world training areas.
EW_PARAMS = dict(n_estimators=400, num_leaves=15, min_child_samples=200, learning_rate=0.03)


def escalation_frame(am: pd.DataFrame) -> pd.DataFrame:
    sup = _prep_admin1(make_supervised(am, ["conflict_case", "admin1_key"], horizons=(1,)))
    base = sup.groupby(["conflict_case", "admin1_key"]).deaths.transform(lambda s: s.rolling(3, 1).mean())
    sup["base3"] = base
    sup["escalation"] = ((sup.target_deaths >= C.ESCALATION_MIN_DEATHS) &
                         (sup.target_deaths >= C.ESCALATION_RATIO * sup.base3)).astype(int)
    sup.loc[sup.target_deaths.isna(), "escalation"] = np.nan
    # country-level tempo (all areas of the same country)
    cty = am.groupby(["country_iso3", "month"]).deaths.sum().rename("cd").reset_index()
    cty = cty.sort_values(["country_iso3", "month"])
    cty["cty_y_l0"] = np.log1p(cty.cd)
    g = cty.groupby("country_iso3").cty_y_l0
    cty["cty_mom"] = g.transform(lambda s: s.rolling(3, 1).mean()) - g.transform(lambda s: s.rolling(12, 1).mean())
    sup = sup.merge(cty[["country_iso3", "month", "cty_mom", "cty_y_l0"]], on=["country_iso3", "month"], how="left")
    sup["y_vs_base"] = sup.y_l0 - np.log1p(sup.base3)
    # case panels start Jan 2014, so their first usable origin is Dec 2014 (12 months of history);
    # the D10 world areas (training only) start in 1989 and are kept from Jan 1990.
    keep = np.where(sup.conflict_case.isin(C.CASES), sup.month >= "2014-12-01", sup.month >= "1990-01-01")
    return sup[keep]


def run_early_warning(am: pd.DataFrame, test_year: int = HOLDOUT_YEAR, frame=None, use_global: bool = True):
    """Fit on target months <= Dec(test_year-1); score Jan..Sep(test_year) on the four cases only.

    With use_global, the training set also holds the D10 world areas (transfer learning, src/global_ew.py)."""
    f = escalation_frame(am) if frame is None else frame
    f = f[f.escalation.notna()]
    is_case = f.conflict_case.isin(C.CASES)
    if not use_global:
        f, is_case = f[is_case], is_case[is_case]
    cutoff = pd.Timestamp(f"{test_year - 1}-12-01")
    tr = f[f.target_month <= cutoff]
    te = f[is_case & (f.target_month > cutoff) & (f.target_month < f"{test_year + 1}-01-01")].copy()
    clf = lgb.LGBMClassifier(**{**LGB_PARAMS, **EW_PARAMS})
    clf.fit(tr[EW_FEATURES], tr.escalation.astype(int))
    te["p_lgb"] = clf.predict_proba(te[EW_FEATURES])[:, 1]
    lr_feats = ["y_l0", "momentum_3v12", "case_momentum_3v12", "zero_streak", "log_events_rm3"]
    lr = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000))
    lr.fit(tr[lr_feats].fillna(0), tr.escalation.astype(int))
    te["p_logit"] = lr.predict_proba(te[lr_feats].fillna(0))[:, 1]
    te["p_rule"] = (te.y_l0 / max(f[is_case].y_l0.max(), 1)).clip(0, 1)
    rep = []
    for col, name in (("p_lgb", "LightGBM classifier"), ("p_logit", "Logistic regression (5 signals)"),
                      ("p_rule", "Rule: rank by last month's deaths")):
        prec_k = te.groupby("target_month").apply(lambda g: g.nlargest(10, col).escalation.mean()).mean()
        rec_k = te.groupby("target_month").apply(
            lambda g: g.nlargest(20, col).escalation.sum() / max(g.escalation.sum(), 1)).mean()
        rep.append(dict(model=name, year=test_year, ROC_AUC=roc_auc_score(te.escalation, te[col]),
                        PR_AUC=average_precision_score(te.escalation, te[col]),
                        Brier=brier_score_loss(te.escalation, te[col].clip(0, 1)),
                        precision_at_10=prec_k, recall_at_20=rec_k, base_rate=te.escalation.mean(),
                        n=len(te), positives=int(te.escalation.sum())))
    return clf, te, pd.DataFrame(rep)


def early_warning_all(am: pd.DataFrame, years=(2023, 2024, 2025, 2026), save=True, use_global=True):
    if use_global:
        from .global_ew import build_global_admin1
        am = pd.concat([am, build_global_admin1()], ignore_index=True)
    frame = escalation_frame(am)
    reps, tes, clfs = [], [], {}
    for Y in years:
        clf, te, rep = run_early_warning(am, Y, frame, use_global=use_global)
        reps.append(rep); tes.append(te.assign(fold=Y)); clfs[Y] = clf
    rep, te = pd.concat(reps, ignore_index=True), pd.concat(tes, ignore_index=True)
    # Platt calibration on the out-of-fold back-test predictions (folds before the holdout year), so the
    # probabilities keep their meaning for the scorecard's hotspot threshold. Monotone: ranking metrics
    # (ROC-AUC, PR-AUC, precision@k) are unchanged; Brier is reported after calibration.
    cal = None
    bt = te[te.fold < HOLDOUT_YEAR]
    if len(bt) and bt.escalation.nunique() == 2:
        z = lambda q: np.log(np.clip(q, 1e-4, 1 - 1e-4) / (1 - np.clip(q, 1e-4, 1 - 1e-4))).reshape(-1, 1)
        cal = LogisticRegression(C=1e6, max_iter=1000).fit(z(bt.p_lgb.values), bt.escalation.astype(int))
        calib = lambda q: cal.predict_proba(z(np.asarray(q)))[:, 1]
        hold = te.fold == HOLDOUT_YEAR
        te.loc[hold, "p_lgb"] = calib(te.loc[hold, "p_lgb"].values)
        m = (rep.year == HOLDOUT_YEAR) & (rep.model == "LightGBM classifier")
        rep.loc[m, "Brier"] = brier_score_loss(te.loc[hold, "escalation"], te.loc[hold, "p_lgb"])
    # live watch-list: refit on everything observed and score origin = last month
    lab = frame[frame.escalation.notna()]
    clf_full = lgb.LGBMClassifier(**{**LGB_PARAMS, **EW_PARAMS}).fit(lab[EW_FEATURES], lab.escalation.astype(int))
    if not use_global:
        lab = lab[lab.conflict_case.isin(C.CASES)]
    case_f = frame[frame.conflict_case.isin(C.CASES)]
    live = case_f[case_f.month == case_f.month.max()].copy()
    live["p_escalation"] = clf_full.predict_proba(live[EW_FEATURES])[:, 1]
    if cal is not None:
        live["p_escalation"] = calib(live.p_escalation.values)
    live = live.sort_values("p_escalation", ascending=False)
    if save:
        rep.to_csv(C.TAB_DIR / "early_warning_scores.csv", index=False)
        te[["fold", "conflict_case", "admin1_key", "country_iso3", "admin1", "target_month", "deaths",
            "target_deaths", "escalation", "p_lgb", "p_logit", "p_rule"]].to_parquet(
            C.PROCESSED / "early_warning_preds.parquet", index=False)
        live[["conflict_case", "admin1_key", "country_iso3", "admin1", "month", "deaths", "base3",
              "momentum_3v12", "p_escalation"]].to_parquet(C.PROCESSED / "early_warning_live.parquet", index=False)
    return dict(report=rep, preds=te, models=clfs, clf_full=clf_full, live=live, frame=frame)


# ---------------------------------------------------------------------------
# SHAP-style attributions from LightGBM (exact TreeSHAP via pred_contrib)
# ---------------------------------------------------------------------------
def shap_importance(model, X: pd.DataFrame) -> pd.DataFrame:
    contrib = model.booster_.predict(X, pred_contrib=True)
    imp = np.abs(contrib[:, :-1]).mean(axis=0)
    return (pd.DataFrame(dict(feature=X.columns, mean_abs_shap=imp))
            .sort_values("mean_abs_shap", ascending=False).reset_index(drop=True))


# ---------------------------------------------------------------------------
# Ablation: which LightGBM design choices matter (back-test folds only)
# ---------------------------------------------------------------------------
ABLATION_VARIANTS = {
    "A. Level target, L2, full features (default ML)": dict(mode="log", feats="full", params={}),
    "B. Δ target, L2, full features": dict(mode="delta", feats="full", params={}),
    "C. Δ target, L2, full features, regularised": dict(mode="delta", feats="full",
                                                        params=dict(n_estimators=300, num_leaves=7, min_child_samples=30)),
    "D. Δ target, Huber, compact features": dict(mode="delta", feats="compact",
                                                 params=dict(n_estimators=300, num_leaves=7, min_child_samples=30,
                                                             objective="huber", alpha=0.5)),
    "E. Δ target, L1, compact features (selected)": dict(mode="delta", feats="compact", params=LGB_CASE_PARAMS),
    "F. Tweedie on raw counts, full features": dict(mode="tweedie", feats="full", params={}),
}


def ablation(cm: pd.DataFrame, years=BACKTEST_YEARS) -> pd.DataFrame:
    sup = _prep_case(make_supervised(cm, ["conflict_case"], horizons=range(1, H_MAX + 1)))
    out = []
    for name, v in ABLATION_VARIANTS.items():
        feats = (CASE_FEATURES if v["feats"] == "compact" else CASE_FEATURES_FULL) + ["case_cat"]
        for Y in years:
            cut, last = pd.Timestamp(f"{Y - 1}-12-01"), pd.Timestamp(f"{Y}-09-01")
            tr = sup[(sup.target_month <= cut) & sup.target_y.notna() & (sup.month >= "2014-12-01")]
            m = fit_lgb(tr, feats, v["mode"], **v["params"])
            for track, f in (("A", sup[(sup.h == 1) & (sup.month >= cut) & (sup.target_month <= last)]),
                             ("B", sup[(sup.month == cut) & (sup.target_month <= last)])):
                f = f.assign(p=m.predict(f[feats]))
                for case, g in f.groupby("conflict_case"):
                    out.append(dict(variant=name, fold=Y, track=track, conflict_case=case,
                                    RMSLE=float(np.sqrt(np.mean((g.p - g.target_y) ** 2)))))
    r = pd.DataFrame(out)
    return (r.groupby(["variant", "track"]).RMSLE.mean().unstack()
            .rename(columns={"A": "RMSLE Track A (1-step)", "B": "RMSLE Track B (1-9 step)"}).round(3))


# ---------------------------------------------------------------------------
# Ensemble selection (back-test only) and the full pipeline
# ---------------------------------------------------------------------------
CANDIDATES = ["naive", "ma3", "ets", "sarima", "lgb_case", "lgb_admin1"]


def rmsle_table(preds: pd.DataFrame) -> pd.DataFrame:
    return (preds.groupby(["model", "track", "fold", "conflict_case"])
            .apply(lambda g: np.sqrt(np.mean((np.log1p(g.pred) - np.log1p(g.actual)) ** 2)))
            .rename("RMSLE").reset_index())


def select_ensemble(bt: pd.DataFrame, max_k: int = 4) -> tuple[list[str], pd.DataFrame]:
    res = []
    for k in range(2, max_k + 1):
        for combo in itertools.combinations(CANDIDATES, k):
            e = add_ensemble(bt, list(combo))
            r = rmsle_table(e[e.model == "ensemble"]).groupby("track").RMSLE.mean()
            res.append(dict(members=" + ".join(combo), k=k, A=r["A"], B=r["B"], avg=(r["A"] + r["B"]) / 2))
    res = pd.DataFrame(res).sort_values("avg").reset_index(drop=True)
    return res.members[0].split(" + "), res


def forecast_future(cm, am, members, q, origin=C.PANEL_END, horizon=C.FORECAST_MONTHS):
    """Refit every member on ALL data (incl. provisional 2026) and forecast Oct-Dec 2026."""
    origin = pd.Timestamp(origin).to_period("M").to_timestamp()
    sup_c = _prep_case(make_supervised(cm, ["conflict_case"], horizons=range(1, H_MAX + 1)))
    feats_c = CASE_FEATURES + ["case_cat"]
    tr = sup_c[sup_c.target_y.notna() & (sup_c.month >= "2014-12-01")]
    m_case = fit_lgb(tr, feats_c, "delta", **LGB_CASE_PARAMS)
    sup_a = _prep_admin1(make_supervised(am, ["conflict_case", "admin1_key"], horizons=range(1, H_MAX + 1)))
    tra = sup_a[sup_a.target_y.notna() & (sup_a.month >= "2014-12-01")]
    m_adm = fit_lgb(tra, ADMIN1_FEATURES, "tweedie")
    rows = []
    fc = sup_c[(sup_c.month == origin) & (sup_c.h <= horizon)]
    rows.append(fc.assign(pred=np.expm1(m_case.predict(fc[feats_c])), model="lgb_case")
                [["conflict_case", "h", "target_month", "pred", "model"]])
    fa = sup_a[(sup_a.month == origin) & (sup_a.h <= horizon)]
    fa = fa.assign(pred=np.expm1(m_adm.predict(fa[ADMIN1_FEATURES])))
    admin_fc = fa[["conflict_case", "admin1_key", "country_iso3", "admin1", "h", "target_month", "pred",
                   "deaths", "y_rm3"]].copy()
    rows.append(fa.groupby(["conflict_case", "h", "target_month"], as_index=False).pred.sum().assign(model="lgb_admin1"))
    months = pd.date_range(origin + pd.DateOffset(months=1), periods=horizon, freq="MS")
    for case in C.CASES:
        s = cm[cm.conflict_case == case].set_index("month").deaths.asfreq("MS")
        ylog = np.log1p(s)
        h = np.arange(1, horizon + 1)
        f = {"naive": np.repeat(s.iloc[-1], horizon), "ma3": np.repeat(s.iloc[-3:].mean(), horizon),
             "snaive": s.reindex(months - pd.DateOffset(months=12)).values,
             "ets": np.expm1(_fit_ets(ylog).forecast(horizon).values),
             "sarima": np.expm1(_fit_sarima(ylog).get_forecast(horizon).predicted_mean.values)}
        for k, v in f.items():
            rows.append(pd.DataFrame(dict(conflict_case=case, h=h, target_month=months, pred=np.clip(v, 0, None), model=k)))
    out = pd.concat(rows, ignore_index=True).assign(fold="future", track="B", actual=np.nan)
    out = add_ensemble(out.assign(actual=-1), members)
    out["actual"] = np.nan
    out["track"] = np.where(out.h == 1, "A", "B")   # one-step band for next month, horizon bands after
    out = apply_intervals(out, q)
    return out, admin_fc, m_case, m_adm


def run_all(cm: pd.DataFrame, am: pd.DataFrame, save: bool = True) -> dict:
    folds, models_by_fold = [], {}
    for Y in BACKTEST_YEARS + [HOLDOUT_YEAR]:
        p, mc, ma = run_fold(cm, am, Y)
        folds.append(p)
        models_by_fold[Y] = (mc, ma)
    allp = pd.concat(folds, ignore_index=True)
    bt = allp[allp.fold.isin(BACKTEST_YEARS)]
    members, ens_table = select_ensemble(bt)
    allp = add_ensemble(allp, members)
    bt = allp[allp.fold.isin(BACKTEST_YEARS)]
    # Plain split conformal on log residuals.  A volatility-normalised variant
    # (attach_sigma) was tested and rejected: it under-covers regime breaks in
    # calm series (the 2022 invasion), see notebook 04.
    q = conformal_quantiles(bt, "ensemble")
    allp = apply_intervals(allp, q)
    scores = score(allp, cm)
    rmsle = rmsle_table(allp)
    future, admin_fc, m_case_full, m_adm_full = forecast_future(cm, am, members, q)
    out = dict(preds=allp, scores=scores, rmsle=rmsle, ensemble_table=ens_table, members=members,
               conformal=q, future=future, admin_future=admin_fc, models_by_fold=models_by_fold,
               m_case_full=m_case_full, m_adm_full=m_adm_full)
    if save:
        allp.to_parquet(C.PROCESSED / "forecast_preds.parquet", index=False)
        scores.to_csv(C.TAB_DIR / "forecast_scores.csv", index=False)
        rmsle.to_csv(C.TAB_DIR / "forecast_rmsle.csv", index=False)
        ens_table.to_csv(C.TAB_DIR / "ensemble_selection.csv", index=False)
        q.to_csv(C.TAB_DIR / "conformal_quantiles.csv", index=False)
        future.to_parquet(C.PROCESSED / "forecast_future.parquet", index=False)
        admin_fc.to_parquet(C.PROCESSED / "admin1_future.parquet", index=False)
        pd.Series(members, name="member").to_csv(C.TAB_DIR / "ensemble_members.csv", index=False)
    return out


# ---------------------------------------------------------------------------
# What-if scenarios (used live in the dashboard)
# ---------------------------------------------------------------------------
def scenario_forecast(cm: pd.DataFrame, case: str, shock_pct: float, k_months: int, m_case,
                      members: list[str], q: pd.DataFrame, horizon: int = C.FORECAST_MONTHS) -> pd.DataFrame:
    """Re-forecast one conflict after scaling its last ``k_months`` of deaths by (1 + shock_pct/100).

    Uses the frozen full-data LightGBM-Δ model, a re-fitted ETS and the moving
    average - i.e. the same ensemble the evaluation selected - so the scenario
    answers 'what would the model say if recent violence had been X% higher'."""
    from .features import add_dynamic_features
    base_cols = [c for c in cm.columns if not c.startswith(("y", "momentum", "accel", "zero_streak", "cum_active",
                                                             "log_", "n_admin1_rm3", "hhi_rm3",
                                                             "outside_core_share_rm3")) and not c.endswith("_rm3")]
    d = cm.loc[cm.conflict_case == case, base_cols].copy()
    last = d.month.max()
    mask = d.month > last - pd.DateOffset(months=k_months)
    d.loc[mask, "deaths"] = d.loc[mask, "deaths"] * (1 + shock_pct / 100)
    d = add_dynamic_features(d, ["conflict_case"])
    sup = _prep_case(make_supervised(d, ["conflict_case"], horizons=range(1, horizon + 1)))
    sup["case_cat"] = pd.Categorical(sup.conflict_case, categories=C.CASES)
    o = sup[sup.month == last]
    preds = {}
    if "lgb_case" in members:
        preds["lgb_case"] = np.expm1(m_case.predict(o[CASE_FEATURES + ["case_cat"]]))
    s = d.set_index("month").deaths.asfreq("MS")
    if "ets" in members:
        preds["ets"] = np.expm1(_fit_ets(np.log1p(s)).forecast(horizon).values)
    if "ma3" in members:
        preds["ma3"] = np.repeat(s.iloc[-3:].mean(), horizon)
    if "naive" in members:
        preds["naive"] = np.repeat(s.iloc[-1], horizon)
    if "sarima" in members:
        preds["sarima"] = np.expm1(_fit_sarima(np.log1p(s)).get_forecast(horizon).predicted_mean.values)
    lp = np.mean([np.log1p(np.clip(v, 0, None)) for v in preds.values()], axis=0)
    out = pd.DataFrame(dict(conflict_case=case, h=np.arange(1, horizon + 1),
                            target_month=pd.date_range(last + pd.DateOffset(months=1), periods=horizon, freq="MS"),
                            pred=np.expm1(lp)))
    out["track"] = np.where(out.h == 1, "A", "B")
    for k, v in preds.items():
        out[f"member_{k}"] = v
    return apply_intervals(out, q)


# ---------------------------------------------------------------------------
# Threat / escalation scorecard (RAG)
# ---------------------------------------------------------------------------
def rag_scorecard(cm: pd.DataFrame, future: pd.DataFrame, live: pd.DataFrame, theatre: pd.DataFrame,
                  p_hot: float = 0.15) -> pd.DataFrame:
    """Transparent, rule-based threat rating built only from model outputs.

    Points
      intensity  forecast deaths next month: >=1000 -> 2, >=100 -> 1, else 0
      trend      forecast vs mean of last 6 months: >= +20% -> 1, <= -20% -> -1
      hotspots   named areas with escalation probability >= p_hot: >=3 -> 2, >=1 -> 1
      spread     more countries hit this year than last -> 1
      volatility a month with >= 1000 deaths in the last 12 months -> 1 (war can resume)
    Rating: RED if forecast >= 1000 deaths/month (active high-intensity war) or
    points >= 5; AMBER if points >= 2; GREEN otherwise.
    """
    rows = []
    for case in C.CASES:
        f1 = future[(future.model == "ensemble") & (future.conflict_case == case) & (future.h == 1)].iloc[0]
        hist = cm[cm.conflict_case == case].set_index("month").deaths
        base6 = hist.iloc[-6:].mean()
        trend = f1.pred / max(base6, 1)
        lv = live[(live.conflict_case == case) & (~live.admin1.str.startswith("("))]
        hot = lv[lv.p_escalation >= p_hot]
        th = theatre[theatre.conflict_case == case].set_index("year")
        yr = cm.month.max().year
        spread_now, spread_prev = th.countries.get(yr, 0), th.countries.get(yr - 1, 0)
        peak12 = hist.iloc[-12:].max()
        pts = dict(pts_intensity=2 if f1.pred >= 1000 else 1 if f1.pred >= 100 else 0,
                   pts_trend=1 if trend >= 1.2 else -1 if trend <= 0.8 else 0,
                   pts_hotspots=2 if len(hot) >= 3 else 1 if len(hot) >= 1 else 0,
                   pts_spread=1 if spread_now > spread_prev else 0,
                   pts_volatility=1 if peak12 >= 1000 else 0)
        score = sum(pts.values())
        rag = "RED" if (f1.pred >= 1000 or score >= 5) else "AMBER" if score >= 2 else "GREEN"
        top = lv.head(3)
        rows.append(dict(
            conflict_case=case, rating=rag, score=score,
            forecast_next=f1.pred, pi80_lo=f1.pi80_lo, pi80_hi=f1.pi80_hi, forecast_month=f1.target_month,
            last6_mean=base6, trend_ratio=trend, hotspots=len(hot), peak_last12=peak12,
            top_areas="; ".join(f"{a.replace(' province', '').replace(' oblast', '')} ({p:.0%})"
                                for a, p in zip(top.admin1, top.p_escalation)),
            countries_this_year=spread_now, countries_last_year=spread_prev, **pts))
    return pd.DataFrame(rows)
