// Scorecard doctrine – identical to src/models.py::rag_scorecard. Verified at load against facts.json.
import type { Score, Rag } from "./data";

export interface Rules { int_hi: number; int_lo: number; trend_up: number; trend_dn: number; hot_p: number;
  hot_hi: number; hot_lo: number; vol: number; red_fc: number; red_pts: number; amber_pts: number;
  use_spread: boolean; use_vol: boolean; }

export const DOCTRINE = (f: any): Rules => ({ ...f.rules, use_spread: true, use_vol: true });

export function rate(s: Score, R: Rules, fcScale = 1) {
  const fc = s.forecast * fcScale;
  const trendPct = (fc / Math.max(s.last6, 1) - 1) * 100;
  const hot = s.p_areas.filter((p) => p >= R.hot_p - 1e-9).length;
  const pts = {
    intensity: fc >= R.int_hi ? 2 : fc >= R.int_lo ? 1 : 0,
    trend: trendPct >= R.trend_up - 1e-9 ? 1 : trendPct <= R.trend_dn + 1e-9 ? -1 : 0,
    hotspots: hot >= R.hot_hi ? 2 : hot >= R.hot_lo ? 1 : 0,
    spread: R.use_spread && s.countries_now > s.countries_prev ? 1 : 0,
    volatility: R.use_vol && s.peak12 >= R.vol ? 1 : 0,
  };
  const points = pts.intensity + pts.trend + pts.hotspots + pts.spread + pts.volatility;
  const rating: Rag = fc >= R.red_fc || points >= R.red_pts ? "RED" : points >= R.amber_pts ? "AMBER" : "GREEN";
  const why: string[] = [];
  if (fc >= R.red_fc) why.push(`forecast ${Math.round(fc).toLocaleString("en-IN")} ≥ ${R.red_fc.toLocaleString("en-IN")} (auto-RED)`);
  return { rating, points, pts, hot, trendPct, fc, why };
}

export function verify(scores: Score[], R: Rules): string[] {
  const bad: string[] = [];
  for (const s of scores) {
    const r = rate(s, R);
    if (r.rating !== s.rating || r.points !== s.points || r.hot !== s.hotspots)
      bad.push(`${s.short}: TS ${r.rating}/${r.points}/${r.hot} vs Python ${s.rating}/${s.points}/${s.hotspots}`);
  }
  return bad;
}
