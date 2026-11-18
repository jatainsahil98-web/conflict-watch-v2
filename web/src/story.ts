import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { type Data, type Score, CASES, CASE_COLOR, CASE_SHORT, CASE_NAME, RAG_COLOR, fmt, fmtM, pct } from "./data";
import { verify, DOCTRINE } from "./rules";
import { mount, update, axis, csv, resizeAll } from "./charts";
import { globe, regionMap, pulse, adminLayer, ramp, tip, el } from "./maps";
import { $, $$, tag, info, ragCards, whatIf, scorecardLab, warningPanel, holdoutChart, leaderboard } from "./widgets";
import { presenter, qaDrawer, footer, strip, navBar } from "./chrome";

gsap.registerPlugin(ScrollTrigger);
const REDUCE = matchMedia("(prefers-reduced-motion: reduce)").matches;

const CHAPTERS = [
  ["hero", "Four wars"], ["bluf", "BLUF"], ["india", "India"], ["signatures", "Signatures"], ["afpak", "Two fronts"],
  ["front", "The front"], ["media", "Headlines"], ["gdelt", "GDELT"], ["displacement", "Displacement"], ["prediction", "Prediction"],
  ["warning", "Early warning"], ["fastclock", "Fast clock"], ["decision", "Decision room"], ["recs", "Recommendations"], ["method", "Limits & method"], ["closing", "Close"],
] as const;
/** Chapters shown only when "Full evidence" is on. The briefing itself is the other nine. */
const DEEP = new Set(["signatures", "media", "gdelt", "displacement", "decision", "method"]);

function countUp(root: ParentNode = document) {
  $$("[data-count]", root).forEach((e) => {
    const end = +e.dataset.count!, dec = +(e.dataset.dec ?? 0), pre = e.dataset.pre ?? "", suf = e.dataset.suf ?? "";
    const show = (v: number) => (e.textContent = pre + v.toLocaleString("en-IN", { minimumFractionDigits: dec, maximumFractionDigits: dec }) + suf);
    if (REDUCE) return show(end);
    show(0);
    ScrollTrigger.create({ trigger: e, start: "top 90%", once: true, onEnter: () => { const o = { v: 0 }; gsap.to(o, { v: end, duration: 1.6, ease: "power3.out", onUpdate: () => show(o.v) }); } });
  });
}
const K = (v: number, l: string, s = "", o: { dec?: number; pre?: string; suf?: string; color?: string } = {}) =>
  `<div class="kpi"><span class="v" style="${o.color ? `color:${o.color}` : ""}" data-count="${v}" data-dec="${o.dec ?? 0}" data-pre="${o.pre ?? ""}" data-suf="${o.suf ?? ""}">${v}</span><span class="l">${l}</span>${s ? `<span class="s">${s}</span>` : ""}</div>`;

export function renderStory(D: Data) {
  const F = D.facts;
  const S: Record<string, Score> = Object.fromEntries(F.scorecard.map((s: Score) => [s.id, s]));
  const O: Record<string, any> = Object.fromEntries(F.overview.map((o: any) => [o.id, o]));
  const v2 = F.v2, gd = F.gdelt, mil = F.military, ind = F.india, med = F.media, dsp = F.displacement, fc = F.forecasting, ew = F.warning;
  const bad = verify(F.scorecard, DOCTRINE(F));
  if (bad.length) console.error("Scorecard parity FAILED", bad);

  document.body.insertAdjacentHTML("beforeend", `
  ${strip(F)} ${navBar(F, "story")}
  <div class="prog" aria-hidden="true"><i id="prog"></i></div>
  <nav class="dots" aria-label="Chapters">${CHAPTERS.map(([id, l]) => `<a href="#${id}" data-l="${l}" aria-label="${l}"${DEEP.has(id) ? ' class="deep"' : ""}></a>`).join("")}</nav>
  <button class="btn deepbtn no-print" id="deep-t" aria-pressed="false" title="Show or hide the seven supporting chapters (E)">FULL EVIDENCE · OFF</button>
  <main id="main">
  <section class="ch" id="hero" aria-label="Four wars, one exposed neighbour">
    <canvas id="globe" aria-label="Globe of conflict deaths 2014 to 2026, coloured by conflict"></canvas>
    <div class="over">
      <div class="yr mono">CONFLICT EVENTS · <span id="hero-yr">2014</span></div>
      <h1 class="display">Four wars.<br><span style="color:var(--teal)">One exposed neighbour.</span></h1>
      <p class="lede" style="margin-top:22px">${F.tagline}</p>
      <div class="legend">${CASES.map((c) => `<span><i style="background:${CASE_COLOR[c]}"></i>${CASE_NAME[c]}</span>`).join("")}</div>
    </div>
    <div class="scrollcue">SCROLL ▾</div>
  </section>

  <section class="ch" id="bluf"><div class="wrap">
    <div class="eyebrow">BLUF · OCTOBER 2026 THREAT SCORECARD</div>
    <h2 class="title reveal">One war at <span style="color:var(--red)">RED</span>, two at <span style="color:var(--amber)">AMBER</span>,<br>one cooling to <span style="color:var(--green)">GREEN</span>.</h2>
    <p class="lede reveal">Every rating comes from model outputs through five transparent rules. Click a card for the points behind it. ${tag("data")}</p>
    <div class="grid g4 reveal" id="bluf-cards" style="margin-top:26px"></div>
    <div class="grid g4 reveal" style="margin-top:22px">
      ${F.scorecard.map((s: Score) => `<div class="panel small"><span class="mono small muted">FORWARD · ${s.short}</span><br>${s.forward.map((f) => `${f.month.slice(0, 3)} <b>${fmt(f.pred)}</b> <span class="muted">(${fmt(f.lo)}–${fmt(f.hi)})</span>`).join("<br>")}</div>`).join("")}
    </div>
  </div></section>

  <section class="ch" id="india"><div class="wrap">
    <div class="eyebrow">WHY IT MATTERS TO INDIA</div>
    <h2 class="title reveal">The 2026 US–Iran war reached India's neighbourhood.</h2>
    <div class="split" style="margin-top:18px">
      <div>
        <div class="grid g2 reveal" style="gap:22px">
          ${K(ind.usir_countries[1], "countries hit by US–Iran in 2026", `up from ${ind.usir_countries[0]} in 2025`, { color: "var(--red)" })}
          ${K(ind.gulf_states, "Gulf states struck", `${ind.gulf_events} events · ${ind.gulf_deaths} deaths`, { color: "var(--amber)" })}
          ${K(ind.hormuz_deaths, "deaths on Iran's Hormuz / Chabahar coast", "Chabahar & INSTC in the strike zone")}
          ${K(ind.srilanka.deaths, "killed off Sri Lanka, 4 Mar 2026", "war at sea in India's IOR")}
          <div class="kpi"><span class="v"><span data-count="${ind.pak_india_adjoining[2022]}">${ind.pak_india_adjoining[2022]}</span> → <span style="color:var(--red)" data-count="${ind.pak_india_adjoining[2025]}">${ind.pak_india_adjoining[2025]}</span></span><span class="l">deaths in Pakistan areas adjoining India / LoC</span><span class="s">2022 → 2025</span></div>
          ${K(ind.yemen_2025, "deaths in Yemen (2025)", "Red Sea shipping lane")}
        </div>
        <p class="reveal" style="margin-top:20px">${tag("data")} All counts above are from UCDP. ${tag("domain")} About 9 million Indians live in the Gulf; precedents for evacuation: ${ind.domain.precedents}.</p>
        <div class="sowhat reveal"><b>SO WHAT</b>Keep Gulf NEO plans current while US–Iran is AMBER, and treat the Af–Pak front as a standing LoC indicator.</div>
      </div>
      <div class="mapbox reveal" id="india-map" aria-label="Map of India's exposure ring: Gulf, Hormuz, Chabahar, Sri Lanka and the LoC"></div>
    </div>
  </div></section>

  <section class="ch" id="signatures"><div class="wrap">
    <div class="eyebrow">FINDING 1 · FOUR THREAT SIGNATURES</div>
    <h2 class="title reveal">Four wars, four different shapes.</h2>
    <div class="split rev" style="align-items:start">
      <div class="panel" id="sig-panel"><div class="ph"><span class="t">Deaths per month, 2014–Sep 2026 (log scale)</span>${info("Each line is one conflict's recorded deaths per month (UCDP best estimate). The vertical scale is logarithmic, so a war of 10,000 a month and one of 100 a month fit on the same chart. The shaded band is 2026, which the models never saw during design.")}</div><div class="chart tall" id="sig-ch"></div></div>
      <div id="sig-steps">${CASES.map((c) => `<div class="panel sig-step" data-c="${c}" style="margin-bottom:16px;border-left:3px solid ${CASE_COLOR[c]};cursor:pointer" tabindex="0">
        <div class="mono small" style="color:${CASE_COLOR[c]};letter-spacing:.2em">${O[c].signature}</div><h3>${CASE_NAME[c]}</h3>
        <p class="small muted" style="margin:6px 0">${O[c].signature_text}. Peak ${O[c].peak_month}: <b style="color:var(--tx)">${fmt(O[c].peak)}</b>. Total ${fmt(O[c].deaths)} (UCDP range ${fmtM(O[c].low)}–${fmtM(O[c].high)}). Civilians ${O[c].civ_pct}%.</p></div>`).join("")}</div>
    </div>
  </div></section>

  <section class="ch" id="afpak"><div class="wrap">
    <div class="eyebrow">BORDERS · INDIA'S WESTERN NEIGHBOUR</div>
    <h2 class="title reveal">Pakistan fights on two fronts.</h2>
    <div class="grid g2" style="margin-top:8px">
      <div class="panel"><div class="ph"><span class="t">Afghanistan–Pakistan state clashes (deaths / month)</span></div><div class="chart" id="dy-ch" style="height:300px"></div>
        <div class="ph" style="margin-top:6px"><span class="t">Why we harmonise FATA</span><div class="seg" id="fata-seg"><button data-v="raw">RAW LABELS</button><button data-v="harm" class="on">HARMONISED</button></div></div>
        <div class="chart short" id="fata-ch" style="height:240px"></div>
        <p class="small muted" id="fata-note"></p></div>
      <div><div class="mapbox" id="afpak-map" style="height:470px"></div>
        <div class="sowhat" style="margin-top:14px"><b>SO WHAT</b>${tag("domain")} With the Pakistan Army committed in the west, watch for diversionary LoC activity and TTP / IS-K spill-over. ${tag("data")} KP deaths have risen every year since 2021; interstate clashes peaked at <b>${fmt(mil.afpak_dyad["2026-03"])}</b> deaths in Mar 2026.</div></div>
    </div>
  </div></section>

  <section class="ch" id="front"><div class="wrap">
    <div class="eyebrow">SUSTAINMENT · RUSSIA–UKRAINE</div>
    <h2 class="title reveal">The front is widening, not moving.</h2>
    <p class="lede reveal">Donetsk's share of located events fell from <b style="color:var(--tx)">${mil.donetsk[0]}%</b> (2022) to <b style="color:var(--tx)">${mil.donetsk[1]}%</b> (2026). Zaporizhzhia, Dnipropetrovsk, Sumy and Belgorod rose. ${tag("data")}</p>
    <div class="grid g2" style="margin-top:12px">
      <div class="panel" style="padding:12px"><div class="ph"><span class="t">Share of located events · <span id="fr-y">2026</span></span>
        <div class="seg" id="fr-years">${[2022, 2023, 2024, 2025, 2026].map((y) => `<button data-y="${y}">${y}</button>`).join("")}</div></div>
        <div class="mapbox" id="front-map" style="height:430px"></div>
        <div class="chart" id="fr-bar" style="height:64px"></div></div>
      <div class="panel"><div class="ph"><span class="t">Fog of war: deaths with no location</span><label class="toggle"><input type="checkbox" id="fog-t"><span class="sw"></span>SHOW ALL DEATHS</label></div>
        <div class="chart" id="fog-ch" style="height:300px"></div>
        <p class="small">Unlocated share: <b>${mil.fog[2022]}%</b> (2022) → <b style="color:var(--red)">${mil.fog[2026]}%</b> (2026). This is why sub-national analysis uses located events, not deaths. ${tag("data")}</p>
        <div class="ph" style="margin-top:8px"><span class="t">Recorded attrition, focal dyad</span>${tag("caveat", "CAVEAT")}</div>
        <div class="chart short" id="att-ch" style="height:230px"></div>
        <p class="small muted">${mil.caveat} Ratio ${mil.attrition.filter((a: any) => [2022, 2025, 2026].includes(a.year)).map((a: any) => `${a.ratio}:1 (${a.year})`).join(" → ")}. US–Iran 2026: Iran ${fmt(mil.usir_2026.iran)} vs coalition ${mil.usir_2026.coalition}.</p></div>
    </div>
    <div class="sowhat reveal" style="margin-top:16px"><b>SO WHAT</b>${tag("domain")} A wide, static front rewards long-range strike, counter-drone and logistics depth over manoeuvre. Deaths inside Russia peaked at ${fmt(mil.russia_inside_peak.deaths)} (${mil.russia_inside_peak.year}).</div>
  </div></section>

  <section class="ch" id="media"><div class="wrap">
    <div class="eyebrow">FINDING 4 · ORIGINAL INDEX: ATTENTION GAP</div>
    <h2 class="title reveal">Headlines are not warnings.</h2>
    <div class="grid g3 reveal" style="margin:10px 0 20px">
      ${K(med.el_events, "elasticity of media references to EVENTS", "R² " + med.r2, { dec: 2, color: "var(--teal)" })}
      ${K(med.el_deaths, "elasticity to DEATHS", "media follow incidents, not severity", { dec: 2, color: "var(--red)" })}
      ${K(med.lead_p, "p-value: does the gap lead escalation?", `coef ${med.lead_coef} → no`, { dec: 2, pre: "p = ", color: "var(--amber)" })}
    </div>
    <div class="grid g2">
      <div class="panel"><div class="ph"><span class="t">References vs events (tight)</span>${info("Each dot is one conflict-month. Media references rise almost one-for-one with the number of incidents. Hover a dot to find the same month in the other chart.")}</div><div class="chart" id="agi-e"></div></div>
      <div class="panel"><div class="ph"><span class="t">References vs deaths (loose)</span></div><div class="chart" id="agi-d"></div></div>
    </div>
    <p class="small" style="margin-top:12px">References per 100 deaths (median month): ${CASES.map((c) => `${CASE_SHORT[c]} <b>${med.refs_per_100[c]}</b>`).join(" · ")}. Indian outlets appear in <b>${Math.round(med.indian_share.afpak * 100)}%</b> of Af–Pak events and almost none elsewhere. ${tag("data")}</p>
  </div></section>

  <section class="ch" id="gdelt"><div class="wrap">
    <div class="eyebrow">FINDING 8 · SECOND SOURCE: GDELT, FEB–NOV 2026 · NEW RESULTS</div>
    <h2 class="title reveal">News sees past UCDP's cut-off. It does not see ahead.</h2>
    <div class="grid g3 reveal" style="margin:10px 0 20px">
      ${K(gd.rho_change.usir, "US–Iran: GDELT tracks UCDP month to month", `Af–Pak ${gd.rho_change.afpak} · RU–UA ${gd.rho_change.ruua} · IL–Hamas ${gd.rho_change.ilh}`, { dec: 2, pre: "ρ ", color: "var(--teal)" })}
      ${K(gd.lead_p, "GDELT a week EARLIER adds nothing", "a nowcast, not a leading indicator", { dec: 2, pre: "p = ", color: "var(--amber)" })}
      ${K(gd.articles_per_death.usir, "articles per UCDP death, US–Iran", `vs ${gd.articles_per_death.ruua} for RU–UA: the attention gap again`, { color: "#A78BFA" })}
    </div>
    <div class="panel"><div class="ph"><span class="t">Weekly: UCDP deaths (bars) vs GDELT violent events per day (line) · shaded = after UCDP ends</span>${info("GDELT counts media-coded reports, not incidents. Rates are per covered day: GDELT has no data for 1–16 May 2026 and stops on 12 Nov 2026. UCDP bars are deaths in discrete, dated events.")}<div class="seg" id="gd-seg">${CASES.map((c) => `<button data-c="${c}"${c === "usir" ? ' class="on"' : ""}>${CASE_SHORT[c]}</button>`).join("")}</div></div><div class="chart" id="gd-ch" style="height:360px"></div></div>
    <div class="panel" style="margin-top:14px"><div class="ph"><span class="t">After UCDP: GDELT signal for Oct and 1–12 Nov 2026</span></div>
      <table class="t"><tr><th>Conflict</th><th>Month</th><th>Violent / day</th><th>Change</th><th>Threats / day</th><th>Signal</th><th>Tracks UCDP?</th></tr>${gd.signals.filter((x: any) => x.m !== "2026-09").map((x: any) => `<tr><td><b style="color:${CASE_COLOR[x.c as keyof typeof CASE_COLOR]}">${CASE_SHORT[x.c]}</b></td><td class="mono">${x.m === "2026-11" ? "1–12 Nov" : "Oct"}</td><td class="mono">${fmt(x.v)}</td><td class="mono">${x.ch == null ? "" : (x.ch > 0 ? "+" : "") + Math.round(x.ch * 100) + "%"}</td><td class="mono">${fmt(x.t)}</td><td><b style="color:${x.flag === "RISING" ? "var(--red)" : x.flag === "FALLING" ? "var(--teal)" : "var(--tx2)"}">${x.flag}</b></td><td>${x.tracks ? "Yes" : "No"}</td></tr>`).join("")}</table></div>
    <div class="sowhat" style="margin-top:14px"><b>SO WHAT</b> Watch spike wars past UCDP's lag with GDELT: <b>US–Iran violence and threats rose in early Nov 2026</b> while the scorecard is AMBER. GDELT did not beat persistence out of sample (${gd.oos_weeks} weeks), so it stays out of the submitted forecasts. ${tag("data")}</div>
  </div></section>

  <section class="ch" id="displacement"><div class="wrap">
    <div class="eyebrow">FINDING 5 · HUMAN COST</div>
    <h2 class="title reveal">Displacement is women and children.</h2>
    <div class="split" style="margin-top:10px;align-items:start">
      <div class="panel hud"><div class="ph"><span class="t">Ukraine, end-2025 · 1 dot = 50,000 people</span><div class="seg" id="wf-seg"><button data-v="type" class="on">REFUGEES / IDPs</button><button data-v="wc">WOMEN & CHILDREN</button></div></div>
        <div class="waffle" id="waffle" role="img" aria-label="Unit chart of Ukraine's 8.9 million displaced"></div>
        <p class="small" id="wf-note" style="margin-top:12px"></p></div>
      <div>
        <div class="grid g2" style="gap:22px">
          ${K(Math.round(dsp.ukr.wc * 100), "of Ukrainian refugees are women or children", "with recorded sex and age", { suf: "%", color: "var(--violet)" })}
          ${K(Math.round(dsp.afg.wc * 100), "of Afghan refugees are women or children", `${Math.round(dsp.afg.u5 * 100)}% under five`, { suf: "%", color: "var(--violet)" })}
        </div>
        <div class="panel" style="margin-top:18px"><div class="ph"><span class="t">Palestine: two series, never summed</span></div><div class="chart short" id="pse-ch" style="height:200px"></div></div>
        <p class="small muted">Afghan refugees abroad ${fmtM(dsp.afg.ref24)} (2024) → ${fmtM(dsp.afg.ref25)} (2025), with ${fmtM(dsp.afg.oip25)} reclassified as "other protection". Deaths vs displacement change: Spearman ${dsp.link.spearman.toFixed(2)} (p = ${dsp.link.p.toFixed(2)}), so displacement cannot be read off death counts. ${tag("data")}</p>
        <div class="sowhat"><b>SO WHAT</b>${tag("domain")} HADR packs for any Indian response must be built for women, children and under-fives.</div>
      </div>
    </div>
  </div></section>

  <section class="ch" id="prediction"><div class="wrap">
    <div class="eyebrow">PREDICTION · WITHHELD 2026 TEST, SCORED ONCE</div>
    <h2 class="title reveal">Beating "no change" on data the model never saw.</h2>
    <div class="grid g4 reveal" style="margin:8px 0 18px">
      ${K(fc.mae_pooled, "lower error than 'no change'", "1-month MAE, pooled", { pre: "−", suf: "%", color: "var(--teal)" })}
      <div class="kpi"><span class="v" id="cov-v" style="color:var(--amber)">0%</span><span class="l">2026 outcomes inside the 80% band</span><span class="s" id="cov-s">target 80%</span></div>
      ${K(fc.direction, "direction of change correct", "Track A", { suf: "%" })}
      ${K(fc.mape_ruua, "RU–UA error (MAPE)", "1-month ahead", { suf: "%" })}
    </div>
    <div class="panel"><div class="ph"><span class="t">2026 replay · forecast vs actual</span>
      <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap"><div class="seg" id="pl-tr"><button data-t="A" class="on">TRACK A · 1 MONTH</button><button data-t="B">TRACK B · 1–9 MONTHS</button></div><button class="btn" id="pl-play">▶ PLAY</button></div></div>
      <div class="ctl"><label>Playhead <output id="pl-o"></output></label><input type="range" id="pl" min="0" max="9" step="1" value="9" aria-label="2026 playhead"></div>
      <div class="grid g2"><div class="chart" id="pl-ru"></div><div class="chart" id="pl-af"></div></div></div>
    <div class="grid g2" style="margin-top:18px">
      <div class="panel"><div class="ph"><span class="t">Leaderboard · RMSLE</span><div class="seg" id="lb-seg"><button data-k="A_bt">A BACK-TEST</button><button data-k="A_hold" class="on">A 2026</button><button data-k="B_bt">B BACK-TEST</button><button data-k="B_hold">B 2026</button></div></div>
        <div class="chart" id="lb-ch"></div><p class="small" id="lb-note"></p></div>
      <div class="panel"><div class="ph"><span class="t">Why predict the change, not the level</span>${info("Tree models cannot predict values beyond what they saw in training. A model trained before February 2022 had never seen thousands of deaths a month, so a level target flat-lines. Predicting the change from last month removes that ceiling.")}</div>
        <div class="chart short" id="abl-ch" style="height:250px"></div>
        <div class="ph" style="margin-top:6px"><span class="t">What drives the forecast (mean |SHAP|)</span></div><div class="chart short" id="shap-ch" style="height:250px"></div></div>
    </div>
    <p class="small muted" style="margin-top:12px">Dashboard model: 3-month mean + ETS (damped, log) + LightGBM-Δ, chosen on the 2022–25 back-test only. The deck's final model is the global ensemble (global LightGBM 0.90 + competition LightGBM-Δ 0.10). Known failure: the Feb 2026 US–Iran war began with no build-up in the death series. ${tag("data")}</p>
  </div></section>

  <section class="ch" id="warning"><div class="wrap">
    <div class="eyebrow">EARLY WARNING · ${ew.areas} SUB-NATIONAL AREA SERIES, ${ew.countries} COUNTRIES</div>
    <h2 class="title reveal">A district watch-list, one month ahead.</h2>
    <div class="grid g4 reveal" style="margin:8px 0 18px">
      ${K(ew.auc, "ROC-AUC on 2026", `back-test ${ew.bt_auc[0]}–${ew.bt_auc[1]}`, { dec: 3, color: "var(--teal)" })}
      ${K(ew.lift, "better than random (top-10)", `${ew.lift_rule}× the rule of thumb`, { dec: 1, suf: "×", color: "var(--amber)" })}
      ${K(Math.round(ew.p10 * 1000) / 10, "top-10 precision", `base rate ${pct(ew.base, 1)}`, { dec: 1, suf: "%" })}
      ${K(Math.round(ew.r20 * 1000) / 10, "of escalations caught in top-20", "", { dec: 1, suf: "%" })}
    </div>
    <div id="ew-box"></div>
  </div></section>

  <section class="ch" id="fastclock"><div class="wrap">
    <div class="eyebrow">FINDING 4 · THE FAST CLOCK · GDELT (D7, D8) AND UCDP SOURCES (D2), D10 · NEW IN V2</div>
    <h2 class="title reveal">Deaths are counted weeks late.<br><span style="color:var(--teal)">The news turns the same day.</span></h2>
    <p class="lede reveal">Two clocks. The monthly forecast sizes a war; a daily news tripwire says when it changes state. The rules were fixed before testing and never tuned. ${tag("data")}</p>
    <div class="grid g4 reveal" style="margin:10px 0 18px;gap:22px">
      ${K(v2.tripwire.confirmed, `of ${v2.tripwire.episodes} red alerts confirmed`, `by a UCDP escalation within ±3 days · chance ${v2.tripwire.chance}`, { color: "var(--teal)" })}
      ${K(v2.tripwire.p, "permutation p-value", "20,000 random alert dates", { dec: 3, color: "var(--amber)" })}
      ${K(Math.round(v2.completeness.ruua.share[3] * 100), "of RU–UA deaths known 90 days on", "the 2026 \"decline\" is mostly late reporting", { suf: "%", color: "var(--red)" })}
      ${K(v2.india.triggers.filter((x: any) => x.state_deaths_45d_after >= 30).length, "J&K attacks followed by state fighting", "≥30 India–Pakistan state deaths within 45 days", { color: "var(--amber)" })}
    </div>
    <div class="split" style="align-items:start">
      <div class="panel"><div class="ph"><span class="t">Tripwire alerts, Feb–Sep 2026</span>${info("RED: violent news events per day at least 4× the trailing 14-day median and at least 100. AMBER: military-posture reports over 7 days at least 4× the trailing 28-day median. Confirmed: a UCDP escalation day (deaths above max(20, 3× the trailing 28-day mean)) within ±3 days for RED, within 21 days after for AMBER.")}</div>
        <table class="t"><tr><th>Date</th><th>Conflict</th><th>Light</th><th>Outcome</th></tr>${v2.tripwire.alerts.slice().sort((a: any, b: any) => a.d.localeCompare(b.d)).map((x: any) => `<tr><td class="mono">${x.d}</td><td style="color:${CASE_COLOR[x.c]}">${CASE_SHORT[x.c]}</td><td class="mono" style="color:${x.light === "RED" ? "var(--red)" : "var(--amber)"}">${x.light}</td><td>${x.ok ? `confirmed${x.lead != null ? ` · ${x.lead} d ahead` : ""}` : `<span class="muted">false alarm</span>`}</td></tr>`).join("")}</table>
        <p class="small muted" style="margin-top:8px">It detects onsets; it does not size them, and it misses most routine insurgent escalations (Af–Pak: ${v2.tripwire.caught.afpak.caught} of ${v2.tripwire.caught.afpak.escalation_days} escalation days).</p></div>
      <div class="panel"><div class="ph"><span class="t">How much of a month's deaths is known k days later</span>${info("For 2022–2025 events: the share of deaths whose last source report (D2) was published within k days of the event's end.")}</div><div class="chart" id="fc-cp" style="height:330px"></div></div>
    </div>
    <div class="panel" style="margin-top:20px"><div class="ph"><span class="t">India's own front · J&amp;K attacks with 15+ deaths, and what followed</span>${info(v2.india.note)}</div>
      <table class="t"><tr><th>Date</th><th>Deaths (civilians)</th><th>India–Pakistan state deaths, 45 d before</th><th>45 d after</th><th>Days to state fighting</th></tr>${v2.india.triggers.map((x: any) => `<tr><td class="mono">${x.date}</td><td class="num">${x.deaths} (${x.civilians})</td><td class="num">${x.state_deaths_45d_before}</td><td class="num" style="color:${x.state_deaths_45d_after >= 30 ? "var(--red)" : "inherit"}">${x.state_deaths_45d_after}</td><td class="num">${x.days_to_state_fighting ?? "–"}</td></tr>`).join("")}</table>
      <div class="sowhat"><b>SO WHAT</b>Start a 15-day watch after any J&amp;K attack with 15+ deaths: after Uri, Pulwama and Pahalgam, state fighting followed in 11–15 days. Cross-border firing was routine in 2016–20, so this is a pattern to watch, not proof of cause.</div></div>
  </div></section>

  <section class="ch" id="decision"><div class="wrap">
    <div class="eyebrow">DECISION ROOM · LIVE MODELS IN YOUR BROWSER</div>
    <h2 class="title reveal" id="whatif">What if violence had been different?</h2>
    <div id="wi-box"></div>
    <h2 class="title" id="lab" style="margin-top:56px;font-size:clamp(30px,3.4vw,52px)">Change the rules. Watch the ratings.</h2>
    <div id="lab-box"></div>
  </div></section>

  <section class="ch" id="recs"><div class="wrap">
    <div class="eyebrow">RECOMMENDATIONS</div>
    <h2 class="title reveal">Sense · Warn · Shield · Sustain</h2>
    <div class="grid g4" style="margin-top:14px">${F.recommendations.map((r: any, i: number) => `<div class="panel hud rec reveal" tabindex="0" style="border-top:3px solid ${["#4FD1E0", "#F2B33D", "#FF4D5E", "#A78BFA"][i]}">
      <div class="line" style="color:${["#4FD1E0", "#F2B33D", "#FF4D5E", "#A78BFA"][i]}">${r.line}</div><div style="font-size:17px">${r.action}</div>
      <div class="mono small muted">LEAD ${r.lead}<br>WHEN ${r.when}</div>
      <div class="more small"><span class="tag data">TRIGGER</span> ${r.why}. <a href="#${r.trigger}">See the finding ↗</a></div>
      <div class="mono small" style="margin-top:auto;color:var(--tx3)">▸ WHY</div></div>`).join("")}</div>
    <div class="panel" style="margin-top:20px"><div class="ph"><span class="t">Agency × time</span></div>
      <table class="t"><tr><th>Line</th><th>Now</th><th>90 days</th><th>6–12 months</th></tr>${F.recommendations.map((r: any) => `<tr><td class="mono"><b>${r.line}</b></td>${["Now", "90 days", "6–12 months"].map((w) => `<td>${r.when.includes(w) ? `● ${r.lead}` : ""}</td>`).join("")}</tr>`).join("")}</table></div>
    <div class="grid g4" style="margin-top:20px">${F.end_state.map((e: string) => `<div class="panel kpi"><span class="l">END STATE</span><span class="v" style="font-size:26px">${e}</span></div>`).join("")}</div>
  </div></section>

  <section class="ch" id="method"><div class="wrap">
    <div class="eyebrow">LIMITS, METHOD AND VERIFICATION</div>
    <h2 class="title reveal">What this cannot tell you.</h2>
    <div class="grid g2">
      <div class="panel hud"><div class="ph"><span class="t">Limits</span></div><ul style="margin:0;padding-left:20px">${F.limits.map((l: string, i: number) => `<li style="margin:6px 0;${i === F.limits.length - 1 ? "color:var(--amber);font-weight:600" : ""}">${l}</li>`).join("")}</ul></div>
      <div class="panel"><div class="ph"><span class="t">Techniques</span></div><table class="t small">${[
        ["Walk-forward CV", "2022–25 folds drive every choice; 2026 scored once"], ["ETS / SARIMA", "Per-conflict statistical baselines"],
        ["LightGBM-Δ", "Global tree model on the change in log deaths"], ["Split conformal", "Calibrated 80% / 95% bands"],
        ["LightGBM classifier", "Area escalation one month ahead"], ["TreeSHAP", "Plain-English drivers of each model"],
        ["FE regression", "Attention Gap Index (media vs violence)"], ["Day-proportional split", "Multi-month events spread across months"]].map(([a, b]) => `<tr><td class="mono"><b>${a}</b></td><td>${b}</td></tr>`).join("")}</table></div>
    </div>
    <div class="panel" style="margin-top:18px"><div class="ph"><span class="t">Data-quality log · ${D.dq.length} checks</span><button class="btn small" id="dq-csv">CSV</button></div><div style="max-height:380px;overflow:auto" id="dq-t"></div></div>
    <div class="grid g2" style="margin-top:18px">
      <div class="panel hud"><div class="ph"><span class="t">Verify this site</span></div>
        <div class="mono small">RUN ${F.run_id}<br>EXPORTED ${F.exported}<br>DATA AS OF ${F.data_as_of}<br>BUILD ${D.inline ? "single-file offline" : "web / PWA"}</div>
        <details style="margin-top:8px"><summary class="mono small">SHA-256 of each data file</summary><div class="mono" style="font-size:11px;word-break:break-all">${Object.entries(D.manifest.files).map(([k, v]: any) => `${k}: ${v.sha256}`).join("<br>")}</div></details>
        <p class="small muted">Reproduce: <span class="mono">python run_pipeline.py && python scripts/export_web.py</span>. The export fails if any number differs from the report.</p></div>
      <div class="panel"><div class="ph"><span class="t">Jury Q&amp;A</span></div><p class="small">Prepared answers to the questions we expect, including "Why not LSTM?", "Did you tune on 2026?" and "Is this map correct?"</p><button class="btn primary" id="qa-open">Open Q&amp;A ▸</button></div>
    </div>
  </div></section>

  <section class="ch" id="closing"><div class="wrap">
    <p class="q reveal">"Open data and an honest model can tell India where to look next month."</p>
    <div class="mono" style="letter-spacing:.2em;color:var(--tx2)">${F.team.join(" · ")}</div>
    <div class="mono small muted" style="margin-top:14px">${F.competition.toUpperCase()}</div>
    <div class="small muted" style="margin-top:28px">Sources: ${F.sources}. Licences: ${F.licence}.</div>
  </div></section>
  </main>
  ${footer(F)}`);

  // ---- Hero globe
  const rings: [number, number, string][] = [[54.4, 24.5, "GULF"], [56.3, 27.2, "HORMUZ"], [60.6, 25.3, "CHABAHAR"], [79.8, 6.2, "SRI LANKA 4 MAR 26"], [74.2, 33.6, "LoC"]];
  const G = globe($("#globe") as HTMLCanvasElement, D.world, D.points, rings);
  const yr = { y: 2014 };
  if (REDUCE) { G.setYear(2026); $("#hero-yr").textContent = "2014–2026"; }
  else gsap.to(yr, { y: 2026, duration: 9, ease: "none", repeat: -1, repeatDelay: 2.5, onUpdate: () => { G.setYear(Math.floor(yr.y)); $("#hero-yr").textContent = String(Math.floor(yr.y)); } });
  ScrollTrigger.create({ trigger: "#hero", start: "top top", end: "bottom top", scrub: true, onUpdate: (s) => G.setFocus(s.progress * 2.2) });

  ragCards($("#bluf-cards"), D);

  // ---- India map
  const im = regionMap($("#india-map"), D.world, [[33, 2], [92, 38]]);
  const exp: [number, number, string, string, number][] = [
    [54.37, 24.45, "UAE", "#F2B33D", 0, "start"], [50.58, 26.22, "Bahrain", "#F2B33D", 300, "end"], [47.98, 29.37, "Kuwait", "#F2B33D", 600, "end"], [58.4, 23.6, "Oman", "#F2B33D", 900, "start"],
    [46.7, 24.7, "Saudi Arabia", "#F2B33D", 1200, "end"], [56.27, 27.18, "Hormozgan · 299", "#FF4D5E", 1500, "start"], [60.64, 25.29, "Chabahar", "#FF4D5E", 1700, "start"],
    [80.0, 5.4, "104 killed · 4 Mar 26", "#FF4D5E", 1900, "end"], [44.2, 15.4, "Yemen · 945 (2025)", "#A78BFA", 2100, "start"], [73.6, 33.9, "LoC · 2→52", "#FF4D5E", 2300, "end"]] as any;
  exp.forEach(([lo, la, l, c, d, an]: any) => pulse(im, lo, la, c, l, d, 7, an));

  // ---- Signatures
  const sigOpt = (hl: string | null) => ({
    legend: { data: CASES.map((c) => CASE_NAME[c]) }, tooltip: { trigger: "axis", valueFormatter: (v: number) => fmt(v) },
    dataZoom: [{ type: "inside" }],
    xAxis: { type: "category", data: D.monthly.ruua.months, ...axis() }, yAxis: { type: "log", min: 1, ...axis(), name: "deaths / month" },
    series: CASES.map((c) => ({ name: CASE_NAME[c], type: "line", data: D.monthly[c].deaths.map((v) => Math.max(v, 1)), symbol: "none", smooth: 0.2,
      lineStyle: { width: hl === c ? 3.5 : 1.8, color: CASE_COLOR[c], opacity: hl && hl !== c ? 0.15 : 1 }, itemStyle: { color: CASE_COLOR[c] }, z: hl === c ? 10 : 2,
      markArea: c === "ruua" ? { silent: true, itemStyle: { color: "rgba(79,209,224,.06)" }, label: { color: "#4FD1E0", fontFamily: "JetBrains Mono", fontSize: 11 }, data: [[{ name: "WITHHELD TEST", xAxis: "2026-01" }, { xAxis: "2026-09" }]] } : undefined,
      markPoint: hl === c ? { symbol: "pin", symbolSize: 46, itemStyle: { color: CASE_COLOR[c] }, label: { fontSize: 10, color: "#05070A", formatter: () => fmtM(O[c].peak) },
        data: [{ name: "peak", coord: [monthOf(O[c].peak_month), O[c].peak] }] } : undefined })),
  });
  function monthOf(s: string) { const d = new Date("1 " + s); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`; }
  mount($("#sig-ch"), sigOpt(null));
  const sigSet = (c: string | null) => { update($("#sig-ch"), sigOpt(c), true); $$(".sig-step").forEach((s) => (s.style.background = s.dataset.c === c ? "rgba(79,209,224,.06)" : "")); };
  $$(".sig-step").forEach((s) => { s.addEventListener("mouseenter", () => sigSet(s.dataset.c!)); s.addEventListener("focus", () => sigSet(s.dataset.c!)); s.addEventListener("click", () => sigSet(s.dataset.c!)); });
  if (!REDUCE && innerWidth > 980) $$(".sig-step").forEach((s) => ScrollTrigger.create({ trigger: s, start: "top 60%", end: "bottom 40%", onEnter: () => sigSet(s.dataset.c!), onEnterBack: () => sigSet(s.dataset.c!) }));

  // ---- Fast clock: reporting completeness
  mount($("#fc-cp"), {
    legend: { top: 4 }, tooltip: { trigger: "axis", valueFormatter: (v: number) => pct(v, 0) },
    grid: { left: 52, right: 20, top: 40, bottom: 40 },
    xAxis: { type: "category", data: v2.completeness.ruua.days.map((d: number) => `${d} d`), ...axis() },
    yAxis: { type: "value", min: 0, max: 1, ...axis({ axisLabel: { formatter: (v: number) => pct(v, 0) } }) },
    series: CASES.map((c) => ({ name: CASE_SHORT[c], type: "line", data: v2.completeness[c].share, symbolSize: 6,
      lineStyle: { width: 2.6, color: CASE_COLOR[c] }, itemStyle: { color: CASE_COLOR[c] } })),
  });

  // ---- Front
  const fm = regionMap($("#front-map"), D.world, [[22, 44], [41, 53]], { india: false });
  const ruAreas = D.areas.areas.filter((a) => a.c === "ruua");
  const nameToId = new Map(ruAreas.map((a) => [a.name.replace(" Special Republican city", ""), a.id]));
  const idToFront = new Map<string, string>();
  for (const k of Object.keys(D.front)) { const id = nameToId.get(k); if (id) idToFront.set(id, k); }
  let fy = 2026;
  const recolorF = adminLayer(fm, D.admin1, (ids) => ids.some((i) => i.startsWith("ruua:")),
    (ids, ev) => { if (!ev) return tip(null); const k = ids.map((i) => idToFront.get(i)).find(Boolean); const a = ruAreas.find((x) => x.id === ids[0]); tip(`<b>${a?.name ?? ""}</b><br>${fy}: ${k ? pct(D.front[k][fy] ?? 0) + " of located events" : "in 'other areas'"}`, ev); });
  const frontKeys = Object.keys(D.front).sort((a, b) => (D.front[b][2022] ?? 0) - (D.front[a][2022] ?? 0));
  const FCOL = ["#FF4D5E", "#F2B33D", "#4FD1E0", "#A78BFA", "#2BB673", "#E87F5A", "#5FA8FF", "#C9D36A", "#9AA6B6", "#7A6CD8", "#6B7788", "#3E5A78"];
  const setFY = (y: number) => {
    fy = y; $("#fr-y").textContent = String(y);
    $$("#fr-years button").forEach((b) => b.classList.toggle("on", +b.dataset.y! === y));
    recolorF((ids) => { const k = ids.map((i) => idToFront.get(i)).find(Boolean); return k ? ramp(Math.sqrt((D.front[k][y] ?? 0) / 0.6)) : "#1A2638"; });
    update($("#fr-bar"), { grid: { left: 8, right: 8, top: 4, bottom: 4 }, legend: { show: false }, toolbox: { show: false }, tooltip: { trigger: "item", formatter: (p: any) => `${p.seriesName}: ${pct(p.value)}` },
      xAxis: { type: "value", max: 1, show: false }, yAxis: { type: "category", data: [""], show: false },
      series: frontKeys.map((k, i) => ({ name: k, type: "bar", stack: "s", data: [D.front[k][y] ?? 0], itemStyle: { color: FCOL[i % FCOL.length] },
        label: { show: (D.front[k][y] ?? 0) > 0.09, formatter: () => `${k.replace("Zaporizhzhya", "Zap.").replace("Dnipropetrovsk", "Dnipro").slice(0, 9)} ${Math.round((D.front[k][y] ?? 0) * 100)}%`, color: "#05070A", fontFamily: "JetBrains Mono", fontSize: 11 } })),
      animationDurationUpdate: 700 }, true);
  };
  $$("#fr-years button").forEach((b) => b.addEventListener("click", () => setFY(+b.dataset.y!)));
  setFY(2026);
  const fogYears = [2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026];
  const ruYear = (y: number) => D.monthly.ruua.months.reduce((s, m, i) => s + (m.startsWith(String(y)) ? D.monthly.ruua.deaths[i] : 0), 0);
  const fogOpt = (all: boolean) => ({
    legend: { data: ["Located to a region", "No sub-national location"] }, tooltip: { trigger: "axis", valueFormatter: (v: number) => fmt(v) },
    xAxis: { type: "category", data: fogYears.map(String), ...axis() }, yAxis: { type: "value", ...axis() },
    series: [{ name: "Located to a region", type: "bar", stack: "f", data: fogYears.map((y) => Math.round(ruYear(y) * (1 - (mil.fog[y] ?? 0) / 100))), itemStyle: { color: "#4FD1E0" } },
      { name: "No sub-national location", type: "bar", stack: "f", data: fogYears.map((y) => (all ? Math.round(ruYear(y) * (mil.fog[y] ?? 0) / 100) : 0)), itemStyle: { color: "#4A5566" } }],
    animationDurationUpdate: 900,
  });
  mount($("#fog-ch"), fogOpt(false));
  ($("#fog-t") as HTMLInputElement).addEventListener("change", (e) => update($("#fog-ch"), fogOpt((e.target as HTMLInputElement).checked)));
  const att = mil.attrition.filter((a: any) => a.year >= 2022);
  mount($("#att-ch"), { legend: { data: ["Russia (recorded)", "Ukraine (recorded)"] }, grid: { left: 60, right: 50, top: 34, bottom: 30 },
    xAxis: { type: "category", data: att.map((a: any) => String(a.year)), ...axis() }, yAxis: [{ type: "value", ...axis() }, { type: "value", ...axis({ splitLine: { show: false } }), name: "ratio" }],
    series: [{ name: "Russia (recorded)", type: "bar", data: att.map((a: any) => a.russia), itemStyle: { color: "#FF4D5E" } },
      { name: "Ukraine (recorded)", type: "bar", data: att.map((a: any) => a.ukraine), itemStyle: { color: "#4FD1E0" } },
      { name: "ratio", type: "line", yAxisIndex: 1, data: att.map((a: any) => a.ratio), lineStyle: { color: "#F2B33D" }, itemStyle: { color: "#F2B33D" }, label: { show: true, color: "#F2B33D", formatter: (p: any) => p.value + ":1", fontFamily: "JetBrains Mono" } }] });

  // ---- Af-Pak
  const dyM = Object.keys(mil.afpak_dyad).filter((m) => m >= "2025-01").sort();
  mount($("#dy-ch"), { legend: { show: false }, xAxis: { type: "category", data: dyM, ...axis() }, yAxis: { type: "value", ...axis() },
    series: [{ type: "bar", data: dyM.map((m) => ({ value: mil.afpak_dyad[m], itemStyle: { color: m === "2026-03" ? "#FF4D5E" : "#F2B33D" } })), label: { show: true, position: "top", color: "#F5F5F7", fontFamily: "JetBrains Mono" } }] });
  const fata = mil.fata;
  const fataSet = (v: string) => {
    $$("#fata-seg button").forEach((b) => b.classList.toggle("on", b.dataset.v === v));
    update($("#fata-ch"), { legend: { data: v === "raw" ? ["FATA (raw label)", "KP (raw label)"] : ["Khyber Pakhtunkhwa (harmonised)"] },
      xAxis: { type: "category", data: fata.years.map(String), ...axis() }, yAxis: { type: "value", ...axis() },
      series: v === "raw" ? [{ name: "FATA (raw label)", type: "line", data: fata.raw_fata, lineStyle: { color: "#A78BFA", width: 3 }, itemStyle: { color: "#A78BFA" } },
        { name: "KP (raw label)", type: "line", data: fata.raw_kp, lineStyle: { color: "#F2B33D", width: 3 }, itemStyle: { color: "#F2B33D" }, markLine: { symbol: "none", data: [{ xAxis: "2018", label: { formatter: "2018 merger", color: "#FF4D5E" }, lineStyle: { color: "#FF4D5E" } }] } }]
        : [{ name: "Khyber Pakhtunkhwa (harmonised)", type: "line", data: fata.harm_kp, lineStyle: { color: "#2BB673", width: 3 }, itemStyle: { color: "#2BB673" }, areaStyle: { color: "rgba(43,182,115,.12)" } }] }, true);
    $("#fata-note").textContent = v === "raw" ? "Raw labels: FATA appears to collapse and KP to surge in 2018. That is the 2018 merger, not a change in violence." : "Harmonised: FATA folded into KP for all years. The artefact disappears and the real post-2021 rise is visible.";
  };
  $$("#fata-seg button").forEach((b) => b.addEventListener("click", () => fataSet(b.dataset.v!)));
  fataSet("harm");
  const am = regionMap($("#afpak-map"), D.world, [[60, 24], [79, 37.5]]);
  const recolorA = adminLayer(am, D.admin1, (ids) => ids.some((i) => i.startsWith("afpak:")),
    (ids, ev) => { if (!ev) return tip(null); const a = D.areas.areas.find((x) => x.id === ids[0]); if (a) tip(`<b>${a.name}</b> · ${a.iso}<br>P(escalate) Oct 2026: <b>${pct(a.p)}</b>`, ev); });
  recolorA((ids) => { const a = D.areas.areas.find((x) => x.id === ids[0]); return a ? ramp(Math.sqrt(a.p / 0.3)) : "#1A2638"; });
  S.afpak.top.forEach((t) => { const a = D.areas.areas.find((x) => x.c === "afpak" && x.name.startsWith(t.name)); if (a?.lon != null) pulse(am, a.lon, a.lat!, "#FF4D5E", `${t.name} ${Math.round(t.p * 100)}%`); });

  // ---- Media (linked scatters)
  const pts = med.points.filter((p: any) => p.d > 0 && p.e > 0 && p.s > 0);
  const scat = (x: "e" | "d") => ({ legend: { data: CASES.map((c) => CASE_NAME[c]) }, tooltip: { trigger: "item", formatter: (p: any) => `${CASE_NAME[p.data[3]]} ${p.data[2]}<br>${x === "e" ? "events" : "deaths"} ${fmt(p.data[0])} · refs ${fmt(p.data[1])}` },
    xAxis: { type: "log", ...axis(), name: x === "e" ? "events" : "deaths", nameLocation: "middle", nameGap: 28 }, yAxis: { type: "log", ...axis(), name: "media references" },
    series: CASES.map((c) => ({ name: CASE_NAME[c], type: "scatter", symbolSize: 6, itemStyle: { color: CASE_COLOR[c], opacity: 0.7 }, emphasis: { scale: 2.6, itemStyle: { opacity: 1, borderColor: "#fff", borderWidth: 2 } },
      data: pts.filter((p: any) => p.c === c).map((p: any) => [x === "e" ? p.e : p.d, p.s, p.m, c]) })) });
  const ce = mount($("#agi-e"), scat("e")), cd = mount($("#agi-d"), scat("d"));
  const link = (a: any, b: any) => { a.on("mouseover", (p: any) => b.dispatchAction({ type: "highlight", seriesIndex: p.seriesIndex, dataIndex: p.dataIndex })); a.on("mouseout", (p: any) => b.dispatchAction({ type: "downplay", seriesIndex: p.seriesIndex, dataIndex: p.dataIndex })); };
  link(ce, cd); link(cd, ce);

  // ---- GDELT vs UCDP
  const gdDraw = (c: string) => {
    const w = gd.weekly[c];
    $$("#gd-seg button").forEach((b) => b.classList.toggle("on", b.dataset.c === c));
    const after = w.weeks.find((x: string) => x >= "2026-09-28");
    update($("#gd-ch"), { grid: { left: 56, right: 64, top: 56, bottom: 36 }, legend: { data: ["UCDP deaths (weekly)", "GDELT violent events / day"], textStyle: { color: "#AEB8C6" } }, tooltip: { trigger: "axis" },
      xAxis: { type: "category", data: w.weeks, ...axis() },
      yAxis: [{ type: "value", ...axis(), name: "UCDP deaths" }, { type: "value", ...axis(), name: "GDELT / day", splitLine: { show: false } }],
      series: [{ name: "UCDP deaths (weekly)", type: "bar", data: w.ucdp, itemStyle: { color: CASE_COLOR[c as keyof typeof CASE_COLOR], opacity: 0.6 },
        markArea: { itemStyle: { color: "rgba(242,179,61,.10)" }, data: after ? [[{ xAxis: after }, { xAxis: w.weeks[w.weeks.length - 1] }]] : [] } },
        { name: "GDELT violent events / day", type: "line", yAxisIndex: 1, data: w.v, smooth: true, showSymbol: false, lineStyle: { color: "#F2B33D", width: 2.5 }, itemStyle: { color: "#F2B33D" } }] }, true);
  };
  $$("#gd-seg button").forEach((b) => b.addEventListener("click", () => gdDraw(b.dataset.c!)));
  gdDraw("usir");

  // ---- Displacement waffle
  const nRef = Math.round(dsp.ukr.refugees / 50000), nIdp = Math.round(dsp.ukr.idps / 50000);
  $("#waffle").innerHTML = Array.from({ length: nRef + nIdp }, (_, i) => `<i data-i="${i}"></i>`).join("");
  const wfSet = (v: string) => {
    $$("#wf-seg button").forEach((b) => b.classList.toggle("on", b.dataset.v === v));
    const nWc = Math.round(nRef * dsp.ukr.wc);
    $$("#waffle i").forEach((d, i) => { d.style.background = v === "type" ? (i < nRef ? "#A78BFA" : "#4FD1E0") : i < nRef ? (i < nWc ? "#FF4D5E" : "#4A5566") : "#1C2A3E"; d.style.transitionDelay = `${(i % 18) * 12}ms`; });
    $("#wf-note").innerHTML = v === "type" ? `<span style="color:#A78BFA">■</span> ${fmtM(dsp.ukr.refugees)} refugees + <span style="color:#4FD1E0">■</span> ${fmtM(dsp.ukr.idps)} internally displaced = <b>${fmtM(dsp.ukr.total)}</b> ${tag("data")}`
      : `<span style="color:#FF4D5E">■</span> ${Math.round(dsp.ukr.wc * 100)}% of refugees with recorded sex and age are women or children ${tag("data")}`;
  };
  $$("#wf-seg button").forEach((b) => b.addEventListener("click", () => wfSet(b.dataset.v!)));
  wfSet("type");
  mount($("#pse-ch"), { legend: { show: false }, grid: { left: 150, right: 60, top: 10, bottom: 24 }, tooltip: { trigger: "item" },
    xAxis: { type: "value", ...axis(), axisLabel: { formatter: (v: number) => fmtM(v), color: "#9AA6B6" } }, yAxis: { type: "category", data: ["UNRWA registered", "IDMC IDPs"], ...axis() },
    series: [{ type: "bar", data: [{ value: dsp.pse.unrwa, itemStyle: { color: "#A78BFA" } }, { value: dsp.pse.idmc, itemStyle: { color: "#4FD1E0" } }], label: { show: true, position: "right", formatter: (p: any) => fmtM(p.value), color: "#F5F5F7", fontFamily: "JetBrains Mono" }, barWidth: "50%" }] });

  // ---- Prediction
  let tr: "A" | "B" = "A";
  const plI = $("#pl") as HTMLInputElement;
  const plDraw = () => {
    const u = +plI.value;
    $("#pl-o").textContent = u === 0 ? "start" : new Date(2026, u - 1, 1).toLocaleString("en-GB", { month: "short", year: "numeric" });
    holdoutChart($("#pl-ru"), D, "ruua", tr, u); holdoutChart($("#pl-af"), D, "afpak", tr, u);
    let ins = 0, n = 0;
    for (const h of D.holdout) h.months.forEach((_: string, j: number) => { if (j < u) { n++; if (h.actual[j] >= h.lo[j] && h.actual[j] <= h.hi[j]) ins++; } });
    $("#cov-v").textContent = n ? Math.round((ins / n) * 100) + "%" : "–";
    $("#cov-s").textContent = `${ins} of ${n} conflict-months · target 80%`;
  };
  $$("#pl-tr button").forEach((b) => b.addEventListener("click", () => { tr = b.dataset.t as any; $$("#pl-tr button").forEach((x) => x.classList.toggle("on", x === b)); plDraw(); }));
  plI.addEventListener("input", plDraw);
  let playing: any = null;
  $("#pl-play").addEventListener("click", () => { if (playing) { clearInterval(playing); playing = null; return; } plI.value = "0"; plDraw(); playing = setInterval(() => { plI.value = String(+plI.value + 1); plDraw(); if (+plI.value >= 9) { clearInterval(playing); playing = null; } }, 700); });
  ScrollTrigger.create({ trigger: "#prediction", start: "top 70%", once: true, onEnter: () => { if (!REDUCE) $("#pl-play").click(); else plDraw(); } });
  plDraw();
  const lbNote: Record<string, string> = { A_bt: "Back-test 2022–25: the ensemble was selected here, before 2026 was opened.", A_hold: "2026 holdout, 1 month ahead: the ensemble stays near the top. SARIMA edges it by 0.001.",
    B_bt: "Back-test, 1–9 months ahead.", B_hold: "Honesty note: on 2026 Track B (1–9 months), SARIMA and the bottom-up LightGBM beat the ensemble." };
  const lbSet = (k: any) => { $$("#lb-seg button").forEach((b) => b.classList.toggle("on", b.dataset.k === k)); leaderboard($("#lb-ch"), D, k); $("#lb-note").innerHTML = (k === "B_hold" ? tag("caveat", "TRACK B") + " " : "") + lbNote[k]; };
  $$("#lb-seg button").forEach((b) => b.addEventListener("click", () => lbSet(b.dataset.k)));
  lbSet("A_hold");
  const abl = fc.ablation;
  mount($("#abl-ch"), { legend: { data: ["Track A", "Track B"] }, grid: { left: 210, right: 20, top: 30, bottom: 24 }, tooltip: { trigger: "axis" },
    xAxis: { type: "value", ...axis(), min: 0 }, yAxis: { type: "category", data: abl.map((a: any) => a.variant.replace(/^[A-Z]\.\s*/, "").slice(0, 34)), ...axis({ axisLabel: { color: "#F5F5F7", fontSize: 12 } }) },
    series: [{ name: "Track A", type: "bar", data: abl.map((a: any) => a.A), itemStyle: { color: "#F2B33D" } }, { name: "Track B", type: "bar", data: abl.map((a: any) => a.B), itemStyle: { color: "#2B6F86" } }] });
  const sh = [...fc.shap.forecast].slice(0, 8).reverse();
  mount($("#shap-ch"), { legend: { show: false }, grid: { left: 260, right: 30, top: 10, bottom: 24 }, tooltip: { trigger: "item" },
    xAxis: { type: "value", ...axis() }, yAxis: { type: "category", data: sh.map((s: any) => s.label), ...axis({ axisLabel: { color: "#F5F5F7", fontSize: 13 } }) },
    series: [{ type: "bar", data: sh.map((s: any) => s.v), itemStyle: { color: "#4FD1E0", borderRadius: [0, 4, 4, 0] } }] });

  // ---- Warning / decision room
  const W = warningPanel($("#ew-box"), D, { month: "2026-03", thr: 0.15 });
  const WI = whatIf($("#wi-box"), D);
  scorecardLab($("#lab-box"), D);

  // ---- Recs, DQ table
  $$(".rec").forEach((r) => { const f = () => r.classList.toggle("open"); r.addEventListener("click", (e) => { if ((e.target as HTMLElement).tagName !== "A") f(); }); r.addEventListener("keydown", (e) => { if (e.key === "Enter") f(); }); });
  let dqSort = { k: "id", asc: true };
  const dqDraw = () => {
    const rows = [...D.dq].sort((a, b) => (a[dqSort.k] > b[dqSort.k] ? 1 : -1) * (dqSort.asc ? 1 : -1));
    const cols = [["id", "ID"], ["table", "Table"], ["check", "Check"], ["category", "Category"], ["rows_affected", "Rows"], ["action", "Action"]];
    $("#dq-t").innerHTML = `<table class="t small"><tr>${cols.map(([k, l]) => `<th data-k="${k}">${l}${dqSort.k === k ? (dqSort.asc ? " ▲" : " ▼") : ""}</th>`).join("")}</tr>${rows.map((r) => `<tr>${cols.map(([k]) => `<td${k === "rows_affected" ? ' class="num"' : ""}>${k === "rows_affected" ? fmt(r[k]) : r[k] ?? ""}</td>`).join("")}</tr>`).join("")}</table>`;
    $$("#dq-t th").forEach((th) => th.addEventListener("click", () => { dqSort = { k: th.dataset.k!, asc: dqSort.k === th.dataset.k ? !dqSort.asc : true }; dqDraw(); }));
  };
  dqDraw();
  $("#dq-csv").addEventListener("click", () => csv("data_quality_log.csv", D.dq));
  const QA = qaDrawer(F);
  $("#qa-open").addEventListener("click", () => QA.open());

  // ---- Reveal + counters + nav dots
  if (!REDUCE) gsap.utils.toArray<HTMLElement>(".reveal").forEach((e) => gsap.to(e, { opacity: 1, y: 0, duration: 0.9, ease: "power3.out", scrollTrigger: { trigger: e, start: "top 88%" } }));
  else document.documentElement.classList.add("noanim");
  countUp();
  const dots = $$(".dots a");
  CHAPTERS.forEach(([id], i) => ScrollTrigger.create({ trigger: "#" + id, start: "top 50%", end: "bottom 50%", onToggle: (s) => { if (s.isActive) { dots.forEach((d, j) => d.classList.toggle("on", j === i)); } } }));

  // ---- Deep links: #whatif?c=afpak&shock=30&m=3, #warning?month=2026-03&thr=0.15
  const applyHash = () => {
    const h = decodeURIComponent(location.hash.slice(1)); if (!h) return;
    const [id, q] = h.split("?"); const p = new URLSearchParams(q ?? "");
    if (id === "whatif" && q) WI.set(p.get("c") ?? "afpak", +(p.get("shock") ?? 30), +(p.get("m") ?? 3));
    if (id === "warning" && q) W.set(p.get("month") ?? undefined, p.get("thr") ? +p.get("thr")! : undefined, (p.get("mode") as any) ?? undefined);
    const t = document.getElementById(id);
    if (t && t.closest(".ch.deep") && document.documentElement.classList.contains("deep-off")) document.getElementById("deep-t")?.click();
    if (t) setTimeout(() => t.scrollIntoView({ behavior: REDUCE ? "auto" : "smooth" }), 50);
  };
  addEventListener("hashchange", applyHash);
  // ---- Progressive disclosure. Everything is laid out once at full size (so maps and charts measure correctly),
  //      then supporting material is folded away: seven "deep" chapters, and second-level blocks inside the briefing.
  const root = document.documentElement;
  const refresh = () => { ScrollTrigger.refresh(); resizeAll(); };
  const setDeep = (on: boolean) => { root.classList.toggle("deep-off", !on); const b = $("#deep-t"); b.textContent = `FULL EVIDENCE · ${on ? "ON" : "OFF"}`; b.classList.toggle("on", on); b.setAttribute("aria-pressed", String(on)); refresh(); };
  $("#deep-t").addEventListener("click", () => setDeep(root.classList.contains("deep-off")));
  addEventListener("keydown", (e) => { const tg = (e.target as HTMLElement).tagName; if (tg === "INPUT" || tg === "SELECT" || tg === "TEXTAREA" || e.metaKey || e.ctrlKey) return; if (e.key === "e" || e.key === "E") setDeep(root.classList.contains("deep-off")); });
  const L2: Record<string, () => (Element | null | undefined)[]> = {
    bluf: () => [$$("#bluf .wrap > .grid.g4")[1]],
    india: () => { const k = $$("#india .grid.g2 > .kpi"); return [k[2], k[4], k[5], $("#india .grid.g2 + p")]; },
    afpak: () => { const p = $$("#afpak .grid.g2 > .panel")[0]; return [$$(".ph", p)[1], $("#fata-ch"), $("#fata-note")]; },
    front: () => [$$("#front .grid.g2 > .panel")[1]],
    prediction: () => [$$("#prediction .grid.g4 > .kpi")[3], $("#prediction .wrap > .grid.g2"), $("#prediction .wrap > p.small")],
    warning: () => [$$("#warning .grid.g4 > .kpi")[3]],
    recs: () => [$("#recs .wrap > .panel")],
  };
  const foldL2 = () => Object.entries(L2).forEach(([id, pick]) => {
    const sec = document.getElementById(id); if (!sec) return;
    const els = pick().filter(Boolean) as HTMLElement[]; if (!els.length) return;
    els.forEach((e) => e.classList.add("l2")); sec.classList.add("l2-closed");
    const b = document.createElement("button"); b.className = "btn l2btn no-print"; b.setAttribute("aria-expanded", "false"); b.textContent = "SHOW EVIDENCE ▾";
    b.addEventListener("click", () => { const open = sec.classList.toggle("l2-closed") === false; b.textContent = open ? "HIDE EVIDENCE ▴" : "SHOW EVIDENCE ▾"; b.setAttribute("aria-expanded", String(open));
      if (open && !REDUCE) gsap.fromTo(els, { opacity: 0, y: 12 }, { opacity: 1, y: 0, duration: 0.3, stagger: 0.05, ease: "power2.out", clearProps: "transform,opacity" });
      refresh(); });
    sec.querySelector("h2.title")?.insertAdjacentElement("afterend", b);
  });
  ScrollTrigger.create({ trigger: "#main", start: "top top", end: "bottom bottom", onUpdate: (st) => { $("#prog").style.transform = `scaleX(${st.progress})`; } });
  setTimeout(() => {
    const h = decodeURIComponent(location.hash.slice(1)).split("?")[0];
    CHAPTERS.forEach(([id]) => { if (DEEP.has(id)) document.getElementById(id)?.classList.add("deep"); });
    foldL2(); setDeep(DEEP.has(h) || h === "whatif" || h === "lab");
    applyHash(); resizeAll();
  }, 300);

  presenter(CHAPTERS.map((c) => c[0]), F);
}
