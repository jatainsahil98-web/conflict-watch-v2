// Record crisp 1080p clips for the promo video (CDP screencast, JPEG frames).
//   (cd app/static && python3 -m http.server 8601) ; streamlit run app/app.py --server.port 8599
//   NODE_PATH=$(npm root -g) node deck/record_promo.js   -> deck/promo_raw/<clip>/ + frames.txt
//   python3 deck/build_promo.py                          -> deck/Conflict_Watch_Promo.mp4
const { chromium } = require('playwright');
const fs = require('fs'), path = require('path');
const W = 1920, H = 1080, OUT = path.resolve(__dirname, 'promo_raw');
const SITE = 'http://localhost:8601/site/', DASH = 'http://localhost:8599';

async function clip(browser, name, url, act, warm = 6000, prep = null) {
  const dir = path.join(OUT, name); fs.rmSync(dir, { recursive: true, force: true }); fs.mkdirSync(dir, { recursive: true });
  const ctx = await browser.newContext({ viewport: { width: W, height: H }, deviceScaleFactor: 1 });
  const p = await ctx.newPage();
  await p.goto(url, { waitUntil: 'networkidle' }); await p.waitForTimeout(warm);
  if (prep) await prep(p, ms => p.waitForTimeout(ms));
  await p.mouse.move(W - 4, H - 4);
  const cdp = await ctx.newCDPSession(p); const frames = [];
  cdp.on('Page.screencastFrame', async f => {
    const fn = String(frames.length).padStart(5, '0') + '.jpg';
    fs.writeFileSync(path.join(dir, fn), Buffer.from(f.data, 'base64'));
    frames.push([fn, f.metadata.timestamp]);
    try { await cdp.send('Page.screencastFrameAck', { sessionId: f.sessionId }); } catch (e) {}
  });
  await cdp.send('Page.startScreencast', { format: 'jpeg', quality: 93, maxWidth: W, maxHeight: H });
  const t0 = Date.now() / 1000;
  await act(p, ms => p.waitForTimeout(ms));
  const t1 = Date.now() / 1000;
  await cdp.send('Page.stopScreencast');
  await p.waitForTimeout(300);
  // ffconcat with real durations; last frame held until the end of the action
  let s = 'ffconcat version 1.0\n';
  for (let i = 0; i < frames.length; i++) {
    const next = i + 1 < frames.length ? frames[i + 1][1] : Math.max(t1, frames[i][1] + 0.04);
    const start = i === 0 ? Math.min(frames[0][1], t0) : frames[i][1];
    s += `file '${frames[i][0]}'\nduration ${Math.max(0.001, next - start).toFixed(4)}\n`;
  }
  s += `file '${frames[frames.length - 1][0]}'\n`;
  fs.writeFileSync(path.join(dir, 'frames.txt'), s);
  console.log(name, frames.length, 'frames', (t1 - t0).toFixed(1), 's');
  await ctx.close();
}

const smooth = async (p, wait, px, ms) => {           // eased wheel scroll
  const n = Math.round(ms / 40);
  for (let i = 1; i <= n; i++) { const e = (1 - Math.cos(Math.PI * i / n)) / 2, e0 = (1 - Math.cos(Math.PI * (i - 1) / n)) / 2;
    await p.mouse.wheel(0, px * (e - e0)); await wait(40); }
};
const glide = async (p, wait, x0, y0, x1, y1, ms) => { // visible cursor-free hover glide
  const n = Math.round(ms / 40);
  for (let i = 0; i <= n; i++) { const e = (1 - Math.cos(Math.PI * i / n)) / 2; await p.mouse.move(x0 + (x1 - x0) * e, y0 + (y1 - y0) * e); await wait(40); }
};

(async () => {
  const b = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl', '--ignore-gpu-blocklist'] });
  const only = process.argv.slice(2);
  const run = (n, ...a) => (!only.length || only.includes(n)) ? clip(b, n, ...a) : null;

  await run('hero', SITE + 'index.html', async (p, wait) => { await wait(9000); }, 2500);
  await run('bluf', SITE + 'index.html#bluf', async (p, wait) => {
    await wait(1200); await glide(p, wait, 300, 500, 1500, 520, 4000); await wait(1500);
  });
  await run('india', SITE + 'index.html#india', async (p, wait) => {
    await wait(1500); await glide(p, wait, 1100, 300, 1500, 700, 4000); await wait(1500);
  });
  await run('predict', SITE + 'index.html#prediction', async (p, wait) => {
    await wait(800);
    const tr = await p.$('#pl'); if (tr) await p.evaluate(() => { const r = document.querySelector('#pl'); r.value = 0; r.dispatchEvent(new Event('input', { bubbles: true })); });
    await wait(600);
    const btn = await p.$('#pl-play'); if (btn) await btn.click();
    await p.mouse.move(W - 4, H - 4); await wait(7600);
  });
  await run('warning', SITE + 'console/index.html#warning?month=2026-01&thr=0.15', async (p, wait) => {
    await wait(1500);
    for (const m of ['2026-02', '2026-03']) {
      await p.evaluate(m => { location.hash = 'warning?month=' + m + '&thr=0.15'; }, m); await wait(2400);
    }
    await wait(1200);
  }, 5000);
  await run('whatif', SITE + 'console/index.html#whatif?c=afpak&shock=0&m=3', async (p, wait) => {
    await wait(1200);
    for (const s of [10, 20, 30]) { await p.evaluate(s => { location.hash = 'whatif?c=afpak&shock=' + s + '&m=3'; }, s); await wait(1700); }
    await wait(1500);
  }, 5000);
  await run('dash', DASH, async (p, wait) => {
    await wait(800); await glide(p, wait, 1200, 760, 1700, 900, 3500); await glide(p, wait, 1700, 900, 1250, 840, 2500); await wait(1200);
  }, 9000, async (p, wait) => {
    await p.locator('[data-testid="stSidebar"] label', { hasText: 'Analyst dashboard' }).first().click(); await wait(6000);
    await p.locator('[data-testid="stSidebar"] [role="radiogroup"] label', { hasText: 'Scorecard lab' }).first().click(); await wait(9000);
    await p.mouse.move(W - 4, H - 4);
  });
  await b.close();
})();
