# Dashboard Kinerja Artikel & Strategi Konten

Dashboard SEO untuk memantau **1.326 artikel** (Apr–Okt 2026, 23 klien) dari kertas kerja
Google Sheets **"Artikel 2026"**. Pola mengikuti dashboard `keyword-analysis` punya mas Syafii,
tapi di sini unitnya **artikel**, bukan landing page.

## Isi dashboard (5 tab)

| Tab | Fungsi |
|---|---|
| 📊 Ringkasan | KPI total, produksi per bulan, kinerja per klien (posted/overdue/draft/keyword/CTA + impresi/klik/CTR/rank kalau data GSC sudah masuk) |
| 🏭 Pipeline Produksi | Filter bulan/klien/status/cari, daftar artikel + status, deadline, catatan `Keterangan`, link draft & live |
| 📈 Performa Artikel | Per klien & per artikel: impresi, klik, CTR, rank, sparkline tren harian — sumber Google Search Console |
| 🎯 Strategi Konten | Kelengkapan SEO per klien (% keyword, % CTA), artikel tanpa keyword, tanpa CTA, rencana konten bulan depan |
| 🛠️ Aksi & Perbaikan | Overdue, deadline ≤7 hari masih draft, artikel impresi tinggi tapi CTR <1,5%, rencana aksi massal per klien |

## Struktur

```
index.html          <- dashboard self-contained (data di-inject, siap GitHub Pages)
template.html       <- sumber HTML/JS
data/articles.json  <- inventaris artikel (hasil parsing kertas kerja)
data/brands.json    <- domain <-> klien
data/gsc.json       <- performa per URL dari Search Console (diisi gsc_pull.py)
build_data.py       <- CSV ekspor Sheets -> data/*.json
build.py            <- data/*.json + template.html -> index.html
gsc_pull.py         <- tarik data Search Console -> data/gsc.json
smoke.js            <- headless test: semua view harus render tanpa error
```

## Cara pakai

```bash
# 1. ekspor kertas kerja (bisa juga pakai URL export CSV)
curl -sL -o sheet0.csv \
  'https://docs.google.com/spreadsheets/d/1poUtrDRaYwTOi_PYMa4q3CvfwA_JXvwT9me2Is7nuFw/export?format=csv&gid=0'

# 2. parse -> data
python build_data.py

# 3. (opsional) tarik performa GSC
python gsc_pull.py --all --days 90

# 4. bangun dashboard
python build.py

# 5. cek tidak ada error render
node smoke.js index.html
```

Deploy ke GitHub Pages: commit semua file di atas ke repo, aktifkan Pages di branch `main`
folder `/ (root)`. Tombol **Live** di dashboard fetch ulang `data/*.json` tiap 5 menit, jadi
cukup push data baru — HTML tidak perlu dibangun ulang kalau struktur tidak berubah.

## Data GSC (belum aktif)

`gsc_pull.py` pakai OAuth yang sama dengan skill google-workspace Hermes:
`~/AppData/Local/hermes/google_token.json` + `google_client_secret.json`.
Sampai file itu ada, kolom impresi/klik/CTR/rank kosong dan tab Performa menampilkan instruksi.

Syarat tambahan di Google Cloud:
1. Enable **Google Search Console API** (API Library).
2. Akun Google yang di-OAuth harus jadi **Owner/Full user** di tiap properti Search Console
   (grc-indonesia.com, ipqi.org, fs-institute.org, dst). Kalau belum, request ke admin masing-masing brand.
3. Site harus dikirim sebagai URL-prefix (`https://domain.com/`) — `--all` memakai pola itu.

## Catatan parsing

- Kolom `Klien` hanya terisi di baris pertama tiap blok → di-forward-fill.
- Nama klien tidak konsisten antar bulan (`Petro Training` vs `Petrotraining`, `academy proxsis`
  vs `ACADEMY PROXSIS`) → dinormalisasi lewat `ALIAS` di `build_data.py`.
- Kolom `Posting & SEO` kadang terisi link Google Doc (draft), kolom `Draft` kadang terisi URL live
  → dinormalisasi: yang bukan `docs.google.com` dianggap URL publik.
- 20 URL live nyasar ke domain lain (salin-baris antar blok) → dibuang dari status "Posted"
  kalau domainnya bukan domain klien tersebut. Cek manual kalau angka terasa kurang.
- Kolom `Deadline Draft` dipakai ganda: sebagian tanggal, sebagian nama penulis (REVO/Firga/
  Rahmadi/Suci) → yang non-numerik masuk field `penulis`.
