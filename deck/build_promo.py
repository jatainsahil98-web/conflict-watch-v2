"""Edit the promo video from the clips that deck/record_promo.js captured.

Title card -> seven captioned clips with slow push-in zooms -> end card, joined with
cross-fades. Captions, cards and logos are rendered as PNGs by headless Chromium so
they use the same type and colours as the Ops site. Every number comes from
app/static/site/data/facts.json (the exported pipeline output).

    python3 deck/build_promo.py   -> deck/Conflict_Watch_Promo.mp4 (+ poster PNG)
"""
import json, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.brand import data_uri, JIMMY, MCTE  # noqa: E402

RAW, WORK = ROOT / "deck" / "promo_raw", ROOT / "deck" / "promo_raw" / "_build"
OUT = ROOT / "deck" / "Conflict_Watch_Promo.mp4"
POSTER = ROOT / "deck" / "Conflict_Watch_Promo_poster.png"
WORK.mkdir(parents=True, exist_ok=True)
F = json.loads((ROOT / "app/static/site/data/facts.json").read_text())
RUN = F["run_id"]
TEAM = " · ".join(F["team"])
LB = {r["model"]: r for r in F["forecasting"]["leaderboard"]}
GAIN = F["forecasting"]["mae_pooled"]  # pooled 1-month MAE gain vs no change
W_ = F["warning"]
RAT = {c["short"]: c["rating"] for c in F["scorecard"]}
FPS, XF = 30, 0.6

# clip, seconds, (zoom focus x, y in 0..1), zoom end, kicker, title, sub
CLIPS = [
    ("hero", 8.8, (0.62, 0.40), 1.10, "OPS SITE · BRIEFING STORY", "Four wars on one globe, 2014–2026",
     "Russia–Ukraine · Israel–Hamas · Afghanistan–Pakistan · US–Iran"),
    ("bluf", 8.6, (0.42, 0.42), 1.08, "COMMANDER'S BRIEF · OCTOBER 2026",
     f"One {RAT['RU–UA']}, two AMBER, one GREEN", "Every rating is traced to model outputs through five transparent rules"),
    ("india", 9.0, (0.62, 0.55), 1.10, "INDIA IMPACT", "The 2026 US–Iran war reached India's neighbourhood",
     "14 countries hit · 5 Gulf states struck · 104 killed off Sri Lanka"),
    ("predict", 9.3, (0.40, 0.55), 1.07, "VALIDATION · WITHHELD 2026 DATA", f"Forecast error {GAIN}% lower than 'no change'",
     "Models frozen at December 2025 and scored on months they never saw"),
    ("warning", 7.3, (0.35, 0.50), 1.08, "OPS CONSOLE · EARLY WARNING", f"{W_['areas']} areas scored for next month",
     f"AUC {W_['auc']:.2f} · the top-10 list is {W_['lift']}× better than random"),
    ("whatif", 7.6, (0.55, 0.48), 1.08, "OPS CONSOLE · WHAT-IF SIMULATOR", "Af–Pak violence up 30% for three months",
     "The ensemble re-forecasts instantly, with calibrated 80% bands"),
    ("dash", 7.7, (0.60, 0.45), 1.06, "ANALYST DASHBOARD · 12 PAGES", "Change the rules, watch the ratings move",
     "Russia–Ukraine stays RED under any sensible rule set"),
]
INTRO_S, OUTRO_S = 5.0, 6.5
CAP_TOP = {"hero": 150}  # clips whose own text sits at the bottom get the caption up top

CSS = """
*{margin:0;box-sizing:border-box} body{width:1920px;height:1080px;background:transparent;font-family:Inter,sans-serif;overflow:hidden}
.mono{font-family:'DejaVu Sans Mono',monospace}
.card{position:absolute;inset:0;background:radial-gradient(1200px 700px at 50% 40%,#13233d 0%,#0a1322 55%,#060b14 100%);color:#e8eef8}
.grid{position:absolute;inset:0;background-image:linear-gradient(rgba(94,234,212,.06) 1px,transparent 1px),linear-gradient(90deg,rgba(94,234,212,.06) 1px,transparent 1px);background-size:64px 64px}
.bar{position:absolute;left:0;right:0;height:10px;background:#2fbf71}.bar.t{top:0}.bar.b{bottom:0}
.lg{position:absolute;top:56px;height:150px}.lg.l{left:70px}.lg.r{right:70px}
.br{position:absolute;width:60px;height:60px;border-color:#F0B03A;border-style:solid}
"""


def html_card(kind):
    j, m = data_uri(JIMMY), data_uri(MCTE)
    brackets = "".join(f'<div class="br" style="{p}"></div>' for p in [
        "left:40px;top:240px;border-width:3px 0 0 3px", "right:40px;top:240px;border-width:3px 3px 0 0",
        "left:40px;bottom:60px;border-width:0 0 3px 3px", "right:40px;bottom:60px;border-width:0 3px 3px 0"])
    if kind == "intro":
        body = f"""<div style="position:absolute;top:330px;width:100%;text-align:center">
<div class="mono" style="color:#F0B03A;letter-spacing:10px;font-size:30px;font-weight:700">DATA ANALYTICS COMPETITION 2026</div>
<div style="font-size:150px;font-weight:900;letter-spacing:6px;margin-top:26px">CONFLICT WATCH</div>
<div style="font-size:52px;font-weight:700;margin-top:18px">Four wars. <span style="color:#5eead4">One exposed neighbour.</span></div>
<div class="mono" style="font-size:26px;color:#9fb0c8;margin-top:56px;letter-spacing:3px">LIVE DEMO · OPS SITE · OPS CONSOLE · ANALYST DASHBOARD</div></div>"""
    else:
        body = f"""<div style="position:absolute;top:290px;width:100%;text-align:center">
<div style="font-size:64px;font-weight:800;line-height:1.2">Open data and an honest model<br>tell India <span style="color:#F0B03A">where to look next month.</span></div>
<div class="mono" style="font-size:38px;color:#5eead4;margin-top:60px">conflictmonitor2026.streamlit.app</div>
<div style="font-size:30px;color:#c9d4e4;margin-top:40px">{TEAM}</div>
<div class="mono" style="font-size:24px;color:#9fb0c8;margin-top:30px;letter-spacing:3px">DATA ANALYTICS COMPETITION 2026 · RUN ID {RUN} · COMPETITION DATA ONLY</div></div>"""
    return f"""<html><head><style>{CSS}</style></head><body><div class="card"><div class="grid"></div><div class="bar t"></div><div class="bar b"></div>
<img class="lg l" src="{j}"><img class="lg r" src="{m}">{brackets}{body}</div></body></html>"""


def html_caption(i, kicker, title, sub, top=None):
    n = f"{i:02d} / {len(CLIPS):02d}"
    pos = f"top:{top}px" if top else "bottom:70px"
    return f"""<html><head><style>{CSS}</style></head><body>
<div style="position:absolute;left:64px;{pos};max-width:1300px;background:rgba(6,11,20,.90);border:1px solid rgba(240,176,58,.45);
 border-left:8px solid #F0B03A;border-radius:8px;padding:22px 34px 24px 30px;box-shadow:0 12px 40px rgba(0,0,0,.6)">
 <div class="mono" style="color:#F0B03A;font-size:21px;letter-spacing:4px;font-weight:700">{kicker}<span style="color:#5d6b80;margin-left:22px">{n}</span></div>
 <div style="color:#fff;font-size:46px;font-weight:800;margin-top:8px;line-height:1.15">{title}</div>
 <div style="color:#b8c6da;font-size:26px;margin-top:8px">{sub}</div></div>
<div class="mono" style="position:absolute;right:64px;bottom:76px;color:rgba(232,238,248,.75);font-size:19px;letter-spacing:3px;
 background:rgba(6,11,20,.75);padding:8px 14px;border-radius:6px">RUN {RUN}</div></body></html>"""


def render_pngs():
    jobs = {"intro": html_card("intro"), "outro": html_card("outro")}
    for i, (c, _, _, _, k, t, s) in enumerate(CLIPS, 1):
        jobs["cap_" + c] = html_caption(i, k, t, s, CAP_TOP.get(c))
    for k, h in jobs.items():
        (WORK / f"{k}.html").write_text(h)
    js = WORK / "render.js"
    js.write_text("""const { chromium } = require('playwright');
(async () => { const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 1920, height: 1080 } });
for (const k of process.argv.slice(2)) { await p.goto('file://' + __dirname + '/' + k + '.html'); await p.waitForTimeout(300);
  await p.screenshot({ path: __dirname + '/' + k + '.png', omitBackground: true }); } await b.close(); })();""")
    npm_root = subprocess.run(["npm", "root", "-g"], capture_output=True, text=True).stdout.strip()
    subprocess.run(["node", str(js), *jobs], check=True, env={**__import__("os").environ, "NODE_PATH": npm_root})


def ff(*a):
    subprocess.run(["ffmpeg", "-v", "error", "-y", *a], check=True)


def build():
    render_pngs()
    enc = ["-c:v", "libx264", "-preset", "slow", "-crf", "17", "-pix_fmt", "yuv420p", "-r", str(FPS)]
    parts = []
    for k, d in (("intro", INTRO_S), ("outro", OUTRO_S)):
        n = int(d * FPS)
        ff("-loop", "1", "-i", str(WORK / f"{k}.png"), "-t", str(d), "-vf",
           f"scale=7680:4320:flags=lanczos,zoompan=z='1.0+0.04*on/{n}':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d=1:s=1920x1080:fps={FPS}",
           *enc, str(WORK / f"{k}.mp4"))
    parts.append(("intro", INTRO_S))
    for c, d, (fx, fy), z1, *_ in CLIPS:
        n = int(d * FPS)
        z = f"1+{z1 - 1:.3f}*(0.5-0.5*cos(PI*on/{n}))"
        vf = (f"[0]fps={FPS},scale=1920:1080:flags=lanczos,setsar=1,trim=duration={d},"
              f"null[v];"  # no zoom on screen clips: zoompan rounds to whole pixels and makes text shake
              f"[1]format=rgba,fade=in:st=0.5:d=0.45:alpha=1,fade=out:st={d - 0.9:.2f}:d=0.45:alpha=1[c];"
              f"[v][c]overlay=0:0:shortest=1[o]")
        ff("-f", "concat", "-safe", "0", "-i", str(RAW / c / "frames.txt"), "-loop", "1", "-t", str(d),
           "-i", str(WORK / f"cap_{c}.png"), "-filter_complex", vf, "-map", "[o]", "-t", str(d), *enc, str(WORK / f"{c}.mp4"))
        parts.append((c, d))
    parts.append(("outro", OUTRO_S))
    # cross-fade chain
    ins, fc, off, last = [], [], 0.0, "0"
    for i, (k, d) in enumerate(parts):
        ins += ["-i", str(WORK / f"{k}.mp4")]
        if i == 0:
            off = d - XF
            continue
        lab = f"x{i}"
        fc.append(f"[{last}][{i}]xfade=transition={'fadeblack' if i in (1, len(parts) - 1) else 'smoothleft' if i % 2 else 'fade'}:duration={XF}:offset={off:.3f}[{lab}]")
        last, off = lab, off + d - XF
    fc.append(f"[{last}]fade=in:st=0:d=0.5,fade=out:st={off + XF - 0.6:.2f}:d=0.6,format=yuv420p[out]")
    ff(*ins, "-filter_complex", ";".join(fc), "-map", "[out]", "-c:v", "libx264", "-preset", "slow", "-crf", "18",
       "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(OUT))
    ff("-ss", "1.8", "-i", str(OUT), "-frames:v", "1", str(POSTER))
    dur = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(OUT)],
                         capture_output=True, text=True).stdout.strip()
    print(f"{OUT.relative_to(ROOT)}  {float(dur):.1f} s  {OUT.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    build()
