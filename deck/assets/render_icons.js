// Render the Lucide SVG icons (ISC licence) in deck/assets/icons/svg to white 256px PNGs.
// node deck/assets/render_icons.js   (needs Playwright; PNGs are committed, so this is only needed to add icons)
const { chromium } = require('playwright');
const fs = require('fs'), path = require('path');
(async () => {
  const dir = path.join(__dirname, 'icons'), svgDir = path.join(dir, 'svg');
  const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 256, height: 256 } });
  for (const f of fs.readdirSync(svgDir).filter(f => f.endsWith('.svg'))) {
    const svg = fs.readFileSync(path.join(svgDir, f), 'utf8').replace(/<!--.*?-->/s, '')
      .replace('width="24"', 'width="256"').replace('height="24"', 'height="256"').replace('stroke="currentColor"', 'stroke="#ffffff"');
    await p.setContent(`<html><body style="margin:0;background:transparent">${svg}</body></html>`);
    await p.locator('svg').screenshot({ path: path.join(dir, f.replace('.svg', '.png')), omitBackground: true });
  }
  await b.close(); console.log('icons rendered');
})();
