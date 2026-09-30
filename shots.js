// Screenshot tiap tab dashboard + cek console error.
const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1440, height: 1000 } });
  const errs = [];
  p.on('pageerror', e => errs.push('PAGEERROR: ' + e.message));
  p.on('console', m => { if (m.type() === 'error') errs.push('CONSOLE: ' + m.text()); });
  await p.goto('file:///C:/Users/MSI/AppData/Local/Temp/artikel2026/index.html');
  await p.waitForTimeout(800);
  const tabs = ['overview', 'pipeline', 'strategi', 'aksi'];
  for (const t of tabs) {
    await p.click(`.tab[data-tab="${t}"]`);
    await p.waitForTimeout(400);
    await p.screenshot({ path: `shot-${t}.png`, fullPage: t === 'overview' });
    console.log(t, 'ok', await p.evaluate(() => document.querySelectorAll('tbody tr').length), 'rows');
  }
  // uji filter
  await p.click('.tab[data-tab="pipeline"]');
  await p.selectOption('#f-status', 'Overdue');
  await p.waitForTimeout(400);
  console.log('filter Overdue ->', await p.evaluate(() => document.querySelectorAll('tbody tr').length), 'rows');
  await p.screenshot({ path: 'shot-overdue.png' });
  console.log('errors:', errs.length ? errs.join('\n') : 'NONE');
  await b.close();
})();
