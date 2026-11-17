// Theatre Commander page for the Ops console: role switcher (WTC / MTC / CDS), daily OODA brief,
// notional AOR map, inbox with FLASH alerts, mock SMS / WhatsApp previews and the OODA-loop timing strip.
// Data: web/public/data/theatre.json, written by src/theatre.py (python scripts/daily_briefs.py).
import { type Data, RAG_COLOR } from "./data";
import { regionMap, ramp, tip } from "./maps";
import { $, $$, tag } from "./widgets";

const ROLES = ["WTC", "MTC", "CDS"] as const;   // v2: no Northern (LAC) view; the issued data hold no LAC incidents
const BBOX: Record<string, [[number, number], [number, number]]> = {
  WTC: [[59, 21], [80, 39]], NTC: [[72, 25], [99, 38]], MTC: [[30, -8], [100, 31]], CDS: [[30, -8], [100, 40]],
};
const CSS = `
.th-cards { display:grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap:14px; margin: 14px 0; }
.th-card { background: var(--panel); border:1px solid var(--line); border-radius:12px; padding:14px 16px; }
.th-card .l { font: 700 11px var(--mono); letter-spacing:.16em; color: var(--tx3); }
.th-card .b { font-size: 34px; font-weight: 800; line-height:1.15; margin: 4px 0; }
.th-card .s { color: var(--tx2); font-size: 14px; }
.ooda-h { font: 800 13px var(--mono); letter-spacing:.2em; margin-bottom:6px; }
.th-obs li { margin: 6px 0; }
.th-act td { vertical-align: top; }
.msg2 { border-left: 4px solid var(--line2); background: rgba(255,255,255,.02); padding: 8px 12px; margin-bottom: 8px; border-radius: 0 8px 8px 0; font-size: 14px; }
.msg2.flash { border-left-color: var(--red); background: rgba(255,77,94,.08); }
.msg2 .t { font: 500 11px var(--mono); color: var(--tx3); letter-spacing:.08em; }
.phone2 { background:#0B1520; border:2px solid var(--line2); border-radius: 24px; padding: 14px; }
.bub { background:#1F3B2E; color:#E8F5EC; border-radius: 12px; padding: 10px 12px; white-space: pre-wrap; font-size: 13px; line-height:1.4; }
.bub.sms { background:#24364A; font-family: var(--mono); font-size: 12px; }
.phone2 { max-height: 520px; overflow-y: auto; }
.chipN { display:inline-block; font: 800 11px var(--mono); letter-spacing:.12em; padding: 3px 8px; border-radius: 6px; border:1px solid var(--amber); color: var(--amber); margin-right:6px; }
.chipS { border-color: var(--red); color: var(--red); }
.ooda-row { display:grid; grid-template-columns: 110px 1fr 1fr 150px; gap: 10px; padding: 8px 0; border-bottom: 1px solid var(--line); font-size: 14px; }
@media (max-width: 980px) { .th-cards { grid-template-columns: 1fr 1fr; } .ooda-row { grid-template-columns: 1fr; } }
`;

function getRole(q: URLSearchParams): string {
  const r = q.get("role") || (window as any).CW_ROLE || (() => { try { return localStorage.getItem("cw-role"); } catch { return null; } })() || "CDS";
  return (ROLES as readonly string[]).includes(r) ? r : "CDS";
}

export function renderTheatre(P: HTMLElement, D: Data, q: URLSearchParams) {
  const X = D.theatre;
  if (!X) { P.innerHTML = `<h2>Theatre briefs not built</h2><p class="muted">Run <code>python scripts/daily_briefs.py</code>.</p>`; return; }
  if (!document.getElementById("th-css")) document.head.insertAdjacentHTML("beforeend", `<style id="th-css">${CSS}</style>`);
  let role = getRole(q);
  let di = X.dates.length - 1;
  const M = X.meta;

  const draw = () => {
    try { localStorage.setItem("cw-role", role); } catch {}
    const T = X.theatres[role];
    const b = X.briefs[role][di];
    const col = RAG_COLOR[b.rating];
    const flashes = X.flashes.filter((f: any) => (role === "CDS" || f.code === role) && f.date <= b.date);
    const msgs = X.inbox.filter((m: any) => (role === "CDS" || m.code === role) && m.date <= b.date).slice(0, 7);
    const tg = (t: string) => t === "SYNTHETIC" ? `<span class="chipN chipS">SYNTHETIC</span>` : t === "MODEL" ? tag("domain", "MODEL") : tag("data");
    P.innerHTML = `<div class="eyebrow">THEATRE COMMANDER · NOTIONAL · DAILY 0600 IST BRIEF</div>
      <h2>${role}: ${T.front}</h2>
      <div class="sub"><span class="chipN">NOTIONAL</span>${M.notional}</div>
      <div class="panel" style="padding:12px;display:flex;gap:16px;flex-wrap:wrap;align-items:center">
        <div class="seg" id="th-r">${ROLES.map((r) => `<button data-r="${r}" class="${r === role ? "on" : ""}">${r}</button>`).join("")}</div>
        <div class="ctl" style="min-width:300px;margin:0;flex:1"><label>Brief <output>${b.dtg}</output></label>
          <input type="range" id="th-d" min="0" max="${X.dates.length - 1}" value="${di}" aria-label="Brief day"></div>
        <span class="muted small mono">${T.name}</span></div>
      <div class="sowhat" style="margin-top:14px;border-left-color:${col}"><b style="color:${col}">BLUF</b>${b.bluf}</div>
      <div class="th-cards">
        <div class="th-card"><div class="l">THREAT LEVEL</div><div class="b" style="color:${col}">${b.rating} ${b.arrow}</div><div class="s">${b.trend} · score ${b.score}</div></div>
        <div class="th-card"><div class="l">CONFIDENCE</div><div class="b" style="color:var(--teal)">${b.confidence}</div><div class="s">${b.confidence_why}</div></div>
        <div class="th-card"><div class="l">FLASH · 7 DAYS</div><div class="b" style="color:${flashes.length ? "var(--red)" : "var(--green)"}">${flashes.length}</div><div class="s">P ≥ ${M.flash_threshold} or a RAG change</div></div>
        <div class="th-card"><div class="l">DATA LATENCY</div><div class="b" style="color:var(--violet)">${M.ucdp_lag_days} d → &lt;1 d</div><div class="s">UCDP to ${M.ucdp_end}; GDELT to ${M.data_end} · built in ${M.build_seconds} s</div></div>
      </div>
      <div class="grid g2">
        <div>
          <div class="panel" style="margin-bottom:12px"><div class="ooda-h" style="color:var(--teal)">① OBSERVE · TOP CHANGES 24 H / 7 D</div>
            <ol class="th-obs">${b.observe.map((o: any) => `<li>${o.text} <span class="muted small mono">${o.window} · ${o.source}</span> ${tg(o.tag)}</li>`).join("")}</ol></div>
          <div class="panel" style="margin-bottom:12px"><div class="ooda-h" style="color:var(--amber)">② ORIENT · ${b.rating} ${b.arrow} ${b.trend.toUpperCase()} · CONF ${b.confidence}</div>
            <ul>${b.orient.points.map((p: any) => `<li><b class="mono">${p.pts > 0 ? "+" : ""}${p.pts}</b> ${p.why}</li>`).join("")}</ul><p class="small muted">${b.orient.model_why}</p></div>
          <div class="panel"><div class="ooda-h" style="color:var(--green)">③ DECIDE · ④ ACT</div>
            <table class="t small th-act"><tr><th>#</th><th>Action</th><th>Owner · when</th><th>Trigger to escalate</th></tr>
            ${b.decide.map((a: any) => `<tr><td class="mono"><b>${a.rank}</b></td><td><b>${a.kind}</b><br>${a.text}</td><td>${a.owner}<br><b style="color:var(--amber)">${a.timeline}</b></td><td class="muted">${a.trigger}</td></tr>`).join("")}</table></div>
        </div>
        <div>
          <div class="panel" style="padding:10px"><div class="ph"><span class="t">${role} AOR · notional</span><span class="muted small mono">◆ = synthetic · ● = model nowcast</span></div>
            <div class="mapbox" id="th-map" style="height:460px"></div></div>
          <div class="grid g2" style="margin-top:12px">
            <div class="panel"><div class="ph"><span class="t">Inbox</span><span class="muted small mono">${M.schedule}</span></div>
              ${msgs.map((m: any) => `<div class="msg2 ${m.kind === "FLASH" ? "flash" : ""}"><div class="t">${m.dtg} · ${m.priority}</div><b>${m.kind === "FLASH" ? "⚡ " : ""}${m.subject}</b></div>`).join("")}</div>
            <div class="panel"><div class="ph"><div class="seg" id="th-ch"><button data-c="wa" class="on">WHATSAPP</button><button data-c="sms">SMS</button></div></div>
              <div class="phone2"><div class="bub" id="th-bub"></div></div><p class="small muted">Mock preview: nothing is sent from the site.</p></div>
          </div>
        </div>
      </div>
      <div class="panel" style="margin-top:16px"><div class="ph"><span class="t">How this shortens the OODA loop</span><span class="muted small mono">event → decision: ${M.ooda_totals.today_days[0]}–${M.ooda_totals.today_days[1]} days → ${M.ooda_totals.cw_hours[0]}–${M.ooda_totals.cw_hours[1]} hours ${tag("domain", "DOMAIN EST.")}</span></div>
        <div class="ooda-row muted mono small"><span>STAGE</span><span>TODAY</span><span>WITH CONFLICT WATCH</span><span>HOURS</span></div>
        ${M.ooda.map((o: any) => `<div class="ooda-row"><b class="mono" style="color:var(--teal)">${o.stage}</b><span>${o.today}</span><span>${o.cw}</span><span class="mono">${o.today_h[0]}–${o.today_h[1]} → <b style="color:var(--amber)">${o.cw_h[0]}–${o.cw_h[1]}</b></span></div>`).join("")}
      </div>`;
    // map
    const m = regionMap($("#th-map"), D.world, BBOX[role]);
    const ns = "http://www.w3.org/2000/svg";
    for (const f of X.aor.features) {
      const on = role === "CDS" || f.properties.code === role;
      const p = document.createElementNS(ns, "path");
      p.setAttribute("d", m.path(f) || "");
      p.setAttribute("fill", f.properties.color); p.setAttribute("fill-opacity", on ? "0.14" : "0.03");
      p.setAttribute("stroke", f.properties.color); p.setAttribute("stroke-width", on ? "2.5" : "1");
      if (!on) p.setAttribute("stroke-dasharray", "4 4");
      m.layer.appendChild(p);
    }
    for (const d of b.districts) {
      if (d.lon == null) continue;
      const xy = m.proj([d.lon, d.lat]); if (!xy) continue;
      const r = 5 + 34 * Math.min(d.p_now, 0.4);
      const c = ramp(Math.sqrt(d.p_now / 0.35));
      const s = document.createElementNS(ns, d.synthetic ? "rect" : "circle");
      if (d.synthetic) { s.setAttribute("x", String(xy[0] - r / 1.4)); s.setAttribute("y", String(xy[1] - r / 1.4)); s.setAttribute("width", String(r * 1.4)); s.setAttribute("height", String(r * 1.4));
        s.setAttribute("transform", `rotate(45 ${xy[0]} ${xy[1]})`); }
      else { s.setAttribute("cx", String(xy[0])); s.setAttribute("cy", String(xy[1])); s.setAttribute("r", String(r)); }
      s.setAttribute("fill", c); s.setAttribute("fill-opacity", "0.85"); s.setAttribute("stroke", "#fff"); s.setAttribute("stroke-width", "1");
      s.addEventListener("mousemove", (e) => tip(`<b>${d.synthetic ? "[SYNTHETIC] " : ""}${d.name}</b> · ${d.iso}<br>nowcast P ${d.p_now.toFixed(2)}`, e as MouseEvent));
      s.addEventListener("mouseleave", () => tip(null));
      m.top.appendChild(s);
    }
    const bub = $("#th-bub");
    const setCh = (c: string) => { $$("#th-ch button").forEach((x) => x.classList.toggle("on", x.dataset.c === c));
      bub.className = "bub" + (c === "sms" ? " sms" : ""); const raw = String(c === "sms" ? X.sms[role] : X.whatsapp[role]).replace(/&/g, "&amp;").replace(/</g, "&lt;");
      bub.innerHTML = c === "sms" ? raw : raw.replace(/\*([^*\n]+)\*/g, "<b>$1</b>").replace(/(^|\s)_([^_\n]+)_/g, '$1<i style="opacity:.7">$2</i>'); };
    setCh("wa");
    $$("#th-ch button").forEach((x) => x.addEventListener("click", () => setCh(x.dataset.c!)));
    $$("#th-r button").forEach((x) => x.addEventListener("click", () => { role = x.dataset.r!; draw(); }));
    $("#th-d").addEventListener("input", (e) => { di = +(e.target as HTMLInputElement).value; draw(); });
  };
  draw();
}
