// Shared page chrome: classification strip, nav, footer, presenter mode, Q&A drawer, theme.
import { RAG_COLOR } from "./data";
import LOGO_L from "./img/jimmy.png";   // Corps of Signals "Jimmy", top left
import LOGO_R from "./img/mcte.png";    // MCTE formation sign, top right

export const strip = (F: any) => `<div class="strip" role="note"><span>UNCLASSIFIED — COMPETITION DATA ONLY</span><span class="sep">·</span><span>DATA AS OF 30 SEP 2026</span><span class="sep">·</span><span>RUN ${F.run_id}</span></div>`;

export const navBar = (F: any, mode: "story" | "console" | "command") => `<header class="nav">
  <img class="logo" src="${LOGO_L}" alt="Corps of Signals" />
  <div class="brand"><span class="dot"></span>CONFLICT EW</div>
  <div class="ragstrip">${F.scorecard.map((s: any) => `<span class="chip-rag" style="color:${RAG_COLOR[s.rating]}" title="${s.name}: ${s.rating}">${s.short} ${s.rating}</span>`).join("")}</div>
  <div class="grow"></div>
  <span class="mono small muted hide-sm" id="net"></span>
  ${mode === "command" ? `<a class="btn" href="#bluf">BRIEFING ▸</a><a class="btn" href="console/index.html" id="to-console">OPS CONSOLE ▸</a>`
    : mode === "story" ? `<a class="btn" href="#cmd" id="to-cmd">◂ COMMAND VIEW</a><a class="btn" href="console/index.html" id="to-console">OPS CONSOLE ▸</a>`
    : `<a class="btn" href="../index.html" id="to-story">◂ COMMAND VIEW</a>`}
  <button class="btn hide-sm" id="theme" aria-label="Toggle light or dark theme">◐</button>
  <button class="btn hide-sm" id="pres" aria-label="Presentation mode: larger text, shorter animations, timer (P)" title="Presentation mode (P)">P</button>
  <img class="logo" src="${LOGO_R}" alt="MCTE formation sign" />
</header>`;

export const footer = (F: any) => `<footer>
  <div>CONFLICT EW · ${F.competition.toUpperCase()} · ${F.team.join(" · ")}</div>
  <div>RUN ${F.run_id} · EXPORTED ${F.exported} · DATA AS OF ${F.data_as_of} · ${F.sources}</div>
</footer>`;

export function initTheme() {
  let t = "dark";
  try { t = localStorage.getItem("cw-theme") || "dark"; } catch {}
  document.documentElement.dataset.theme = t;
  document.addEventListener("click", (e) => {
    if ((e.target as HTMLElement).closest("#theme")) {
      const n = document.documentElement.dataset.theme === "light" ? "dark" : "light";
      document.documentElement.dataset.theme = n;
      try { localStorage.setItem("cw-theme", n); } catch {}
      try { window.name = "cw-hash:" + location.hash; } catch {}   // keep the view across the reload (see main.ts)
      location.reload();
    }
  });
  // Presentation mode: larger text and shorter animations for screen sharing. Persists across the three views.
  const root = document.documentElement;
  try { if (localStorage.getItem("cw-pres") === "1") root.classList.add("pres"); } catch {}
  const pres = () => { const on = root.classList.toggle("pres"); try { localStorage.setItem("cw-pres", on ? "1" : "0"); } catch {}
    document.getElementById("pres")?.classList.toggle("on", on); dispatchEvent(new Event("resize")); };
  document.addEventListener("click", (e) => { if ((e.target as HTMLElement).closest("#pres")) pres(); });
  addEventListener("keydown", (e) => { const tg = (e.target as HTMLElement).tagName; if (tg === "INPUT" || tg === "SELECT" || tg === "TEXTAREA" || e.metaKey || e.ctrlKey) return; if (e.key === "p" || e.key === "P") pres(); });
  setTimeout(() => document.getElementById("pres")?.classList.toggle("on", root.classList.contains("pres")), 0);
  const net = () => { const e = document.getElementById("net"); if (e) e.innerHTML = navigator.onLine ? "● ONLINE" : `<span style="color:var(--amber)">● OFFLINE</span>`; };
  addEventListener("online", net); addEventListener("offline", net); setTimeout(net, 500);
}

const NOTES: Record<string, string> = {
  hero: "Open: four wars, one exposed neighbour. Globe shows where the dying happened, 2014–2026. (Maj Mehta)",
  bluf: "BLUF: RU–UA RED 6,780 next month; Af–Pak AMBER rising; US–Iran AMBER; IL–Hamas GREEN. Flip Af–Pak card to show the points.",
  india: "Why India: 14 countries, 5 Gulf states, 104 killed off Sri Lanka, LoC-adjoining deaths 2→52. Domain: Gulf diaspora, NEO.",
  signatures: "Four signatures: attrition, spikes, creep, decline. 2026 band = withheld test.",
  front: "Front widening: Donetsk 55%→30%. Flip FOG OF WAR toggle: 92% of 2026 deaths unlocated. Caveat on attrition ratio.",
  afpak: "Two fronts: dyad peak 411 (Mar 2026). Flip RAW/HARMONISED to show why FATA is merged.",
  media: "Headlines follow incidents (0.96) not deaths (0.01); gap does not lead escalation (p = 0.50).",
  gdelt: "GDELT (new): tracks UCDP for US–Iran (rho 0.86) and Af–Pak, not RU–UA. A week earlier adds nothing (p 0.55): a nowcast. Show US–Iran rising in early Nov.",
  displacement: "Women and children: 72% / 63%; HADR packs.",
  prediction: "Hand over to Capt Sangwan. Playhead: coverage ticks to 83%. Show Track B honestly.",
  warning: "Replay Mar 2026: 3 of top 10 escalated. Move the threshold slider.",
  decision: "What-if: Af–Pak +30% for 3 months → 359. Then scorecard lab: reset to doctrine.",
  recs: "Hand over to Capt Singh. Sense, Warn, Shield, Sustain; end state.",
  method: "Limits first. Verify panel: run ID matches the report. Open Q&A if asked.",
  closing: "Close. Invite questions.",
};

export function presenter(ids: string[], F: any) {
  let on = false, t0 = 0, iv: any = null;
  const timer = document.createElement("div"); timer.className = "timer"; timer.setAttribute("aria-live", "off"); document.body.appendChild(timer);
  const bc = "BroadcastChannel" in window ? new BroadcastChannel("cw-notes") : null;
  const all = ids;
  const vis = () => all.filter((id) => { const e = document.getElementById(id); return !!e && e.getClientRects().length > 0; });
  const cur = () => { ids = vis(); let best = 0; ids.forEach((id, i) => { const e = document.getElementById(id); if (e && e.getBoundingClientRect().top < innerHeight * 0.5) best = i; }); return best; };
  const go = (i: number) => { ids = vis(); const id = ids[Math.max(0, Math.min(ids.length - 1, i))]; document.getElementById(id)?.scrollIntoView({ behavior: "smooth" }); bc?.postMessage({ id, note: NOTES[id] ?? "" }); };
  const tick = () => {
    const s = Math.floor((Date.now() - t0) / 1000), m = Math.floor(s / 60), left = 15 * 60 - s;
    timer.textContent = `${left < 0 ? "+" : ""}${String(Math.floor(Math.abs(left) / 60)).padStart(2, "0")}:${String(Math.abs(left) % 60).padStart(2, "0")}`;
    timer.classList.toggle("amber", m >= 12 && m < 14); timer.classList.toggle("red", m >= 14);
  };
  const toggle = () => { on = !on; timer.classList.toggle("on", on);
    if (on) { let s = 0; try { s = +(sessionStorage.getItem("cw-t0") ?? 0); } catch {} t0 = s || Date.now(); try { sessionStorage.setItem("cw-t0", String(t0)); } catch {} tick(); iv = setInterval(tick, 1000); }
    else { clearInterval(iv); try { sessionStorage.removeItem("cw-t0"); } catch {} } };
  document.getElementById("pres")?.addEventListener("click", toggle);
  if (document.documentElement.classList.contains("pres")) toggle();
  addEventListener("keydown", (e) => {
    const tg = (e.target as HTMLElement).tagName; if (tg === "INPUT" || tg === "SELECT" || tg === "TEXTAREA" || e.metaKey || e.ctrlKey) return;
    if (e.key === "p" || e.key === "P") toggle();
    else if (e.key === "n" || e.key === "N") openNotes(ids);
    else if (on && (e.key === "ArrowDown" || e.key === "ArrowRight" || e.key === "PageDown")) { e.preventDefault(); go(cur() + 1); }
    else if (on && (e.key === "ArrowUp" || e.key === "ArrowLeft" || e.key === "PageUp")) { e.preventDefault(); go(cur() - 1); }
    else if (on && /^[1-9]$/.test(e.key)) { e.preventDefault(); go(+e.key - 1); }
  });
  let last = -1;
  addEventListener("scroll", () => { const c = cur(); if (c !== last) { last = c; bc?.postMessage({ id: ids[c], note: NOTES[ids[c]] ?? "" }); } }, { passive: true });
}

function openNotes(ids: string[]) {
  const w = window.open("", "cw-notes", "width=560,height=420");
  if (!w) return;
  w.document.write(`<!doctype html><title>Speaker notes</title><body style="background:#05070A;color:#F5F5F7;font:22px/1.45 Inter,system-ui;padding:24px">
    <div id="id" style="font:700 14px monospace;letter-spacing:.2em;color:#F2B33D">SPEAKER NOTES</div><p id="n">Scroll the main window.</p>
    <script>const bc=new BroadcastChannel("cw-notes");bc.onmessage=e=>{document.getElementById("id").textContent=e.data.id.toUpperCase();document.getElementById("n").textContent=e.data.note;}<\/script>`);
}

const QA: [string, string][] = [
  ["Why not an LSTM or transformer?", "Four monthly series of about 150 points each is far too little data for deep sequence models. We tested seven forecasters on a walk-forward back-test; a small ensemble of simple and tree models beat 'no change' by 29% on 2026. Deep models would add variance without evidence of benefit."],
  ["Did you tune on 2026?", "No. Every design choice (features, ensemble members, interval width, classifier features) was made on the 2022–25 back-test folds. 2026 was scored once, at the end. The site's export script asserts those exact 2026 numbers."],
  ["Is the 10:1 ratio real?", "It is what UCDP recorded: an upper bound of reporting, not a verified exchange ratio. Ukrainian losses are under-reported in open sources. We show the caveat on every chart that uses it."],
  ["Is this map correct?", "Every map draws India's boundary from Natural Earth's India point-of-view layer, which shows all of J&K and Ladakh, including PoK, Gilgit-Baltistan and Aksai Chin, as India. Pakistan's areas are clipped to match; PoK incidents are shown as points labelled PoK."],
  ["Why is Israel–Hamas GREEN?", "Deaths fell to about 130 a month in 2026, the forecast is 128 for October, there are no areas above 15% escalation probability and no ≥1,000-death month in the last year. The scorecard is mechanical; the lab shows how sensitive each rating is."],
  ["Why can't you predict the US–Iran war?", "It began by decision, with no build-up in the death series. No model of past deaths can forecast that. This is why the warning effort watches spread and hotspots, not headlines, and why we say so as a limit."],
  ["How good is the early warning, in plain terms?", "Each month, 1.4 of the top-10 flagged areas escalate, against 0.4 if we picked at random: 3.5 times better. AUC 0.795 on 2026."],
  ["What is the Attention Gap Index?", "An original measure: media references explained by events and deaths, with the residual as 'attention gap'. Media track incidents (elasticity 0.96), not severity (0.01), and the gap does not lead escalation (p = 0.50)."],
  ["Where does the what-if come from?", "The exact frozen Python ensemble was run for every slider position (4 conflicts × 16 shocks × 6 durations) and the results ship with the site, so the browser shows what the submitted model says. Af–Pak +30% for 3 months gives 359."],
  ["What would you do with more time or data?", "Add ACLED and satellite fire data for location, model the Indian Ocean shipping picture, and run the watch-list monthly as a standing I&W product."],
];
export function qaDrawer(F: any) {
  const d = document.createElement("aside"); d.className = "drawer"; d.setAttribute("aria-label", "Jury Q&A");
  d.innerHTML = `<button class="btn" style="position:absolute;top:28px;right:28px" id="qa-x">✕ CLOSE</button><div class="eyebrow">JURY Q&amp;A</div>${QA.map(([q, a]) => `<details><summary>${q}</summary><p class="small">${a}</p></details>`).join("")}`;
  document.body.appendChild(d);
  d.querySelector("#qa-x")!.addEventListener("click", () => d.classList.remove("open"));
  addEventListener("keydown", (e) => { if (e.key === "Escape") d.classList.remove("open"); });
  return { open: () => d.classList.add("open") };
}
