import { getFile, INLINE } from "./data-source";
import { geoArea } from "d3-geo";

/** d3-geo wants clockwise exterior rings (the opposite of RFC 7946). Flip any polygon that d3 would read as "the whole globe minus the shape". */
function rewind(fc: any) {
  for (const f of fc.features) {
    const g = f.geometry; if (!g) continue;
    const polys = g.type === "Polygon" ? [g.coordinates] : g.type === "MultiPolygon" ? g.coordinates : [];
    for (const rings of polys) {
      if (geoArea({ type: "Polygon", coordinates: rings } as any) > 2 * Math.PI) rings.forEach((r: any[]) => r.reverse());
    }
  }
  return fc;
}

export type Rag = "RED" | "AMBER" | "GREEN";
export interface Score {
  id: string; name: string; short: string; rating: Rag; points: number; forecast: number; lo: number; hi: number;
  month: string; trend_pct: number; trend_ratio: number; last6: number; hotspots: number; peak12: number;
  top: { name: string; p: number }[]; countries_now: number; countries_prev: number; p_areas: number[];
  pts: { intensity: number; trend: number; hotspots: number; spread: number; volatility: number };
  forward: { month: string; pred: number; lo: number; hi: number; lo95: number; hi95: number }[];
}
export interface Area {
  id: string; key: string; c: string; iso: string; name: string; lon: number | null; lat: number | null;
  unloc: boolean; p: number; last: number; d: number[]; pm: (number | null)[]; esc: (number | null)[];
}
export interface Data {
  facts: any; monthly: Record<string, { months: string[]; deaths: number[]; low: number[]; high: number[]; events: number[]; civ: number[]; countries: number[] }>;
  areas: { months: string[]; ew_months: string[]; areas: Area[] };
  admin1: any; world: any; points: [string, number, number, number, number][]; front: Record<string, Record<string, number>>;
  leaderboard: any; holdout: any[]; whatif: any; dq: any[]; manifest: any; theatre: any; inline: boolean;
}

let P: Promise<Data> | null = null;
export function loadData(onProgress?: (f: number) => void): Promise<Data> {
  if (P) return P;
  const files = ["facts.json", "monthly_conflict.json", "areas.json", "admin1.geojson", "world_ind.geojson",
    "events_points.json", "front_shares.json", "leaderboard.json", "holdout_paths.json", "whatif.json", "dq_log.json", "manifest.json", "theatre.json"];
  let done = 0;
  P = Promise.all(files.map((f) => getFile(f).then((x) => { done++; onProgress?.(done / files.length); return x; })))
    .then(([facts, monthly, areas, admin1, world, points, front, leaderboard, holdout, whatif, dq, manifest, theatre]) =>
      ({ facts, monthly, areas, admin1: rewind(admin1), world: rewind(world), points, front, leaderboard, holdout, whatif, dq, manifest,
         theatre: theatre && theatre.aor ? { ...theatre, aor: rewind(theatre.aor) } : theatre, inline: INLINE }));
  return P;
}

export const CASES = ["ruua", "ilh", "afpak", "usir"] as const;
export const CASE_COLOR: Record<string, string> = { ruua: "#FF4D5E", ilh: "#A78BFA", afpak: "#F2B33D", usir: "#4FD1E0" };
export const CASE_SHORT: Record<string, string> = { ruua: "RU–UA", ilh: "IL–Hamas", afpak: "Af–Pak", usir: "US–Iran" };
export const CASE_NAME: Record<string, string> = { ruua: "Russia–Ukraine", ilh: "Israel–Hamas", afpak: "Afghanistan–Pakistan", usir: "US–Iran" };
export const RAG_COLOR: Record<string, string> = { RED: "#FF4D5E", AMBER: "#F2B33D", GREEN: "#2BB673" };
export const fmt = (n: number | null | undefined, d = 0) =>
  n == null || Number.isNaN(n) ? "–" : n.toLocaleString("en-IN", { maximumFractionDigits: d, minimumFractionDigits: d });
export const fmtM = (n: number) => (n >= 1e6 ? (n / 1e6).toFixed(1) + "M" : n >= 1e3 ? Math.round(n / 1e3) + "k" : String(n));
export const pct = (x: number, d = 0) => (x * 100).toFixed(d) + "%";
