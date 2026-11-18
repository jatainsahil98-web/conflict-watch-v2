// Staff documents generated from the daily theatre brief (theatre.json), in Indian Armed Forces layouts:
//   SITREP          - the brief itself, as a situation report for the commander (dashboard view)
//   WARNING ORDER   - service message form: to forward-deployed troops
//   OPERATION ORDER - service operation order layout: to the CDS, the Service Chiefs and the commanders
// Everything is drafted from the model outputs; the commander or staff officer approves and releases it.
// Addressees, HQs and units are NOTIONAL. Nothing is transmitted by the site itself: SEND opens the user's own
// WhatsApp or e-mail with the text filled in, so a person always chooses the recipient and presses send.
import { type Data, CASE_NAME } from "./data";
import { $, $$ } from "./widgets";

type B = any;
export type DocKind = "sitrep" | "warno" | "opo";

const OPNAME: Record<string, string> = { WTC: "SENTINEL WEST", NTC: "SENTINEL NORTH", MTC: "SENTINEL SEA", CDS: "SENTINEL APEX" };
const HQ: Record<string, string> = { WTC: "HQ Western Theatre Comd", NTC: "HQ Northern Theatre Comd", MTC: "HQ Maritime Theatre Comd", CDS: "HQ IDS (Office of CDS)" };
const HQS: Record<string, string> = { WTC: "HQ WTC", NTC: "HQ NTC", MTC: "HQ MTC", CDS: "HQ IDS" };
/** Forward-deployed addressees for the Warning Order (notional). Last entry = signals, "By Originator". */
const FWD: Record<string, string[]> = {
  WTC: ["Fwd Holding Bdes, LoC (J&K)", "Holding Fmns, IB Punjab", "Holding Fmns, IB Rajasthan", "Sir Creek Sector Units", "Theatre ISR Cell", "Theatre Sig Regt (By Originator)"],
  NTC: ["Fwd Bdes, Eastern Ladakh", "Fwd Bdes, Central Sector", "Fwd Bdes, Sikkim", "Fwd Bdes, Arunachal Pradesh", "Theatre ISR Cell", "Theatre Sig Regt (By Originator)"],
  MTC: ["Fwd Naval Task Gp, Arabian Sea", "Fwd Naval Task Gp, Gulf of Aden", "A&N Fwd Elements", "Coastal Surveillance Network", "Air Det, NEO Staging", "Theatre Sig Regt (By Originator)"],
  CDS: ["HQ WTC (for Fwd Fmns)", "HQ NTC (for Fwd Fmns)", "HQ MTC (for Fwd Fmns)", "Strategic Forces Liaison", "Def Comn Network (By Originator)"],
};
const OPO_TO = ["CDS", "COAS", "CNS", "CAS", "Cdr WTC", "Cdr NTC", "Cdr MTC"];
const NOTICE: Record<string, number> = { RED: 2, AMBER: 12, GREEN: 24 };
const PREC: Record<string, string> = { RED: "OP IMMEDIATE", AMBER: "PRIORITY", GREEN: "ROUTINE" };
const MON = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"];

const esc = (s: any) => String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
/** Brief issue time = 0600 IST on the day after the data date (as in src/theatre.py). */
const t0 = (b: B) => { const d = new Date(b.date + "T06:00:00"); d.setDate(d.getDate() + 1); return d; };
const plusH = (d: Date, h: number) => new Date(d.getTime() + h * 3600e3);
/** Date-time group, service style: ddHHMM (six figures) + month + year, e.g. 130600 NOV 26. */
const dtg = (d: Date) => `${String(d.getDate()).padStart(2, "0")}${String(d.getHours()).padStart(2, "0")}${String(d.getMinutes()).padStart(2, "0")} ${MON[d.getMonth()]} ${String(d.getFullYear()).slice(2)}`;
const dt6 = (d: Date) => dtg(d).slice(0, 6);
const hr = (d: Date) => `${String(d.getHours()).padStart(2, "0")}${String(d.getMinutes()).padStart(2, "0")} Hr`;
const dshort = (d: Date) => `${String(d.getDate()).padStart(2, "0")} ${MON[d.getMonth()][0]}${MON[d.getMonth()].slice(1).toLowerCase()} ${String(d.getFullYear()).slice(2)}`;
const hoursOf = (tl: string) => { const m = /(\d+)\s*([hd])/.exec(tl || ""); return m ? +m[1] * (m[2] === "d" ? 24 : 1) : 72; };
const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);
const owner = (a: any) => String(a.owner).replace(/^Theatre /, "").split(" / ")[0];
const hot = (b: B, n = 5) => [...(b.districts || [])].filter((d: any) => !d.name.startsWith("(")).sort((x: any, y: any) => y.p_now - x.p_now).slice(0, n);
const serial = (X: any, b: B) => X.dates.indexOf(b.date) + 1;
/** Observations for staff documents: market lines stay in the analyst brief, not in a SITREP or an order. */
const obs = (b: B) => b.observe.filter((o: any) => o.source !== "Markets");

function context(X: any, role: string, di: number) {
  const b = X.briefs[role][di], T = X.theatres[role];
  const now = t0(b);
  return { b, T, now, notice: NOTICE[b.rating], wef: plusH(now, 4), ogp: plusH(now, 6), opoBy: plusH(now, 12),
    prec: PREC[b.rating], op: OPNAME[role], hq: HQ[role], hqs: HQS[role], syn: !!b.synthetic };
}

// ---------------------------------------------------------------------------------------------- SITREP
function sitrepText(D: Data, X: any, role: string, di: number) {
  const c = context(X, role, di), { b, T, now } = c;
  const ids = Object.keys(CASE_NAME).filter((k) => T.cases.includes(CASE_NAME[k]));
  const cas = ids.map((k) => { const M = D.monthly[k]; const i = M.deaths.length - 1;
    const [y, mo] = M.months[i].split("-");
    const civ = M.civ[i] <= 1 ? `civilians ${Math.round(M.civ[i] * 100)}%` : `civilians ${M.civ[i].toLocaleString("en-IN")}`;
    return `${CASE_NAME[k]}: ${M.deaths[i].toLocaleString("en-IN")} killed in ${MON[+mo - 1][0]}${MON[+mo - 1].slice(1).toLowerCase()} ${y.slice(2)} (UCDP; ${civ})`; });
  const paras: [string, string[]][] = [
    ["ADVERSARY / THREAT ACTIVITY (last 24 hr to 7 days)", obs(b).map((o: any) => `${o.text} [${o.tag}, ${o.source}, ${o.window}]`)],
    ["THREAT ASSESSMENT", [`Threat level ${b.rating} ${b.arrow} (${b.trend}); score ${b.score}; confidence ${b.confidence}.`, `Basis: ${b.confidence_why}`,
      ...b.orient.points.map((p: any) => `${p.pts > 0 ? "+" : ""}${p.pts}: ${p.why}`)]],
    ["AREAS OF CONCERN (escalation probability, nowcast)", hot(b).map((d: any) => `${d.synthetic ? "[SYNTHETIC] " : ""}${d.name} (${d.iso}): P ${d.p_now.toFixed(2)}${d.p_now >= X.meta.flash_threshold ? " - OVER FLASH THRESHOLD" : ""}`)],
    ["CASUALTIES (latest month on record)", cas.length ? cas : ["Nil held for this AOR in the issued data."]],
    ["OWN TPS", ["Dispositions and states are not held in Conflict EW; to be added by the duty officer before release."]],
    ["ACTIONS RECOMMENDED (for Cdr's approval)", b.decide.map((a: any) => `${a.rank}. ${a.kind} - ${a.text} Owner: ${owner(a)}. NLT ${dtg(plusH(now, hoursOf(a.timeline)))}.`)],
    ["ESCALATION TRIGGERS", b.decide.map((a: any) => `${a.rank}. ${a.trigger}`)],
    ["COMMANDER'S ASSESSMENT", [b.bluf]],
    ["NEXT SITREP", [`${dtg(plusH(now, 12))}, or at once by FLASH if a trigger is met.`]],
  ];
  return { c, paras, cas };
}

export function sitrepHTML(D: Data, X: any, role: string, di: number) {
  const { c, paras } = sitrepText(D, X, role, di), { b, now } = c;
  const to = role === "CDS" ? "Chiefs of Staff Committee" : "HQ IDS (Office of CDS)";
  return `<div class="doc" data-doc="sitrep">
    <div class="doc-cls">RESTRICTED · EXERCISE (COMPETITION DATA)${c.syn ? " · INCLUDES SYNTHETIC DATA" : ""}</div>
    <table class="sig"><tr><td><b>PRECEDENCE</b> ${c.prec}</td><td><b>DTG</b> ${dtg(now)}</td><td><b>ORIGINATOR'S NO</b> SR/${role}/${String(serial(X, b)).padStart(3, "0")}</td></tr>
      <tr><td><b>FROM</b> ${c.hqs} (Ops Room)</td><td colspan="2"><b>TO</b> ${to} &nbsp; <b>INFO</b> ${role === "CDS" ? "Cdrs WTC, NTC, MTC" : "Other theatre HQs"}</td></tr></table>
    <div class="doc-h">SITREP No ${serial(X, b)} · ${esc(c.T.name.toUpperCase())} · PERIOD 24 HR ENDING ${dtg(now)}</div>
    <ol class="sr">${paras.map(([h, ls]) => `<li><b>${h}.</b>${ls.length > 1 ? `<ol class="sr2">${ls.map((l) => `<li>${esc(l)}</li>`).join("")}</ol>` : ` ${esc(ls[0])}`}</li>`).join("")}</ol>
    <div class="doc-foot">Drafted automatically by Conflict EW from the ${esc(b.dtg)} brief · to be checked and released by the duty staff officer · ${esc(X.meta.notional)}</div></div>`;
}

// ------------------------------------------------------------------------------------- WARNING ORDER
function warnoLines(X: any, role: string, di: number) {
  const c = context(X, role, di), { b } = c;
  const tasks = b.decide.map((a: any) => a.short).join("; ");
  const areas = hot(b, 3).map((d: any) => d.name).join(", ");
  return { c, lines: [
    `Op ${c.op} (.) WARNING ORDER No ${serial(X, b)} (.)`,
    `Firstly (.) WARNING ONLY (.) Threat ${b.rating} ${b.trend} (.) probable tasks: ${tasks}${areas ? ` (.) areas of concern ${areas}` : ""} (.)`,
    `Secondly (.) EXECUTIVE (.) all addressees placed ${c.notice} hr notice wef ${dt6(c.wef)} (.) no move before ${dt6(plusH(c.wef, c.notice))} unless ordered (.)`,
    `Thirdly (.) EXECUTIVE (.) O gp RV ${c.hqs} ${dt6(c.ogp)} (.) COs or reps with maps of AOR (.)`,
    `Fourthly (.) EXECUTIVE (.) report readiness state and any change in adversary activity by ${dt6(plusH(c.wef, 2))} (.) FLASH at once if ${b.decide[0].trigger.split(" -> ")[0]} (.)`,
    `Fifthly (.) WARNING ONLY (.) detailed orders: Op O No ${serial(X, b)} by ${dt6(c.opoBy)} (.)`,
    `Ack`] };
}

export function warnoHTML(X: any, role: string, di: number) {
  const { c, lines } = warnoLines(X, role, di), to = FWD[role];
  return `<div class="doc" data-doc="warno">
    <div class="doc-cls">RESTRICTED · EXERCISE (COMPETITION DATA)${c.syn ? " · INCLUDES SYNTHETIC DATA" : ""}</div>
    <table class="mf">
      <tr><td><b>PRECEDENCE - ACTION</b><br>${c.prec}</td><td><b>PRECEDENCE - INFO</b><br>${c.prec === "OP IMMEDIATE" ? "PRIORITY" : "ROUTINE"}</td><td><b>DATE TIME GROUP</b><br>${dtg(c.now)}</td><td><b>MESSAGE INSTRUCTIONS</b><br>Tac sig</td></tr>
      <tr><td><b>FROM</b></td><td colspan="2">${c.hq} (notional)</td><td><b>PREFIX</b> G R</td></tr>
      <tr><td><b>TO</b></td><td colspan="2">${to.map(esc).join("<br>")}</td><td><b>SECURITY CLASSIFICATION</b><br>RESTRICTED (EXERCISE)<br><br><b>ORIGINATOR'S NUMBER</b><br>O/${role}/${String(serial(X, c.b)).padStart(3, "0")}</td></tr>
      <tr><td><b>INFO</b></td><td colspan="2">${role === "CDS" ? "COAS, CNS, CAS" : "HQ IDS (J3)"}</td><td><b>SPECIAL INSTRUCTIONS</b><br>Ack reqd</td></tr>
      <tr><td colspan="4" class="mf-txt">${lines.map(esc).join("<br>")}</td></tr>
      <tr class="mf-sm"><td><b>PAGE</b> 1 <b>OF</b> 1</td><td><b>REFERS TO MESSAGE</b> CW brief ${esc(c.b.dtg)}<br><b>CLASSIFIED</b> YES ☒ NO ☐</td><td><b>DRAFTER'S NAME</b> Conflict EW (auto)<br><b>OFFICE</b> ${role} J3</td><td><b>RELEASING OFFICER'S SIGNATURE / RANK</b><br><br>________________</td></tr>
    </table>
    <div class="doc-foot">Executive parts are marked EXECUTIVE; probable tasks are WARNING ONLY. Notice by threat level: RED 2 hr, AMBER 12 hr, GREEN 24 hr. Units are notional.</div></div>`;
}

// ----------------------------------------------------------------------------------- OPERATION ORDER
function opoParts(D: Data, X: any, role: string, di: number) {
  const c = context(X, role, di), { b, T, now } = c;
  const { cas } = sitrepText(D, X, role, di);
  const acts = b.decide;
  const maxH = Math.max(...acts.map((a: any) => hoursOf(a.timeline)));
  const mission = `${c.hqs} will raise surveillance and readiness across ${T.sectors.join(", ")} wef ${dtg(c.wef)} to detect and pre-empt escalation on the ${T.front}, and will be prepared to act on any trigger in the coordinating instructions.`;
  const S: [string, string[]][] = [
    ["SITUATION", []],
    ["Background", [b.bluf]],
    ["Higher Directives", [`Conflict EW threat level for this AOR: ${b.rating} ${b.arrow} (${b.trend}), confidence ${b.confidence}.`, ...(cas.length ? cas : [])]],
    ["Adversary", obs(b).map((o: any) => `${o.text} [${o.tag}]`).concat([`Likely pattern: ${b.orient.drivers.join("; ")}. ${b.orient.model_why}`])],
    ["Own Forces", ["As per theatre ORBAT (not held in Conflict EW). Grouping: no change."]],
    ["Topography", [`AOR sectors: ${T.sectors.join("; ")}. Areas of concern: ${hot(b).map((d: any) => `${d.name} (P ${d.p_now.toFixed(2)})`).join(", ") || "nil over threshold"}.`]],
    ["Weather", ["Not covered by the issued data; as per Met forecast."]],
    ["MISSION", [mission]],
    ["EXECUTION", []],
    ["General Outline", [`Ph 1 SENSE (0 to 24 hr): verify and task ISR. Ph 2 POSTURE (to ${Math.min(72, maxH)} hr): adjust readiness. Ph 3 SUSTAIN (to ${maxH} hr): review on each SITREP.`]],
    ["Tasks", acts.map((a: any) => `${owner(a)} will ${a.short} (${a.kind}). ${a.text} NLT ${dtg(plusH(now, hoursOf(a.timeline)))}.`)],
    ["Coordinating Instructions", [...acts.map((a: any) => `Trigger ${a.rank}: ${a.trigger}.`), `Degree of notice: ${c.notice} hr wef ${dtg(c.wef)} (Warning Order No ${serial(X, b)}).`,
      `SITREPs by 0600 Hr and 1800 Hr daily; FLASH by fastest means.`]],
    ["MAINTENANCE, ADMINISTRATION AND LOGISTICS", ["As per existing arrangements. No change indicated by the data."]],
    ["COMMUNICATIONS AND ELECTRONICS", [`Code words: ${c.op} (this operation); FLASH (area P ≥ ${X.meta.flash_threshold} or a change of threat level); STAND FAST (revert to normal notice). Reports on secure nets.`]],
    ["COMMAND AND CONTROL", [`${role === "CDS" ? "CDS" : "Theatre Cdr"} retains command. ${role === "CDS" ? "HQ IDS (J3)" : `${role} J3`} coordinates. HQ location as notified (notional).`]],
    ["ACKNOWLEDGEMENT AND DISPOSAL", ["Acknowledge."]],
  ];
  return { c, S };
}

export function opoHTML(D: Data, X: any, role: string, di: number) {
  const { c, S } = opoParts(D, X, role, di), { b, now } = c;
  let n = 0;
  const body = S.map(([h, ls]) => {
    if (!ls.length || ["MISSION", "MAINTENANCE, ADMINISTRATION AND LOGISTICS", "COMMUNICATIONS AND ELECTRONICS", "COMMAND AND CONTROL", "ACKNOWLEDGEMENT AND DISPOSAL"].includes(h))
      return `<div class="oh">${h}</div>` + ls.map((l) => `<p><span class="pn">${++n}.</span> ${esc(l)}</p>`).join("");
    return `<div class="osh">${h}</div><p><span class="pn">${++n}.</span> ${ls.length === 1 ? esc(ls[0]) : ls.map((l, i) => `<br><span class="pn2">${n}.${i + 1}.</span> ${esc(l)}`).join("")}</p>`;
  }).join("");
  return `<div class="doc opo" data-doc="opo">
    <div class="doc-cls">RESTRICTED · EXERCISE (COMPETITION DATA)${c.syn ? " · INCLUDES SYNTHETIC DATA" : ""}</div>
    <div class="opo-top"><div>Tele: Mil XXXX</div><div><b>${c.prec}</b><br>Copy No 01/${String(OPO_TO.length).padStart(2, "0")}</div></div>
    <div class="opo-top"><div>${c.hq}<br>(location as notified)</div><div></div></div>
    <div class="opo-top"><div>CW/${role}/Ops/${String(serial(X, b)).padStart(2, "0")}</div><div>${dshort(now)}</div></div>
    <div class="doc-h">OPERATION ORDER No ${String(serial(X, b)).padStart(2, "0")}/${now.getFullYear()} · OP ${c.op}</div>
    <p><b>References</b>:- a. Conflict EW daily brief ${esc(b.dtg)}. b. Monthly threat scorecard (Conflict EW). c. Warning Order No ${serial(X, b)} dt ${dt6(now)}. d. Map: ${role} AOR (Ops console ▸ Theatre).</p>
    <p><b>Appendices</b>:- A. Areas of concern and escalation probability. B. Escalation triggers and reporting.</p>
    <p><b>All Times</b>: IST.</p>${body}
    <div class="sigblk">(Anonymous)<br>Rank<br>Appointment<br>For ${role === "CDS" ? "CDS" : `Cdr ${role}`}<br>Time: ${hr(now)}</div>
    <p><b>Distribution</b>:- ${OPO_TO.join(", ")}.</p>
    <div class="doc-foot">Drafted by Conflict EW for the staff; HQs, owners and units are notional.</div></div>`;
}

// ------------------------------------------------------------------------------- plain text (send)
function plain(html: string) {
  const el = document.createElement("div");
  el.innerHTML = html.replace(/<br\s*\/?>/g, "\n").replace(/<\/(p|li|tr|div)>/g, "\n</$1>").replace(/<\/td>/g, "  </td>");
  return el.textContent!.replace(/[ \t]+\n/g, "\n").replace(/\n{3,}/g, "\n\n").trim();
}

export const DOC_CSS = `
.doc { background:#FBFAF5; color:#111; border-radius:6px; padding:22px 26px; font:14px/1.5 "Times New Roman", Georgia, serif; box-shadow:0 6px 24px rgba(0,0,0,.35); }
.doc b { color:#000; } .doc .doc-cls { text-align:center; font:700 12px var(--mono); letter-spacing:.14em; color:#8a1c1c; margin-bottom:10px; }
.doc .doc-h { text-align:center; font-weight:700; text-decoration:underline; margin:12px 0 10px; letter-spacing:.04em; }
.doc table { border-collapse:collapse; width:100%; } .doc td { border:1px solid #333; padding:5px 7px; vertical-align:top; font-size:13px; }
.doc .sig td { font-size:12.5px; } .doc .mf-txt { font:14px/1.75 var(--mono); padding:12px; min-height:150px; }
.doc .mf-sm td { font-size:11.5px; } .doc ol.sr { padding-left:22px; margin:0; } .doc ol.sr > li { margin:7px 0; }
.doc ol.sr2 { list-style:lower-alpha; padding-left:22px; margin:3px 0; } .doc .doc-foot { margin-top:14px; border-top:1px solid #bbb; padding-top:6px; font:11.5px var(--mono); color:#555; }
.doc .opo-top { display:flex; justify-content:space-between; font-size:13px; margin:3px 0; }
.doc .oh { font-weight:700; text-decoration:underline; text-align:center; margin:14px 0 4px; }
.doc .osh { font-weight:700; text-decoration:underline; margin:10px 0 2px; } .doc p { margin:4px 0; }
.doc .pn { display:inline-block; min-width:26px; } .doc .pn2 { display:inline-block; min-width:40px; margin-left:26px; }
.doc .sigblk { margin:16px 0 8px auto; width:200px; font-size:13px; }
.docs-wrap { display:grid; grid-template-columns: minmax(0,1fr) 330px; gap:16px; align-items:start; }
.docs-tabs { display:flex; gap:8px; flex-wrap:wrap; margin-bottom:12px; }
.dsp { background: var(--panel); border:1px solid var(--line); border-radius:12px; padding:14px; position:sticky; top:70px; }
.dsp h4 { margin:0 0 6px; font: 800 12px var(--mono); letter-spacing:.14em; color: var(--tx3); }
.dsp ul { margin:4px 0 10px; padding-left:18px; font-size:13.5px; } .dsp .btns { display:flex; flex-wrap:wrap; gap:8px; margin:8px 0; }
.dsp .log { font: 12px var(--mono); color: var(--tx2); max-height:160px; overflow:auto; border-top:1px solid var(--line); padding-top:8px; margin-top:8px; }
.dsp input { width:100%; box-sizing:border-box; background:var(--bg); color:var(--tx1); border:1px solid var(--line2); border-radius:8px; padding:7px 9px; font: 13px var(--mono); margin:4px 0; }
@media (max-width: 1100px) { .docs-wrap { grid-template-columns: 1fr; } .dsp { position:static; } }
@media print { body * { visibility:hidden; } .doc, .doc * { visibility:visible; } .doc { position:absolute; left:0; top:0; width:100%; box-shadow:none; } }
`;

export const DOC_META: Record<DocKind, { title: string; who: (role: string) => string[]; label: string }> = {
  sitrep: { title: "SITREP", label: "Situation report · the commander's brief", who: (r) => [r === "CDS" ? "Chiefs of Staff Committee" : "HQ IDS (Office of CDS)", r === "CDS" ? "Cdrs WTC, NTC, MTC (info)" : "Other theatre HQs (info)"] },
  warno: { title: "WARNING ORDER", label: "To forward-deployed troops", who: (r) => FWD[r] },
  opo: { title: "OPERATION ORDER", label: "To the CDS, Service Chiefs and commanders", who: () => OPO_TO },
};

export function docHTML(kind: DocKind, D: Data, X: any, role: string, di: number) {
  return kind === "sitrep" ? sitrepHTML(D, X, role, di) : kind === "warno" ? warnoHTML(X, role, di) : opoHTML(D, X, role, di);
}

function printDoc(html: string) {
  const f = document.createElement("iframe");
  f.style.cssText = "position:fixed;right:0;bottom:0;width:0;height:0;border:0";
  document.body.appendChild(f);
  const w = f.contentWindow!;
  w.document.open();
  w.document.write(`<!doctype html><html><head><meta charset="utf-8"><style>:root{--mono:Consolas,"Courier New",monospace}${DOC_CSS} .doc{box-shadow:none}</style></head><body>${html}</body></html>`);
  w.document.close();
  setTimeout(() => { try { w.focus(); w.print(); } catch { /* blocked */ } setTimeout(() => f.remove(), 1500); }, 250);
}

/** Documents panel: tabs, the document, and a dispatch card. Used on the Theatre page and in the commander sheet. */
export function mountDocs(host: HTMLElement, D: Data, X: any, role: string, di: number, start: DocKind = "sitrep") {
  if (!document.getElementById("doc-css")) document.head.insertAdjacentHTML("beforeend", `<style id="doc-css">${DOC_CSS}</style>`);
  let kind: DocKind = start;
  const log: string[] = [];
  const draw = () => {
    const html = docHTML(kind, D, X, role, di), M = DOC_META[kind], text = plain(html);
    host.innerHTML = `<div class="docs-tabs seg">${(Object.keys(DOC_META) as DocKind[]).map((k) => `<button data-k="${k}" class="${k === kind ? "on" : ""}">${DOC_META[k].title}</button>`).join("")}</div>
      <div class="docs-wrap"><div>${html}</div>
        <aside class="dsp"><h4>${M.title} · DISPATCH</h4><div class="small muted">${M.label}</div>
          <h4 style="margin-top:12px">ADDRESSEES (NOTIONAL)</h4><ul>${M.who(role).map((w) => `<li>${esc(w)}</li>`).join("")}</ul>
          <label class="small muted">WhatsApp number (with country code) or e-mail</label><input id="dsp-to" placeholder="e.g. 9198xxxxxxxx or name@army.example">
          <div class="btns"><button class="btn primary" id="dsp-wa">SEND · WHATSAPP</button><button class="btn" id="dsp-mail">SEND · E-MAIL</button>
            <button class="btn" id="dsp-copy">COPY TEXT</button><button class="btn" id="dsp-print">⎙ PRINT</button></div>
          <div class="log" id="dsp-log"${log.length ? "" : " hidden"}>${log.map(esc).join("<br>")}</div></aside></div>`;
    $$(".docs-tabs button", host).forEach((b) => b.addEventListener("click", () => { kind = b.dataset.k as DocKind; draw(); }));
    const to = () => ($("#dsp-to", host) as HTMLInputElement).value.trim();
    const note = (s: string) => { const d = new Date(); log.unshift(`${String(d.getHours()).padStart(2, "0")}${String(d.getMinutes()).padStart(2, "0")} ${M.title}: ${s}`); const lg = $("#dsp-log", host); lg.hidden = false; lg.innerHTML = log.map(esc).join("<br>"); };
    $("#dsp-wa", host).addEventListener("click", () => {
      const num = to().replace(/[^\d]/g, "");
      const a = document.createElement("a"); a.target = "_blank"; a.rel = "noopener";
      a.href = `https://wa.me/${num}?text=${encodeURIComponent(text)}`; a.click();
      note(`opened WhatsApp${num ? " for +" + num : " (choose the chat)"}`);
    });
    $("#dsp-mail", host).addEventListener("click", () => {
      const subj = `${M.title} ${role} ${dtg(t0(X.briefs[role][di]))}`;
      const body = text.length > 1800 ? text.slice(0, 1800) + "\n[... truncated: paste the full text with COPY TEXT]" : text;
      const a = document.createElement("a"); a.href = `mailto:${encodeURIComponent(to())}?subject=${encodeURIComponent(subj)}&body=${encodeURIComponent(body)}`; a.click();
      note(`opened e-mail${to() ? " to " + to() : ""}`);
    });
    $("#dsp-copy", host).addEventListener("click", async () => { try { await navigator.clipboard.writeText(text); note("text copied"); } catch { note("copy blocked by the browser"); } });
    $("#dsp-print", host).addEventListener("click", () => { printDoc(html); note("sent to printer"); });
  };
  draw();
}

/** Full-screen overlay with the documents, opened from the commander landing page. Esc or ✕ closes it. */
export function openDocsModal(D: Data, X: any, role: string, kind: DocKind) {
  document.getElementById("docs-modal")?.remove();
  const m = document.createElement("div");
  m.id = "docs-modal";
  m.setAttribute("role", "dialog"); m.setAttribute("aria-modal", "true"); m.setAttribute("aria-label", "Brief and orders");
  m.style.cssText = "position:fixed;inset:0;z-index:80;background:rgba(5,11,18,.97);backdrop-filter:blur(6px);overflow:auto;padding:28px 3vw";
  m.innerHTML = `<div style="max-width:1320px;margin:0 auto"><div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
      <div class="eyebrow" style="margin:0">${esc(X.theatres[role].name.toUpperCase())} · BRIEF AND ORDERS · ${esc(X.briefs[role][X.dates.length - 1].dtg)}</div>
      <button class="btn" id="docs-x" aria-label="Close">✕ CLOSE</button></div><div id="docs-host"></div></div>`;
  document.body.appendChild(m);
  mountDocs(m.querySelector("#docs-host") as HTMLElement, D, X, role, X.dates.length - 1, kind);
  const close = () => { m.remove(); document.removeEventListener("keydown", onKey); };
  const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") close(); };
  document.addEventListener("keydown", onKey);
  (m.querySelector("#docs-x") as HTMLElement).addEventListener("click", close);
  m.addEventListener("click", (e) => { if (e.target === m) close(); });
}
