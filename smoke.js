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
global.location = { protocol: 'file:', hash: '' };
global.history = { replaceState(){} };
global.fetch = () => Promise.reject(new Error('no fetch'));

const wrapped = code + `
;module.exports = { ARTICLES, BRANDS, CLIENTS, MONTHS, agg, status, metrics,
  viewWork, viewSite, viewArticles, viewKeyword, viewReport, viewAksi, filtered, F, POSTS,
  articlesRows, LAPORAN, IDEAS, LANDING_GAP,
  tabsFor, syncModeUI, buildReport, globalWeeks, render,
  tabsHtml: ()=>document.getElementById('tabs').innerHTML,
  setMode: (m)=>setMode(m), get mode(){return mode;} };`;

const api = eval(wrapped);

let fail = 0;
const check = (name, fn) => {
  try { const out = fn(); console.log(`${name.padEnd(12)} ok  ${out.length} bytes`); }
  catch (e) { fail++; console.log(`${name.padEnd(12)} FAIL ${e.message}`); }
};
// 4 tab yang benar-benar dipakai (sisanya sudah dibuang dari TABS)
check('work', api.viewWork);
check('site', api.viewSite);
check('articles', api.viewArticles);
check('keyword', api.viewKeyword);
check('report', api.viewReport);
check('aksi', api.viewAksi);
check('laporan', () => { const n = Object.keys(api.LAPORAN).length;
  if (!n) throw new Error('LAPORAN kosong'); return 'x'.repeat(n); });
check('ideas', () => { const n = api.IDEAS.length;
  if (!n) throw new Error('IDEAS kosong'); return 'x'.repeat(n); });
check('gap', () => { const n = api.LANDING_GAP.length;
  if (!n) throw new Error('LANDING_GAP kosong'); return 'x'.repeat(n); });

// dual-mode + Tarik Report
check('tabs(mode2)', () => 'x'.repeat(api.tabsFor().length));
api.setMode('1');
if (api.tabsFor().length !== 2) throw new Error('Mode 1 harus 2 tab, dapat ' + api.tabsFor().length);
if (api.mode !== '1') throw new Error('mode tidak berubah');
api.setMode('2');
if (api.tabsFor().length !== 6) throw new Error('Mode 2 harus 6 tab');
check('weeks', () => 'x'.repeat(api.globalWeeks().length));
check('report-m2', () => api.buildReport());
api.setMode('1');
const r1 = api.buildReport();
if (r1.includes('Butuh Tindakan')) throw new Error('Mode 1 masih menyisip blok operasional');
check('report-m1', () => r1);
api.setMode('2');

// render() di kedua mode: pastikan tab + view benar-benar dirender
api.setMode('1'); api.render();
const t1 = api.tabsHtml();
if (!t1.includes('Performa Website') || !t1.includes('Laporan Klien'))
  throw new Error('Mode 1: tab ringkasan tidak render: ' + JSON.stringify(t1).slice(0,200));
if (t1.includes('data-tab="aksi"') || t1.includes('data-tab="keyword"') || t1.includes('data-tab="articles"'))
  throw new Error('Mode 1: tab operasional masih tampil: ' + t1);
api.setMode('2'); api.render();
const t2 = api.tabsHtml();
['work','site','articles','keyword','report','aksi'].forEach(k => {
  if (!t2.includes(`data-tab="${k}"`)) throw new Error('Mode 2: tab hilang ' + k);
});
console.log('render mode1 ->', t1.length, 'bytes; mode2 ->', t2.length, 'bytes');

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
