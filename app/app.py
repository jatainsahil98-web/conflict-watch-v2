"""CONFLICT EW - interactive dashboard for the Data Analytics Competition 2026.

Run from the submission folder:
    streamlit run app/app.py

It reads the artefacts written by ``python run_pipeline.py`` (already included),
so it starts in seconds and works offline. The What-if and Live re-train pages
run the real models on the fly.
"""
from __future__ import annotations

import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src import config as C, viz  # noqa: E402
from src import models as M  # noqa: E402
from src import theatre as TH, theatre_viz as TV  # noqa: E402

T = C.THEME
# The Ops site (the default) is shown full screen with no Streamlit sidebar; the site has its own
# navigation, and its Ops console has its own left rail. The 15-page analyst dashboard, with the
# Streamlit sidebar, opens with ?mode=analyst.
ANALYST = st.query_params.get("mode", "") == "analyst"
st.set_page_config(page_title="Conflict EW | Data Analytics Competition 2026", page_icon="🛰️", layout="wide",
                   initial_sidebar_state="expanded" if ANALYST else "collapsed")

# ---------------------------------------------------------------------------
# Styling: the jury-deck theme, sized for a video call
# ---------------------------------------------------------------------------
st.markdown(f"""
<style>
html, body, [class*="css"] {{ font-size: 18px; }}
.block-container {{ padding-top: 1.2rem; padding-bottom: 2rem; max-width: 1500px; }}
h1, h2, h3 {{ color: {T['text']} !important; letter-spacing: 0.2px; }}
h1 {{ font-size: 2.3rem !important; }} h2 {{ font-size: 1.7rem !important; }} h3 {{ font-size: 1.35rem !important; }}
section[data-testid="stSidebar"] {{ background: {T['panel']}; border-right: 1px solid {T['border']}; }}
section[data-testid="stSidebar"] label, section[data-testid="stSidebar"] p {{ font-size: 1.05rem !important; }}
.kicker {{ color: {T['amber']}; font-weight: 700; font-size: 0.95rem; letter-spacing: 2px; text-transform: uppercase;
          margin-bottom: -0.4rem; }}
.card {{ background: {T['panel']}; border: 1px solid {T['border']}; border-radius: 12px; padding: 18px 20px;
        height: 100%; }}
.card .lab {{ color: {T['text3']}; font-size: 0.85rem; font-weight: 700; letter-spacing: 1.5px; text-transform: uppercase; }}
.card .big {{ font-size: 2.6rem; font-weight: 800; line-height: 1.1; margin: 6px 0 4px 0; }}
.card .sub {{ color: {T['text2']}; font-size: 1.0rem; }}
.card .note {{ color: {T['text3']}; font-size: 0.85rem; margin-top: 6px; }}
.sowhat {{ background: {T['amber_bg']}; border: 1px solid {T['amber']}; border-radius: 10px; padding: 12px 18px;
          color: {T['text']}; font-size: 1.05rem; margin: 10px 0 18px 0; }}
.sowhat b {{ color: {T['amber']}; letter-spacing: 1.5px; margin-right: 10px; }}
.rag {{ border-radius: 14px; padding: 16px 18px; background: {T['panel']}; text-align: center; }}
.rag .case {{ color: {T['text']}; font-size: 1.25rem; font-weight: 700; }}
.rag .rating {{ font-size: 2.6rem; font-weight: 900; letter-spacing: 2px; margin: 4px 0; }}
.rag .line {{ color: {T['text2']}; font-size: 1.0rem; }}
.rag .small {{ color: {T['text3']}; font-size: 0.88rem; margin-top: 6px; }}
.tag-data {{ background: {T['teal']}; color: {T['bg']}; border-radius: 6px; padding: 1px 8px; font-weight: 700;
            font-size: 0.8rem; }}
.tag-dom {{ background: {T['violet']}; color: {T['bg']}; border-radius: 6px; padding: 1px 8px; font-weight: 700;
           font-size: 0.8rem; }}
div[data-testid="stMetricValue"] {{ font-size: 2.2rem; }}
.stTabs [data-baseweb="tab"] {{ font-size: 1.05rem; }}
.footer {{ color: {T['muted']}; font-size: 0.8rem; letter-spacing: 1.5px; margin-top: 30px; }}
.chip {{ display:inline-block; border-radius: 6px; padding: 2px 9px; font-weight: 800; font-size: 0.78rem; letter-spacing: 1.2px;
        margin-right: 6px; }}
.chip-notional {{ background: {T['amber_bg']}; color: {T['amber']}; border: 1px solid {T['amber']}; }}
.chip-syn {{ background: #3A1420; color: {T['red']}; border: 1px solid {T['red']}; }}
.chip-role {{ background: {T['panel2']}; color: {T['cyan']}; border: 1px solid {T['cyan']}; }}
.ooda {{ background: {T['panel']}; border: 1px solid {T['border']}; border-radius: 12px; padding: 12px 16px; margin-bottom: 10px; }}
.ooda .h {{ font-weight: 900; letter-spacing: 3px; font-size: 0.95rem; }}
.ooda ol, .ooda ul {{ margin: 6px 0 2px 0; }}
.msg {{ background: {T['panel']}; border: 1px solid {T['border']}; border-left: 6px solid {T['muted']}; border-radius: 8px;
       padding: 8px 12px; margin-bottom: 8px; font-size: 0.95rem; }}
.msg.flash {{ border-left-color: {T['red']}; background: #2A0F17; }}
.msg .s {{ font-weight: 800; }} .msg .t {{ color: {T['text3']}; font-size: 0.8rem; letter-spacing: 1px; }}
.phone {{ background: #0B1520; border: 2px solid {T['border']}; border-radius: 26px; padding: 18px 14px; max-width: 360px; }}
.bubble {{ background: #1F3B2E; color: #E8F5EC; border-radius: 12px; padding: 10px 12px; font-size: 0.85rem;
          white-space: pre-wrap; line-height: 1.35; }}
.bubble.sms {{ background: #24364A; color: #EAF2FA; }}
table.acts td, table.acts th {{ border-bottom: 1px solid {T['border']}; padding: 8px 6px; vertical-align: top; text-align: left; }}
</style>
""", unsafe_allow_html=True)


def kicker(t):
    st.markdown(f'<div class="kicker">{t}</div>', unsafe_allow_html=True)


def sowhat(t, label="SO WHAT"):
    st.markdown(f'<div class="sowhat"><b>{label}</b>{t}</div>', unsafe_allow_html=True)


def card(label, big, sub, color=None, note=""):
    st.markdown(f'<div class="card"><div class="lab">{label}</div><div class="big" style="color:{color or T["amber"]}">'
                f'{big}</div><div class="sub">{sub}</div><div class="note">{note}</div></div>',
                unsafe_allow_html=True)


def show(fig, key=None, height=None):
    if height:
        fig.update_layout(height=height)
    st.plotly_chart(fig, theme=None, key=key, config={"displaylogo": False})


def download(df, name, label="Download CSV"):
    st.download_button(f"⬇ {label}", df.to_csv(index=False).encode("utf-8"), file_name=f"{name}.csv",
                       mime="text/csv", key=f"dl_{name}")


DATA_TAG = '<span class="tag-data">DATA</span>'
DOM_TAG = '<span class="tag-dom">DOMAIN</span>'


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------
P, TB = C.PROCESSED, C.TAB_DIR


@st.cache_data(show_spinner=False)
def load_all():
    d = dict(
        events=pd.read_parquet(P / "events.parquet"),
        cm=pd.read_parquet(P / "case_month.parquet"),
        am=pd.read_parquet(P / "admin1_month.parquet"),
        preds=pd.read_parquet(P / "forecast_preds.parquet"),
        future=pd.read_parquet(P / "forecast_future.parquet"),
        admin_future=pd.read_parquet(P / "admin1_future.parquet"),
        ew_preds=pd.read_parquet(P / "early_warning_preds.parquet"),
        ew_live=pd.read_parquet(P / "early_warning_live.parquet"),
        dq=pd.read_csv(TB / "data_quality_log.csv"),
        scores=pd.read_csv(TB / "forecast_scores.csv"),
        rmsle=pd.read_csv(TB / "forecast_rmsle.csv"),
        ens=pd.read_csv(TB / "ensemble_selection.csv"),
        abl=pd.read_csv(TB / "ablation_lgb.csv"),
        ew_rep=pd.read_csv(TB / "early_warning_scores.csv"),
        rag=pd.read_csv(TB / "rag_scorecard.csv", parse_dates=["forecast_month"]),
        shap_case=pd.read_csv(TB / "shap_lgb_case.csv"),
        shap_ew=pd.read_csv(TB / "shap_early_warning.csv"),
        stats=pd.read_csv(TB / "insight_stats.csv").iloc[0].to_dict(),
    )
    for k in ["case_overview", "attrition", "front_geography", "geo_precision", "theatre_spread", "country_deaths",
              "seasonality", "violence_mix", "dyads", "afpak_provinces", "media", "outlet_mix", "displacement",
              "unrwa", "demographics_profile", "hosts", "india_hosted", "india_context", "india_exposure",
              "indian_press"]:
        d[k] = pd.read_csv(TB / f"insight_{k}.csv")
    d["media"]["month"] = pd.to_datetime(d["media"]["month"])
    return d


@st.cache_resource(show_spinner=False)
def load_models():
    return joblib.load(ROOT / "models" / "models.joblib")


try:
    D = load_all()
except FileNotFoundError:
    st.error("Artefacts not found. Run `python run_pipeline.py` from the submission folder first.")
    st.stop()

cm, E = D["cm"], D["events"]
LAST = cm.month.max()

# ---------------------------------------------------------------------------
# Navigation
# ---------------------------------------------------------------------------
PAGES = ["🎯 Commander's brief", "📊 Conflict explorer", "📍 Area drill-down", "⚔️ Military lens", "🇮🇳 India impact",
         "🏠 Displacement", "📡 Media attention", "📈 Forecast (2026 test)", "🚨 Early warning",
         "🧪 What-if simulator", "🎛️ Scorecard lab", "🧹 Data quality & method", "💹 Economic front",
         "🎖️ Theatre daily brief", "🗂️ Brief history & OODA"]
PAGE_THEATRE = PAGES[13]
if "role" not in st.session_state:
    st.session_state.role = "CDS"


def _on_login():
    """A commander who signs in lands on their theatre's daily brief."""
    st.session_state.mode = "📊 Analyst dashboard"
    st.session_state.nav = PAGE_THEATRE


ROLE = st.session_state.role
TT = TH.theatre(ROLE)
# Conflicts linked to the signed-in theatre (own first, then context links); CDS sees all four
TCASES = list(C.CASES) if ROLE == "CDS" else (TT["cases"] + TT["context_cases"])
OWN = list(C.CASES) if ROLE == "CDS" else TT["cases"]


def ordered(cases=C.CASES):
    """Conflict options with the signed-in theatre's own conflicts first."""
    return [c for c in TCASES if c in cases] + [c for c in cases if c not in TCASES]


def idx(cds_index: int) -> int:
    """Keep the original default for CDS; a theatre commander gets their own conflict first."""
    return cds_index if ROLE == "CDS" else 0


@st.cache_data(show_spinner=False)
def aor_keys(role: str) -> set:
    """admin1 keys whose centroid lies inside the theatre's notional AOR polygon."""
    import json as _j
    areas = _j.loads((ROOT / "web" / "public" / "data" / "areas.json").read_text(encoding="utf-8"))["areas"]
    t = TH.theatre(role)
    return {a["key"] for a in areas if t["polygon"] is None or TH.inside(a["lon"], a["lat"], t["polygon"])}
from src.brand import data_uri, JIMMY, MCTE
_LJ, _LM = data_uri(JIMMY), data_uri(MCTE)
with st.sidebar:
    st.markdown(f"<div style='display:flex;justify-content:space-between;align-items:flex-start;margin:-6px 0 10px 0'>"
                f"<img src='{_LJ}' alt='Corps of Signals' style='height:78px'/>"
                f"<img src='{_LM}' alt='MCTE formation sign' style='height:72px'/></div>", unsafe_allow_html=True)
    st.markdown(f"<div style='color:{T['amber']};font-weight:800;letter-spacing:3px;font-size:1.0rem'>DATA ANALYTICS COMPETITION 2026</div>"
                f"<div style='color:{T['text']};font-weight:900;font-size:1.9rem;line-height:1.1'>CONFLICT EW</div>"
                f"<div style='color:{T['text3']};font-size:0.95rem;margin-bottom:12px'>When and where will deaths rise next, "
                f"and what does it mean for India?</div>", unsafe_allow_html=True)
    MODES = ["🛰️ Ops site", "📊 Analyst dashboard"]
    st.markdown(f"<div style='color:{T['amber']};font-weight:800;letter-spacing:2px;font-size:0.8rem'>COMMANDER LOGIN (DEMO)</div>",
                unsafe_allow_html=True)
    st.selectbox("Role", TH.ROLES, format_func=lambda k: TH.ROLE_LABEL[k], key="role", on_change=_on_login,
                 label_visibility="collapsed", help="Demo login, no password. WTC, NTC and MTC filter the whole "
                 "dashboard to that theatre's AOR; CDS sees all theatres.")
    st.markdown("<span class='chip chip-notional'>NOTIONAL THEATRES</span>"
                + ("<span class='chip chip-syn'>SYNTHETIC LAC DATA</span>" if st.session_state.role == "NTC" else ""),
                unsafe_allow_html=True)
    mode = st.radio("Mode", MODES, horizontal=True, label_visibility="collapsed", key="mode", index=1 if ANALYST else 0)
    st.markdown("---")
    page = st.radio("Navigate", PAGES, label_visibility="collapsed", key="nav") if mode == MODES[1] else None
    if mode == MODES[0]:
        st.markdown("The **Ops site** is the story and the ops console in one: scroll the story, or press "
                    "**OPS CONSOLE** for the staff-officer view. Switch to *Analyst dashboard* for the 15-page tool.")
        st.link_button("⤢ Open full screen", "https://conflictmonitor2026.streamlit.app/~/+/app/static/conflictwatch.html", use_container_width=True)
        st.link_button("Ops site (no sidebar)", "/", use_container_width=True)
    st.markdown("---")
    st.caption(f"Data: UCDP GED 26.1 (2014–25) + Candidate 26.01.26.09 (Jan–Sep 2026, provisional), UNHCR, IDMC, "
               f"UNRWA, World Bank. Latest month: {LAST:%b %Y}.")
    st.caption("Team: Maj Shivam Mehta · Capt Siddharth Sangwan · Capt Sahil Singh")
    st.caption("UNCLASSIFIED · COMPETITION DATA ONLY")
    _rid = C.TAB_DIR / "run_id.txt"
    if _rid.exists():
        st.caption(f"RUN {_rid.read_text().strip()} · matches the report, deck and Ops site")


SITE = ROOT / "app" / "static" / "conflictwatch.html"
if page is None or not ANALYST:
    import streamlit.components.v1 as components
    # Full-screen Ops site: hide the Streamlit header (sidebar arrow, Fork, GitHub), the sidebar and padding.
    if not ANALYST:
      st.markdown("<style>"
                "header[data-testid='stHeader'],[data-testid='stSidebar'],[data-testid='stSidebarCollapsedControl'],"
                "[data-testid='collapsedControl'],[data-testid='stToolbar'],[data-testid='stDecoration'],footer{display:none!important}"
                ".block-container,[data-testid=stMainBlockContainer]{padding:0!important;max-width:100%!important}"
                "[data-testid='stAppViewContainer'] > section, .main{padding:0!important}"
                "iframe{height:100vh!important;display:block;border:0}"
                "html,body,[data-testid='stApp']{overflow:hidden!important}</style>", unsafe_allow_html=True)
    else:
      st.markdown("<style>.block-container,[data-testid=stMainBlockContainer]{padding:0.6rem 1rem 0 1rem!important;max-width:100%!important}"
                  "header[data-testid='stHeader']{background:transparent}</style>", unsafe_allow_html=True)
    if SITE.exists():
        # No role is injected: the site opens on its own "Select your view" picker (CDS / WTC / NTC / MTC).
        components.html(SITE.read_text(encoding="utf-8"), height=940, scrolling=True)
    else:
        st.warning("Ops site not built. Run `cd web && npm run build` then `python scripts/build_site.py`.")
    st.stop()


# Formation banner on every analyst page: Corps of Signals 'Jimmy' top left, MCTE formation sign top right
st.markdown(f"<div style='display:flex;align-items:center;justify-content:space-between;gap:16px;padding:4px 2px 10px 2px;"
            f"border-bottom:1px solid {T['border']};margin-bottom:10px'>"
            f"<img src='{_LJ}' alt='Corps of Signals' style='height:64px'/>"
            f"<div style='text-align:center;flex:1'><div style='color:{T['amber']};font-weight:800;letter-spacing:4px;font-size:0.85rem'>"
            f"DATA ANALYTICS COMPETITION 2026</div><div style='color:{T['text']};font-weight:900;letter-spacing:3px;font-size:1.25rem'>"
            f"CONFLICT EW</div><div style='margin-top:4px'><span class='chip chip-role'>SIGNED IN: {ROLE} · {TT['name'].upper()}</span>"
            f"<span class='chip chip-notional'>NOTIONAL</span>"
            + ("<span class='chip chip-syn'>LAC DATA SYNTHETIC</span>" if ROLE == "NTC" else "")
            + (f"<span style='color:{T['text3']};font-size:0.8rem'>filtered to {', '.join(TCASES)}</span>" if ROLE != "CDS" else "")
            + f"</div></div>"
            f"<img src='{_LM}' alt='MCTE formation sign' style='height:60px'/></div>", unsafe_allow_html=True)


def footer():
    _rid = C.TAB_DIR / "run_id.txt"
    run = f"  |  RUN {_rid.read_text().strip()}" if _rid.exists() else ""
    st.markdown(f'<div class="footer">CONFLICT EW  |  DATA ANALYTICS COMPETITION 2026  |  UNCLASSIFIED - COMPETITION DATA ONLY{run}</div>',
                unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# 1. Commander's brief
# ---------------------------------------------------------------------------
def page_brief():
    kicker("Bottom line up front")
    st.markdown("# Four wars, three warning signals, one exposed neighbour")
    rag = D["rag"]
    if ROLE != "CDS":
        rag = rag.set_index("conflict_case").loc[TCASES].reset_index()
        st.caption(f"Filtered to {TT['name']} (notional): " + ", ".join(
            f"{c}{' (context link)' if c not in OWN else ''}" for c in TCASES) + ". Sign in as CDS for all four.")
    cols = st.columns(max(len(rag), 1))
    for c, (_, r) in zip(cols, rag.iterrows()):
        col = C.RAG_COLORS[r.rating]
        with c:
            st.markdown(
                f'<div class="rag" style="border:3px solid {col}"><div class="case">{r.conflict_case}</div>'
                f'<div class="rating" style="color:{col}">{r.rating}</div>'
                f'<div class="line"><b>{r.forecast_next:,.0f}</b> deaths forecast {r.forecast_month:%b %Y}</div>'
                f'<div class="small">80% range {r.pi80_lo:,.0f}–{r.pi80_hi:,.0f} · trend {r.trend_ratio - 1:+.0%} vs 6 mo'
                f'<br>{int(r.hotspots)} hotspot area(s) · {int(r.score)} pts</div></div>', unsafe_allow_html=True)
            with st.expander("Why this rating?"):
                st.markdown(f"Intensity **{int(r.pts_intensity):+d}** · trend **{int(r.pts_trend):+d}** · hotspots "
                            f"**{int(r.pts_hotspots):+d}** · spread **{int(r.pts_spread):+d}** · volatility "
                            f"**{int(r.pts_volatility):+d}**  \nTop areas: {r.top_areas}  \nChange the rules live in "
                            "**🎛️ Scorecard lab**.")
    st.markdown("")
    h = D["scores"]
    hold = h[(h.fold == 2026) & (h.track == "A")]
    base = hold[hold.model == "naive"].set_index("conflict_case").MAE
    ens = hold[hold.model == "ensemble"].set_index("conflict_case").MAE
    red = (1 - ens.sum() / base.sum())
    ew26 = D["ew_rep"][(D["ew_rep"].year == 2026) & (D["ew_rep"].model == "LightGBM classifier")].iloc[0]
    p = D["preds"]
    e26 = p[(p.model == "ensemble") & (p.fold == 2026)]
    cov = ((e26.actual >= e26.pi80_lo) & (e26.actual <= e26.pi80_hi)).mean()
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        card("Forecast", f"−{red:.0%}", "error vs 'no-change' rule, 1 month ahead, on unseen 2026 data",
             T["cyan"], "Ensemble of ETS, moving average and LightGBM-Δ")
    with c2:
        card("Warning", f"{ew26.ROC_AUC:.2f} AUC", f"sub-national escalation, 2026 · top-10 list "
             f"{ew26.precision_at_10 / ew26.base_rate:.1f}× better than random", T["amber"])
    with c3:
        card("Reliability", f"{cov:.0%}", "of 2026 outcomes inside the 80% interval", T["teal"],
             "Conformal intervals calibrated on 2022–25")
    with c4:
        card("India", "104", "killed off Sri Lanka, 4 Mar 2026: the US–Iran war reached the Indian Ocean", T["red"],
             "Plus strikes in 5 Gulf states hosting the Indian diaspora")
    st.markdown("")
    l, r = st.columns([1.15, 1])
    with l:
        kicker("Key findings")
        st.markdown(f"""
1. **Russia–Ukraine is a sustained attrition war**: 4–11k recorded deaths a month since 2023 (median 7.8k). The front is
   **widening, not moving**: Donetsk's share of located events fell from 55% to 30% as Zaporizhzhia, Dnipropetrovsk,
   Sumy and Russia's border oblasts rose. {DATA_TAG}
2. **Af–Pak has become a two-front problem for Pakistan**: the TTP insurgency in Khyber Pakhtunkhwa has grown every
   year since 2021, and since Oct 2025 the two **governments fight each other directly** (411 deaths in Mar 2026). {DATA_TAG}
3. **US–Iran escalated from proxy strikes to direct war in Feb–Mar 2026**: 14 countries were hit, with 299 deaths
   on Iran's Hormuz/Chabahar coast. {DATA_TAG}
4. **Israel–Hamas has de-escalated** to about 130 deaths a month in 2026, but it had a 2,474-death month as recently as Jul 2025. {DATA_TAG}
5. **Forecastable vs not**: tempo and spread give sub-national warning a month ahead. A decision to go to war
   (Feb 2022, Feb 2026) does not show up in death counts beforehand, so watch spread and hotspots, not media volume. {DATA_TAG}
""", unsafe_allow_html=True)
    with r:
        kicker("India: what it means")
        st.markdown(f"""
| Theatre | Impact on India | Basis |
|---|---|---|
| Af–Pak | Pakistan stretched on its western front; risk of diversion along the LoC; TTP spill-over | {DATA_TAG} + {DOM_TAG} |
| US–Iran / Gulf | Diaspora of about 9M in the Gulf; Hormuz energy flows; Chabahar–INSTC in the strike zone | {DATA_TAG} + {DOM_TAG} |
| Indian Ocean | War reached Sri Lanka's waters, so maritime domain awareness and NEO readiness matter | {DATA_TAG} |
| Russia–Ukraine | Legacy-platform spares and S-400 deliveries at risk; lessons on drones and attrition | {DOM_TAG} |
| Israel–Hamas | Supplier of UAVs, missiles and sensors at war; Red Sea shipping | {DOM_TAG} |
""", unsafe_allow_html=True)
    sowhat("Task ISR on the escalation watch-list, not on headlines. Pre-position for a Gulf NEO while US–Iran is "
           "AMBER. Treat the Af–Pak interstate front as a standing indicator for the LoC.", "SO WHAT")
    footer()


# ---------------------------------------------------------------------------
# 2. Explorer
# ---------------------------------------------------------------------------
def page_explorer():
    kicker("Explore the data")
    st.markdown("# Conflict explorer")
    c1, c2, c3 = st.columns([2, 2, 1])
    cases = c1.multiselect("Conflicts", C.CASES, default=TCASES, key=f"ex_c_{ROLE}")
    yr = c2.slider("Years", 2014, 2026, (2014, 2026))
    logy = c3.toggle("Log scale", value=True)
    d = cm[(cm.month.dt.year >= yr[0]) & (cm.month.dt.year <= yr[1])]
    show(viz.fig_monthly_deaths(d, log=logy, cases=cases or C.CASES, title="Deaths per month"), "ex1")
    ov = D["case_overview"].set_index("conflict_case")
    cols = st.columns(len(cases or C.CASES))
    for c, case in zip(cols, cases or C.CASES):
        o = ov.loc[case]
        with c:
            card(case, f"{o.deaths_best:,.0f}", f"recorded deaths 2014–Sep 2026 (range {o.deaths_low:,.0f}–{o.deaths_high:,.0f})",
                 C.CASE_COLORS[case], f"Peak {o.peak_month}: {o.peak_month_deaths:,} · civilians {o.civilian_share:.0%} · "
                 f"{o.areas_affected} areas")
    st.markdown("")
    t1, t5, t6, t2, t3, t4 = st.tabs(["Map", "▶ Animated: where the dying happens", "Event browser", "Violence type",
                                      "Seasonality", "Top areas & dyads"])
    with t5:
        anim_case = st.selectbox("Conflict", ordered(), key=f"anim_case_{ROLE}")
        x = E[(E.conflict_case == anim_case) & ~E.admin1.str.startswith("(")]
        g = x.groupby([x.month.dt.year.rename("year"), "admin1"]).deaths_best.sum().reset_index()
        top = g.groupby("admin1").deaths_best.sum().nlargest(12).index
        g = g[g.admin1.isin(top)]
        full = pd.MultiIndex.from_product([sorted(g.year.unique()), top], names=["year", "admin1"])
        g = g.set_index(["year", "admin1"]).reindex(full, fill_value=0).reset_index()
        g["area"] = g.admin1.str.replace(" province", "").str.replace(" oblast", "")
        import plotly.express as px
        fig = px.bar(g, x="deaths_best", y="area", animation_frame="year", orientation="h",
                     range_x=[0, g.deaths_best.max() * 1.1], color_discrete_sequence=[C.CASE_COLORS[anim_case]],
                     labels={"deaths_best": "located deaths in the year", "area": ""})
        fig.update_layout(height=620,
                          title=f"{anim_case}: located deaths by area, year by year (press ▶)",
                          paper_bgcolor=T["bg"], plot_bgcolor=T["bg"], font=dict(color=T["text2"], size=16),
                          yaxis=dict(categoryorder="total ascending"))
        show(fig, "ex_anim")
        st.caption("Located events only (country-level aggregates excluded). Press ▶ or drag the year slider.")
    with t6:
        f1, f2, f3, f4 = st.columns([1.4, 1.4, 1.2, 1])
        bc = f1.multiselect("Conflicts", C.CASES, default=[ordered()[0] if ROLE != "CDS" else "Afghanistan–Pakistan"],
                            key=f"eb_c_{ROLE}")
        vt = f2.multiselect("Violence type", sorted(E.violence_type.dropna().unique()), key="eb_v")
        md = f3.number_input("Minimum deaths per event", 0, 5000, 10, step=5, key="eb_m")
        q = f4.text_input("Search place / actor", key="eb_q")
        dr = st.slider("Date range", min_value=E.month.min().date(), max_value=E.month.max().date(),
                       value=(pd.Timestamp("2025-01-01").date(), E.month.max().date()), key="eb_d")
        x = E[E.conflict_case.isin(bc or C.CASES) & (E.deaths_best >= md)
              & (E.month >= pd.Timestamp(dr[0])) & (E.month <= pd.Timestamp(dr[1]))]
        if vt:
            x = x[x.violence_type.isin(vt)]
        if q:
            mask = (x.ucdp_location_name.str.contains(q, case=False, na=False) | x.admin1.str.contains(q, case=False, na=False)
                    | x.side_a_name.str.contains(q, case=False, na=False) | x.side_b_name.str.contains(q, case=False, na=False))
            x = x[mask]
        x = x.sort_values("date_start", ascending=False)
        k1, k2, k3 = st.columns(3)
        k1.metric("Events", f"{len(x):,}")
        k2.metric("Deaths (best)", f"{x.deaths_best.sum():,.0f}")
        k3.metric("Civilian share", f"{x.deaths_civilians.sum() / max(x.deaths_best.sum(), 1):.0%}")
        cols = ["date_start", "conflict_case", "country_iso3", "admin1", "ucdp_location_name", "violence_type",
                "side_a_name", "side_b_name", "deaths_best", "deaths_civilians", "is_provisional"]
        st.dataframe(x[cols].head(500), hide_index=True, use_container_width=True, height=460)
        download(x[cols], "event_browser_selection", "Download this selection")
    with t1:
        yf = st.select_slider("Map period from", options=list(range(2014, 2027)), value=2024)
        cs = st.selectbox("Conflict", ["All"] + ordered(), index=0 if ROLE == "CDS" else 1, key=f"map_cs_{ROLE}")
        show(viz.fig_country_map(D["country_deaths"], case=None if cs == "All" else cs, year_from=yf, height=720), "ex_map")
    with t2:
        show(viz.fig_violence_mix(D["violence_mix"]), "ex2")
    with t3:
        show(viz.fig_seasonality(D["seasonality"]), "ex3")
        sowhat("Russia–Ukraine runs about 15–35% above trend in May–August and well below in Dec–Jan. Af–Pak peaks in "
               "Sep–Oct. Seasonal priors go into the forecast.")
    with t4:
        case = st.selectbox("Conflict ", ordered(), key=f"topa_{ROLE}")
        x = E[(E.conflict_case == case) & (E.month.dt.year >= yr[0]) & (E.month.dt.year <= yr[1])]
        a = (x.groupby(["country_iso3", "admin1"]).agg(deaths=("deaths_best", "sum"), events=("event_id", "count"),
                                                        civilians=("deaths_civilians", "sum"))
             .sort_values("deaths", ascending=False).head(15).reset_index())
        st.dataframe(a, hide_index=True, column_config={"deaths": st.column_config.ProgressColumn(
            "deaths", format="%d", min_value=0, max_value=float(a.deaths.max() or 1))})
        dy = D["dyads"]
        st.dataframe(dy[dy.conflict_case == case], hide_index=True)
    footer()


# ---------------------------------------------------------------------------
# 3. Military lens
# ---------------------------------------------------------------------------
def page_military():
    kicker("How the wars are being fought")
    st.markdown("# Military lens")
    t1, t2, t3, t4, t5 = st.tabs(["Front geography", "Attrition by side", "Af–Pak: second front", "Horizontal escalation",
                                  "Fog of war"])
    with t1:
        show(viz.fig_front_geography(D["front_geography"]), "m1")
        sowhat("A wide, static front favours long-range strike, counter-drone and logistics depth over manoeuvre. "
               "Warning should track the number of active sectors, which our models use as a feature.")
    with t2:
        show(viz.fig_attrition(D["attrition"]), "m2")
        st.info("These are UCDP-recorded figures. Ukrainian memorial and OSINT databases document Russian losses more "
                "completely than the reverse, so treat the ratio as a reporting upper bound, not a verified exchange ratio.")
        sowhat("With ISR-cued precision fires and drones, the defender imposes disproportionate recorded attrition. "
               "This is relevant to India's force structure on both fronts. (Domain inference)")
    with t3:
        show(viz.fig_afpak_interstate(E), "m3")
        show(viz.fig_afpak(D["afpak_provinces"]), "m4")
        sowhat("Pakistan now fights the TTP in KP and the Afghan state on the Durand Line. Watch for diversionary "
               "activity on the LoC and for TTP spill-over. Treat the Af–Pak interstate dyad as a standing I&W indicator.")
    with t4:
        show(viz.fig_theatre_spread(D["theatre_spread"]), "m5")
        ts = D["theatre_spread"]
        st.dataframe(ts[ts.year >= 2022].round(3), hide_index=True)
        sowhat("US–Iran went from 4 countries in 2025 to 14 in 2026, including the Gulf states and Sri Lankan waters. "
               "Horizontal spread is the earliest sign that India's interests (diaspora, shipping) are in the envelope.")
    with t5:
        show(viz.fig_fog_of_war(D["geo_precision"]), "m6")
        sowhat("By 2026, over 90% of RU–UA deaths have no sub-national location. Any sub-national claim about "
               "Ukraine must say so. Located events are a better guide to where the fighting is.")
    footer()


# ---------------------------------------------------------------------------
# 4. India
# ---------------------------------------------------------------------------
def page_india():
    kicker("So what for India")
    st.markdown("# India impact")
    c1, c2, c3, c4 = st.columns(4)
    ie = D["india_exposure"]
    g26 = ie[(ie.year == 2026)]
    with c1:
        card("Gulf states hit (2026)", "5", f"{int(g26[g26.india_tag.str.startswith('Gulf')].events.sum())} events, "
             f"{int(g26[g26.india_tag.str.startswith('Gulf')].deaths.sum())} deaths", T["amber"], "UAE, Kuwait, Saudi Arabia, "
             "Bahrain, Oman (Qatar hit in 2025)")
    with c2:
        card("Indian Ocean", "104", "killed in one strike off Sri Lanka, 4 Mar 2026", T["red"])
    with c3:
        h = g26[g26.india_tag.str.startswith("Iran")]
        card("Hormuz / Chabahar coast", f"{int(h.deaths.sum())}", f"deaths in {int(h.events.sum())} events, 2026",
             T["cyan"], "Hormozgan, Bushehr, Sistan-Baluchestan")
    with c4:
        ip = D["indian_press"].set_index("conflict_case")
        card("Indian OSINT coverage", f"{ip.loc['Afghanistan–Pakistan', 'events_covered_share']:.0%}",
             "of Af–Pak events cite an Indian outlet; about 0% for the other three theatres", T["violet"])
    st.markdown("")
    show(viz.fig_country_map(D["country_deaths"], year_from=2025, height=720), "i_map")
    l, r = st.columns(2)
    with l:
        show(viz.fig_india_exposure(D["india_exposure"]), "i1")
    with r:
        show(viz.fig_india_hosted(D["india_hosted"]), "i2")
    kicker("Impact matrix")
    st.markdown(f"""
| Theatre | What the data show {DATA_TAG} | What it means for India {DOM_TAG} | Recommended action |
|---|---|---|---|
| **Af–Pak** | KP deaths up every year since 2021; Afghan–Pakistan state clashes since Oct 2025 (peak 411 in Mar 2026); deaths in Pakistan areas adjoining India rose from 2 to 52 (2022–25) | Pakistan Army committed to its west, so risk of diversionary LoC activity and infiltration; TTP and IS-K spill-over | Treat the AF–PK interstate dyad and KP escalation probability as LoC I&W indicators |
| **US–Iran / Gulf** | War hit 14 countries in 2026, including 5 Gulf states; 299 deaths on Iran's Hormuz/Chabahar coast | About 9M Indians in the Gulf; large share of crude and LPG via Hormuz; Chabahar/INSTC exposed | Keep NEO plans for the Gulf current; escort and route-diversification plans |
| **Indian Ocean** | 104 killed off Sri Lanka on 4 Mar 2026 | The war reached India's maritime neighbourhood | Strengthen IFC-IOR maritime picture; monitor belligerent naval movement |
| **Russia–Ukraine** | Sustained 4–11k deaths/month (median 7.8k); front widening | Legacy Russian platforms: spares and deliveries at risk; drone and EW lessons | Indigenise spares; accelerate counter-drone |
| **Israel–Hamas** | De-escalated to about 130/month in 2026 | Key supplier of UAVs, missiles and sensors; Red Sea route | Buffer stocks of critical imports |
| **Refugees in India** | Afghans 16.2k (2021) to 8.4k (2025); Russian asylum seekers 5 to 329 | Small numbers, but rising Russian flows signal draft-evasion migration | Monitor; no surge capacity needed now |
""", unsafe_allow_html=True)
    with st.expander("India macro context (World Bank) vs conflict years"):
        ic = D["india_context"]
        x = ic.pivot(index="year", columns="economy_name", values="consumer_inflation_annual_pct")
        fig = go.Figure()
        for c in x.columns:
            fig.add_trace(go.Scatter(x=x.index, y=x[c], name=c, mode="lines+markers",
                                     line=dict(width=4 if c == "India" else 2)))
        fig.update_layout(title="Consumer inflation, % (India bold)", height=420)
        show(fig, "i3")
        st.caption("Correlation is not attribution: 2022 Indian inflation (6.7%) coincides with the invasion and the "
                   "energy shock, but many factors drive inflation.")
    footer()


# ---------------------------------------------------------------------------
# 5. Displacement
# ---------------------------------------------------------------------------
def page_displacement():
    kicker("Humanitarian planning")
    st.markdown("# Displacement")
    show(viz.fig_displacement(D["displacement"]), "d1")
    l, r = st.columns(2)
    with l:
        show(viz.fig_demographics(D["demographics_profile"]), "d2")
    with r:
        iso = st.selectbox("Origin", ["UKR", "AFG", "PSE", "IRN", "RUS", "PAK"],
                           format_func=lambda s: viz.NAMES.get(s, s))
        h = D["hosts"][D["hosts"].origin_iso3 == iso]
        st.dataframe(h[["asylum_name", "refugees_unhcr", "asylum_seekers", "total_international"]], hide_index=True)
        u = D["unrwa"]
        st.caption("UNRWA registered Palestine refugees, kept separate from IDMC/UNHCR series (different definitions):")
        st.dataframe(u.pivot_table(index="reporting_name", columns="year", values="people"), height=230)
    sowhat("72% of Ukrainian and 63% of Afghan refugees with recorded sex and age are women or children (10% of Afghans are "
           "under five). Stock paediatric and maternal supplies. Displacement tracks war onset and spread more than monthly "
           "deaths (Spearman about 0.1), so trigger HADR planning on our escalation flags.")
    footer()


# ---------------------------------------------------------------------------
# 6. Media
# ---------------------------------------------------------------------------
def page_media():
    kicker("Original index")
    st.markdown("# Media attention vs deaths")
    s = D["stats"]
    c1, c2, c3 = st.columns(3)
    with c1:
        card("Elasticity to events", f"{s['media_elasticity_events']:.2f}", "References rise about 1:1 with incidents", T["cyan"])
    with c2:
        card("Elasticity to deaths", f"{s['media_elasticity_deaths']:.2f}", "…and hardly at all with lethality", T["red"])
    with c3:
        card("Leads escalation?", "No", f"Attention gap → next-month change: p = {s['media_lead_p']:.2f}", T["amber"])
    st.markdown("")
    show(viz.fig_media_scatter(D["media"]), "md1")
    show(viz.fig_media_gap(D["media"]), "md2")
    case = st.selectbox("Outlets cited for", ordered(), key=f"med_{ROLE}")
    om = D["outlet_mix"][D["outlet_mix"].conflict_case == case]
    st.dataframe(om[["publisher_norm", "refs", "share"]], hide_index=True,
                 column_config={"share": st.column_config.ProgressColumn("share", format="%.2f", min_value=0, max_value=1)})
    sowhat("The Attention Gap Index is a regression residual: references explained by events and deaths. One "
           "mass-casualty strike is one story, so high-lethality violence is under-documented per death. Do not use media "
           "volume as a warning signal.")
    footer()


# ---------------------------------------------------------------------------
# 7. Forecast
# ---------------------------------------------------------------------------
def page_forecast():
    kicker("Model performance on withheld data")
    st.markdown("# Forecast: Jan–Sep 2026 withheld test")
    c1, c2, c3 = st.columns([2, 2, 2])
    case = c1.selectbox("Conflict", ordered(), key=f"fc_{ROLE}")
    track = c2.radio("Question", ["A: next month (rolling)", "B: 1–9 months from Dec 2025"], horizontal=False)
    tr = "A" if track.startswith("A") else "B"
    model = c3.selectbox("Model", list(M.MODEL_LABELS), index=list(M.MODEL_LABELS).index("ensemble"),
                         format_func=lambda m: M.MODEL_LABELS[m])
    show(viz.fig_forecast_case(cm, D["preds"], case, track=tr, model=model,
                               future=D["future"] if (tr == "A" and model == "ensemble") else None), "f1")
    sc = D["scores"]
    h = sc[(sc.fold == 2026) & (sc.track == tr) & (sc.conflict_case == case)].set_index("model")
    h.index = h.index.map(M.MODEL_LABELS)
    st.dataframe(h[["MAE", "RMSE", "MAPE", "sMAPE", "MASE", "RMSLE", "Bias"]].sort_values("RMSLE").round(2))
    t1, t2, t3, t4 = st.tabs(["All models", "Why these models (ablation)", "Interval reliability", "Explainability"])
    with t1:
        show(viz.fig_model_compare(D["rmsle"]), "f2")
        hold = sc[(sc.fold == 2026) & (sc.track == "A")]
        base = hold[hold.model == "naive"].set_index("conflict_case").MAE
        ens = hold[hold.model == "ensemble"].set_index("conflict_case").MAE
        st.dataframe(((1 - ens / base) * 100).round(1).rename("% MAE reduction vs naive (2026, 1 month ahead)").to_frame())
    with t2:
        st.dataframe(D["abl"].set_index("variant"))
        st.markdown("Trees cannot extrapolate. A level model trained before 2022 can never predict the invasion's "
                    "death toll. Predicting the **change** in log deaths, with a compact feature set and an L1 loss, "
                    "generalises best. Ensemble members were chosen on the 2022–25 back-test only:")
        st.dataframe(D["ens"].head(8), hide_index=True)
    with t3:
        p = D["preds"]
        e = p[p.model == "ensemble"]
        cov = e.groupby(["fold", "track"]).apply(lambda g: pd.Series({
            "80% interval coverage": ((g.actual >= g.pi80_lo) & (g.actual <= g.pi80_hi)).mean(),
            "95% interval coverage": ((g.actual >= g.pi95_lo) & (g.actual <= g.pi95_hi)).mean()})).round(2)
        st.dataframe(cov)
        st.caption("Split-conformal intervals on log residuals from 2022–25. The 95% upper tail is wide by design "
                   "because the back-test contains the 2022 invasion: outbreak risk is real.")
    with t4:
        show(viz.fig_shap(D["shap_case"]), "f3")
    kicker("Forward forecast")
    f = D["future"]
    ff = f[f.model == "ensemble"][["conflict_case", "target_month", "pred", "pi80_lo", "pi80_hi"]].copy()
    ff["target_month"] = ff.target_month.dt.strftime("%b %Y")
    st.dataframe(ff.round(0), hide_index=True)
    download(ff.round(0), "forward_forecast_oct_dec_2026")
    footer()


# ---------------------------------------------------------------------------
# 8. Early warning
# ---------------------------------------------------------------------------
def page_ew():
    kicker("Indications & warning")
    st.markdown("# Sub-national escalation warning")
    rep = D["ew_rep"]
    r26 = rep[rep.year == 2026].set_index("model")
    c1, c2, c3, c4 = st.columns(4)
    lg = r26.loc["LightGBM classifier"]
    with c1:
        card("ROC-AUC 2026", f"{lg.ROC_AUC:.2f}", f"vs {r26.loc['Rule: rank by last month' + chr(39) + 's deaths', 'ROC_AUC']:.2f} for "
             "'watch last month's deadliest'", T["amber"])
    with c2:
        card("Top-10 precision", f"{lg.precision_at_10:.0%}", f"base rate {lg.base_rate:.1%}: "
             f"{lg.precision_at_10 / lg.base_rate:.1f}× lift", T["cyan"])
    with c3:
        card("Escalations caught", f"{lg.recall_at_20:.0%}", "of each month's escalations are in the top-20 list", T["teal"])
    with c4:
        am_ = D["am"]
        card("Series monitored", f"{am_.groupby(['conflict_case', 'admin1_key']).ngroups}",
             f"sub-national area series in {am_.country_iso3.nunique()} countries, scored every month", T["violet"])
    st.markdown("")
    t1, t2, t4, t3 = st.tabs([f"Watch-list for {(LAST + pd.DateOffset(months=1)):%b %Y}", "Replay a 2026 month",
                              "Alert threshold", "Model quality"])
    with t4:
        ep = D["ew_preds"]
        x = ep[ep.fold == 2026]
        thr = st.slider("Raise an alert when P(escalation) is at least", 0.02, 0.60, 0.15, step=0.01, key="ew_thr")
        flag = x.p_lgb >= thr
        tp = int((flag & (x.escalation == 1)).sum()); fp = int((flag & (x.escalation == 0)).sum())
        fn = int((~flag & (x.escalation == 1)).sum()); tn = int((~flag & (x.escalation == 0)).sum())
        a1, a2, a3, a4 = st.columns(4)
        with a1:
            card("Alerts per month", f"{flag.sum() / x.target_month.nunique():.1f}", "areas flagged, 2026 average", T["amber"])
        with a2:
            card("Precision", f"{tp / max(tp + fp, 1):.0%}", f"of alerts escalated (base rate {x.escalation.mean():.1%})",
                 T["cyan"])
        with a3:
            card("Recall", f"{tp / max(tp + fn, 1):.0%}", f"of {tp + fn} escalations were alerted", T["teal"])
        with a4:
            card("False alarms", f"{fp}", f"over {x.target_month.nunique()} months", T["red"])
        th = np.linspace(0.02, 0.6, 59)
        prec = [((x.p_lgb >= t) & (x.escalation == 1)).sum() / max((x.p_lgb >= t).sum(), 1) for t in th]
        rec = [((x.p_lgb >= t) & (x.escalation == 1)).sum() / max(x.escalation.sum(), 1) for t in th]
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=th, y=prec, name="Precision", line=dict(color=T["cyan"], width=4)))
        fig.add_trace(go.Scatter(x=th, y=rec, name="Recall", line=dict(color=T["teal"], width=4)))
        fig.add_vline(x=thr, line=dict(color=T["amber"], width=3, dash="dash"))
        fig.update_layout(title="Trade-off on the 2026 withheld months: move the slider", height=420,
                          paper_bgcolor=T["bg"], plot_bgcolor=T["bg"], font=dict(color=T["text2"], size=16),
                          xaxis_title="alert threshold", yaxis=dict(tickformat=".0%"))
        show(fig, "ew_thr_fig")
        st.markdown(f"**Confusion matrix (2026):** alerted & escalated **{tp}** · alerted, no escalation **{fp}** · "
                    f"missed **{fn}** · correctly quiet **{tn:,}**")
        sowhat("A lower threshold catches more escalations at the cost of more false alarms. Pick it by the ISR "
               "capacity available: about 10 alerts a month matches the top-10 list in the report.", "TRADE-OFF")
    with t1:
        a1, a2 = st.columns([3, 1])
        cs = a1.multiselect("Filter conflicts", C.CASES, default=TCASES, key=f"ewc_{ROLE}")
        only = a2.toggle("Only my AOR", value=ROLE != "CDS", key=f"ew_aor_{ROLE}", disabled=ROLE == "CDS",
                         help="Keep only areas whose centroid is inside the signed-in theatre's notional AOR polygon")
        lv = D["ew_live"]
        lv = lv[lv.conflict_case.isin(cs) & ~lv.admin1.str.startswith("(")]
        if only:
            lv = lv[lv.admin1_key.isin(aor_keys(ROLE))]
            if ROLE == "NTC":
                st.info("No real district in the NTC AOR except Gilgit-Baltistan (PoK). The LAC sectors are synthetic and "
                        "are shown on 🎖️ Theatre daily brief.")
        lv = lv.head(20).round({"deaths": 0, "base3": 0})
        st.dataframe(lv[["conflict_case", "country_iso3", "admin1", "deaths", "base3", "p_escalation"]].rename(
            columns={"conflict_case": "Conflict", "country_iso3": "Country", "admin1": "Area", "deaths": f"Deaths {LAST:%b}", "base3": "3-mo mean"}), hide_index=True, height=600, use_container_width=True,
            column_config={"p_escalation": st.column_config.ProgressColumn("P(escalation next month)", format="%.2f",
                                                                          min_value=0, max_value=0.4)})
        download(lv[["conflict_case", "country_iso3", "admin1", "deaths", "base3", "p_escalation"]], "watch_list")
    with t2:
        ep = D["ew_preds"]
        months = sorted(ep[ep.fold == 2026].target_month.unique())
        m = st.select_slider("Month being predicted", options=months, value=months[2],
                             format_func=lambda x: pd.Timestamp(x).strftime("%b %Y"))
        x = ep[(ep.fold == 2026) & (ep.target_month == m)].sort_values("p_lgb", ascending=False)
        top = x.head(10)
        hits = int(top.escalation.sum())
        st.markdown(f"### Top-10 list issued at end of {pd.Timestamp(m) - pd.DateOffset(months=1):%b %Y}: "
                    f"**{hits}** of 10 escalated (out of {int(x.escalation.sum())} escalations that month)")
        top = top.assign(outcome=np.where(top.escalation == 1, "✅ escalated", "—"))
        st.dataframe(top[["conflict_case", "admin1", "deaths", "target_deaths", "p_lgb", "outcome"]].round(
            {"deaths": 0, "target_deaths": 0, "p_lgb": 2}).rename(
            columns={"deaths": "deaths (month t)", "target_deaths": "deaths (t+1)", "p_lgb": "P(escalation)"}),
            hide_index=True)
        missed = x[(x.escalation == 1)].iloc[10:] if len(x) > 10 else x.iloc[0:0]
        missed = x[(x.escalation == 1) & ~x.index.isin(top.index)]
        if len(missed):
            st.caption("Missed escalations: " + ", ".join(f"{a} ({c})" for a, c in zip(missed.admin1, missed.conflict_case)))
    with t3:
        show(viz.fig_ew_curves(D["ew_preds"]), "e1")
        st.dataframe(rep.round(3), hide_index=True)
        show(viz.fig_shap(D["shap_ew"], title="What drives the warning (mean |SHAP|)"), "e2")
    sowhat("Use the list to task ISR and analysts. Escalation is contagious within a theatre: the whole conflict's tempo "
           "and spread are among the strongest signals. It cannot foresee a political decision to start a war.")
    footer()


# ---------------------------------------------------------------------------
# 9. What-if + live retrain
# ---------------------------------------------------------------------------
def page_whatif():
    kicker("Interactive")
    st.markdown("# What-if simulator")
    art = load_models()
    l, r = st.columns([1, 2.4])
    with l:
        case = st.selectbox("Conflict", ordered(), index=idx(2), key=f"wi_{ROLE}")
        shock = st.slider("Change in violence over the last months (%)", -80, 200, 30, step=10)
        k = st.slider("…applied to the last N months", 1, 6, 3)
        st.caption("The frozen full-data LightGBM-Δ, a refitted ETS and the moving average are re-run on the modified "
                   "history. This is the same ensemble that was scored on 2026.")
    base = M.scenario_forecast(cm, case, 0, k, art["m_case_full"], art["members"], art["conformal"])
    scen = M.scenario_forecast(cm, case, shock, k, art["m_case_full"], art["members"], art["conformal"])
    with r:
        fig = viz.fig_forecast_case(cm, D["preds"], case, track="A", future=D["future"], scenario=scen,
                                    history_from="2025-01-01")
        fig.update_layout(title=f"{case}: baseline forward forecast (amber) vs scenario {shock:+d}% (red)")
        show(fig, "w1")
    c = st.columns(3)
    for i in range(3):
        with c[i]:
            b, s = base.iloc[i], scen.iloc[i]
            card(f"{s.target_month:%b %Y}", f"{s.pred:,.0f}", f"baseline {b.pred:,.0f} ({s.pred / max(b.pred, 1) - 1:+.0%}); "
                 f"80% range {s.pi80_lo:,.0f}–{s.pi80_hi:,.0f}", T["red"] if s.pred > b.pred else T["teal"])
    tidy = pd.DataFrame({"Month": pd.to_datetime(scen.target_month).dt.strftime("%b %Y"),
                         "Baseline forecast": base.pred.round(0).values, "Scenario forecast": scen.pred.round(0).values,
                         "80% low": scen.pi80_lo.round(0).values, "80% high": scen.pi80_hi.round(0).values,
                         "95% high": scen.pi95_hi.round(0).values})
    st.dataframe(tidy, hide_index=True, use_container_width=True)
    sowhat("The model damps shocks: a 30% three-month surge raises the next-month forecast by less than 30%. "
           "That is because both the ensemble and history say that most surges partly revert. Sustained surges "
           "(6 months) carry through.")
    st.markdown("---")
    kicker("Live re-train")
    st.markdown("### Re-train LightGBM-Δ from scratch on any cut-off and test on the following year")
    yr = st.select_slider("Train on data up to December of", options=[2021, 2022, 2023, 2024, 2025], value=2025)
    if st.button("Train now", type="primary"):
        from src.features import make_supervised
        with st.spinner("Training on the 4-conflict panel…"):
            sup = M._prep_case(make_supervised(cm, ["conflict_case"], horizons=range(1, 10)))
            cut = pd.Timestamp(f"{yr}-12-01")
            trn = sup[(sup.target_month <= cut) & sup.target_y.notna() & (sup.month >= "2014-12-01")]
            feats = M.CASE_FEATURES + ["case_cat"]
            mdl = M.fit_lgb(trn, feats, "delta", **M.LGB_CASE_PARAMS)
            te = sup[(sup.h == 1) & (sup.month >= cut) & (sup.target_month <= min(cut + pd.DateOffset(months=9), LAST))]
            te = te.assign(pred=np.expm1(mdl.predict(te[feats])))
        out = []
        for cs in C.CASES:
            g = te[te.conflict_case == cs]
            mm = M.metrics(g.target_deaths, g.pred)
            nv = M.metrics(g.target_deaths, g.deaths)
            out.append(dict(conflict=cs, MAE_model=mm["MAE"], MAE_naive=nv["MAE"], RMSLE_model=mm["RMSLE"],
                            RMSLE_naive=nv["RMSLE"]))
        st.success(f"Trained on {len(trn):,} rows (data to Dec {yr}); scored 1-month-ahead on the next 9 months.")
        st.dataframe(pd.DataFrame(out).round(2), hide_index=True)
        fig = go.Figure()
        for cs in C.CASES:
            g = te[te.conflict_case == cs]
            fig.add_trace(go.Scatter(x=g.target_month, y=g.target_deaths, name=f"{cs} actual",
                                     line=dict(color=C.CASE_COLORS[cs], width=3)))
            fig.add_trace(go.Scatter(x=g.target_month, y=g.pred, name=f"{cs} model", line=dict(color=C.CASE_COLORS[cs],
                                     width=3, dash="dash")))
        fig.update_yaxes(type="log")
        fig.update_layout(title="Actual (solid) vs freshly trained model (dashed)", height=460)
        show(fig, "w2")
    footer()


# ---------------------------------------------------------------------------
# 10. DQ & method
# ---------------------------------------------------------------------------
def page_dq():
    kicker("Reproducible, auditable")
    st.markdown("# Data quality & method")
    dq = D["dq"]
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        card("Checks", f"{len(dq)}", "documented checks across 6 tables", T["cyan"])
    with c2:
        card("Issues handled", f"{int((dq.rows_affected > 0).sum())}", "fixed, imputed or flagged, never silently dropped",
             T["amber"])
    with c3:
        card("Estimate repairs", "692", "out-of-order low/best/high rows", T["red"])
    with c4:
        card("Provisional rows", "4,644", "2026 Candidate records, used for testing only", T["violet"])
    st.markdown("")
    show(viz.fig_dq_summary(dq), "q1")
    st.dataframe(dq, hide_index=True, height=420)
    download(dq, "data_quality_log")
    kicker("Pipeline")
    st.markdown("""
`python run_pipeline.py` reproduces everything in about 2.5 minutes:

**1 Clean** (36 checks, data-quality log) → **2 Features** (conflict-month and 222 sub-national series; 40+ features,
no look-ahead) → **3 Insights** (military, India, displacement, media) → **4 Models** (7 forecasters, 4-fold walk-forward
back-test, 2026 holdout, conformal intervals, escalation classifier, TreeSHAP) → **5 Scorecard** → **6 Figures**.
Notebooks `01`–`05` re-run each stage with commentary.
""")
    kicker("Assumptions and limitations")
    st.markdown("""
* UCDP records **reported** lethal organised violence. Access, coding and source mix vary by place and time.
* 2026 events are **provisional** (Candidate) and are usually revised upward. Holdout error includes revision noise.
* Over 90% of 2026 RU–UA deaths have no sub-national location, so sub-national results for Ukraine use events.
* The US–Iran focal dyad codes Israel + US as **one actor**, so there is no country split.
* Displacement stocks **cannot be attributed** to single events. IDMC and UNRWA series are kept separate.
* World Bank context ends in 2025 and is used with a one-year lag.
* Forecasts cannot anticipate political decisions to start wars. Outbreak risk sits in the wide 95% tail.
* Points marked DOMAIN are expert reasoning, not outputs of this dataset.
""")
    footer()


# ---------------------------------------------------------------------------
# Area drill-down
# ---------------------------------------------------------------------------
def page_area():
    kicker("Zoom in")
    st.markdown("# Area drill-down")
    am_ = D["am"]
    c1, c2, c3 = st.columns([1.2, 1.6, 1])
    case = c1.selectbox("Conflict", ordered(), index=idx(2), key=f"ar_case_{ROLE}")
    a = am_[am_.conflict_case == case]
    if ROLE != "CDS" and st.toggle("Only areas in my AOR", value=True, key=f"ar_aor_{ROLE}"):
        _a = a[a.admin1_key.isin(aor_keys(ROLE))]
        a = _a if len(_a) else a
    tot = a.groupby(["admin1_key", "admin1"]).deaths.sum().sort_values(ascending=False).reset_index()
    tot = tot[~tot.admin1.str.startswith("(")]
    key = c2.selectbox("Area (sorted by total deaths)", tot.admin1_key, format_func=lambda k: k.split(" | ", 1)[1]
                       + f"  ({k.split(' | ')[0]})", key="ar_key")
    start = c3.select_slider("From", options=list(range(2014, 2027)), value=2020, key="ar_from")
    s_ = a[(a.admin1_key == key) & (a.month >= f"{start}-01-01")].sort_values("month")
    name = key.split(" | ", 1)[1]
    # an area can appear under two conflicts (e.g. Tehran under US–Iran and Israel–Hamas): use this conflict's row
    lv = D["ew_live"][D["ew_live"].conflict_case == case].set_index("admin1_key")
    af = D["admin_future"]
    af = af[af.admin1_key == key].sort_values("h")
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        card("Deaths since " + str(start), f"{s_.deaths.sum():,.0f}", f"{int(s_.n_events.sum()):,} events", C.CASE_COLORS[case])
    with k2:
        last = s_.iloc[-1] if len(s_) else None
        card(f"Deaths {LAST:%b %Y}", f"{(last.deaths if last is not None else 0):,.0f}",
             f"3-month mean {s_.deaths.tail(3).mean():,.0f}", T["cyan"])
    with k3:
        pe = lv.loc[key, "p_escalation"] if key in lv.index else np.nan
        rank = int((D["ew_live"].p_escalation > pe).sum() + 1) if pe == pe else None
        card(f"P(escalation) {(LAST + pd.DateOffset(months=1)):%b}", f"{pe:.0%}" if pe == pe else "n/a",
             f"rank {rank} of {len(D['ew_live'])} areas" if rank else "", T["amber"] if pe == pe and pe >= 0.15 else T["teal"])
    with k4:
        nxt = af.pred.iloc[0] if len(af) else np.nan
        card("Bottom-up forecast", f"{nxt:,.0f}" if nxt == nxt else "n/a", "deaths next month (LightGBM Tweedie)", T["violet"])
    fig = go.Figure()
    fig.add_trace(go.Bar(x=s_.month, y=s_.n_events, name="events", marker_color=T["border"], yaxis="y2", opacity=0.8))
    fig.add_trace(go.Scatter(x=s_.month, y=s_.deaths, name="deaths", line=dict(color=C.CASE_COLORS[case], width=4)))
    if len(af):
        fig.add_trace(go.Scatter(x=af.target_month, y=af.pred, name="forecast", mode="lines+markers",
                                 line=dict(color=T["amber"], width=3, dash="dash")))
    fig.update_layout(title=f"{name}: deaths and events per month", height=460, paper_bgcolor=T["bg"],
                      plot_bgcolor=T["bg"], font=dict(color=T["text2"], size=16), hovermode="x unified",
                      yaxis=dict(title="deaths", gridcolor=T["panel2"]),
                      yaxis2=dict(title="events", overlaying="y", side="right", showgrid=False),
                      legend=dict(orientation="h", y=-0.15), margin=dict(t=70, b=70))
    show(fig, "ar1")
    ep = D["ew_preds"]
    h = ep[ep.admin1_key == key].sort_values("target_month")
    if len(h):
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=h.target_month, y=h.p_lgb, name="P(escalation), issued a month earlier",
                                 line=dict(color=T["amber"], width=3), fill="tozeroy", fillcolor="rgba(240,176,58,0.15)"))
        esc = h[h.escalation == 1]
        fig.add_trace(go.Scatter(x=esc.target_month, y=esc.p_lgb, mode="markers", name="escalation happened",
                                 marker=dict(color=T["red"], size=14, symbol="x")))
        fig.update_layout(title="Out-of-sample warning history (each year predicted by a model trained only on earlier years)",
                          height=360, paper_bgcolor=T["bg"], plot_bgcolor=T["bg"], font=dict(color=T["text2"], size=15),
                          yaxis=dict(tickformat=".0%", gridcolor=T["panel2"]), legend=dict(orientation="h", y=-0.18),
                          margin=dict(t=70, b=70))
        show(fig, "ar2")
    ev = E[(E.admin1_key == key)].sort_values("date_start", ascending=False)
    kicker("Latest events in this area")
    cols = ["date_start", "ucdp_location_name", "violence_type", "side_a_name", "side_b_name", "deaths_best",
            "deaths_civilians"]
    st.dataframe(ev[cols].head(100).assign(date_start=lambda d: pd.to_datetime(d.date_start).dt.strftime("%d %b %Y"))
                 .rename(columns={"date_start": "Date", "ucdp_location_name": "Country", "violence_type": "Type",
                                  "side_a_name": "Side A", "side_b_name": "Side B", "deaths_best": "Deaths",
                                  "deaths_civilians": "Civilians"}),
                 hide_index=True, use_container_width=True, height=360)
    download(ev[cols], f"events_{name.replace(' ', '_')}", "Download all events in this area")
    footer()


# ---------------------------------------------------------------------------
# Scorecard lab
# ---------------------------------------------------------------------------
def page_lab():
    kicker("Interactive")
    st.markdown("# Scorecard lab: change the rules, watch the ratings move")
    rag = D["rag"].set_index("conflict_case")
    live = D["ew_live"]
    l, r = st.columns([1, 2.3])
    with l:
        hi = st.number_input("Intensity: 2 points at ≥ deaths/month", 100, 20000, 1000, step=100)
        mid = st.number_input("Intensity: 1 point at ≥ deaths/month", 1, 5000, 100, step=10)
        tr = st.slider("Trend: ± point when forecast vs last 6 months moves by (%)", 5, 100, 20, step=5)
        p_hot = st.slider("Hotspot: area escalation probability ≥", 0.05, 0.40, 0.15, step=0.01)
        use_vol = st.toggle("Volatility rule", value=True)
        use_spread = st.toggle("Spread rule", value=True)
        red_pts = st.slider("RED at ≥ points", 3, 8, 5)
        amb_pts = st.slider("AMBER at ≥ points", 1, 4, 2)
        st.caption("Volatility: a ≥1,000-death month in the last year. Spread: more countries hit than last year. "
                   "Auto-RED: forecast at or above the 2-point intensity level.")
        red_auto = st.toggle("Auto-RED at top intensity", value=True)
    rows = []
    for case in C.CASES:
        g = rag.loc[case]
        f = g.forecast_next
        lv = live[(live.conflict_case == case) & ~live.admin1.str.startswith("(")]
        hot = int((lv.p_escalation >= p_hot).sum())
        pts = dict(Intensity=2 if f >= hi else 1 if f >= mid else 0,
                   Trend=1 if g.trend_ratio >= 1 + tr / 100 else -1 if g.trend_ratio <= 1 - tr / 100 else 0,
                   Hotspots=2 if hot >= 3 else 1 if hot >= 1 else 0,
                   Spread=int(g.pts_spread) if use_spread else 0,
                   Volatility=int(g.pts_volatility) if use_vol else 0)
        sc = sum(pts.values())
        rating = "RED" if ((red_auto and f >= hi) or sc >= red_pts) else "AMBER" if sc >= amb_pts else "GREEN"
        rows.append(dict(conflict=case, rating=rating, points=sc, hotspots=hot, forecast=f, base=g.rating, **pts))
    res = pd.DataFrame(rows)
    with r:
        cols = st.columns(4)
        for c, (_, x) in zip(cols, res.iterrows()):
            col = C.RAG_COLORS[x.rating]
            changed = "" if x.rating == x.base else f"<div class='small'>was {x.base}</div>"
            with c:
                st.markdown(f'<div class="rag" style="border:3px solid {col}"><div class="case" style="font-size:1.05rem">{x.conflict}</div>'
                            f'<div class="rating" style="color:{col};font-size:1.9rem;letter-spacing:1px">{x.rating}</div>'
                            f'<div class="line">{int(x.points)} pts · {x.hotspots} hotspot(s)</div>{changed}</div>',
                            unsafe_allow_html=True)
        long = res.melt(id_vars="conflict", value_vars=["Intensity", "Trend", "Hotspots", "Spread", "Volatility"],
                        var_name="rule", value_name="pts")
        import plotly.express as px
        fig = px.bar(long, x="pts", y="conflict", color="rule", orientation="h",
                     color_discrete_sequence=[T["red"], T["cyan"], T["amber"], T["violet"], T["teal"]])
        fig.add_vline(x=red_pts, line=dict(color=T["red"], dash="dash", width=2))
        fig.add_vline(x=amb_pts, line=dict(color=T["amber"], dash="dash", width=2))
        fig.update_layout(title="Points by rule (dashed lines: AMBER and RED thresholds)", height=420, barmode="relative",
                          paper_bgcolor=T["bg"], plot_bgcolor=T["bg"], font=dict(color=T["text2"], size=16),
                          yaxis_title="", xaxis_title="", legend=dict(orientation="h", y=-0.25, title_text=""),
                          margin=dict(l=210, t=70, b=90))
        show(fig, "lab1")
    sowhat("Every input is a model output, so the rating is transparent and auditable. Show how robust the picture is: "
           "Russia–Ukraine stays RED under any sensible rule set; the AMBER/GREEN line is where judgement matters.",
           "WHY IT MATTERS")
    download(res, "scorecard_lab_result")
    footer()



# ---------------------------------------------------------------------------
# 13. Economic front
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def load_econ():
    import json
    t = {k: pd.read_csv(TB / f"econ_{k}.csv") for k in
         ["episodes", "event_study", "india_monthly", "reserves", "fronts", "political_timeline", "claims_check",
          "paths", "gpr_monthly", "series_log", "protests_2026"]}
    t["summary"] = json.loads((TB / "econ_summary.json").read_text())
    return t


def page_econ():
    kicker("The second front")
    st.markdown("# Economic front: markets, currencies, reserves and politics")
    try:
        X = load_econ()
    except FileNotFoundError:
        st.warning("Economic tables not found. Run `python run_pipeline.py` first.")
        return
    S = X["summary"]
    H, OIL, RSV, REM = S["headline"], S["india_oil_bill"], S["reserves"], S["india_remittances"]
    sowhat("The battlefield kills locally, but markets hit everyone. India took no fire in the 2026 Gulf war and still "
           f"saw Brent {H['brent_d20_2026']:+.0f}% and the Nifty {H['nifty_d20_2026']:+.1f}% within 20 trading days.",
           label="BLUF")
    c = st.columns(4)
    with c[0]:
        card("Brent, 20 days after 28 Feb 2026", f"{H['brent_d20_2026']:+.0f}%", f"peak {H['brent_best_2026']:+.0f}%; VIX "
             f"{H['vix_best_2026']:+.0f}%", T["amber"], "DATA: Yahoo BZ=F")
    with c[1]:
        card("Nifty 50 / rupee, 2026", f"{H['nifty_d20_2026']:+.1f}%", f"worst {H['nifty_worst_2026']:+.1f}%; rupee worst "
             f"{H['inr_worst_2026']:+.1f}%", T["red"], "DATA: Yahoo ^NSEI, INR=X")
    with c[2]:
        card("India's extra crude bill", f"≈${OIL['extra_usd_bn_per_year_2026']:.0f}B/yr",
             f"Brent +${OIL['brent_up_usd_2026']:.0f}/bbl since the war; ${OIL['per_10usd_bn_per_year']:.1f}B per $10",
             T["amber"], f"DATA price × DOMAIN {OIL['crude_mbd_domain']} mb/d imports")
    with c[3]:
        card("India reserves drawn, 2022", f"−${RSV['ind_2021_bn'] - RSV['ind_2022_bn']:.0f}B",
             f"${RSV['ind_2021_bn']:.0f}B → ${RSV['ind_2022_bn']:.0f}B defending the rupee; "
             f"{RSV['ind_2025_months']:.1f} months cover in 2025", T["cyan"], "DATA: World Bank")
    st.markdown("")
    c = st.columns(4)
    with c[0]:
        card("MOEX, 24 Feb 2022", f"{H['moex_day1']:+.0f}%", "then no trading until 24 Mar", T["cyan"], "DATA: MOEX ISS")
    with c[1]:
        card("TA-35 after 7 Oct 2023", f"{H['ta35_worst']:+.1f}%", f"shekel {H['ils_worst']:+.1f}%; ZIM shipping "
             f"{H['zim_worst']:+.0f}%", T["cyan"], "DATA: Yahoo")
    with c[2]:
        ir = S["irr_2026"]
        card("Iranian rial since the war", f"{ir['value_change_pct']:+.0f}%", f"{ir['pre_war']:,.0f} → {ir['last']:,.0f} "
             f"per USD ({ir['last_date']})", T["red"], "DATA: Yahoo IRR=X, free-market rate from Jan 2026")
    with c[3]:
        card("Gulf remittances at risk", f"≈${REM['gulf_usd_bn']:.0f}B/yr", f"of ${REM['usd_bn']:.0f}B total ({REM['year']}); "
             f"{REM['gulf_share_domain']:.0%} Gulf share", T["violet"], "DATA World Bank × DOMAIN share")

    st.markdown("")
    show(viz.fig_econ_fronts(X["fronts"]), "e_fronts")
    st.caption("One row per theatre's largest episode. Af–Pak has no stock-index series reachable (PSX blocked), so it "
               "shows the rupee and India only.")

    kicker("Event paths around each shock")
    ph = X["paths"]
    l, r = st.columns([1, 3])
    with l:
        case = st.radio("Shock", ordered(list(ph.conflict_case.unique())), key=f"e_case_{ROLE}")
        sers = list(ph[ph.conflict_case == case].series.unique())
        pick = st.multiselect("Series", sers, default=sers, key="e_ser",
                              format_func=lambda k: viz.ECON_LABEL.get(k, k))
        st.markdown(f"{DATA_TAG} Index = 100 at the last close before day 0. Day 0 is picked from UCDP daily deaths, "
                    "not from the news.", unsafe_allow_html=True)
    with r:
        show(viz.fig_econ_paths(ph[ph.series.isin(pick)], case), "e_paths")

    kicker("India panel")
    show(viz.fig_econ_india(X["india_monthly"]), "e_india")
    with st.expander("What-if: India's crude bill at a given Brent price", expanded=True):
        a, b = st.columns([2, 3])
        with a:
            mbd = st.slider("Crude imports (million bbl/day)", 3.0, 6.0, float(OIL["crude_mbd_domain"]), 0.1, key="e_mbd")
            px = st.slider("Brent rise vs pre-war (USD/bbl)", 0.0, 80.0, round(OIL["brent_up_usd_2026"] * 2) / 2, 0.5, key="e_px")
        with b:
            extra = mbd * 1e6 * 365 * px / 1e9
            card("Extra import bill", f"≈${extra:.0f}B / year", f"{mbd:.1f} mb/d × ${px:.1f}/bbl × 365 days; about "
                 f"{extra / RSV['ind_2025_bn']:.0%} of 2025 reserves", T["amber"],
                 "DOMAIN estimate; ignores discounts on Russian crude and demand response")

    l, r = st.columns(2)
    with l:
        show(viz.fig_econ_reserves(X["reserves"]), "e_res")
    with r:
        g = X["gpr_monthly"].copy()
        g["month"] = pd.to_datetime(g.month)
        fig = go.Figure(go.Scatter(x=g.month, y=g.GPR, name="GPR", line=dict(color=T["amber"], width=3)))
        fig.update_layout(title="Geopolitical Risk index (Caldara–Iacoviello, monthly)", height=440, yaxis_title="Index")
        show(fig, "e_gpr")

    kicker("Every episode, every market")
    es = X["event_study"]
    hz = st.radio("Horizon", ["d1_pct", "d5_pct", "d20_pct", "d60_pct", "worst60_pct"], index=2, horizontal=True,
                  format_func=lambda h: {"d1_pct": "1 day", "d5_pct": "5 days", "d20_pct": "20 days",
                                         "d60_pct": "60 days", "worst60_pct": "worst in 60"}[h], key="e_hz")
    _ecs = list(es.conflict_case.unique())
    cases = st.multiselect("Theatres", _ecs, default=[c for c in TCASES if c in _ecs] or _ecs, key=f"e_cs_{ROLE}")
    topn = st.slider("Show the largest moves", 10, len(es), 30, 5, key="e_top")
    sel = es[es.conflict_case.isin(cases)]
    sel = sel.loc[sel[hz].abs().sort_values(ascending=False).index[:topn]]
    show(viz.fig_econ_event_bars(sel, hz), "e_bars")
    st.markdown(f"{DATA_TAG} {S['n_episodes']} death-spike episodes, {S['n_moves']} market moves. Main onsets: median "
                f"|20-day move| {S['median_abs_move20_main']:.1f}%, {S['sig_share_main_onsets']:.0%} significant at p<0.10 "
                f"against every non-war 20-day window since 2014. Routine spikes: {S['median_abs_move20_other']:.1f}%, "
                f"{S['sig_share_other_episodes']:.0%} significant. Markets react to new wars, not to more of the same war.",
                unsafe_allow_html=True)
    cols = ["conflict_case", "day0", "label", "d1_pct", "d5_pct", "d20_pct", "d60_pct", "worst60_pct", "p20"]
    st.dataframe(es[es.conflict_case.isin(cases)][cols].round(2), hide_index=True, use_container_width=True)
    download(es, "econ_event_study")

    kicker("Political crises")
    pt = X["political_timeline"]
    st.markdown(f"{DOM_TAG} dated crises, aligned to the nearest death-spike episode (±45 days). War onsets and sanctions "
                f"line up; domestic crises such as Pakistan 2022–24 mostly do not ({int(pt.within_45d.sum())} of {len(pt)}).",
                unsafe_allow_html=True)
    st.dataframe(pt, hide_index=True, use_container_width=True)
    download(pt, "econ_political_timeline")

    kicker("Checking the figures we quote")
    st.dataframe(X["claims_check"], hide_index=True, use_container_width=True)
    download(X["claims_check"], "econ_claims_check")
    with st.expander("Sources and series log"):
        st.dataframe(X["series_log"], hide_index=True, use_container_width=True)
        st.caption("Yahoo Finance daily closes, MOEX ISS (IMOEX, RTSI), World Bank WDI (reserves, imports, remittances, "
                   "GDP), Caldara–Iacoviello GPR. Currencies are shown as value vs USD (a fall = depreciation). "
                   "Fetched by data/econ/fetch_econ*.py; built by src/econ.py.")
    footer()


# ---------------------------------------------------------------------------
# 14. Theatre daily brief (role-based, notional theatres)
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def load_briefs(_stamp: float):
    import json as _j
    f = TH.OUT / "briefs.json"
    if not f.exists():
        TH.run()
    return _j.loads(f.read_text(encoding="utf-8"))


@st.cache_resource(show_spinner=False)
def theatre_inputs():
    return TH.load_inputs()


def _briefs():
    f = TH.OUT / "briefs.json"
    return load_briefs(f.stat().st_mtime if f.exists() else 0.0)


def ooda_block(b: dict, compact: bool = False):
    col = C.RAG_COLORS[b["rating"]]
    tag = {"DATA": DATA_TAG, "MODEL": '<span class="tag-dom" style="background:#4FD6E8">MODEL</span>',
           "SYNTHETIC": '<span class="chip chip-syn" style="font-size:0.7rem">SYNTHETIC</span>'}
    obs = "".join(f"<li>{o['text']} <span style='color:{T['text3']}'>· {o['window']} · {o['source']}</span> "
                  f"{tag.get(o['tag'], '')}</li>" for o in b["observe"])
    st.markdown(f"<div class='ooda'><div class='h' style='color:{T['cyan']}'>① OBSERVE · top changes, last 24 h / 7 d</div>"
                f"<ol>{obs}</ol></div>", unsafe_allow_html=True)
    pts = "".join(f"<li><b>{p['pts']:+d}</b> {p['why']}</li>" for p in b["orient"]["points"])
    st.markdown(f"<div class='ooda'><div class='h' style='color:{T['amber']}'>② ORIENT · threat level and why</div>"
                f"<div style='font-size:1.5rem;font-weight:900;color:{col}'>{b['rating']} {b['arrow']} "
                f"<span style='font-size:1rem;color:{T['text2']}'>{b['trend']} · score {b['score']} · confidence "
                f"<b>{b['confidence']}</b></span></div><ul>{pts}</ul>"
                f"<div style='color:{T['text3']};font-size:0.9rem'>{b['orient']['model_why']} {b['confidence_why']}</div></div>",
                unsafe_allow_html=True)
    if compact:
        acts = "".join(f"<li><b>{a['short']}</b> · {a['owner']} · <b>{a['timeline']}</b></li>" for a in b["decide"])
        st.markdown(f"<div class='ooda'><div class='h' style='color:{T['teal']}'>③ DECIDE + ④ ACT</div><ol>{acts}</ol></div>",
                    unsafe_allow_html=True)
        return
    st.markdown(f"<div class='ooda' style='margin-bottom:4px'><div class='h' style='color:{T['teal']}'>③ DECIDE · three "
                f"ranked actions &nbsp; ④ ACT · owner, timeline, trigger to escalate</div></div>", unsafe_allow_html=True)
    rows = "".join(
        f"<tr><td style='font-size:1.3rem;font-weight:900;color:{T['teal']}'>{a['rank']}</td><td><b>{a['kind']}</b><br>"
        f"{a['text']}</td><td>{a['owner']}<br><b style='color:{T['amber']}'>{a['timeline']}</b></td>"
        f"<td style='color:{T['text2']}'>{a['trigger']}</td></tr>" for a in b["decide"])
    st.markdown(f"<table style='width:100%;font-size:0.92rem;border-collapse:collapse' class='acts'><tr style='color:{T['text3']}'>"
                f"<th>#</th><th>DECIDE: action</th><th>ACT: owner, timeline</th><th>Trigger to escalate</th></tr>{rows}</table>",
                unsafe_allow_html=True)


def page_theatre():
    B = _briefs()
    meta = B["meta"]
    kicker(f"{TT['name']} · notional · daily 0600 IST brief")
    st.markdown(f"# {ROLE}: {TT['front']}")
    st.markdown(f"<span class='chip chip-notional'>NOTIONAL</span> {TH.NOTIONAL}"
                + (f"<br><span class='chip chip-syn'>SYNTHETIC</span> {TH.SYN_NOTE}" if ROLE in ("NTC", "CDS") else ""),
                unsafe_allow_html=True)
    dates = B["dates"]
    d = st.select_slider("Brief for", options=dates, value=dates[-1], key=f"th_d_{ROLE}",
                         format_func=lambda x: TH.dtg(pd.Timestamp(x)))
    b = B["briefs"][ROLE][dates.index(d)]
    col = C.RAG_COLORS[b["rating"]]
    st.markdown(f"<div class='sowhat' style='border-color:{col};background:{T['panel']}'><b style='color:{col}'>BLUF</b>"
                f"{b['bluf']}</div>", unsafe_allow_html=True)
    my_flash = [f for f in B["flashes"] if ROLE in (f["code"], "CDS") and f["date"] <= d]
    c = st.columns(4)
    with c[0]:
        card("Threat level", f"{b['rating']} {b['arrow']}", f"{b['trend']} · score {b['score']}", col,
             "Monthly model RAG + daily signals")
    with c[1]:
        card("Confidence", b["confidence"], b["confidence_why"][:90] + ("…" if len(b["confidence_why"]) > 90 else ""),
             T["cyan"])
    with c[2]:
        card("FLASH alerts, 7 days", f"{len(my_flash)}", (my_flash[-1]["text"][:80] + "…") if my_flash else "none raised",
             T["red"] if my_flash else T["teal"], f"threshold P ≥ {TH.FLASH_P:.2f} or a RAG change")
    with c[3]:
        card("Data latency", f"{meta['ucdp_lag_days']} d → <1 d", f"UCDP ends {pd.Timestamp(meta['ucdp_end']):%d %b}; "
             f"GDELT and markets to {pd.Timestamp(meta['data_end']):%d %b}", T["violet"],
             f"All four briefs built in {meta['build_seconds']} s")
    st.markdown("")
    l, r = st.columns([1.05, 1])
    with l:
        ooda_block(b)
    with r:
        show(TV.fig_aor_map(b, ROLE, height=560), f"aor_{ROLE}")
        if ROLE == "NTC":
            st.caption("Diamonds are [SYNTHETIC] LAC sectors (seeded generator with a scripted demo surge at Tawang and "
                       "Depsang). Gilgit-Baltistan (PoK) is the only real area in the AOR.")
    t1, t2, t3, t4 = st.tabs(["📥 Inbox & notifications", "📡 GDELT nowcast", "💹 Second front (oil, shipping, rupee)",
                              "🧪 Brief what-if"])
    with t1:
        inbox_panel(B, b)
    with t2:
        if TT["gdelt_case"] or TT["gdelt_geo"]:
            show(TV.fig_gdelt_strip(ROLE, b["date"]), f"gd_{ROLE}")
        g = pd.DataFrame(b["gdelt"])
        if len(g):
            st.dataframe(g[["series", "last", "mean28", "z", "last7", "prior28", "r7"]].rename(columns={
                "last": "yesterday", "mean28": "28-day mean", "z": "24 h z", "last7": "7-day mean", "prior28": "4 weeks before",
                "r7": "7-day ratio"}).round(2), hide_index=True, use_container_width=True)
        st.markdown(f"{DATA_TAG} GDELT is media-coded news volume, not ground truth. It is not in the model; here it "
                    "nudges the district nowcast and flags spikes. The NTC view uses India-wide GDELT only (no China "
                    "file was issued).", unsafe_allow_html=True)
    with t3:
        show(TV.fig_econ_strip(ROLE, b["date"]), f"ec_{ROLE}")
        e = pd.DataFrame(b["econ"])
        if len(e):
            st.dataframe(e[["series", "close", "asof", "ch5", "z5", "adverse"]].rename(columns={
                "ch5": "5-session change", "z5": "z vs 2 years", "adverse": "adverse z (+ = bad for India)"}).round(3),
                hide_index=True, use_container_width=True)
        st.caption("Full analysis on 💹 Economic front. Market stress (adverse z ≥ 2) adds a point to the theatre score and "
                   "raises the logistics-buffer action.")
    with t4:
        whatif_brief(b)
    with st.expander("Brief as plain text (Markdown) and the AOR polygon (GeoJSON)"):
        st.code(TH.to_markdown(b), language="markdown")
        st.download_button("⬇ Brief (.md)", TH.to_markdown(b), file_name=f"{ROLE}_{b['date']}_brief.md", key=f"dlb_{ROLE}")
        import json as _j
        st.download_button("⬇ Notional AORs (.geojson)", _j.dumps(TH.aor_geojson()), file_name="aor_notional.geojson",
                           key=f"dlg_{ROLE}")
    footer()


def inbox_panel(B: dict, b: dict):
    msgs = [m for m in B["inbox"] if (ROLE == "CDS" or m["code"] == ROLE) and m["date"] <= b["date"]]
    l, r = st.columns([1.1, 1])
    with l:
        st.markdown(f"**In-app inbox · {ROLE}** ({sum(m['kind'] == 'FLASH' for m in msgs)} FLASH, "
                    f"{sum(m['kind'] != 'FLASH' for m in msgs)} daily briefs). Job: {B['meta']['schedule']}.")
        for m in msgs[:8]:
            fl = m["kind"] == "FLASH"
            st.markdown(f"<div class='msg {'flash' if fl else ''}'><div class='t'>{m['dtg']} · {m['priority']} · "
                        f"{' / '.join(m['channels'])}</div><div class='s' style='color:{T['red'] if fl else T['text']}'>"
                        f"{'⚡ ' if fl else ''}{m['subject']}</div>{m['text']}</div>", unsafe_allow_html=True)
        a, c2 = st.columns(2)
        if a.button("▶ Run the 0600 job now", key=f"run_{ROLE}", help="Rebuilds every theatre's brief from the data "
                    "(what the scheduler does at 0030 UTC)"):
            with st.spinner("Building WTC, NTC, MTC and CDS briefs…"):
                o = TH.run()
            load_briefs.clear()
            st.success(f"Built {len(TH.ROLES)} × {o['meta']['days']} briefs in {o['meta']['build_seconds']} s; "
                       f"{o['meta']['n_flash']} FLASH alerts.")
        c2.caption("Scheduler: `scripts/daily_briefs.py` via Windows Task Scheduler, cron (30 0 * * * UTC) or the "
                   "GitHub workflow `daily-briefs.yml`.")
    with r:
        ch = st.radio("Preview channel", ["E-mail", "SMS", "WhatsApp"], horizontal=True, key=f"ch_{ROLE}")
        if ch == "E-mail":
            import streamlit.components.v1 as components
            components.html(TH.to_email_html(b), height=760, scrolling=True)
            with st.form(f"mail_{ROLE}"):
                to = st.text_input("Send this brief by e-mail (optional, needs SMTP settings)", placeholder="name@example.com")
                if st.form_submit_button("Send"):
                    import os
                    if not os.environ.get("CW_SMTP_HOST"):
                        st.info("Demo mode: no SMTP server is configured (set CW_SMTP_HOST, CW_SMTP_USER, CW_SMTP_PASS). "
                                "The .eml file is written to outputs/theatre/outbox/ by the daily job.")
                    elif to:
                        st.write(TH.send_email(b, [x.strip() for x in to.split(",") if x.strip()]))
        else:
            txt = TH.to_sms(b) if ch == "SMS" else TH.to_whatsapp(b)
            txt = txt.replace("*", "").replace("_", "") if ch == "WhatsApp" else txt
            st.markdown(f"<div class='phone'><div style='color:{T['text3']};font-size:0.75rem;text-align:center'>"
                        f"{'Messages' if ch == 'SMS' else 'WhatsApp'} · Conflict EW · {b['dtg']}</div>"
                        f"<div class='bubble {'sms' if ch == 'SMS' else ''}'>{txt}</div></div>", unsafe_allow_html=True)
            st.caption(f"Mock preview ({len(TH.to_sms(b))} characters for SMS). A gateway would be wired in "
                       "`scripts/daily_briefs.py`; nothing is sent.")


def whatif_brief(b: dict):
    st.markdown("Change the inputs and the brief is rebuilt with the same rules: threat level, ranked actions and "
                "timelines move with the evidence.")
    a, c, e = st.columns(3)
    gm = a.slider("GDELT conflict reporting in the last 7 days ×", 0.5, 4.0, 1.0, 0.25, key=f"wb_g_{ROLE}")
    ps = c.slider("Shift the model's district probabilities (pp)", -10, 20, 0, 1, key=f"wb_p_{ROLE}")
    lx = e.slider("[SYNTHETIC] extra LAC incidents today (NTC)", 0, 10, 0, 1, key=f"wb_l_{ROLE}", disabled=ROLE not in ("NTC", "CDS"))
    I = theatre_inputs()
    d = pd.Timestamp(b["date"])
    nb = TH.build_brief(ROLE, d, TH.apply_shock(I, d, gm, ps / 100, lx))
    col = C.RAG_COLORS[nb["rating"]]
    x, y = st.columns([1, 2])
    with x:
        card("What-if threat level", f"{nb['rating']} {nb['arrow']}", f"was {b['rating']} {b['arrow']} · score "
             f"{b['score']} → {nb['score']}", col)
    with y:
        st.markdown(f"**What-if BLUF:** {nb['bluf']}")
        st.dataframe(pd.DataFrame([dict(Rank=r["rank"], Action=r["short"], Owner=r["owner"], Timeline=r["timeline"])
                                   for r in nb["decide"]]), hide_index=True, use_container_width=True)
    st.caption("The forecast what-if (deaths) is on 🧪 What-if simulator, filtered to this theatre's conflicts.")


# ---------------------------------------------------------------------------
# 15. Brief history, side by side, OODA
# ---------------------------------------------------------------------------
def page_history():
    B = _briefs()
    kicker("Seven days of briefs · two commanders, one dataset · the OODA loop")
    st.markdown("# Brief history & OODA")
    t1, t2, t3, t4 = st.tabs(["🗓️ 7-day history", "👥 Side by side", "⏱️ How it shortens the OODA loop", "⚡ FLASH log"])
    with t1:
        show(TV.fig_rag_history(B), "hist_rag")
        who = st.radio("Theatre", TH.ROLES, index=TH.ROLES.index(ROLE), horizontal=True, key="hist_who",
                       format_func=lambda k: TH.ROLE_LABEL[k])
        rows = [dict(DTG=x["dtg"], Rating=f"{x['rating']} {x['arrow']}", Confidence=x["confidence"], BLUF=x["bluf"])
                for x in B["briefs"][who]][::-1]
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True,
                     column_config={"BLUF": st.column_config.TextColumn(width="large")})
        for x in B["briefs"][who][::-1]:
            with st.expander(f"{x['dtg']} · {x['rating']} {x['arrow']} · {x['bluf'][:110]}…"):
                ooda_block(x, compact=True)
    with t2:
        a, c, dd = st.columns(3)
        r1 = a.selectbox("Commander A", TH.ROLES, index=0, format_func=lambda k: TH.ROLE_LABEL[k], key="sx_a")
        r2 = c.selectbox("Commander B", TH.ROLES, index=2, format_func=lambda k: TH.ROLE_LABEL[k], key="sx_b")
        d = dd.select_slider("Same day", options=B["dates"], value=B["dates"][-1], key="sx_d",
                             format_func=lambda x: TH.dtg(pd.Timestamp(x)))
        i = B["dates"].index(d)
        sowhat(f"Same data run, same rules, same minute: {r1} and {r2} see different maps, different top changes and "
               "different actions, because each brief is filtered to its own AOR and playbook. Nobody has to read the "
               "other theatre's traffic to find their own.", "SAME DATA")
        L, R = st.columns(2)
        for colx, rr in ((L, r1), (R, r2)):
            bb = B["briefs"][rr][i]
            with colx:
                cl = C.RAG_COLORS[bb["rating"]]
                st.markdown(f"<div class='rag' style='border:3px solid {cl};text-align:left'><div class='case'>{rr} · "
                            f"{TH.theatre(rr)['name']}</div><div class='rating' style='color:{cl};font-size:2rem'>"
                            f"{bb['rating']} {bb['arrow']}</div><div class='line'>{bb['bluf']}</div></div>",
                            unsafe_allow_html=True)
                show(TV.fig_aor_map(bb, rr, height=420), f"sx_map_{rr}_{colx is L}")
                ooda_block(bb, compact=True)
    with t3:
        tot = TH.ooda_totals()
        meta = B["meta"]
        sowhat(f"Event to decision: about {tot['today_days'][0]:.0f}–{tot['today_days'][1]:.0f} days in a weekly staff "
               f"cycle, about {tot['cw_hours'][0]:.0f}–{tot['cw_hours'][1]:.0f} hours with an automatic 0600 brief and "
               "pre-agreed triggers. Days to hours.", "OODA")
        show(TV.fig_ooda(), "ooda_bar")
        st.dataframe(pd.DataFrame([dict(Stage=o["stage"], Today=o["today"], **{"Today (h)": f"{o['today_h'][0]}–{o['today_h'][1]}"},
                                        **{"With Conflict EW": o["cw"]}, **{"CW (h)": f"{o['cw_h'][0]}–{o['cw_h'][1]}"},
                                        **{"What shortens it": o["how"]}) for o in TH.OODA]),
                     hide_index=True, use_container_width=True,
                     column_config={k: st.column_config.TextColumn(width="medium") for k in
                                    ["Today", "With Conflict EW", "What shortens it"]})
        c = st.columns(4)
        with c[0]:
            card("Observe: data latency", f"{meta['ucdp_lag_days']} d → <1 d", "UCDP's last record vs GDELT and market "
                 "closes, same day", T["cyan"], "DATA (measured)")
        with c[1]:
            card("Orient: build time", f"{meta['build_seconds']} s", "four theatres × 7 days of briefs, scored and "
                 "ranked", T["amber"], "DATA (measured on this run)")
        with c[2]:
            card("Decide: options ready", "3 / theatre", "ranked actions at 0600 for the 0700 update", T["teal"],
                 "playbook rules")
        with c[3]:
            card("Act: trigger", "FLASH", "pushed to the owner on ingest; no new conference", T["red"],
                 f"P ≥ {TH.FLASH_P:.2f} or a RAG change")
        st.markdown(f"{DOM_TAG} The staff-cycle hours are an illustrative DOMAIN estimate, not a measurement. The "
                    "measured parts are the data latency and the build time. The claim is about the loop, not the "
                    "model: the brief removes collation, scoring and option-building from the critical path, so "
                    "the commander's time goes to judgement.", unsafe_allow_html=True)
    with t4:
        F = pd.DataFrame(B["flashes"])
        if len(F):
            st.dataframe(F[["dtg", "code", "kind", "text"]].rename(columns={"dtg": "DTG", "code": "Theatre", "kind": "Type",
                                                                           "text": "Message"}),
                         hide_index=True, use_container_width=True,
                         column_config={"Message": st.column_config.TextColumn(width="large")})
        st.caption(f"FLASH rules: a district's nowcast P crosses {TH.FLASH_P:.2f} upward (with a 0.01 band to stop "
                   "jitter), or a theatre's RAG changes between two daily runs. NTC FLASHes come from the scripted "
                   "[SYNTHETIC] demo surge.")
    footer()


{
    PAGES[0]: page_brief, PAGES[1]: page_explorer, PAGES[2]: page_area, PAGES[3]: page_military, PAGES[4]: page_india,
    PAGES[5]: page_displacement, PAGES[6]: page_media, PAGES[7]: page_forecast, PAGES[8]: page_ew,
    PAGES[9]: page_whatif, PAGES[10]: page_lab, PAGES[11]: page_dq, PAGES[12]: page_econ,
    PAGES[13]: page_theatre, PAGES[14]: page_history,
}[page]()
