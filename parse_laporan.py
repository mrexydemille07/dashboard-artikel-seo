"""laporan/*.csv (12 laporan manual klien) -> data/laporan.json.

Ponytail: 4 format header berbeda, jadi deteksi header = baris yang punya
'keyword' DAN 'posisi', lalu petakan kolom lewat nama. Angka manual ini BUKAN
sumber metrik dashboard (GSC yang jadi sumber) — cuma kolom pembanding posisi.
"""
import csv, json, os, re
from urllib.parse import urlsplit

HERE = os.path.dirname(os.path.abspath(__file__))
LAP = os.path.join(HERE, "laporan")
OUT = os.path.join(HERE, "data", "laporan.json")

# nama file -> domain, dipakai kalau kolom link kosong
FILE_DOM = {
    "01": "grc-indonesia.com", "02": "ipqi.org", "03": "fs-institute.org",
    "04": "strategy.proxsisgroup.com", "05": "synergysolusi.com",
    "06": "indonesiasafetycenter.org", "07": "environment-indonesia.com",
    "08": "petrotrainingasia.com", "09": "it.proxsisgroup.com",
    "13": "icicert.com", "14": "isoindonesiacenter.com", "15": "hr.proxsisgroup.com",
}


def pick(header, *names):
    """Indeks kolom pertama yang namanya cocok (substring, case-insensitive)."""
    for i, h in enumerate(header):
        hl = (h or "").strip().lower()
        for n in names:
            if n in hl:
                return i
    return None


def num(s):
    s = re.sub(r"[^\d]", "", str(s or ""))
    return int(s) if s else None


def parse(path, dom_default):
    rows = list(csv.reader(open(path, encoding="utf-8-sig", newline="")))
    hi = next((i for i, r in enumerate(rows)
               if any(("keyword" in (c or "").lower() or "kyword" in (c or "").lower()) for c in r)
               and any("posisi" in (c or "").lower() for c in r)), None)
    if hi is None:
        return []
    h = rows[hi]
    c_prod = pick(h, "produk unggulan", "judul page")
    c_land = pick(h, "landing page", "link")
    c_kw = pick(h, "keywords unggulan", "long kyword", "keyword")
    c_pos = pick(h, "posisi seo", "posisi")
    c_vol = pick(h, "volume", "vol")
    c_pri = pick(h, "priority")
    out = []
    for r in rows[hi + 1:]:
        if c_kw is None or c_kw >= len(r):
            continue
        kw = (r[c_kw] or "").strip()
        if not kw or kw.lower() in ("keyword", "long kyword"):
            continue
        land = (r[c_land] or "").strip() if c_land is not None and c_land < len(r) else ""
        dom = urlsplit(land).netloc.lower().replace("www.", "") if land.startswith("http") else ""
        out.append({
            "domain": dom or dom_default,
            "produk": (r[c_prod] or "").strip() if c_prod is not None and c_prod < len(r) else "",
            "landing": land,
            "keyword": kw,
            "posisi": num(r[c_pos]) if c_pos is not None and c_pos < len(r) else None,
            "vol": num(r[c_vol]) if c_vol is not None and c_vol < len(r) else None,
            "priority": num(r[c_pri]) if c_pri is not None and c_pri < len(r) else None,
        })
    return out


def main():
    by_dom = {}
    for f in sorted(os.listdir(LAP)):
        if not f.endswith(".csv"):
            continue
        dom = FILE_DOM.get(f[:2], "")
        got = parse(os.path.join(LAP, f), dom)
        for g in got:
            if g["domain"]:
                by_dom.setdefault(g["domain"], []).append(g)
        print("%-40s %3d baris" % (f, len(got)))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(by_dom, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\ndomain:", len(by_dom), "| total baris:", sum(len(v) for v in by_dom.values()))
    for d, v in sorted(by_dom.items(), key=lambda x: -len(x[1])):
        print("  %-32s %4d" % (d, len(v)))


if __name__ == "__main__":
    main()
