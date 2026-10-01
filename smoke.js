// Headless smoke-test dashboard: jalankan inline script dengan DOM stub,
// lalu panggil tiap view function dan cek tidak ada exception.
const fs = require('fs');
const html = fs.readFileSync(process.argv[2], 'utf8');
const m = html.match(/<script>\r?\n([\s\S]*?)\r?\n<\/script>/);
if (!m) { console.error('script block not found'); process.exit(1); }
const code = m[1];

const el = () => ({ textContent: '', innerHTML: '', dataset: {}, style: {},
  onchange: null, oninput: null, onclick: null, focus(){}, setSelectionRange(){},
  selectionStart: 0 });
global.__els = {};
global.document = {
  getElementById: (id) => (global.__els[id] ||= el()),
  querySelectorAll: () => [],
  querySelector: () => null,
};
global.location = { protocol: 'file:' };
global.fetch = () => Promise.reject(new Error('no fetch'));

const wrapped = code + `
;module.exports = { ARTICLES, BRANDS, CLIENTS, MONTHS, agg, status, metrics,
  viewWork, viewSite, viewKeyword, viewReport, viewAksi, filtered, F, LAPORAN, IDEAS, LANDING_GAP };`;

const api = eval(wrapped);

let fail = 0;
const check = (name, fn) => {
  try { const out = fn(); console.log(`${name.padEnd(12)} ok  ${out.length} bytes`); }
  catch (e) { fail++; console.log(`${name.padEnd(12)} FAIL ${e.message}`); }
};
// 4 tab yang benar-benar dipakai (sisanya sudah dibuang dari TABS)
check('work', api.viewWork);
check('site', api.viewSite);
check('keyword', api.viewKeyword);
check('report', api.viewReport);
check('aksi', api.viewAksi);
check('laporan', () => { const n = Object.keys(api.LAPORAN).length;
  if (!n) throw new Error('LAPORAN kosong'); return 'x'.repeat(n); });
check('ideas', () => { const n = api.IDEAS.length;
  if (!n) throw new Error('IDEAS kosong'); return 'x'.repeat(n); });
check('gap', () => { const n = api.LANDING_GAP.length;
  if (!n) throw new Error('LANDING_GAP kosong'); return 'x'.repeat(n); });

console.log('\narticles:', api.ARTICLES.length, '| clients:', api.CLIENTS.length, '| months:', api.MONTHS.length);
const st = {};
api.ARTICLES.forEach(a => { const s = api.status(a); st[s] = (st[s] || 0) + 1; });
console.log('status:', JSON.stringify(st));
const a = api.agg(api.ARTICLES);
console.log('agg:', JSON.stringify(a));

// filter smoke
api.F.client = api.CLIENTS[0]; api.F.month = api.MONTHS[0];
console.log('filter', api.F.client, api.F.month, '->', api.filtered().length, 'rows');
api.F.client = ''; api.F.month = ''; api.F.status = 'Overdue';
console.log('filter Overdue ->', api.filtered().length, 'rows');
check('aksi(overdue)', api.viewAksi);

process.exit(fail ? 1 : 0);
