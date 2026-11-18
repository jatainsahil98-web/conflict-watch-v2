import "./styles.css";
import { loadData } from "./data";
import { initTheme } from "./chrome";

const isConsole = () => document.body.dataset.mode === "console" || /^#console/.test(location.hash);
const isStoryOnly = () => /^#(hero|bluf|india|signatures|front|afpak|media|gdelt|displacement|prediction|fastclock|decision|recs|method|closing)\b/.test(location.hash);
/** Three views: Commander (landing, no hash or #cmd), Story (any chapter hash), Console. */
const mode = () => (isConsole() ? "console" : location.hash && location.hash !== "#" && location.hash !== "#cmd" ? "story" : "command");

function preloader() {
  const pre = document.getElementById("pre")!;
  const cv = pre.querySelector("canvas") as HTMLCanvasElement, ctx = cv.getContext("2d")!;
  const r = devicePixelRatio || 1; cv.width = 260 * r; cv.height = 260 * r; ctx.scale(r, r);
  const theatres = [[0.62, -0.95, "#FF4D5E"], [0.78, 0.35, "#A78BFA"], [0.55, 2.55, "#F2B33D"], [0.42, 1.55, "#4FD1E0"]] as const;
  let a = 0, raf = 0;
  const draw = () => {
    ctx.clearRect(0, 0, 260, 260); const c = 130;
    ctx.strokeStyle = "rgba(79,209,224,.35)"; ctx.lineWidth = 1;
    for (const rr of [40, 80, 120]) { ctx.beginPath(); ctx.arc(c, c, rr, 0, 7); ctx.stroke(); }
    ctx.beginPath(); ctx.moveTo(c - 120, c); ctx.lineTo(c + 120, c); ctx.moveTo(c, c - 120); ctx.lineTo(c, c + 120); ctx.stroke();
    const g = ctx.createConicGradient ? ctx.createConicGradient(a - 0.8, c, c) : null;
    if (g) { g.addColorStop(0, "rgba(79,209,224,0)"); g.addColorStop(0.12, "rgba(79,209,224,.45)"); g.addColorStop(0.125, "rgba(79,209,224,0)"); ctx.fillStyle = g; ctx.beginPath(); ctx.arc(c, c, 120, 0, 7); ctx.fill(); }
    for (const [d, ang, col] of theatres) {
      const diff = ((a - ang) % (2 * Math.PI) + 2 * Math.PI) % (2 * Math.PI);
      const alpha = Math.max(0.15, 1 - diff / 3);
      ctx.fillStyle = col; ctx.globalAlpha = alpha; ctx.beginPath(); ctx.arc(c + Math.cos(ang) * d * 120, c + Math.sin(ang) * d * 120, 5, 0, 7); ctx.fill(); ctx.globalAlpha = 1;
    }
    a += 0.05; raf = requestAnimationFrame(draw);
  };
  draw();
  return {
    progress: (f: number) => { (pre.querySelector(".pc") as HTMLElement).textContent = `ACQUIRING · ${Math.round(f * 100)}%`; },
    done: () => { (pre.querySelector(".wm") as HTMLElement).style.opacity = "1"; setTimeout(() => { pre.style.opacity = "0"; setTimeout(() => { cancelAnimationFrame(raf); pre.remove(); }, 700); }, 650); },
  };
}

/** A reload inside an embedding frame (Streamlit serves the site as an about:srcdoc iframe) drops the
 *  URL hash, so the view switch was lost and the Commander view came back. The target hash is kept in
 *  window.name, which survives a reload of the same frame, and restored before the view is chosen. */
const KEEP = "cw-hash:";
export function reloadKeepingHash() { try { window.name = KEEP + location.hash; } catch {} location.reload(); }
function restoreHash() {
  try {
    if (window.name.startsWith(KEEP)) {
      const h = window.name.slice(KEEP.length); window.name = "";
      if (h && !location.hash) { try { history.replaceState(null, "", h); } catch { location.hash = h; } }
    }
  } catch {}
}

/** In an about:srcdoc frame (Streamlit), a plain <a href="#x"> resolves against the parent page's URL and
 *  loads the whole Streamlit app inside the frame. Same-page hash links are therefore applied by script. */
function keepHashLinksInPage() {
  document.addEventListener("click", (e) => {
    if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey) return;
    const a = (e.target as Element).closest?.("a[href^='#']") as HTMLAnchorElement | null;
    if (!a || a.target === "_blank") return;
    e.preventDefault();
    const h = a.getAttribute("href")!;
    if (h === "#" ) return;
    if (location.hash === h) { const t = document.getElementById(decodeURIComponent(h.slice(1))); t?.scrollIntoView(); return; }
    location.hash = h;
  });
}

async function boot() {
  keepHashLinksInPage();
  restoreHash();
  initTheme();
  const P = preloader();
  try {
    const D = await loadData(P.progress);
    const was = mode();
    if (was === "console") (await import("./console")).renderConsole(D);
    else if (was === "story") (await import("./story")).renderStory(D);
    else (await import("./commander")).renderCommander(D);
    if (D.inline) {
      document.querySelectorAll<HTMLAnchorElement>("#to-console").forEach((a) => (a.href = "#console"));
      document.querySelectorAll<HTMLAnchorElement>("#to-story").forEach((a) => (a.href = "#cmd"));
    }
    // Inside the console, page links are plain hashes (#theatre, #map): they must not be read as story chapters.
    const next = () => (was === "console" && location.hash !== "#cmd" && !isStoryOnly() ? "console" : mode());
    addEventListener("hashchange", () => { if (next() !== was) reloadKeepingHash(); });
    P.done();
  } catch (e) {
    console.error(e);
    (document.querySelector("#pre .pc") as HTMLElement).textContent = "DATA LOAD FAILED · " + (e as Error).message;
  }
  try {
    const D2 = await loadData();
    if (!D2.inline && "serviceWorker" in navigator && location.protocol.startsWith("http")) {
      const root = new URL(document.body.dataset.mode === "console" ? "../" : "./", location.href);
      navigator.serviceWorker.register(new URL("sw.js", root), { scope: root.pathname });
    }
  } catch {}
}
boot();
