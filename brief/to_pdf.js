// HTML -> PDF for the brief and Q&A sheet:  NODE_PATH=$(npm root -g) node brief/to_pdf.js
const { chromium } = require('playwright');
const path = require('path');
(async () => {
  const b = await chromium.launch();
  for (const n of ['Commanders_Brief', 'QA_Prep_and_Speaker_Split']) {
    const p = await b.newPage();
    await p.goto('file://' + path.resolve(__dirname, n + '.html'), { waitUntil: 'networkidle' });
    await p.pdf({ path: path.resolve(__dirname, n + '.pdf'), format: 'A4', printBackground: true,
      margin: { top: '0', bottom: '0', left: '0', right: '0' }, preferCSSPageSize: true });
    await p.close();
  }
  await b.close();
})();
