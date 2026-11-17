import { geoOrthographic, geoPath, geoGraticule10, geoMercator, geoDistance, geoCircle } from "d3-geo";
import { CASE_COLOR } from "./data";

const NS = "http://www.w3.org/2000/svg";
export const el = (tag: string, attrs: Record<string, any> = {}, parent?: Element) => {
  const e = document.createElementNS(NS, tag);
  for (const k in attrs) e.setAttribute(k, String(attrs[k]));
  parent?.appendChild(e);
  return e;
};

/** Hex colour ramp (dark → teal → amber → red) for probabilities / intensities in [0,1]. */
const STOPS = [[0, [20, 32, 50]], [0.25, [36, 96, 120]], [0.5, [79, 209, 224]], [0.75, [242, 179, 61]], [1, [255, 77, 94]]] as const;
export function ramp(t: number) {
  t = Math.max(0, Math.min(1, t));
  for (let i = 1; i < STOPS.length; i++) {
    const [t1, c1] = STOPS[i]; const [t0, c0] = STOPS[i - 1];
    if (t <= t1) { const f = (t - t0) / (t1 - t0); return `rgb(${c0.map((v, j) => Math.round(v + f * (c1[j] - v))).join(",")})`; }
  }
  return "rgb(255,77,94)";
}

let tipEl: HTMLDivElement | null = null;
export function tip(html: string | null, ev?: MouseEvent) {
  if (!tipEl) { tipEl = document.createElement("div"); tipEl.className = "tip"; document.body.appendChild(tipEl); }
  if (!html || !ev) { tipEl.style.display = "none"; return; }
  tipEl.innerHTML = html; tipEl.style.display = "block";
  const x = Math.min(ev.clientX + 14, innerWidth - 330); tipEl.style.left = x + "px"; tipEl.style.top = ev.clientY + 14 + "px";
}

// ---------------------------------------------------------------------------
// Hero globe (canvas, orthographic)
// ---------------------------------------------------------------------------
export interface Globe { setYear(y: number): void; setFocus(t: number): void; stop(): void; }
export function globe(canvas: HTMLCanvasElement, world: any, points: [string, number, number, number, number][], rings: [number, number, string][]): Globe {
  const ctx = canvas.getContext("2d")!;
  const proj = geoOrthographic().clipAngle(90).precision(0.6);
  const path = geoPath(proj, ctx);
  const grat = geoGraticule10();
  const india = world.features.find((f: any) => f.properties.ADM0_A3 === "IND");
  let year = 2014, focus = 0, rot = 20, raf = 0, t0 = performance.now();
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const maxD = Math.max(...points.map((p) => p[4]));
  function size() {
    const r = devicePixelRatio || 1, w = canvas.clientWidth, h = canvas.clientHeight;
    canvas.width = w * r; canvas.height = h * r; ctx.setTransform(r, 0, 0, r, 0, 0);
    const R = Math.min(w, h) * (w > 900 ? 0.42 : 0.4);
    proj.scale(R).translate([w > 900 ? w * 0.7 : w / 2, h * 0.46]);
  }
  size(); addEventListener("resize", size);
  function draw(now: number) {
    const w = canvas.clientWidth, h = canvas.clientHeight;
    if (!reduce) rot += 0.06;
    const spin = -rot % 360;
    // interpolate from spinning view to India-centred view
    const tgt = [-60, -18];
    const lam = spin + (tgt[0] - spin) * focus, phi = -12 + (tgt[1] + 12) * focus;
    proj.rotate([lam, phi]);
    ctx.clearRect(0, 0, w, h);
    const [cx, cy] = proj.translate(), R = proj.scale();
    const g = ctx.createRadialGradient(cx - R * 0.3, cy - R * 0.3, R * 0.1, cx, cy, R * 1.05);
    g.addColorStop(0, "#0E1C2E"); g.addColorStop(1, "#05070A");
    ctx.beginPath(); ctx.arc(cx, cy, R, 0, 2 * Math.PI); ctx.fillStyle = g; ctx.fill();
    ctx.strokeStyle = "rgba(79,209,224,.35)"; ctx.lineWidth = 1.2; ctx.stroke();
    ctx.beginPath(); path(grat); ctx.strokeStyle = "rgba(79,209,224,.08)"; ctx.lineWidth = 0.6; ctx.stroke();
    ctx.beginPath(); path(world); ctx.fillStyle = "#13233A"; ctx.fill(); ctx.strokeStyle = "rgba(120,150,190,.35)"; ctx.lineWidth = 0.5; ctx.stroke();
    ctx.beginPath(); path(india); ctx.fillStyle = `rgba(79,209,224,${0.12 + 0.18 * focus})`; ctx.fill();
    ctx.strokeStyle = "#4FD1E0"; ctx.lineWidth = 1 + focus * 1.2; ctx.stroke();
    const centre = proj.invert!([cx, cy])!;
    ctx.globalCompositeOperation = "lighter";
    for (const p of points) {
      if (p[3] > year) continue;
      if (geoDistance([p[1], p[2]], centre) > Math.PI / 2) continue;
      const xy = proj([p[1], p[2]]); if (!xy) continue;
      const age = year - p[3];
      const rad = 1.6 + 13 * Math.sqrt(p[4] / maxD);
      ctx.beginPath(); ctx.arc(xy[0], xy[1], rad, 0, 2 * Math.PI);
      ctx.fillStyle = CASE_COLOR[p[0]] + (age < 1 ? "CC" : "55"); ctx.fill();
    }
    ctx.globalCompositeOperation = "source-over";
    if (focus > 0.05) {
      const ph = ((now - t0) / 1800) % 1;
      for (const [lon, lat, label] of rings) {
        if (geoDistance([lon, lat], centre) > Math.PI / 2) continue;
        const circ = geoCircle().center([lon, lat]).radius(1.2 + ph * 3.2)();
        ctx.beginPath(); path(circ); ctx.strokeStyle = `rgba(242,179,61,${(1 - ph) * focus})`; ctx.lineWidth = 2; ctx.stroke();
        const xy = proj([lon, lat]); if (!xy) continue;
        ctx.beginPath(); ctx.arc(xy[0], xy[1], 3, 0, 2 * Math.PI); ctx.fillStyle = "#F2B33D"; ctx.fill();
        if (focus > 0.6) { ctx.font = "600 12px JetBrains Mono"; ctx.fillStyle = `rgba(245,245,247,${focus})`; ctx.fillText(label, xy[0] + 8, xy[1] - 6); }
      }
      // exposure arc from India
      const xyI = proj([78, 22]);
      if (xyI) for (const [lon, lat] of rings) {
        const xy = proj([lon, lat]); if (!xy) continue;
        ctx.beginPath(); ctx.moveTo(xyI[0], xyI[1]);
        ctx.quadraticCurveTo((xyI[0] + xy[0]) / 2, Math.min(xyI[1], xy[1]) - 40, xy[0], xy[1]);
        ctx.strokeStyle = `rgba(79,209,224,${0.45 * focus})`; ctx.setLineDash([4, 4]); ctx.lineWidth = 1.2; ctx.stroke(); ctx.setLineDash([]);
      }
    }
    raf = requestAnimationFrame(draw);
  }
  raf = requestAnimationFrame(draw);
  return { setYear: (y) => (year = y), setFocus: (t) => (focus = Math.max(0, Math.min(1, t))), stop: () => cancelAnimationFrame(raf) };
}

// ---------------------------------------------------------------------------
// Flat regional maps (SVG, Mercator) – India point-of-view outline always drawn on top
// ---------------------------------------------------------------------------
export interface RegionMap { svg: SVGSVGElement; proj: any; path: any; layer: SVGGElement; top: SVGGElement; w: number; h: number; }
export function regionMap(box: HTMLElement, world: any, bbox: [[number, number], [number, number]], opts: { india?: boolean } = {}): RegionMap {
  box.innerHTML = "";
  const w = box.clientWidth || 900, h = box.clientHeight || 560;
  const svg = el("svg", { class: "map", viewBox: `0 0 ${w} ${h}`, role: "img" }, box) as SVGSVGElement;
  const proj = geoMercator().fitExtent([[10, 10], [w - 10, h - 10]], { type: "MultiPoint", coordinates: bbox } as any);
  const path = geoPath(proj);
  el("path", { class: "grat", d: path(geoGraticule10()) }, svg);
  const base = el("g", {}, svg);
  for (const f of world.features) {
    if (f.properties.ADM0_A3 === "IND") continue;
    const d = path(f); if (d) el("path", { class: "land", d }, base);
  }
  const layer = el("g", {}, svg) as SVGGElement;
  const ind = world.features.find((f: any) => f.properties.ADM0_A3 === "IND");
  const indG = el("g", {}, svg);
  el("path", { class: opts.india === false ? "land" : "india", d: path(ind) }, indG);
  if (opts.india !== false) {
    const c = proj([79, 23]);
    if (c) { const t = el("text", { x: c[0], y: c[1], "text-anchor": "middle", style: "fill:#4FD1E0;font-size:14px;letter-spacing:.3em" }, indG); t.textContent = "INDIA"; }
  }
  const top = el("g", {}, svg) as SVGGElement;
  return { svg, proj, path, layer, top, w, h };
}

export function pulse(m: RegionMap, lon: number, lat: number, color: string, label?: string, delay = 0, r = 7, anchor: "start" | "end" = "start") {
  const xy = m.proj([lon, lat]); if (!xy) return;
  const g = el("g", {}, m.top);
  const ring = el("circle", { cx: xy[0], cy: xy[1], r: r * 1.6, fill: "none", stroke: color, "stroke-width": 2, class: "pulse", style: `animation-delay:${delay}ms` }, g);
  el("circle", { cx: xy[0], cy: xy[1], r: r / 2, fill: color }, g);
  if (label) { const t = el("text", { x: anchor === "end" ? xy[0] - r - 6 : xy[0] + r + 6, y: xy[1] + 4, "text-anchor": anchor }, g); t.textContent = label; }
  return { g, ring };
}

/** Draw admin-1 polygons (once) and return a recolour function. */
export function adminLayer(m: RegionMap, admin1: any, filter: (ids: string[]) => boolean,
  onHover?: (ids: string[], ev: MouseEvent | null) => void, onClick?: (ids: string[]) => void) {
  const paths: { p: SVGPathElement; ids: string[] }[] = [];
  for (const f of admin1.features) {
    if (!filter(f.properties.ids)) continue;
    const d = m.path(f); if (!d) continue;
    const p = el("path", { class: "a1", d, fill: "#1A2638" }, m.layer) as SVGPathElement;
    const ids = f.properties.ids as string[];
    if (onHover) { p.addEventListener("mousemove", (e) => onHover(ids, e)); p.addEventListener("mouseleave", () => onHover(ids, null)); }
    if (onClick) { p.style.cursor = "pointer"; p.addEventListener("click", () => onClick(ids)); }
    paths.push({ p, ids });
  }
  return (color: (ids: string[]) => string) => paths.forEach(({ p, ids }) => p.setAttribute("fill", color(ids)));
}
