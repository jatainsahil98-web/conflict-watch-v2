import { mountOutlook } from "./outlook";
import { type Data, type Score, CASES, CASE_COLOR, CASE_SHORT, CASE_NAME, RAG_COLOR, fmt, fmtM, pct } from "./data";
import { verify, DOCTRINE } from "./rules";
import { mount, update, axis, csv, resizeAll } from "./charts";
import { regionMap, adminLayer, ramp, tip } from "./maps";
import { $, $$, tag, ragCards, whatIf, scorecardLab, warningPanel, holdoutChart, leaderboard, areaDrill, topN } from "./widgets";
import { strip, navBar, footer, qaDrawer } from "./chrome";
import { renderTheatre } from "./theatre";

const CSS = `
.con { display:grid; grid-template-columns: 236px minmax(0,1fr); min-height:100vh; padding-top: calc(var(--strip) + var(--nav)); position:relative; z-index:1; }
.rail { position: sticky; top: calc(var(--strip) + var(--nav)); height: calc(100vh - var(--strip) - var(--nav)); padding:20px 14px; display:flex; flex-direction:column; gap:3px; background: linear-gradient(180deg, rgba(13,20,33,.9), rgba(5,7,10,.6)); border-right:1px solid var(--line); }
.rail a { display:flex; gap:12px; align-items:center; padding:8px 10px; border-radius:10px; color:var(--tx2); text-decoration:none; font:600 14.5px var(--sans); transition: background .2s, color .2s; }
.rail a span { width:30px; height:30px; flex:none; display:grid; place-items:center; border-radius:8px; background: rgba(255,255,255,.04); border:1px solid var(--line); font-size:14px; transition: all .2s; }
.rail a:hover, .rail a:focus-visible { color: var(--tx); background: rgba(255,255,255,.04); outline:none; }
.rail a.on { color: var(--tx); background: rgba(79,209,224,.10); }
.rail a.on span { background: var(--teal); border-color: var(--teal); color:#05070A; box-shadow: 0 0 16px rgba(79,209,224,.35); }
.rail-g { font: 700 10.5px var(--mono); letter-spacing:.24em; color: var(--tx3); padding: 16px 10px 6px; }
.rail-g:first-child { padding-top: 0; }
.rail .k { margin-top:auto; font: 500 11px var(--mono); color: var(--tx3); padding: 12px; line-height:1.8; border:1px solid var(--line); border-radius:10px; background: rgba(255,255,255,.02); }
:root[data-theme="light"] .rail { background:#fff; } :root[data-theme="light"] .rail a span { background:#F4F6F9; }
.page { padding: 26px 30px 40px; }
.page h2 { font-size: 34px; margin: 0 0 4px; }
.page .sub { color: var(--tx2); margin-bottom: 18px; }
.radar { width: 14px; height: 14px; border-radius:50%; border:1px solid var(--teal); position:relative; overflow:hidden; }
.radar::after { content:""; position:absolute; inset:0; background: conic-gradient(rgba(79,209,224,.8), transparent 30%); animation: spin 2.4s linear infinite; }
@keyframes spin { to { transform: rotate(360deg) } }
@media (max-width: 980px) { .con { grid-template-columns: 1fr; } .rail { position: static; height:auto; flex-direction:row; overflow-x:auto; } .rail .k, .rail-g { display:none; } .page { padding: 18px 16px; } }
@media print { .con { display:block; padding:0; } .rail { display:none; } .page { padding:0; } .panel { border:1px solid #999; background:#fff; color:#000; break-inside: avoid; } .print-only { display:block !important; } }
.print-only { display:none; }
`;

const PAGES = [["brief", "◉", "Brief", "DECIDE"], ["theatre", "✪", "Theatre", "DECIDE"], ["warning", "⚠", "Warning", "DECIDE"],
  ["map", "◎", "Map", "EXPLORE"], ["area", "⌖", "Area", "EXPLORE"], ["forecast", "↗", "Forecast", "EXPLORE"], ["outlook", "◷", "2027 Outlook", "EXPLORE"], ["whatif", "⚗", "What-if", "EXPLORE"],
  ["scorecard", "▦", "Scorecard", "VERIFY"], ["dq", "✓", "Data quality", "VERIFY"], ["about", "ⓘ", "About", "VERIFY"]] as const;

export function renderConsole(D: Data) {
  const F = D.facts;
  document.head.insertAdjacentHTML("beforeend", `<style>${CSS}</style>`);
  document.body.insertAdjacentHTML("beforeend", `${strip(F)}${navBar(F, "console")}
    <div class="con"><nav class="rail" aria-label="Console pages">${PAGES.map(([id, ic, l, g], i) => `${i === 0 || PAGES[i - 1][3] !== g ? `<div class="rail-g">${g}</div>` : ""}<a href="${D.inline ? "#console/" : "#"}${id}" data-p="${id}"><span>${ic}</span>${l}</a>`).join("")}
      <div class="k">CTRL/⌘ K · command<br>/ · search areas<br><span style="display:flex;gap:8px;align-items:center"><span class="radar"></span>WATCH ACTIVE</span></div></nav>
      <div class="page" id="page"></div></div>
    <div class="palette" id="pal" role="dialog" aria-label="Command palette"><div class="box"><input id="pal-i" placeholder="Jump to a page or area…" aria-label="Search"><ul id="pal-l"></ul></div></div>
    ${footer(F)}`);
  const bad = verify(F.scorecard, DOCTRINE(F));
  const QA = qaDrawer(F);
  let areaId = D.areas.areas[0].id;
  const P = $("#page");

  const pages: Record<string, (q: URLSearchParams) => void> = {
    brief() {
      P.innerHTML = `<div class="eyebrow">COMMANDER'S BRIEF · OCTOBER 2026</div><h2>Four wars, three warning signals, one exposed neighbour</h2>
        <div class="sub">RU–UA stays RED; Af–Pak and US–Iran AMBER; IL–Hamas GREEN. ${tag("data")}</div>
        <div class="grid g4" id="b-cards"></div>
        <div class="grid g2" style="margin-top:18px">
          <div class="panel hud"><div class="ph"><span class="t">India impact</span></div><table class="t small">
            <tr><th>Theatre</th><th>Data ${tag("data")}</th><th>For India ${tag("domain")}</th></tr>
            <tr><td><b>Af–Pak</b></td><td>Interstate clashes peak ${fmt(F.military.afpak_dyad["2026-03"])} (Mar 26); LoC-adjoining deaths ${F.india.pak_india_adjoining[2022]}→${F.india.pak_india_adjoining[2025]}</td><td>Diversionary LoC activity; TTP / IS-K spill-over</td></tr>
            <tr><td><b>US–Iran</b></td><td>${F.india.usir_countries[1]} countries; ${F.india.gulf_states} Gulf states; ${F.india.hormuz_deaths} on Hormuz/Chabahar; ${F.india.srilanka.deaths} off Sri Lanka</td><td>Diaspora: NEO; energy; Chabahar / INSTC</td></tr>
            <tr><td><b>RU–UA</b></td><td>${fmt(F.scorecard[0].forecast)} forecast for Oct; front widening</td><td>Spares for Russian-origin kit; drone / EW lessons</td></tr>
            <tr><td><b>IL–Hamas</b></td><td>~130 a month in 2026; reached Qatar Sep 2025</td><td>Israeli-origin spares; Red Sea shipping</td></tr></table></div>
          <div class="panel"><div class="ph"><span class="t">Recommendations</span></div>${F.recommendations.map((r: any) => `<div class="ptsrow"><span><b class="mono">${r.line}</b> ${r.action}</span><span class="muted small mono">${r.when}</span></div>`).join("")}
            <div style="margin-top:14px;display:flex;gap:10px;flex-wrap:wrap" class="no-print"><button class="btn primary" id="b-print">⎙ Print 1-page brief</button><button class="btn" id="b-bul">⎙ Monthly I&amp;W bulletin</button><button class="btn" id="b-csv">Watch-list CSV</button></div></div>
        </div>
        <div class="panel print-only" id="b-bulletin"></div>
        ${bad.length ? `<div class="sowhat"><b>PARITY</b>${bad.join("; ")}</div>` : `<p class="small muted mono" style="margin-top:12px">✓ Scorecard rules recomputed in-browser match the pipeline for all four conflicts.</p>`}`;
      ragCards($("#b-cards"), D);
      $("#b-print").addEventListener("click", () => { $("#b-bulletin").innerHTML = ""; print(); });
      $("#b-bul").addEventListener("click", () => { $("#b-bulletin").innerHTML = bulletin(D); print(); });
      $("#b-csv").addEventListener("click", () => csv("watchlist_2026-10.csv", D.areas.areas.filter((a) => !a.unloc).slice(0, 20).map((a, i) => ({ rank: i + 1, area: a.name, country: a.iso, conflict: CASE_NAME[a.c], p_escalate_oct26: a.p }))));
    },
    theatre(q) { renderTheatre(P, D, q); },
    map(q) {
      const lay = q.get("layer") ?? "p";
      P.innerHTML = `<div class="eyebrow">THEATRE MAP · ${D.areas.areas.length} AREA SERIES</div><h2>Map</h2><div class="sub">Click an area to drill down. India's boundary: Natural Earth India point of view.</div>
        <div class="panel" style="padding:12px"><div class="ph"><div class="seg" id="m-l"><button data-l="p">P(ESCALATE) OCT 26</button><button data-l="d">DEATHS IN MONTH</button></div>
          <div class="ctl" style="min-width:320px;margin:0"><label>Month <output id="m-mo"></output></label><input type="range" id="m-m" min="0" max="${D.areas.months.length - 1}" value="${D.areas.months.length - 1}" aria-label="Month"></div></div>
          <div class="mapbox" id="m-map" style="height:calc(100vh - 300px);min-height:460px"></div></div>`;
      const m = regionMap($("#m-map"), D.world, [[22, 4], [80, 57]]);
      const byId = new Map(D.areas.areas.map((a) => [a.id, a]));
      let L = lay, mi = D.areas.months.length - 1;
      const val = (a: any) => (L === "p" ? a.p : a.d[mi] ?? 0);
      const rec = adminLayer(m, D.admin1, () => true, (ids, ev) => { if (!ev) return tip(null); const as = ids.map((i) => byId.get(i)!).filter(Boolean);
        tip(as.map((a) => `<b>${a.name}</b> · ${CASE_SHORT[a.c]}<br>${L === "p" ? "P(escalate) " + pct(a.p) : fmt(a.d[mi]) + " deaths " + D.areas.months[mi]}`).join("<hr>"), ev); },
        (ids) => { areaId = ids[0]; location.hash = "area?id=" + encodeURIComponent(ids[0]); });
      const draw = () => { $$("#m-l button").forEach((b) => b.classList.toggle("on", b.dataset.l === L)); $("#m-mo").textContent = L === "p" ? "Oct 2026 (forecast)" : D.areas.months[mi];
        rec((ids) => { const v = Math.max(0, ...ids.map((i) => byId.get(i)).filter(Boolean).map(val)); return L === "p" ? ramp(Math.sqrt(v / 0.35)) : v > 0 ? ramp(Math.log10(1 + v) / 3.5) : "#141E2E"; }); };
      $$("#m-l button").forEach((b) => b.addEventListener("click", () => { L = b.dataset.l!; draw(); }));
      $("#m-m").addEventListener("input", (e) => { mi = +(e.target as HTMLInputElement).value; L = "d"; draw(); });
      draw();
    },
    area(q) {
      if (q.get("id")) areaId = q.get("id")!;
      P.innerHTML = `<div class="eyebrow">AREA DRILL-DOWN</div><h2>Area</h2><div class="sub"><select id="a-s" aria-label="Choose area">${D.areas.areas.map((a) => `<option value="${a.id}" ${a.id === areaId ? "selected" : ""}>${a.name} · ${a.iso} · ${CASE_SHORT[a.c]} · ${pct(a.p)}</option>`).join("")}</select> <span class="muted small mono">or press / to search</span></div><div id="a-box"></div>`;
      areaDrill($("#a-box"), D, areaId);
      $("#a-s").addEventListener("change", (e) => { location.hash = "area?id=" + encodeURIComponent((e.target as HTMLSelectElement).value); });
    },
    forecast() {
      P.innerHTML = `<div class="eyebrow">FORECAST · 2026 WITHHELD TEST + FORWARD</div><h2>Forecast</h2><div class="sub">Dashboard model: 3-month mean + ETS + LightGBM-Δ. The deck's final model is the global ensemble (global LightGBM 0.90 + competition LightGBM-Δ 0.10). Dashboard 80% band coverage on 2026: ${F.forecasting.coverage.all}%. MAE −${F.forecasting.mae_pooled}% vs no change.</div>
        <div class="panel"><div class="ph"><div class="seg" id="f-c">${CASES.map((c) => `<button data-c="${c}">${CASE_SHORT[c]}</button>`).join("")}</div><div class="seg" id="f-t"><button data-t="A" class="on">TRACK A</button><button data-t="B">TRACK B</button></div></div><div class="chart tall" id="f-ch"></div></div>
        <div class="grid g2" style="margin-top:16px"><div class="panel"><div class="ph"><span class="t">Forward forecast</span><button class="btn small" id="f-csv">CSV</button></div><table class="t"><tr><th>Conflict</th>${F.scorecard[0].forward.map((f: any) => `<th class="num">${f.month}</th>`).join("")}</tr>${F.scorecard.map((s: Score) => `<tr><td style="color:${CASE_COLOR[s.id]}"><b>${s.short}</b></td>${s.forward.map((f) => `<td class="num">${fmt(f.pred)}<br><span class="muted small">${fmt(f.lo)}–${fmt(f.hi)}</span></td>`).join("")}</tr>`).join("")}</table></div>
        <div class="panel"><div class="ph"><span class="t">Leaderboard · 2026 Track A</span></div><div class="chart" id="f-lb"></div></div></div>`;
      let c = "ruua", t: "A" | "B" = "A";
      const draw = () => { $$("#f-c button").forEach((b) => b.classList.toggle("on", b.dataset.c === c)); $$("#f-t button").forEach((b) => b.classList.toggle("on", b.dataset.t === t)); holdoutChart($("#f-ch"), D, c, t, 9); };
      $$("#f-c button").forEach((b) => b.addEventListener("click", () => { c = b.dataset.c!; draw(); }));
      $$("#f-t button").forEach((b) => b.addEventListener("click", () => { t = b.dataset.t as any; draw(); }));
      draw(); leaderboard($("#f-lb"), D, "A_hold");
      $("#f-csv").addEventListener("click", () => csv("forward_forecast.csv", F.scorecard.flatMap((s: Score) => s.forward.map((f) => ({ conflict: s.name, ...f })))));
    },
    warning(q) {
      P.innerHTML = `<div class="eyebrow">EARLY WARNING · AUC ${F.warning.auc} · ${F.warning.lift}× RANDOM</div><h2>Warning</h2><div class="sub">Replay 2026 month by month, or switch to the live October list. Click an area to drill down.</div><div id="w-box"></div>`;
      const W = warningPanel($("#w-box"), D, { month: q.get("month") ?? "2026-03", thr: q.get("thr") ? +q.get("thr")! : 0.15, onArea: (id) => { location.hash = "area?id=" + encodeURIComponent(id); } });
      if (q.get("mode")) W.set(undefined, undefined, q.get("mode") as any);
    },
    outlook(q) {
      const roles = ["CDS", "WTC", "MTC", "NTC"].filter((x) => x === "CDS" || D.theatre?.theatres?.[x]); let r = q.get("r") && roles.includes(q.get("r")!) ? q.get("r")! : "CDS";
      P.innerHTML = `<div class="eyebrow">2027 OUTLOOK · SCENARIO RANGE FROM HISTORY</div><h2>How the wars reach India in 2027</h2>
        <div class="sub">Pick a theatre and a period. Not a validated forecast: what happened next to similar conflicts in 117 countries.</div>
        <div class="seg" id="ol-r" style="margin:6px 0 14px">${roles.map((x) => `<button data-r="${x}" class="${x === r ? "on" : ""}">${x}</button>`).join("")}</div><div id="ol-p"></div>`;
      const go = () => { mountOutlook($("#ol-p"), D, r); document.querySelectorAll<HTMLElement>("#ol-r button").forEach((b) => b.classList.toggle("on", b.dataset.r === r)); };
      document.querySelectorAll<HTMLElement>("#ol-r button").forEach((b) => b.addEventListener("click", () => { r = b.dataset.r!; go(); }));
      if (D.outlook) go(); else $("#ol-p").innerHTML = `<p class="muted">2027 outlook not built.</p>`;
    },
    whatif(q) {
      P.innerHTML = `<div class="eyebrow">DECISION ROOM</div><h2>What-if simulator</h2><div class="sub">The exact submitted ensemble, for every slider position.</div><div id="wi"></div>`;
      whatIf($("#wi"), D, { c: q.get("c") ?? "afpak", shock: +(q.get("shock") ?? 30), k: +(q.get("m") ?? 3) });
    },
    scorecard() {
      P.innerHTML = `<div class="eyebrow">DECISION ROOM</div><h2>Scorecard lab</h2><div class="sub">Move any threshold. Cards re-rate live; "Reset to doctrine" restores the submitted rules.</div><div id="sl"></div>`;
      scorecardLab($("#sl"), D);
    },
    dq() {
      P.innerHTML = `<div class="eyebrow">DATA QUALITY</div><h2>${D.dq.length} checks, logged and acted on</h2><div class="sub"><button class="btn" id="dq-c">CSV</button></div>
        <div class="panel"><table class="t small"><tr><th>ID</th><th>Table</th><th>Check</th><th>Category</th><th class="num">Rows</th><th>Action</th><th>Impact</th></tr>${D.dq.map((r) => `<tr><td class="mono">${r.id}</td><td>${r.table}</td><td>${r.check}</td><td>${r.category}</td><td class="num">${fmt(r.rows_affected)}</td><td>${r.action ?? ""}</td><td class="muted">${r.analytical_impact ?? ""}</td></tr>`).join("")}</table></div>`;
      $("#dq-c").addEventListener("click", () => csv("data_quality_log.csv", D.dq));
    },
    about() {
      P.innerHTML = `<div class="eyebrow">ABOUT</div><h2>Conflict EW Console</h2><div class="sub">${F.competition} · ${F.team.join(" · ")}</div>
        <div class="grid g2"><div class="panel hud mono small">RUN ${F.run_id}<br>EXPORTED ${F.exported}<br>DATA AS OF ${F.data_as_of}<br>BUILD ${D.inline ? "single-file offline" : "web / PWA"}<br><br>${Object.entries(D.manifest.files).map(([k, v]: any) => `${k}<br><span class="muted" style="font-size:11px;word-break:break-all">${v.sha256}</span>`).join("<br>")}</div>
        <div class="panel"><p class="small muted">Sources: ${F.sources}. ${F.licence}.</p><p class="small muted">Limits: ${F.limits.join(" ")}</p>
        <div style="display:flex;gap:10px;flex-wrap:wrap"><button class="btn primary" id="ab-qa">Jury Q&amp;A ▸</button><button class="btn" id="ab-inst" style="display:none">⤓ Install app</button></div></div></div>`;
      $("#ab-qa").addEventListener("click", () => QA.open());
      if (deferred) { const b = $("#ab-inst"); b.style.display = ""; b.addEventListener("click", () => deferred.prompt()); }
    },
  };

  let deferred: any = null;
  addEventListener("beforeinstallprompt", (e) => { e.preventDefault(); deferred = e; });

  // Summary header: the page's headline numbers and the order it supports, above the detail.
  const hot = F.scorecard.reduce((n: number, x: Score) => n + x.hotspots, 0);
  const SUM: Record<string, { n: [string, string][]; line?: string }> = {
    warning: { n: [[`${F.warning.lift}×`, "better than chance"], [`${(F.warning.p10 * 10).toFixed(1)} of 10`, "flagged areas escalate each month"], [String(hot), `areas at ${Math.round(F.rules.hot_p * 100)}% or more now`]], line: "SENSE" },
    map: { n: [[String(F.warning.areas), "areas tracked"], [String(F.warning.countries), "countries"], [String(hot), "hotspots now"]], line: "SENSE" },
    forecast: { n: [[`−${F.forecasting.mae_pooled}%`, "error vs \"no change\""], [`${F.forecasting.coverage.all}%`, "of 2026 outcomes inside the range"], [`${F.forecasting.direction}%`, "direction called right"]] },
    scorecard: { n: [[String(F.scorecard.filter((x: Score) => x.rating === "RED").length), "RED"], [String(F.scorecard.filter((x: Score) => x.rating === "AMBER").length), "AMBER"], [String(F.scorecard.filter((x: Score) => x.rating === "GREEN").length), "GREEN"]], line: "WARN" },
    dq: { n: [[String(D.dq.length), "checks logged"], [String(D.dq.filter((r) => +r.rows_affected > 0).length), "found something to act on"], [String(D.dq.filter((r) => +r.rows_affected === 0).length), "passed clean"]] },
  };
  const sumbar = (pg: string) => { const x = SUM[pg]; if (!x) return;
    const r = x.line ? F.recommendations.find((q: any) => q.line === x.line) : null;
    P.querySelector(".sub")?.insertAdjacentHTML("afterend", `<div class="sumbar">${x.n.map(([v, l]) => `<div class="sb-n"><b>${v}</b><span>${l}</span></div>`).join("")}${r ? `<div class="sb-a"><span class="mono">${r.line}</span><div>${r.action.split(". ")[0]}.<em>${r.lead} · ${r.when}</em></div></div>` : ""}</div>`); };

  const route = () => {
    if (location.hash === "#cmd") return;  // leaving for the Commander view; main.ts reloads
    const h = decodeURIComponent(location.hash.replace(/^#(console\/?)?/, "")) || "brief";
    const [id, qs] = h.split("?");
    const pg = pages[id] ? id : "brief";
    // Keep the "#console/" prefix in the single-file build so a refresh reopens the console, not the story.
    // In an about:srcdoc frame (Streamlit) replaceState to a hash URL throws, so it is optional here.
    if (D.inline && !/^#console/.test(location.hash)) { try { history.replaceState(null, "", "#console/" + h); } catch {} }
    $$(".rail a").forEach((a) => a.classList.toggle("on", a.dataset.p === pg));
    pages[pg](new URLSearchParams(qs ?? "")); sumbar(pg);
    if (!matchMedia("(prefers-reduced-motion: reduce)").matches) P.animate([{ opacity: 0, transform: "translateY(8px)" }, { opacity: 1, transform: "none" }], { duration: document.documentElement.classList.contains("pres") ? 120 : 260, easing: "cubic-bezier(.2,.7,.2,1)" });
    scrollTo(0, 0); setTimeout(resizeAll, 50);
  };
  addEventListener("hashchange", route);
  route();

  // Command palette
  const pal = $("#pal"), pi = $("#pal-i") as HTMLInputElement, pl = $("#pal-l");
  let items: { l: string; r: string; h: string }[] = [], sel = 0;
  const all = [...PAGES.map(([id, , l]) => ({ l, r: "page", h: id })), ...D.areas.areas.map((a) => ({ l: `${a.name} · ${a.iso}`, r: `${CASE_SHORT[a.c]} ${pct(a.p)}`, h: "area?id=" + encodeURIComponent(a.id) }))];
  const draw = () => { const q = pi.value.toLowerCase(); items = all.filter((x) => (x.l + " " + x.r).toLowerCase().includes(q)).slice(0, 40); sel = Math.min(sel, items.length - 1);
    pl.innerHTML = items.map((x, i) => `<li class="${i === sel ? "sel" : ""}" data-i="${i}"><span>${x.l}</span><span class="muted mono small">${x.r}</span></li>`).join("");
    $$("li", pl).forEach((li) => li.addEventListener("click", () => pick(+li.dataset.i!))); };
  const open = (q = "") => { pal.classList.add("open"); pi.value = q; sel = 0; draw(); pi.focus(); };
  const close = () => pal.classList.remove("open");
  const pick = (i: number) => { if (items[i]) location.hash = items[i].h; close(); };
  pi.addEventListener("input", () => { sel = 0; draw(); });
  pi.addEventListener("keydown", (e) => { if (e.key === "ArrowDown") { sel = Math.min(sel + 1, items.length - 1); draw(); e.preventDefault(); } else if (e.key === "ArrowUp") { sel = Math.max(sel - 1, 0); draw(); e.preventDefault(); } else if (e.key === "Enter") pick(sel); else if (e.key === "Escape") close(); });
  pal.addEventListener("click", (e) => { if (e.target === pal) close(); });
  addEventListener("keydown", (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); open(); }
    else if (e.key === "/" && !/INPUT|SELECT|TEXTAREA/.test((e.target as HTMLElement).tagName)) { e.preventDefault(); open(""); }
  });
}

function bulletin(D: Data) {
  const F = D.facts;
  const top = D.areas.areas.filter((a) => !a.unloc).slice(0, 20);
  return `<h2>MONTHLY I&amp;W BULLETIN · OCTOBER 2026</h2><p class="small">UNCLASSIFIED — COMPETITION DATA ONLY · RUN ${F.run_id} · Data as of 30 Sep 2026</p>
  <p><b>RAG:</b> ${F.scorecard.map((s: Score) => `${s.short} ${s.rating} (${fmt(s.forecast)})`).join(" · ")}. No rating changed from the model's September run.</p>
  <table class="t small"><tr><th>#</th><th>Area</th><th>Country</th><th>Conflict</th><th class="num">P(escalate)</th></tr>${top.map((a, i) => `<tr><td>${i + 1}</td><td>${a.name}</td><td>${a.iso}</td><td>${CASE_NAME[a.c]}</td><td class="num">${pct(a.p)}</td></tr>`).join("")}</table>
  <p><b>Signposts to watch:</b> Af–Pak interstate clashes above 150 deaths a month; any US–Iran strike in a Gulf state or Indian Ocean waters; RU–UA deaths above 10,000 a month; any hotspot rising above 25%.</p>`;
}
