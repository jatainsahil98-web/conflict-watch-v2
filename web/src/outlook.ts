// 2027 outlook, visual: an animated map of India's theatre zones with the wars' impact lines, and for each war a short
// chain "war → what it does to them → what it means for India → what India should do". Levels come from
// web/public/data/outlook2027.json (analogue scenario range, scripts/outlook_2027.py); the chains are our analysis.
import { type Data, RAG_COLOR } from "./data";
import { regionMap } from "./maps";

const esc = (s: any) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]!));
const k = (n: number) => (n >= 1000 ? `${(n / 1000).toFixed(n >= 10000 ? 0 : 1)}k` : String(n));

const CSS = `
.o7 { display:grid; grid-template-columns: minmax(0,1.2fr) minmax(0,1fr); gap:18px; align-items:start; }
@media (max-width: 1100px) { .o7 { grid-template-columns: 1fr; } }
.o7-map { position:relative; height: clamp(420px, 78vh, 720px); background: var(--panel); border:1px solid var(--line); border-radius:14px; overflow:hidden; }
.o7-map .arc { fill:none; stroke-width:2.6; stroke-dasharray: 9 7; animation: o7dash 1.6s linear infinite; }
.o7-map .arc-bg { fill:none; stroke-width:9; }
.o7-map .lbl { font: 700 12px var(--mono); letter-spacing:.08em; paint-order: stroke; stroke:#05070A; stroke-width:4px; }
.o7-map .zl { font: 800 13px var(--mono); letter-spacing:.14em; paint-order: stroke; stroke:#05070A; stroke-width:4px; }
@keyframes o7dash { to { stroke-dashoffset: -32; } }
.o7-leg { position:absolute; left:14px; bottom:12px; display:flex; gap:12px; flex-wrap:wrap; font: 700 11px var(--mono); letter-spacing:.08em; color: var(--tx2); }
.o7-leg i { display:inline-block; width:12px; height:12px; border-radius:3px; margin-right:5px; vertical-align:-2px; }
.o7-tag { position:absolute; left:14px; top:12px; font: 800 11px var(--mono); letter-spacing:.14em; color: var(--amber); }
.o7-chains { display:flex; flex-direction:column; gap:12px; }
.o7-ch { background: var(--panel); border:1px solid var(--line); border-left:4px solid var(--c); border-radius:12px; padding:12px 14px; opacity:0; transform: translateY(8px); animation: o7in .5s ease forwards; }
.o7-ch h4 { margin:0 0 10px; display:flex; align-items:center; gap:10px; font-size:17px; flex-wrap:wrap; }
.o7-ch h4 .lv { font: 800 11px var(--mono); letter-spacing:.1em; color: var(--tx3); display:flex; gap:6px; align-items:center; }
.o7-ch h4 .lv b { padding:2px 7px; border-radius:5px; color:#05070A; }
.o7-ch h4 .n { margin-left:auto; font: 700 12px var(--mono); color: var(--tx3); }
.o7-steps { display:grid; grid-template-columns: 1fr 22px 1fr 22px 1fr; align-items:stretch; }
.o7-st { border-radius:10px; padding:8px 10px; background: rgba(255,255,255,.035); opacity:0; animation: o7in .45s ease forwards; }
.o7-st .h { font: 800 10.5px var(--mono); letter-spacing:.14em; margin-bottom:5px; }
.o7-st ul { margin:0; padding:0; list-style:none; } .o7-st li { font-size:13.5px; line-height:1.35; margin:3px 0; }
.o7-st li::before { content:"▸ "; color: var(--tx3); }
.o7-st.them .h { color:#F2B33D; } .o7-st.ind .h { color:#4FD1E0; } .o7-st.do { background: rgba(53,194,166,.08); border:1px solid rgba(53,194,166,.35); } .o7-st.do .h { color:#35C2A6; }
.o7-ar { display:flex; align-items:center; justify-content:center; color: var(--tx3); font-size:18px; }
.o7-ar span { display:inline-block; animation: o7nudge 1.4s ease-in-out infinite; }
@keyframes o7nudge { 0%,100% { transform: translateX(-2px); opacity:.5 } 50% { transform: translateX(3px); opacity:1 } }
@keyframes o7in { to { opacity:1; transform:none; } }
@media (max-width: 700px) { .o7-steps { grid-template-columns: 1fr; } .o7-ar { height:18px; } .o7-ar span { animation:none; transform: rotate(90deg); } }
.o7-india { background: linear-gradient(135deg, rgba(79,209,224,.10), rgba(53,194,166,.06)); border:1px solid rgba(79,209,224,.45); border-radius:12px; padding:12px 16px; opacity:0; animation: o7in .5s ease forwards; }
.o7-india .h { font: 800 12px var(--mono); letter-spacing:.16em; color: var(--teal); margin-bottom:8px; }
.o7-india .row { display:grid; grid-template-columns: repeat(auto-fit, minmax(170px,1fr)); gap:8px; }
.o7-india .row div { background: rgba(5,11,18,.5); border:1px solid var(--line); border-radius:10px; padding:8px 10px; font-size:13.5px; line-height:1.35; }
.o7-india .row div b { display:block; font-size:15px; margin-bottom:2px; }
.o7-gap { border:1px dashed #E28CC1; background: rgba(226,140,193,.06); border-radius:12px; padding:10px 14px; font-size:14px; }
.o7-per { display:flex; gap:6px; flex-wrap:wrap; }
.o7-per button { font: 800 12px var(--mono); letter-spacing:.12em; padding:8px 14px; border-radius:999px; border:1px solid var(--line2); background: var(--panel); color: var(--tx2); cursor:pointer; }
.o7-per button.on { background: var(--teal); color:#05070A; border-color: var(--teal); }
.o7-so { border-radius:14px; padding:14px 18px; background: linear-gradient(120deg, rgba(242,179,61,.16), rgba(255,107,107,.10)); border:1px solid rgba(242,179,61,.55); opacity:0; animation: o7in .5s ease .1s forwards; }
.o7-so .h { font: 800 12px var(--mono); letter-spacing:.2em; color: var(--amber); margin-bottom:4px; }
.o7-so { border-color: var(--sc); background: linear-gradient(120deg, color-mix(in srgb, var(--sc) 18%, transparent), rgba(5,11,18,.2)); }
.o7-so .t { font-size: clamp(20px, 1.6vw, 26px); font-weight:800; line-height:1.3; }
.o7-so .t .c, .o7-so .s .c { font-size:.72em; font-weight:600; color: var(--tx2); }
.o7-so .s { font-size: 16px; line-height:1.45; color: var(--tx); margin-top:6px; }
.o7-so .s b { font-weight:800; }
.o7-map svg.map { animation: o7zoom 1s cubic-bezier(.2,.8,.2,1) both; transform-origin: 60% 55%; }
@keyframes o7zoom { from { transform: scale(1.12); opacity:.25; filter: blur(3px); } to { transform: none; opacity:1; filter:none; } }
.o7-map .breath { animation: o7fade .8s ease both, o7breath 2.6s ease-in-out .8s infinite; }
@keyframes o7breath { 0%,100% { fill-opacity: var(--fo); } 50% { fill-opacity: calc(var(--fo) * 1.9); } }
.o7-ch h4 .n { margin-left:auto; text-align:right; font: 700 12px var(--mono); color: var(--tx3); }
.o7-ch h4 .n b { display:block; font: 800 30px var(--sans); line-height:1; color: var(--lvc); letter-spacing:-.01em; }
.o7-ch h4 .lv b { font-size:13px; padding:3px 9px; }
.o7-st.ind { background: rgba(79,209,224,.10); border:1px solid rgba(79,209,224,.45); }
.o7-st.ind li { font-size:15px; font-weight:600; }
.o7-st.them li { color: var(--tx2); }
.o7-map .stamp { font: 900 64px var(--sans); letter-spacing:-.02em; fill: #fff; fill-opacity:.07; }
.o7-map .draw { animation: o7draw 1.1s ease-out both, o7dash 1.6s linear 1.1s infinite; }
@keyframes o7draw { from { stroke-dasharray: 1400; stroke-dashoffset: 1400; } to { stroke-dasharray: 1400; stroke-dashoffset: 0; } }
.o7-map .pop { transform-box: fill-box; transform-origin: center; animation: o7pop .7s cubic-bezier(.2,1.6,.4,1) both; }
@keyframes o7pop { from { transform: scale(0); opacity:0 } to { transform: scale(1); opacity:1 } }
.o7-map .fade { opacity:0; animation: o7fade .6s ease forwards; }
@keyframes o7fade { to { opacity:1 } }
.o7-map .halo { transform-box: fill-box; transform-origin:center; animation: o7halo 2.2s ease-out infinite; }
@keyframes o7halo { 0% { transform: scale(.6); opacity:.7 } 100% { transform: scale(2.4); opacity:0 } }
.o7-map .zone { animation: o7fade .8s ease both; }
.o7-foot { grid-column: 1 / -1; font-size:12.5px; color: var(--tx3); }
`;

type Chain = { lab: [number, number, "start" | "end"]; war: string; short: string; c: string; at: [number, number]; to: [number, number]; via: string; themLabel: string; them: string[]; ind: string[]; act: string[] };
// Facts from our data (deaths, spread, prices, Donetsk share) and our judgement (worded as risk / watch).
const CHAINS: Record<string, Chain> = {
  "Afghanistan–Pakistan": { lab: [-14, -10, "end"], war: "Afghanistan–Pakistan", short: "Af–Pak", c: "#F2B33D", at: [66.5, 31.2], to: [74.6, 34.1], via: "LoC diversion",
    themLabel: "ON PAKISTAN", them: ["Army fighting on its western front", "411 killed in Mar 2026", "Kandahar · Balochistan · Kunar hot"],
    ind: ["LoC diversion risk", "Attack → state fighting in ~15 days (since 2016)", "Afghan evacuation"],
    act: ["Watch the LoC when Af–Pak is AMBER/RED", "ISR on the top-3 districts", "Readiness keyed to the 15-day clock"] },
  "US–Iran": { lab: [-14, 18, "end"], war: "US–Iran", short: "US–Iran", c: "#FF6B6B", at: [56.3, 27.0], to: [72.9, 19.0], via: "oil · diaspora · sea lanes",
    themLabel: "ON THE US & GULF", them: ["War reached 14 countries (4 in 2025)", "Brent +55% in 20 trading days", "US forces held in the Gulf"],
    ind: ["Oil bill ≈ +$52 B a year (est.)", "Indian diaspora in the Gulf", "Hormuz & Chabahar route at risk"],
    act: ["On a posture alert: top up reserves, hedge", "Keep Gulf evacuation plans live", "Watch Hormuz sea lanes"] },
  "Russia–Ukraine": { lab: [14, 4, "start"], war: "Russia–Ukraine", short: "RU–UA", c: "#A794FF", at: [35.5, 48.5], to: [77.2, 28.6], via: "energy · fertiliser · spares",
    themLabel: "ON RUSSIA & EUROPE", them: ["Front widening (Donetsk 55% → 30%)", "War reaches inside Russia", "Sanctions & energy shock"],
    ind: ["Energy & fertiliser prices", "Defence spares supply", "Russia–China closeness (LAC)"],
    act: ["Diversify energy & fertiliser", "Stock critical spares", "Watch Russia–China on the LAC"] },
  "Israel–Hamas": { lab: [8, 24, "start"], war: "Israel–Hamas", short: "IL–H", c: "#3DD68C", at: [34.4, 31.4], to: [76.3, 9.9], via: "Red Sea trade",
    themLabel: "ON ISRAEL & REGION", them: ["Cooled to ~100 deaths a month", "Gaza & West Bank still watched", "Red Sea / Houthi risk"],
    ind: ["Red Sea trade route", "Indians in Israel & the Gulf", "India–Middle East corridor on hold"],
    act: ["Naval presence: Red Sea & Arabian Sea", "Evacuation plan ready (Op Ajay model)"] },
};
const ROLE_WARS: Record<string, string[]> = { WTC: ["Afghanistan–Pakistan"], MTC: ["US–Iran", "Israel–Hamas"], NTC: ["Russia–Ukraine", "Afghanistan–Pakistan"], CDS: ["US–Iran", "Afghanistan–Pakistan", "Russia–Ukraine", "Israel–Hamas"] };
const ZONE: Record<string, { lv: string; why: string; at: [number, number] }> = { WTC: { lv: "AMBER", why: "Af–Pak rising", at: [71.6, 28.6] }, MTC: { lv: "AMBER", why: "restart risk · oil", at: [67, 9] }, NTC: { lv: "DATA GAP", why: "1 fatal clash since 1975", at: [87, 33.5] } };
const PRI: Record<string, { h: string; items: string[][] }> = {
  WTC: { h: "WESTERN THEATRE · 2027 PRIORITIES", items: [["LoC first", "Raise LoC watch whenever Af–Pak is AMBER/RED."], ["Eyes on 3 districts", "Kandahar, Balochistan, Kunar."], ["15-day clock", "Pre-set readiness after any qualifying attack."]] },
  MTC: { h: "MARITIME THEATRE · 2027 PRIORITIES", items: [["Sea lanes", "Hormuz, Arabian Sea, Red Sea under watch."], ["NEO ready", "Gulf diaspora evacuation plans live."], ["Same-day action", "Posture alert → Warning Order."]] },
  NTC: { h: "NORTHERN THEATRE · 2027 PRIORITIES", items: [["Close the data gap", "Face-offs, build-ups, infrastructure, patrol clashes."], ["Watch the partners", "Russia–China closeness; Pakistan on two fronts."], ["Drill the flow", "FLASH drill on synthetic data until real indicators exist."]] },
  CDS: { h: "INDIA LEVEL (CDS) · 2027 PRIORITIES", items: [["Main effort: West & sea", "Af–Pak the rising front; US–Iran the restart risk with the widest reach."], ["Energy shield", "Reserves, crude hedging, rupee readiness on a posture alert."], ["Evacuation ready", "Gulf & Afghanistan plans live; 6 of 7 past evacuations were on our list."], ["Close the LAC gap", "Add non-fatal LAC & LoC indicators in H1 2027."], ["One monthly picture", "Watch-list & RAG in the HQ IDS brief; tripwire daily."]] },
};
const BOX: [[number, number], [number, number]] = [[28, 2], [98, 51]];

export function mountOutlook(host: HTMLElement, D: Data, role: string, per = "2027") {
  const O = (D as any).outlook, X = D.theatre;
  if (!O) { host.innerHTML = `<p class="muted">2027 outlook not built.</p>`; return; }
  if (!document.getElementById("o7-css")) document.head.insertAdjacentHTML("beforeend", `<style id="o7-css">${CSS}</style>`);
  const wars = ROLE_WARS[role] ?? ROLE_WARS.CDS, P = PRI[role] ?? PRI.CDS;
  const PER = ["2027", "Q1", "Q2", "Q3", "Q4"], pl = per === "2027" ? "2027" : `${per} 2027`;
  const pv = (w: string) => { const c = O.cases[w]; if (!c) return null; return per === "2027" ? { ...c.y2027, level: c.level2027 } : c.quarters?.[per]; };
  const lvl = (w: string) => pv(w)?.level ?? "-";
  // "So what" changes with the period: level and deaths of the theatre's wars, change vs the previous period, season.
  const SEASON: Record<string, string> = { Q1: "Seasonal norm for Af–Pak.", Q2: "Af–Pak's quietest quarter in our data (June −11%).", Q3: "Af–Pak fighting season: September runs +26% in our data.", Q4: "October stays high (+22%); December is the year's low (−24%).", "2027": "Af–Pak peaks every September–October." };
  const prev = (w: string) => { const c = O.cases[w]; if (!c) return null; if (per === "2027") return c.last12; if (per === "Q1") return Math.round(c.recent_month * 3); return c.quarters?.[`Q${+per[1] - 1}`]?.p50; };
  const chg = (w: string) => { const v = pv(w), p0 = prev(w); if (!v || !p0) return ""; const d = (v.p50 - p0) / p0; return Math.abs(d) < 0.05 ? "about level" : `${d > 0 ? "▲ up" : "▼ down"} ${Math.round(Math.abs(d) * 100)}% on ${per === "2027" ? "the last 12 months" : per === "Q1" ? "today's pace" : `Q${+per[1] - 1}`}`; };
  const ln = (w: string, nm: string) => { const v = pv(w); return v ? `<b style="color:${RAG_COLOR[v.level]}">${nm} ${v.level}</b> ~${k(v.p50)} deaths <span class="c">(${chg(w)})</span>` : ""; };
  const so = ({
    WTC: { t: `${ln("Afghanistan–Pakistan", "Af–Pak")} in ${pl}.`, s: `${SEASON[per]} For India: pressure on the LoC while Pakistan fights on two fronts; state fighting has followed a major attack within ~15 days since 2016.` },
    MTC: { t: `${ln("US–Iran", "US–Iran")} in ${pl}, up to ${k(pv("US–Iran")?.p90 ?? 0)} if it restarts.`, s: `A quiet ${per === "2027" ? "year" : "quarter"} is not a closed war. India's stake: the Gulf diaspora, the Hormuz sea lanes and ≈ $52 B a year on oil (est.). Israel–Hamas: ${ln("Israel–Hamas", "")}.` },
    NTC: { t: `No LAC forecast for ${pl}: one fatal clash in 36 years (Galwan 2020).`, s: `The risk reaches the north through Pakistan (${ln("Afghanistan–Pakistan", "Af–Pak")}) and Russia–China (${ln("Russia–Ukraine", "RU–UA")}).` },
    CDS: { t: `${ln("Afghanistan–Pakistan", "Af–Pak")} on land · ${ln("US–Iran", "US–Iran")} at sea.`, s: `${ln("Russia–Ukraine", "RU–UA")} keeps energy dear. ${SEASON[per]} Main effort: West and sea.` },
  } as Record<string, { t: string; s: string }>)[role] ?? { t: "", s: "" };
  const top = wars.map((w) => pv(w)?.level).includes("RED") ? "RED" : wars.map((w) => pv(w)?.level).includes("AMBER") ? "AMBER" : "GREEN";
  const soCol = RAG_COLOR[top];
  const chain = (w: string, i: number) => {
    const C = CHAINS[w], c = O.cases[w], v = pv(w)!, d0 = per === "2027" ? 250 + i * 450 : 60 + i * 140;
    const st = (cls: string, h: string, items: string[], d: number) => `<div class="o7-st ${cls}" style="animation-delay:${d}ms"><div class="h">${h}</div><ul>${items.map((x) => `<li>${esc(x)}</li>`).join("")}</ul></div>`;
    return `<div class="o7-ch" style="--c:${C.c};animation-delay:${d0}ms">
      <h4><span style="color:${C.c}">●</span>${esc(C.war)}
        <span class="lv">NOW <b style="background:${RAG_COLOR[c.rating_now] ?? "#888"}">${c.rating_now}</b> → ${pl} <b style="background:${RAG_COLOR[v.level]}">${v.level}</b></span>
        <span class="n" style="--lvc:${RAG_COLOR[v.level]}"><b>~${k(v.p50)}</b>deaths in ${pl} · range ${k(v.p10)}–${k(v.p90)}</span></h4>
      <div class="o7-steps">${st("them", C.themLabel, C.them, d0 + 150)}<div class="o7-ar"><span>➜</span></div>${st("ind", "ON INDIA", C.ind, d0 + 300)}<div class="o7-ar"><span>➜</span></div>${st("do", "INDIA SHOULD", C.act, d0 + 450)}</div></div>`;
  };
  host.innerHTML = `<div class="o7">
    <div class="o7-map"><div class="o7-tag">${esc((X?.theatres?.[role]?.name ?? "All theatres").toUpperCase())} · ${pl.toUpperCase()}</div>
      <div class="o7-leg"><span><i style="background:${RAG_COLOR.RED}"></i>RED</span><span><i style="background:${RAG_COLOR.AMBER}"></i>AMBER</span><span><i style="background:${RAG_COLOR.GREEN}"></i>GREEN</span><span><i style="border:1.5px dashed #E28CC1"></i>DATA GAP</span><span>┅ impact on India</span></div></div>
    <div class="o7-chains">
      <div class="o7-so" style="--sc:${soCol}"><div class="h">SO WHAT FOR INDIA · ${pl.toUpperCase()}</div><div class="t">${so.t}</div><div class="s">${so.s}</div></div>
      <div class="o7-per" role="tablist" aria-label="Period">${PER.map((p) => `<button role="tab" data-per="${p}" class="${p === per ? "on" : ""}">${p === "2027" ? "2027 · WHOLE YEAR" : p}</button>`).join("")}</div>
      ${role === "NTC" ? `<div class="o7-gap"><b>Northern theatre: no 2027 numbers.</b> The data hold one fatal LAC clash since 1975 (Galwan, Jun 2020), too few to project; the outlook works through the wars that touch it.</div>` : ""}
      ${wars.map(chain).join("")}
      <div class="o7-india" style="animation-delay:${300 + wars.length * 450}ms"><div class="h">${P.h}</div>
        <div class="row">${P.items.map(([a, b]) => `<div><b>${esc(a)}</b>${esc(b)}</div>`).join("")}</div></div>
    </div>
    <div class="o7-foot">${esc(O.meta.footnote ?? "Level = middle case of a scenario range from history, for the whole year or each quarter of 2027: what happened next to similar conflicts in 117 countries, 1989–2025 (the range held 89% out of time). Not a validated forecast. Chains are our analysis.")}</div>
  </div>`;
  host.querySelectorAll<HTMLElement>(".o7-per button").forEach((b) => b.addEventListener("click", () => mountOutlook(host, D, role, b.dataset.per!)));
  const box = host.querySelector(".o7-map") as HTMLElement;
  const draw = () => {
    if (!box.clientWidth) return requestAnimationFrame(draw);
    const keep = [...box.children];
    const m = regionMap(box, D.world, BOX);
    keep.forEach((c) => box.appendChild(c));
    { const st = document.createElementNS("http://www.w3.org/2000/svg", "text"); st.setAttribute("x", String(m.w - 24)); st.setAttribute("y", String(m.h - 40)); st.setAttribute("text-anchor", "end"); st.setAttribute("class", "stamp fade"); st.textContent = pl.toUpperCase(); m.layer.appendChild(st); }
    const ns = "http://www.w3.org/2000/svg";
    const mk = (tag: string, a: Record<string, any>, parent: Element) => { const e = document.createElementNS(ns, tag); for (const [kk, v] of Object.entries(a)) e.setAttribute(kk, String(v)); parent.appendChild(e); return e; };
    for (const f of X?.aor?.features ?? []) {
      const code = f.properties.code, z = ZONE[code]; if (!z) continue;
      const on = role === "CDS" || code === role, col = z.lv === "DATA GAP" ? "#E28CC1" : RAG_COLOR[z.lv];
      const p = mk("path", { d: m.path(f) || "", class: on ? "zone breath" : "zone", style: `--fo:${(on ? 0.26 : 0.06) * (code === "MTC" ? 0.45 : 1)}`, fill: col, "fill-opacity": (on ? 0.26 : 0.06) * (code === "MTC" ? 0.45 : 1), stroke: col, "stroke-width": on ? 2.6 : 1 }, m.layer);
      if (z.lv === "DATA GAP" || !on) p.setAttribute("stroke-dasharray", "5 4");
      const ct = m.proj(z.at);
      if (ct && isFinite(ct[0])) {
        const t = mk("text", { x: ct[0], y: ct[1], "text-anchor": "middle", class: "zl fade", style: "animation-delay:.3s", fill: col, "fill-opacity": on ? 1 : 0.45 }, m.top); t.textContent = `${code} · ${z.lv}`;
        const t2 = mk("text", { x: ct[0], y: ct[1] + 16, "text-anchor": "middle", class: "lbl fade", style: "animation-delay:.4s", fill: "#C9D6E3", "fill-opacity": on ? 1 : 0.45 }, m.top); t2.textContent = z.why;
      }
    }
    Object.keys(CHAINS).forEach((w, i) => {
      const C = CHAINS[w], on = wars.includes(w), col = RAG_COLOR[lvl(w)] ?? C.c;
      const a = m.proj(C.at), b = m.proj(C.to); if (!a || !b) return;
      const mx = (a[0] + b[0]) / 2, my = Math.min(a[1], b[1]) - Math.abs(b[0] - a[0]) * 0.22;
      const d = `M${a[0]},${a[1]} Q${mx},${my} ${b[0]},${b[1]}`;
      mk("path", { d, class: "arc-bg", stroke: C.c, "stroke-opacity": on ? 0.14 : 0.03 }, m.layer);
      const dl = 0.15 + i * 0.22, v0 = pv(w), sw = on && v0 ? Math.max(2.4, Math.min(7, 1.2 + 1.1 * Math.log10(1 + v0.p50))) : 2;
      if (on) mk("path", { d, fill: "none", stroke: C.c, "stroke-width": sw * 3.2, "stroke-opacity": 0.12, class: "fade", style: `animation-delay:${dl + 0.6}s;filter:blur(4px)` }, m.layer);
      mk("path", { d, class: on ? "arc draw" : "arc", stroke: C.c, "stroke-width": sw, "stroke-opacity": on ? 1 : 0.15, style: on ? `animation-delay:${dl}s, ${dl + 1.1}s` : "" }, m.layer);
      if (on) { // particles travelling from the war into India; more and faster when the period is deadlier
        const n = v0 && v0.p50 > 1000 ? 4 : v0 && v0.p50 > 100 ? 3 : 2, dur = v0 && v0.p50 > 1000 ? 2.2 : 3.2;
        for (let j = 0; j < n; j++) {
          const c = mk("circle", { r: Math.max(3, sw * 0.9), fill: "#fff", "fill-opacity": 0.95, stroke: C.c, "stroke-width": 2 }, m.top);
          const am = document.createElementNS(ns, "animateMotion");
          am.setAttribute("dur", `${dur}s`); am.setAttribute("repeatCount", "indefinite"); am.setAttribute("path", d);
          am.setAttribute("begin", `${dl + 1.1 + (j * dur) / n}s`); am.setAttribute("keyPoints", "0;1"); am.setAttribute("keyTimes", "0;1"); am.setAttribute("calcMode", "linear");
          c.setAttribute("opacity", "0"); c.appendChild(am);
          const op = document.createElementNS(ns, "set"); op.setAttribute("attributeName", "opacity"); op.setAttribute("to", "1"); op.setAttribute("begin", `${dl + 1.1 + (j * dur) / n}s`); c.appendChild(op);
        }
      }
      // hotspot: size scales with the period's middle-case deaths
      const v = pv(w), rr = on && v ? Math.max(8, Math.min(30, 5 + 4.2 * Math.log10(1 + v.p50))) : 5;
      if (on) mk("circle", { cx: a[0], cy: a[1], r: rr, fill: col, "fill-opacity": 0.25, stroke: col, "stroke-width": 2, class: "halo", style: `animation-delay:${dl}s` }, m.top);
      mk("circle", { cx: a[0], cy: a[1], r: on ? rr * 0.55 : 3, fill: col, "fill-opacity": on ? 0.9 : 0.4, class: "pop", style: `animation-delay:${dl}s` }, m.top);
      if (on) {
        mk("circle", { cx: b[0], cy: b[1], r: 7, fill: C.c, stroke: "#05070A", "stroke-width": 2, class: "pop", style: `animation-delay:${dl + 1.0}s` }, m.top);
        mk("circle", { cx: b[0], cy: b[1], r: 7, fill: "none", stroke: C.c, "stroke-width": 2, class: "halo", style: `animation-delay:${dl + 1.1}s` }, m.top);
        let [dx, dy, an] = C.lab;
        if (m.w < 760 && an === "end") { const tw = 10.5 * `${C.short} · ${pl} ${lvl(w)} · ~${k(v?.p50 ?? 0)}`.length; if (a[0] + dx - tw < 4) { an = "start"; dx = 12; } }
        const t = mk("text", { x: a[0] + dx, y: a[1] + dy, "text-anchor": an, class: "zl fade", style: `animation-delay:${dl + .2}s`, fill: col }, m.top); t.textContent = `${C.short} · ${pl} ${lvl(w)} · ~${k(v?.p50 ?? 0)}`;
        const t2 = mk("text", { x: a[0] + dx, y: a[1] + dy + 15, "text-anchor": an, class: "lbl fade", style: `animation-delay:${dl + .5}s`, fill: C.c }, m.top); t2.textContent = `→ India: ${C.via}`;
      }
    });
  };
  requestAnimationFrame(draw);
}

export function openOutlookModal(D: Data, role: string) {
  document.getElementById("ol-modal")?.remove();
  const m = document.createElement("div");
  m.id = "ol-modal"; m.setAttribute("role", "dialog"); m.setAttribute("aria-modal", "true"); m.setAttribute("aria-label", "2027 outlook");
  m.style.cssText = "position:fixed;inset:0;z-index:80;background:rgba(5,11,18,.97);backdrop-filter:blur(6px);overflow:auto;padding:24px 2.5vw";
  const T = D.theatre?.theatres?.[role];
  m.innerHTML = `<div style="max-width:1500px;margin:0 auto"><div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
      <div class="eyebrow" style="margin:0">${esc((T ? T.name : "All theatres").toUpperCase())} · 2027 OUTLOOK · HOW THE WARS REACH INDIA</div>
      <button class="btn" id="ol-x" aria-label="Close">✕ CLOSE</button></div><div id="ol-host"></div></div>`;
  document.body.appendChild(m);
  mountOutlook(m.querySelector("#ol-host") as HTMLElement, D, role);
  const close = () => { m.remove(); document.removeEventListener("keydown", onKey); };
  const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") close(); };
  document.addEventListener("keydown", onKey);
  (m.querySelector("#ol-x") as HTMLElement).addEventListener("click", close);
  m.addEventListener("click", (e) => { if (e.target === m) close(); });
}
