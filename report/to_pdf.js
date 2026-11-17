// HTML -> PDF with headless Chromium:  NODE_PATH=$(npm root -g) node report/to_pdf.js
const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');
const RUN = fs.readFileSync(path.resolve(__dirname, '../outputs/tables/run_id.txt'), 'utf8').trim();
(async () => {
  const b = await chromium.launch();
  const p = await b.newPage();
  const src = path.resolve(__dirname, 'Conflict_Watch_Report.html');
  await p.goto('file://' + src, { waitUntil: 'networkidle' });
  await p.pdf({ path: path.resolve(__dirname, 'Conflict_Watch_Report.pdf'), format: 'A4', printBackground: true,
    displayHeaderFooter: true, headerTemplate: '<span></span>',
    footerTemplate: '<div style="font-size:7px;width:100%;text-align:center;color:#5E7B99">CONFLICT WATCH | DATA ANALYTICS COMPETITION 2026 | UNCLASSIFIED - COMPETITION DATA ONLY | RUN ' + RUN + ' | <span class="pageNumber"></span>/<span class="totalPages"></span></div>',
    margin: { top: '12mm', bottom: '14mm', left: '12mm', right: '12mm' } });
  await b.close();
})();
