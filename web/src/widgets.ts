// Interactive engines shared by the story site and the console.
import { type Data, type Score, CASES, CASE_COLOR, CASE_SHORT, CASE_NAME, RAG_COLOR, fmt, pct } from "./data";
import { rate, DOCTRINE, type Rules } from "./rules";
import { mount, update, axis, csv } from "./charts";
import { regionMap, adminLayer, ramp, tip, el, pulse } from "./maps";

export const $ = <T extends HTMLElement = HTMLElement>(s: string, r: ParentNode = document) => r.querySelector(s) as T;
export const $$ = <T extends HTMLElement = HTMLElement>(s: string, r: ParentNode = document) => Array.from(r.querySelectorAll(s)) as T[];
export const tag = (k: "data" | "domain" | "caveat", t?: string) => `<span class="tag ${k}">${t ?? k.toUpperCase()}</span>`;
export const info = (text: string) => `<span class="info" tabindex="0" role="button" aria-label="Explain this chart" data-info="${text.replace(/"/g, "&quot;")}">i</span>`;

document.addEventListener("click", (e) => {
  const t = (e.target as HTMLElement).closest(".info") as HTMLElement | null;
  $$(".pop").forEach((p) => p.remove());
  if (t) { const p = document.createElement("div"); p.className = "pop"; p.textContent = t.dataset.info!; t.appendChild(p); e.stopPropagation(); }
});

// ---------------------------------------------------------------------------
// RAG cards with "Why this rating?" flip side
// ---------------------------------------------------------------------------
export function ragCards(box: HTMLElement, D: Data, scores?: (s: Score) => ReturnType<typeof rate>) {
  const R = DOCTRINE(D.facts);
  box.innerHTML = D.facts.scorecard.map((s: Score) => {
    const r = scores ? scores(s) : rate(s, R);
    const col = RAG_COLOR[r.rating];
    const row = (l: string, v: number, why: string) => `<div class="ptsrow"><span>${l} <span class="muted small">${why}</span></span><b style="color:${v > 0 ? col : "var(--tx2)"}">${v > 0 ? "+" : ""}${v}</b></div>`;
    return `<div class="rag" tabindex="0" role="button" aria-label="${s.name}: ${r.rating}. Press to see why." data-id="${s.id}">
      <div class="inner">
        <div class="face" style="box-shadow: inset 0 3px 0 ${col}, 0 0 40px ${col}22">
          <div class="name"><span class="status" style="background:${col};box-shadow:0 0 10px ${col}"></span>${s.name}</div>
          <div class="rating" style="color:${col}">${r.rating}</div>
          <div class="fc">${fmt(Math.round(r.fc))} <span class="muted small mono">deaths · ${s.month}</span></div>
          <div class="meta mono">80% band ${fmt(s.lo)}–${fmt(s.hi)}<br>trend ${r.trendPct >= 0 ? "+" : ""}${Math.round(r.trendPct)}% vs 6 mo · ${r.hot} hotspot${r.hot === 1 ? "" : "s"}</div>
          <div class="meta small">Watch: ${s.top.map((t) => `${t.name} ${Math.round(t.p * 100)}%`).join(" · ")}</div>
          <div class="hint">▸ WHY THIS RATING? · ${r.points} PTS</div>
        </div>
        <div class="face back">
          <div class="name">${s.short} · points breakdown</div>
          ${row("Intensity", r.pts.intensity, "forecast ≥1,000→2, ≥100→1")}
          ${row("Trend", r.pts.trend, "≥+20%→+1, ≤−20%→−1")}
          ${row("Hotspots", r.pts.hotspots, "areas P≥15%: ≥3→2, ≥1→1")}
          ${row("Spread", r.pts.spread, `${s.countries_now} vs ${s.countries_prev} countries`)}
          ${row("Volatility", r.pts.volatility, "a ≥1,000 month in last year")}
          <div class="ptsrow" style="border:0"><span>TOTAL</span><b style="color:${col}">${r.points} → ${r.rating}</b></div>
          <div class="meta small">${r.fc >= R.red_fc ? "Auto-RED: forecast ≥1,000 deaths a month." : "RED ≥5 pts or ≥1,000 forecast · AMBER 2–4 · GREEN ≤1"}</div>
          <div class="hint">▸ FLIP BACK</div>
        </div>
      </div></div>`;
  }).join("");
  $$(".rag", box).forEach((c) => {
    const f = () => c.classList.toggle("flip");
    c.addEventListener("click", f); c.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); f(); } });
  });
}

// ---------------------------------------------------------------------------
// What-if simulator (exact Python engine, precomputed grid)
// ---------------------------------------------------------------------------
export function whatIf(box: HTMLElement, D: Data, init = { c: "afpak", shock: 30, k: 3 }) {
  const W = D.whatif;
  box.innerHTML = `
  <div class="split" style="align-items:start">
    <div class="panel hud">
      <div class="ctl"><label>Conflict</label><div class="seg" id="wi-c">${CASES.map((c) => `<button data-c="${c}">${CASE_SHORT[c]}</button>`).join("")}</div></div>
      <div class="ctl"><label>Shock to recent violence <output id="wi-so"></output></label><input type="range" id="wi-s" min="-50" max="100" step="10" aria-label="Shock percent"></div>
      <div class="ctl"><label>Applied to last N months <output id="wi-ko"></output></label><input type="range" id="wi-k" min="1" max="6" step="1" aria-label="Months shocked"></div>
      <div id="wi-cards" class="grid g3" style="margin:14px 0"></div>
      <div id="wi-rag" class="sowhat"></div>
      <p class="small muted" style="margin-top:12px">${W.note}</p>
    </div>
    <div class="panel"><div class="ph"><span class="t">Forecast before vs after the shock</span>${info("Grey: the last 12 months of recorded deaths (dashed where the shock is applied). Amber: the model's baseline forecast for Oct–Dec 2026. Red: the forecast if recent violence had been different. The shaded band is the 80% range.")}</div><div class="chart tall" id="wi-ch"></div></div>
  </div>`;
  const st = { ...init };
  const sI = $("#wi-s", box) as HTMLInputElement, kI = $("#wi-k", box) as HTMLInputElement;
  sI.value = String(st.shock); kI.value = String(st.k);
  const R = DOCTRINE(D.facts);
  function render() {
    $$("#wi-c button", box).forEach((b) => b.classList.toggle("on", b.dataset.c === st.c));
    $("#wi-so", box).textContent = `${st.shock >= 0 ? "+" : ""}${st.shock}%`;
    $("#wi-ko", box).textContent = `${st.k} mo`;
    const base = W.grid[st.c][`0|${st.k}`] as number[][], scen = W.grid[st.c][`${st.shock}|${st.k}`] as number[][];
    const hist = W.history[st.c] as { m: string; d: number }[];
    const shocked = hist.map((h, i) => (i >= hist.length - st.k ? h.d * (1 + st.shock / 100) : h.d));
    $("#wi-cards", box).innerHTML = W.months.map((m: string, i: number) => {
      const ch = scen[i][0] / Math.max(base[i][0], 1) - 1;
      return `<div class="kpi"><span class="l">${m}</span><span class="v" style="font-size:34px;color:${scen[i][0] > base[i][0] ? "var(--red)" : scen[i][0] < base[i][0] ? "var(--green)" : "var(--tx)"}">${fmt(scen[i][0])}</span>
        <span class="s">baseline ${fmt(base[i][0])} (${ch >= 0 ? "+" : ""}${Math.round(ch * 100)}%)<br>80%: ${fmt(scen[i][1])}–${fmt(scen[i][2])}</span></div>`;
    }).join("");
    const s: Score = D.facts.scorecard.find((x: Score) => x.id === st.c);
    const last6 = shocked.slice(-6).reduce((a, b) => a + b, 0) / 6;
    const s2 = { ...s, forecast: scen[0][0], last6, peak12: Math.max(...shocked) };
    const r0 = rate(s, R), r1 = rate(s2, R);
    $("#wi-rag", box).innerHTML = `<b>RAG</b> ${CASE_NAME[st.c]}: <span style="color:${RAG_COLOR[r0.rating]}">${r0.rating}</span> → <span style="color:${RAG_COLOR[r1.rating]};font-weight:700">${r1.rating}</span> (${r1.points} pts).
      ${st.k <= 3 && st.shock > 0 ? "Short surges damp: the model expects most of a brief spike to revert." : st.k >= 5 && st.shock > 0 ? "Sustained surges carry through into the forecast." : ""}`;
    const xs = [...hist.map((h) => h.m), "2026-10", "2026-11", "2026-12"];
    const pad = (a: (number | null)[]) => [...Array(hist.length - 1).fill(null), hist[hist.length - 1].d, ...a];
    const padS = (a: (number | null)[]) => [...Array(hist.length - 1).fill(null), shocked[shocked.length - 1], ...a];
    update($("#wi-ch", box), {
      legend: { data: ["Recorded", "Shocked history", "Baseline forecast", "Scenario forecast"] },
      xAxis: { type: "category", data: xs, ...axis() }, yAxis: { type: "value", ...axis(), name: "deaths / month" },
      series: [
        { name: "band-lo", type: "line", data: [...Array(hist.length).fill(null), ...scen.map((v) => v[1])], stack: "b", lineStyle: { opacity: 0 }, symbol: "none", tooltip: { show: false } },
        { name: "band", type: "line", data: [...Array(hist.length).fill(null), ...scen.map((v) => v[2] - v[1])], stack: "b", lineStyle: { opacity: 0 }, symbol: "none", areaStyle: { color: "rgba(255,77,94,.13)" }, tooltip: { show: false } },
        { name: "Recorded", type: "line", data: [...hist.map((h) => h.d), null, null, null], lineStyle: { color: "#9AA6B6", width: 2 }, itemStyle: { color: "#9AA6B6" }, symbolSize: 6 },
        { name: "Shocked history", type: "line", data: [...shocked.map((v, i) => (i >= hist.length - st.k - 1 ? Math.round(v) : null)), null, null, null], lineStyle: { color: "#FF4D5E", type: "dashed", width: 2 }, itemStyle: { color: "#FF4D5E" }, symbolSize: 6 },
        { name: "Baseline forecast", type: "line", data: pad(base.map((v) => v[0])), lineStyle: { color: "#F2B33D", width: 3 }, itemStyle: { color: "#F2B33D" }, symbolSize: 8 },
        { name: "Scenario forecast", type: "line", data: padS(scen.map((v) => v[0])), lineStyle: { color: "#FF4D5E", width: 3 }, itemStyle: { color: "#FF4D5E" }, symbolSize: 9 },
      ],
    }, true);
    box.dispatchEvent(new CustomEvent("state", { detail: { ...st }, bubbles: true }));
  }
  $$("#wi-c button", box).forEach((b) => b.addEventListener("click", () => { st.c = b.dataset.c!; render(); }));
  sI.addEventListener("input", () => { st.shock = +sI.value; render(); });
  kI.addEventListener("input", () => { st.k = +kI.value; render(); });
  render();
  return { set(c: string, shock: number, k: number) { Object.assign(st, { c, shock, k }); sI.value = String(shock); kI.value = String(k); render(); } };
}

// ---------------------------------------------------------------------------
// Scorecard lab
// ---------------------------------------------------------------------------
export function scorecardLab(box: HTMLElement, D: Data) {
  const R0 = DOCTRINE(D.facts);
  let R: Rules = { ...R0 };
  let fcScale = 1;
  const S = [
    ["int_hi", "Intensity: 2 pts at forecast ≥", 200, 5000, 100, ""], ["int_lo", "Intensity: 1 pt at forecast ≥", 10, 1000, 10, ""],
    ["trend_up", "Trend +1 at ≥", 5, 100, 5, "%"], ["trend_dn", "Trend −1 at ≤", -100, -5, 5, "%"],
    ["hot_p", "Hotspot = area with P(escalate) ≥", 0.05, 0.4, 0.01, "p"], ["hot_hi", "Hotspots: 2 pts at ≥", 1, 10, 1, ""],
    ["vol", "Volatility: a month ≥", 100, 5000, 100, ""], ["red_fc", "Auto-RED at forecast ≥", 200, 10000, 100, ""],
    ["red_pts", "RED at points ≥", 3, 7, 1, ""], ["amber_pts", "AMBER at points ≥", 1, 4, 1, ""],
  ] as const;
  box.innerHTML = `<div class="split" style="align-items:start">
    <div class="panel hud">
      ${S.map(([k, l, mn, mx, stp, u]) => `<div class="ctl"><label>${l} <output data-o="${k}"></output></label><input type="range" data-k="${k}" min="${mn}" max="${mx}" step="${stp}" aria-label="${l}"></div>`).join("")}
      <div class="ctl"><label>Scale all forecasts <output id="lab-fo"></output></label><input type="range" id="lab-f" min="0.5" max="2" step="0.05" value="1" aria-label="Forecast scale"></div>
      <div style="display:flex;gap:14px;flex-wrap:wrap;margin:6px 0 12px">
        <label class="toggle"><input type="checkbox" id="lab-sp" checked><span class="sw"></span>SPREAD RULE</label>
        <label class="toggle"><input type="checkbox" id="lab-vo" checked><span class="sw"></span>VOLATILITY RULE</label>
      </div>
      <button class="btn primary" id="lab-reset">↺ Reset to doctrine</button>
    </div>
    <div><div class="grid g2" id="lab-cards" style="--h:330px"></div><div class="panel" style="margin-top:16px"><div class="ph"><span class="t">What changed</span></div><div id="lab-diff"></div></div></div>
  </div>`;
  const inputs = $$<HTMLInputElement>("input[data-k]", box);
  const sync = () => inputs.forEach((i) => { i.value = String((R as any)[i.dataset.k!]); });
  sync();
  let prev: Record<string, string> = {};
  function render() {
    inputs.forEach((i) => { const v = (R as any)[i.dataset.k!]; $(`[data-o="${i.dataset.k}"]`, box).textContent = i.dataset.k === "hot_p" ? pct(v) : i.dataset.k!.startsWith("trend") ? v + "%" : fmt(v); });
    $("#lab-fo", box).textContent = `×${fcScale.toFixed(2)}`;
    const res: Record<string, ReturnType<typeof rate>> = {};
    ragCards($("#lab-cards", box), D, (s) => (res[s.id] = rate(s, R, fcScale)));
    const diff = D.facts.scorecard.map((s: Score) => {
      const r = res[s.id], changed = r.rating !== s.rating;
      return `<div class="ptsrow"><span>${s.short}: <span style="color:${RAG_COLOR[s.rating]}">${s.rating}</span> → <b style="color:${RAG_COLOR[r.rating]}">${r.rating}</b> ${changed ? "<span class='tag caveat'>CHANGED</span>" : "<span class='muted small'>held</span>"}</span>
        <span class="muted small">int ${r.pts.intensity} · trend ${r.pts.trend} · hot ${r.pts.hotspots} · spread ${r.pts.spread} · vol ${r.pts.volatility} = ${r.points}${r.fc >= R.red_fc ? " · auto-RED" : ""}</span></div>`;
    }).join("");
    $("#lab-diff", box).innerHTML = diff;
    $$(".rag", box).forEach((c) => { const id = c.dataset.id!; if (prev[id] && prev[id] !== res[id].rating) c.animate([{ transform: "scale(.92)", filter: "brightness(2)" }, { transform: "scale(1)", filter: "none" }], { duration: 600, easing: "cubic-bezier(.2,.7,.2,1)" }); prev[id] = res[id].rating; });
  }
  inputs.forEach((i) => i.addEventListener("input", () => { (R as any)[i.dataset.k!] = +i.value; render(); }));
  ($("#lab-f", box) as HTMLInputElement).addEventListener("input", (e) => { fcScale = +(e.target as HTMLInputElement).value; render(); });
  ($("#lab-sp", box) as HTMLInputElement).addEventListener("change", (e) => { R.use_spread = (e.target as HTMLInputElement).checked; render(); });
  ($("#lab-vo", box) as HTMLInputElement).addEventListener("change", (e) => { R.use_vol = (e.target as HTMLInputElement).checked; render(); });
  $("#lab-reset", box).addEventListener("click", () => { R = { ...R0 }; fcScale = 1; ($("#lab-f", box) as HTMLInputElement).value = "1";
    ($("#lab-sp", box) as HTMLInputElement).checked = true; ($("#lab-vo", box) as HTMLInputElement).checked = true; sync(); render(); });
  render();
}

// ---------------------------------------------------------------------------
// Early warning: map + replay + threshold
// ---------------------------------------------------------------------------
export function ewStats(D: Data, thr: number) {
  const A = D.areas.areas;
  let tp = 0, fp = 0, fn = 0, tn = 0;
  for (const a of A) a.pm.forEach((p, i) => { const e = a.esc[i]; if (p == null || e == null) return; const f = p >= thr; if (f && e) tp++; else if (f) fp++; else if (e) fn++; else tn++; });
  return { tp, fp, fn, tn, prec: tp / Math.max(tp + fp, 1), rec: tp / Math.max(tp + fn, 1), fpr: fp / Math.max(fp + tn, 1), months: D.areas.ew_months.length };
}
export function rocCurve(D: Data) {
  const pairs: [number, number][] = [];
  for (const a of D.areas.areas) a.pm.forEach((p, i) => { if (p != null && a.esc[i] != null) pairs.push([p, a.esc[i]!]); });
  pairs.sort((x, y) => y[0] - x[0]);
  const P = pairs.filter((p) => p[1]).length, N = pairs.length - P;
  let tp = 0, fp = 0, auc = 0, prevF = 0; const pts: [number, number][] = [[0, 0]];
  for (const [, e] of pairs) { if (e) tp++; else { fp++; auc += tp / P / N; } pts.push([fp / N, tp / P]); prevF = fp; }
  return { pts, auc };
}
export const aname = (a: any) => (a.unloc ? `${a.iso} · no sub-national location` : a.name);
export function topN(D: Data, mi: number, n = 10) {
  return D.areas.areas.filter((a) => a.pm[mi] != null).sort((a, b) => (b.pm[mi]! - a.pm[mi]!)).slice(0, n);
}

export function warningPanel(box: HTMLElement, D: Data, opts: { month?: string; thr?: number; onArea?: (id: string) => void } = {}) {
  const M = D.areas.ew_months;
  const st = { mi: Math.max(0, M.indexOf(opts.month ?? "2026-03")), thr: opts.thr ?? 0.15, mode: "replay" as "replay" | "oct" };
  box.innerHTML = `
  <div class="split rev" style="align-items:start">
    <div class="panel" style="padding:12px"><div class="ph"><span class="t" id="ew-title"></span>
      <div class="seg" id="ew-mode"><button data-m="replay">REPLAY 2026</button><button data-m="oct">OCT 2026 LIVE</button></div></div>
      <div class="mapbox" id="ew-map" style="height:520px"></div>
      <div class="ctl" style="margin-top:10px" id="ew-mctl"><label>Month <output id="ew-mo"></output></label><input type="range" id="ew-m" min="0" max="${M.length - 1}" step="1" aria-label="Replay month"></div>
    </div>
    <div>
      <div class="panel hud"><div class="ph"><span class="t">Top-10 watch-list</span><button class="btn small" id="ew-csv">CSV</button></div><div id="ew-list"></div><div id="ew-hits" class="sowhat" style="margin-top:10px"></div></div>
      <div class="panel" style="margin-top:16px"><div class="ph"><span class="t">Alert threshold</span>${info("Every area-month in 2026 with a probability above the threshold raises an alert. A lower threshold catches more escalations (recall) but raises more false alarms. The dot on the ROC curve shows where the threshold sits.")}</div>
        <div class="ctl"><label>Alert if P(escalate) ≥ <output id="ew-to"></output></label><input type="range" id="ew-t" min="0.02" max="0.5" step="0.01" aria-label="Alert threshold"></div>
        <div class="grid g3" id="ew-k"></div><div class="chart short" id="ew-roc" style="height:250px"></div></div>
    </div>
  </div>`;
  const m = regionMap($("#ew-map", box), D.world, [[26, 10], [75, 54]]);
  const byId = new Map(D.areas.areas.map((a) => [a.id, a]));
  const val = (a: any) => (st.mode === "oct" ? a.p : a.pm[st.mi] ?? 0);
  const recolor = adminLayer(m, D.admin1, () => true,
    (ids, ev) => { if (!ev) return tip(null); const a = byId.get(ids[0]); if (!a) return; tip(`<b>${a.name}</b> · ${a.iso}<br>${CASE_SHORT[a.c]}<br>P(escalate): <b>${pct(val(a), 1)}</b>${st.mode === "replay" && a.esc[st.mi] ? "<br><span style='color:#FF4D5E'>● ESCALATED</span>" : ""}`, ev); },
    (ids) => opts.onArea?.(ids[0]));
  const pointG = el("g", {}, m.top);
  const sI = $("#ew-m", box) as HTMLInputElement, tI = $("#ew-t", box) as HTMLInputElement;
  sI.value = String(st.mi); tI.value = String(st.thr);
  const roc = rocCurve(D);
  function render() {
    $$("#ew-mode button", box).forEach((b) => b.classList.toggle("on", b.dataset.m === st.mode));
    ($("#ew-mctl", box)).style.visibility = st.mode === "replay" ? "visible" : "hidden";
    const mLabel = st.mode === "oct" ? "Oct 2026 (forecast)" : new Date(M[st.mi] + "-01").toLocaleString("en-GB", { month: "short", year: "numeric" });
    $("#ew-title", box).textContent = `P(escalate) · ${mLabel}`;
    $("#ew-mo", box).textContent = mLabel;
    recolor((ids) => { const vs = ids.map((i) => byId.get(i)).filter(Boolean).map((a) => val(a)); const v = Math.max(0, ...vs); return ramp(Math.sqrt(v / 0.35)); });
    pointG.innerHTML = "";
    const top = st.mode === "oct" ? [...D.areas.areas].filter((a) => !a.unloc).sort((a, b) => b.p - a.p).slice(0, 10) : topN(D, st.mi).filter(Boolean);
    top.forEach((a, i) => {
      if (a.lon == null) return;
      const xy = m.proj([a.lon, a.lat]); if (!xy) return;
      const hit = st.mode === "replay" && a.esc[st.mi] === 1;
      el("circle", { cx: xy[0], cy: xy[1], r: 9, fill: "none", stroke: hit ? "#FF4D5E" : "#F2B33D", "stroke-width": hit ? 3 : 1.5, class: hit ? "pulse" : "" }, pointG);
      const t = el("text", { x: xy[0] + 11, y: xy[1] + 4, style: `fill:${hit ? "#FF4D5E" : "#F5F5F7"};font-size:11px` }, pointG); t.textContent = String(i + 1);
    });
    const hits = st.mode === "replay" ? top.filter((a) => a.esc[st.mi] === 1).length : null;
    $("#ew-list", box).innerHTML = `<table class="t"><tr><th>#</th><th>Area</th><th>Conflict</th><th class="num">P</th>${st.mode === "replay" ? "<th>Outcome</th>" : ""}</tr>${top.map((a, i) =>
      `<tr data-id="${a.id}" style="cursor:pointer"><td class="mono">${i + 1}</td><td>${aname(a)}${a.unloc ? "" : ` <span class="muted small">${a.iso}</span>`}</td><td style="color:${CASE_COLOR[a.c]}" class="mono small">${CASE_SHORT[a.c]}</td><td class="num">${pct(val(a), 0)}</td>${st.mode === "replay" ? `<td class="mono small" style="color:${a.esc[st.mi] ? "var(--red)" : "var(--tx3)"}">${a.esc[st.mi] ? "● ESCALATED" : "–"}</td>` : ""}</tr>`).join("")}</table>`;
    $$("#ew-list tr[data-id]", box).forEach((r) => r.addEventListener("click", () => opts.onArea?.(r.dataset.id!)));
    $("#ew-hits", box).innerHTML = st.mode === "replay"
      ? `<b>REPLAY</b> ${hits} of the top 10 escalated the next month. Random choice would expect ${(10 * D.facts.warning.base).toFixed(1)}.`
      : `<b>LIVE</b> Areas to task for ISR in October 2026. ${D.facts.warning.lift}× better than random on the 2026 holdout.`;
    const s = ewStats(D, st.thr);
    $("#ew-to", box).textContent = pct(st.thr);
    $("#ew-k", box).innerHTML = [["Precision", pct(s.prec)], ["Recall", pct(s.rec)], ["False alarms / month", (s.fp / s.months).toFixed(1)]]
      .map(([l, v]) => `<div class="kpi"><span class="l">${l}</span><span class="v" style="font-size:30px">${v}</span></div>`).join("");
    update($("#ew-roc", box), {
      grid: { left: 46, right: 14, top: 24, bottom: 36 }, legend: { show: false }, toolbox: { show: false },
      tooltip: { trigger: "item" },
      xAxis: { type: "value", min: 0, max: 1, name: "false-alarm rate", nameLocation: "middle", nameGap: 24, ...axis() },
      yAxis: { type: "value", min: 0, max: 1, name: "recall", ...axis() },
      series: [{ type: "line", data: roc.pts.filter((_, i) => i % 6 === 0), symbol: "none", lineStyle: { color: "#4FD1E0", width: 2 }, areaStyle: { color: "rgba(79,209,224,.08)" } },
        { type: "line", data: [[0, 0], [1, 1]], symbol: "none", lineStyle: { color: "#6B7788", type: "dashed" } },
        { type: "scatter", data: [[s.fpr, s.rec]], symbolSize: 16, itemStyle: { color: "#F2B33D", shadowBlur: 16, shadowColor: "#F2B33D" } }],
      graphic: [{ type: "text", right: 20, bottom: 50, style: { text: `AUC ${roc.auc.toFixed(3)}`, fill: "#4FD1E0", font: "700 16px JetBrains Mono" } }],
    }, true);
    box.dispatchEvent(new CustomEvent("state", { detail: { month: M[st.mi], thr: st.thr, mode: st.mode }, bubbles: true }));
    (box as any)._top = top.map((a, i) => ({ rank: i + 1, area: a.name, country: a.iso, conflict: CASE_NAME[a.c], p_escalate: +val(a).toFixed(4), escalated: st.mode === "replay" ? a.esc[st.mi] : "" }));
  }
  $$("#ew-mode button", box).forEach((b) => b.addEventListener("click", () => { st.mode = b.dataset.m as any; render(); }));
  sI.addEventListener("input", () => { st.mi = +sI.value; render(); });
  tI.addEventListener("input", () => { st.thr = +tI.value; render(); });
  $("#ew-csv", box).addEventListener("click", () => csv(`watchlist_${st.mode === "oct" ? "2026-10" : M[st.mi]}.csv`, (box as any)._top));
  render();
  return { roc, set(month?: string, thr?: number, mode?: "replay" | "oct") { if (month && M.includes(month)) st.mi = M.indexOf(month); if (thr) st.thr = thr; if (mode) st.mode = mode; sI.value = String(st.mi); tI.value = String(st.thr); render(); } };
}

// ---------------------------------------------------------------------------
// Forecast vs actual on the 2026 holdout (playhead) + leaderboard
// ---------------------------------------------------------------------------
export function holdoutChart(chartEl: HTMLElement, D: Data, c: string, track: "A" | "B", upto: number) {
  const h = D.holdout.find((x: any) => x.c === c && x.track === track);
  const mon = D.monthly[c];
  const i0 = mon.months.indexOf("2025-01");
  const xs = mon.months.slice(i0);
  const idx = (m: string) => xs.indexOf(m);
  const arr = (vals: number[]) => { const a: (number | null)[] = Array(xs.length).fill(null); h.months.forEach((m: string, j: number) => { if (j < upto) a[idx(m)] = vals[j]; }); return a; };
  const lo = arr(h.lo), hi = arr(h.hi);
  update(chartEl, {
    legend: { data: ["Recorded deaths", "Forecast (ensemble)", "80% band"] },
    xAxis: { type: "category", data: xs, ...axis() }, yAxis: { type: "log", ...axis(), name: "deaths / month (log)", min: c === "usir" ? 1 : undefined },
    series: [
      { name: "lo", type: "line", data: lo, stack: "band", symbol: "none", lineStyle: { opacity: 0 }, tooltip: { show: false } },
      { name: "80% band", type: "line", data: hi.map((v, i) => (v == null ? null : v - (lo[i] ?? 0))), stack: "band", symbol: "none", lineStyle: { opacity: 0 }, areaStyle: { color: "rgba(242,179,61,.18)" } },
      { name: "Recorded deaths", type: "line", data: mon.deaths.slice(i0), lineStyle: { color: "#9AA6B6", width: 2 }, itemStyle: { color: "#9AA6B6" }, symbolSize: 5 },
      { name: "Forecast (ensemble)", type: "line", data: arr(h.pred), lineStyle: { color: "#F2B33D", width: 3 }, itemStyle: { color: "#F2B33D" }, symbolSize: 8,
        markArea: { silent: true, itemStyle: { color: "rgba(79,209,224,.05)" }, label: { color: "#4FD1E0", fontFamily: "JetBrains Mono", fontSize: 11 }, data: [[{ name: "WITHHELD TEST 2026", xAxis: "2026-01" }, { xAxis: "2026-09" }]] } },
    ],
  }, true);
  let inside = 0, n = 0;
  h.months.forEach((_: string, j: number) => { if (j < upto) { n++; if (h.actual[j] >= h.lo[j] && h.actual[j] <= h.hi[j]) inside++; } });
  return { inside, n };
}

export function leaderboard(chartEl: HTMLElement, D: Data, col: "A_bt" | "A_hold" | "B_bt" | "B_hold") {
  const rows = [...D.leaderboard.leaderboard].filter((r: any) => r[col] != null).sort((a: any, b: any) => b[col] - a[col]);
  update(chartEl, {
    grid: { left: 230, right: 60, top: 20, bottom: 30 }, legend: { show: false }, tooltip: { trigger: "item" },
    xAxis: { type: "value", ...axis(), name: "RMSLE (lower is better)", nameLocation: "middle", nameGap: 26, min: 0 },
    yAxis: { type: "category", data: rows.map((r: any) => r.label), ...axis({ axisLabel: { color: "#F5F5F7", fontFamily: "Inter", fontSize: 14 } }) },
    series: [{ type: "bar", data: rows.map((r: any) => ({ value: r[col], itemStyle: { color: r.model === "ensemble" ? "#F2B33D" : r.model === "naive" ? "#6B7788" : "#2B6F86", borderRadius: [0, 4, 4, 0] } })),
      label: { show: true, position: "right", color: "#F5F5F7", fontFamily: "JetBrains Mono", formatter: (p: any) => p.value.toFixed(3) }, barWidth: "62%",
      animationDurationUpdate: 900, universalTransition: true }],
    animationDurationUpdate: 900,
  }, false);
}

// ---------------------------------------------------------------------------
// Area drill-down
// ---------------------------------------------------------------------------
export function areaDrill(box: HTMLElement, D: Data, id: string) {
  const a = D.areas.areas.find((x) => x.id === id) ?? D.areas.areas[0];
  const ms = D.areas.months;
  const tot = a.d.reduce((x, y) => x + (y || 0), 0);
  const d26 = a.d.slice(ms.indexOf("2026-01")).reduce((x, y) => x + (y || 0), 0);
  box.innerHTML = `<div class="grid g4" style="margin-bottom:16px">
      <div class="panel kpi"><span class="l">${CASE_NAME[a.c]} · ${a.iso}</span><span class="v" style="font-size:32px">${a.name}</span></div>
      <div class="panel kpi"><span class="l">P(escalate) Oct 2026</span><span class="v" style="color:${a.p >= 0.15 ? "var(--red)" : "var(--teal)"}">${pct(a.p)}</span><span class="s">rank ${D.areas.areas.indexOf(a) + 1} of ${D.areas.areas.length}${a.p >= 0.15 ? " · HOTSPOT" : ""}</span></div>
      <div class="panel kpi"><span class="l">Deaths 2014–Sep 2026</span><span class="v">${fmt(tot)}</span></div>
      <div class="panel kpi"><span class="l">Deaths Jan–Sep 2026</span><span class="v">${fmt(d26)}</span><span class="s">last month ${fmt(a.last)}</span></div>
    </div>
    <div class="grid g2"><div class="panel"><div class="ph"><span class="t">Monthly deaths</span></div><div class="chart" id="ad-d"></div></div>
    <div class="panel"><div class="ph"><span class="t">2026 warning history</span>${info("Bars: the model's escalation probability for each month of 2026, made one month ahead. Red bars mark months that did escalate (≥10 deaths and ≥1.5× the trailing 3-month mean).")}</div><div class="chart" id="ad-w"></div></div></div>`;
  mount($("#ad-d", box), {
    legend: { show: false }, dataZoom: [{ type: "inside", start: 55 }, { type: "slider", start: 55, height: 18, bottom: 6, borderColor: "#2B4763", textStyle: { color: "#9AA6B6" } }],
    grid: { left: 60, right: 20, top: 30, bottom: 60 },
    xAxis: { type: "category", data: ms, ...axis() }, yAxis: { type: "value", ...axis() },
    series: [{ type: "bar", data: a.d, itemStyle: { color: CASE_COLOR[a.c] } }],
  }, false);
  mount($("#ad-w", box), {
    legend: { show: false },
    xAxis: { type: "category", data: D.areas.ew_months, ...axis() }, yAxis: { type: "value", ...axis(), axisLabel: { formatter: (v: number) => Math.round(v * 100) + "%", color: "#9AA6B6" } },
    series: [{ type: "bar", data: a.pm.map((p, i) => ({ value: p, itemStyle: { color: a.esc[i] ? "#FF4D5E" : "#2B6F86" } })),
      markLine: { symbol: "none", data: [{ yAxis: 0.15, label: { formatter: "hotspot 15%", color: "#F2B33D" }, lineStyle: { color: "#F2B33D", type: "dashed" } }] } }],
  }, false);
}

export { pulse, regionMap, adminLayer, ramp, tip, el };
