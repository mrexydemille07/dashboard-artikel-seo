"""Kertas kerja 'Artikel 2026' -> data/*.json untuk dashboard.

Sumber: export CSV Google Sheets (gid=0 = 'Artikel 2026').
Ponytail: parser kolom tetap (A..P) sesuai header sheet; kalau sheet nambah kolom,
ubah COL di bawah, jangan refactor.
"""
import csv, json, os, re, collections, datetime, sys

SRC = os.environ.get("SHEET_CSV") or os.path.expanduser(
    "~/AppData/Local/Temp/artikel2026/sheet0.csv")
OUT = os.environ.get("DATA_DIR") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

COL = dict(no=0, klien=1, judul=2, deadline_draft=3, draft=4, revisi=5,
           deadline_posting=6, keterangan=7, live=8, seo_only=9, keyword=10,
           posisi=11, produk=12, referensi=13, outline=14, note=15)

# Nama bulan campur: Inggris (May/June/July/August) + Indonesia (Februari/Maret).
MONTH_RE = re.compile(r"^(January|February|March|April|May|June|July|August|"
                      r"September|October|November|December|"
                      r"Januari|Februari|Maret|Mei|Juni|Juli|Agustus|Oktober|"
                      r"November|Desember)(?:\s+(20\d\d))?$")
MONTH_ID = {"Januari": "January", "Februari": "February", "Maret": "March",
            "Mei": "May", "Juni": "June", "Juli": "July", "Agustus": "August",
            "Oktober": "October", "Desember": "December"}
URL_RE = re.compile(r"https?://[^\s\"']+", re.I)

# Nama klien di sheet tidak konsisten antar bulan -> kanonikalisasi.
ALIAS = {
    "petro training": "Petrotraining",
    "iec": "IEC Training BNSP",
    "iec training & consulting (non bnsp)": "IEC Non-BNSP",
    "iec training bnsp": "IEC Training BNSP",
    "academy proxsis": "Proxsis Academy",
    "biztech academy": "Biztech Academy",
    "strategy.proxsis": "Strategy.Proxsis",
    "proxsis it": "Proxsis IT",
    "proxsis hr": "Proxsis HR",
    "proxsis digital": "Proxsis Digital",
    "proxsis infra": "Proxsis Infra",
    "infra sec": "Infra Sec",
    "artikel cadangan": "ARTIKEL CADANGAN",
}
# domain resmi per klien (untuk deteksi link nyasar di kolom live)
CLIENT_DOMAIN = {
    "FSI": "fs-institute.org", "GRC": "grc-indonesia.com", "IPQI": "ipqi.org",
    "Strategy.Proxsis": "strategy.proxsisgroup.com", "ISC": "indonesiasafetycenter.org",
    "IEC Training BNSP": "environment-indonesia.com", "IEC Non-BNSP": "environment-indonesia.com",
    "Petrotraining": "petrotrainingasia.com", "SSP": "synergysolusi.com",
    "SSI": "synergysolusi.com", "Proxsis IT": "it.proxsisgroup.com", "ITGID": "itgid.org",
    "Isocenter": "isoindonesiacenter.com", "Icicert": "icicert.com",
    "Biztech Academy": "biztechacademy.id", "Proxsis Digital": "digital.proxsisgroup.com",
    "Proxsis HR": "hr.proxsisgroup.com", "Talkactive": "talkactive.co.id",
    "Proxsis Infra": "infra.proxsisgroup.com", "Proxsis Academy": "academy.proxsisgroup.com",
    "Infra Sec": "infrasec.proxsisgroup.com",
}


def canon_client(raw):
    c, kuota = split_client(raw)
    return ALIAS.get(c.lower(), c), kuota

# Kolom Klien cuma diisi di baris pertama tiap blok -> forward-fill.
# Nama klien kadang punya kuota "FSI (5)" -> dipisah.
def clean(s):
    return re.sub(r"\s+", " ", (s or "")).strip()


def split_client(raw):
    m = re.match(r"^(.*?)\s*\((\d+)\)\s*$", raw)
    if m:
        return clean(m.group(1)), int(m.group(2))
    return clean(raw), None


def is_url(s, host=None):
    if not s or not s.lower().startswith(("http://", "https://")):
        return False
    if host is None:
        return True
    return host.lower() in s.lower()


def parse_date(s):
    s = clean(s)
    if not s:
        return None
    for fmt in ("%d %B %Y", "%d %b %Y", "%Y-%m-%d", "%Y-%m-%d at %I:%M %p",
                "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            pass
    m = re.search(r"(\d{1,2})\s+(January|February|March|April|May|June|July|August|"
                  r"September|October|November|December)\s+(20\d\d)", s, re.I)
    if m:
        return datetime.datetime.strptime(" ".join(m.groups()), "%d %B %Y").date().isoformat()
    return None


def domain(url):
    m = re.match(r"https?://([^/]+)", url or "")
    return m.group(1).lower().replace("www.", "") if m else ""


def main():
    rows = list(csv.reader(open(SRC, encoding="utf-8")))
    items, month, client, kuota = [], None, None, None
    for i, r in enumerate(rows):
        cells = [clean(c) for c in r]
        get = lambda k: cells[COL[k]] if COL[k] < len(cells) else ""
        a = get("no")
        mm = MONTH_RE.match(a)
        if mm:
            nm = MONTH_ID.get(mm.group(1), mm.group(1))
            yr = mm.group(2) or (month.split()[-1] if month else "2026")
            month = "%s %s" % (nm, yr)
            client, kuota = None, None
            continue
        if not a.isdigit():
            continue
        if get("klien"):
            client, kuota = canon_client(get("klien"))
        live = get("live")
        draft = get("draft")
        # kolom 'draft' kadang diisi URL live (artikel lama), dan kolom live kadang
        # diisi link gdoc (draft). Normalize: yang bukan docs.google = URL publik.
        def pub(u):
            return u if is_url(u) and "docs.google.com" not in u else ""
        live_url = pub(live) or (pub(draft) if not is_url(draft, "docs.google.com") else "")
        # kolom Keterangan kadang nyimpen URL live (119 baris) — pakai sbg fallback;
        # validasi domain klien di bawah tetap berlaku, jadi URL nyasar tetap dibuang.
        if not live_url:
            live_url = pub(get("keterangan"))
        # URL live harus cocok dengan domain klien; kalau nyasar (salin baris), buang.
        expected = CLIENT_DOMAIN.get(client or "")
        if live_url and expected and expected not in domain(live_url):
            live_url = ""
        doc_url = draft if "docs.google.com/document" in draft else (
            live if "docs.google.com/document" in live else "")
        kw = get("keyword")
        items.append(dict(
            id="A%04d" % i,
            row=i + 1,
            no=int(a),
            month=month,
            client=client,
            kuota=kuota,
            judul=get("judul"),
            penulis=get("deadline_draft") if not get("deadline_draft").isdigit() else "",
            draft_url=doc_url,
            deadline_posting=parse_date(get("deadline_posting")),
            keterangan=get("keterangan"),
            live_url=live_url,
            domain=domain(live_url),
            keyword=kw if not is_url(kw) else "",
            posisi=get("posisi"),
            produk=get("produk"),
            referensi=get("referensi"),
            outline=get("outline"),
            note=get("note"),
            seo_only=get("seo_only"),
        ))

    # brand registry: domain -> klien (majority vote dari data)
    dom_client = collections.Counter((it["domain"], it["client"]) for it in items
                                     if it["domain"] and it["client"])
    brands = {}
    for (d, c), n in dom_client.most_common():
        brands.setdefault(d, dict(domain=d, client=c, articles=n))
    for it in items:
        if not it["client"] and it["domain"] in brands:
            it["client"] = brands[it["domain"]]["client"]

    os.makedirs(OUT, exist_ok=True)
    json.dump(items, open(os.path.join(OUT, "articles.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    json.dump(sorted(brands.values(), key=lambda b: -b["articles"]),
              open(os.path.join(OUT, "brands.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    posted = [it for it in items if it["live_url"]]
    print("artikel     :", len(items))
    print("punya URL   :", len(posted), "(%.0f%%)" % (100 * len(posted) / len(items)))
    print("domain      :", len(brands))
    print("bulan       :", sorted({it["month"] for it in items if it["month"]},
                                 key=lambda m: (m.split()[1], m.split()[0])))
    print("punya keyword:", sum(1 for it in items if it["keyword"]))
    print("punya produk :", sum(1 for it in items if is_url(it["produk"])))
    print("punya outline:", sum(1 for it in items if len(it["outline"]) > 40))
    print()
    for b in sorted(brands.values(), key=lambda x: -x["articles"]):
        print("%-32s %-24s %4d" % (b["domain"], b["client"], b["articles"]))


if __name__ == "__main__":
    main()
