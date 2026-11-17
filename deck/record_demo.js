// Record a ~2.5-minute backup demo of the dashboard (silent, with on-screen captions).
//   streamlit run app/app.py   (in another terminal, port 8501)
//   NODE_PATH=$(npm root -g) node deck/record_demo.js
//   ffmpeg -i deck/demo_raw/<file>.webm -c:v libx264 -pix_fmt yuv420p -crf 22 deck/Conflict_Watch_Demo.mp4
const { chromium } = require('playwright');
const path = require('path');
const W = 1600, H = 900;

(async () => {
  const b = await chromium.launch();
  const ctx = await b.newContext({ viewport: { width: W, height: H },
    recordVideo: { dir: path.resolve(__dirname, 'demo_raw'), size: { width: W, height: H } } });
  const p = await ctx.newPage();
  const wait = ms => p.waitForTimeout(ms);
  const caption = async (t, sub = '') => {
    await p.evaluate(([t, sub]) => {
      let d = document.getElementById('cw-cap');
      if (!d) {
        d = document.createElement('div'); d.id = 'cw-cap';
        d.style.cssText = 'position:fixed;left:50%;transform:translateX(-50%);bottom:26px;z-index:999999;' +
          'background:rgba(42,32,8,.96);border:2px solid #F0B03A;border-radius:10px;padding:12px 26px;' +
          'font:700 24px Calibri,Carlito,sans-serif;color:#fff;max-width:1250px;text-align:center;' +
          'box-shadow:0 6px 24px rgba(0,0,0,.6)';
        document.body.appendChild(d);
      }
      d.style.display = 'block';
      d.innerHTML = t + (sub ? '<div style="font-weight:400;font-size:18px;color:#F0B03A;margin-top:4px">' + sub + '</div>' : '');
    }, [t, sub]);
  };
  const nav = async i => {
    const ls = await p.$$('[data-testid="stSidebar"] [role="radiogroup"] label');
    await p.evaluate(() => { const d = document.getElementById('cw-cap'); if (d) d.style.display = 'none'; });
    await ls[i].click();
    await wait(4500);
    await p.mouse.move(1000, 450);
  };
  const scroll = async (px, steps = 6, ms = 600) => {
    await p.mouse.move(1000, 450);
    for (let i = 0; i < steps; i++) { await p.mouse.wheel(0, px / steps); await wait(ms); }
  };

  await p.goto('http://localhost:8501', { waitUntil: 'networkidle' });
  await wait(7000);
  await caption('CONFLICT WATCH: live dashboard', 'Where will conflict deaths rise next, and what does it mean for India?');
  await wait(6000);
  await caption('Commander\'s brief: threat scorecard for October 2026', 'Russia–Ukraine RED · Af–Pak and US–Iran AMBER · Israel–Hamas GREEN');
  await wait(7000);
  await caption('Tested on unseen 2026 data', 'Forecast error −29% vs "no change" · escalation warning AUC 0.79 · 83% inside the 80% band');
  await wait(7000);
  await scroll(700);
  await caption('Key findings and India impact, each tagged DATA or DOMAIN');
  await wait(7000);

  await nav(2);
  await caption('Area drill-down: any of 222 areas, with its own warning history', 'Deaths, events, bottom-up forecast and out-of-sample escalation probability');
  await wait(7000);
  await scroll(600, 6, 600);
  await wait(4000);

  await nav(3);
  await caption('Military lens: the Ukrainian front is widening, not moving', 'Donetsk share of located events 55% → 30%, 2022 → 2026');
  await wait(6500);
  await scroll(900, 8, 700);
  await caption('Pakistan fights on two fronts', 'Afghan and Pakistani forces clash directly since Oct 2025 · 411 deaths in Mar 2026');
  await wait(6500);

  await nav(4);
  await caption('India impact: the 2026 war reached the Gulf, Hormuz and Sri Lankan waters', '104 killed off Sri Lanka on 4 Mar 2026 · 5 Gulf states struck');
  await wait(7000);
  await scroll(800, 6, 700);
  await wait(4000);

  await nav(7);
  await caption('Forecast vs actual on the withheld 2026 months', 'Models frozen at Dec 2025 · shaded band = 80% conformal interval');
  await wait(7000);
  await scroll(600, 6, 700);
  await wait(4000);

  await nav(8);
  await caption('Early warning: 222 districts and provinces scored for next month', 'Top-10 list is 3.5× better than random');
  await wait(7000);
  await p.getByRole('tab', { name: /Replay/ }).click();
  await wait(3500);
  await caption('Replay a 2026 month: what was flagged, and what escalated');
  await scroll(500, 5, 600);
  await wait(7000);

  await p.mouse.wheel(0, -3000); await wait(800);
  await p.getByRole('tab', { name: /Alert threshold/ }).click();
  await caption('Alert threshold: trade precision against recall live');
  await wait(6000);

  await nav(9);
  await caption('What-if simulator: Af–Pak violence +30% for three months', 'The ensemble re-forecasts with calibrated bands');
  await wait(6500);
  const btn = await p.$('button:has-text("Train now")');
  if (btn) {
    await btn.scrollIntoViewIfNeeded(); await wait(1500);
    await caption('Live re-train: LightGBM-Δ fitted from scratch in seconds');
    await btn.click(); await wait(7000);
  }

  await nav(10);
  await caption('Scorecard lab: change the rules, watch the ratings move', 'Every input is a model output, so the RED / AMBER / GREEN rating is auditable');
  await wait(5000);
  await p.getByRole('slider').nth(1).focus();
  for (let i = 0; i < 6; i++) { await p.keyboard.press('ArrowLeft'); await wait(900); }
  await wait(4000);

  await nav(11);
  await caption('Data quality and method: 36 documented checks, nothing silently dropped');
  await wait(6500);

  await nav(0);
  await caption('Open data and an honest model can tell India where to look next month.', 'CONFLICT WATCH · Data Analytics Competition 2026 · Maj Shivam Mehta, Capt Siddharth Sangwan, Capt Sahil Singh');
  await wait(7000);

  await ctx.close();
  await b.close();
})();
