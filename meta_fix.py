"""Hitung ulang saran meta dari cache meta_audit.json + gsc.json (tanpa fetch ulang).

Alasan: versi pertama memakai queries[0] mentah, sehingga query sampah
('site:domain', 'ya', 'iya') ikut dijadikan dasar saran judul.
"""
import json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
TITLE_MAX, DESC_MAX = 60, 155

NOISE = re.compile(r"^(site|inurl|intitle|link|cache|related):", re.I)


def clean_queries(qlist):
    """Ambil keyword GSC yang layak dipakai: bukan operator, ≥3 karakter, ≥2 kata ATAU ≥6 karakter."""
    out = []
    for q in qlist or []:
        s = (q.get("q") or "").strip().lower()
        if len(s) < 3 or NOISE.match(s) or s in {"ya", "iya", "ok", "tidak", "ada", "tidak ada"}:
            continue
        if len(s) < 6 and " " not in s:
            continue
        out.append((s, q.get("impr", 0)))
    out.sort(key=lambda x: -x[1])
    return [s for s, _ in out]


def build(title, desc, h1, kws):
    kw = kws[0] if kws else ""
    issues = []
    if not title:
        issues.append("title kosong")
    elif len(title) > TITLE_MAX:
        issues.append("title %d karakter (ideal ≤%d) — terpotong di SERP" % (len(title), TITLE_MAX))
    elif len(title) < 25:
        issues.append("title terlalu pendek (%d karakter)" % len(title))
    if not desc:
        issues.append("meta description kosong")
    elif len(desc) > DESC_MAX:
        issues.append("description %d karakter (ideal ≤%d)" % (len(desc), DESC_MAX))
    elif len(desc) < 70:
        issues.append("description terlalu pendek (%d karakter)" % len(desc))
    if kw and kw not in (title or "").lower():
        issues.append('keyword "%s" tidak ada di title' % kw)
    if kw and kw not in (desc or "").lower():
        issues.append('keyword "%s" tidak ada di description' % kw)

    # buang suffix brand dari judul lama
    base = re.sub(r"\s*[-–|:]\s*[^-–|:]{0,28}$", "", (title or h1 or "")).strip() or (h1 or "")
    # keyword terlalu panjang/aneh -> jangan dipaksa masuk title
    if kw and (len(kw) > 32 or kw.split()[0] in base.lower().split()):
        kw_title = ""
    else:
        kw_title = kw
    if kw_title and kw_title not in base.lower():
        room = TITLE_MAX - len(kw_title) - 3
        if room >= 15:
            head = base[:room]
            if len(base) > room:            # potong di batas kata, bukan di tengah kata
                head = head.rsplit(" ", 1)[0]
            st = (kw_title[:1].upper() + kw_title[1:] + " — " + head).strip()
        else:
            st = base
    else:
        st = base
    # potong di batas kata
    if len(st) > TITLE_MAX:
        st = st[:TITLE_MAX].rsplit(" ", 1)[0].strip().rstrip("-–|:,")
    sd = desc or (h1 + ". " if h1 else "")
    if kw and len(kw) <= 40 and kw not in sd.lower():
        sd = "Simak %s: " % kw + sd
    if len(sd) > DESC_MAX:
        sd = sd[:DESC_MAX].rsplit(" ", 1)[0].strip().rstrip(",;:") + "…"
    return issues, st, sd


def main():
    gsc = json.load(open(os.path.join(DATA, "gsc.json"), encoding="utf-8"))
    meta = json.load(open(os.path.join(DATA, "meta_audit.json"), encoding="utf-8"))

    def norm(u):
        s = (u or "").strip().lower().replace("http://", "https://").split("#")[0]
        return s.rstrip("/")

    gm = {norm(u): m for u, m in gsc.items()}
    changed = 0
    for url, v in meta.items():
        if "error" in v:
            continue
        g = gm.get(norm(url), {})
        kws = clean_queries(g.get("queries", []))
        issues, st, sd = build(v["title"], v["desc"], v["h1"], kws)
        v["issues"], v["saran_title"], v["saran_desc"], v["keyword"] = issues, st, sd, (kws[0] if kws else "")
        changed += 1
    json.dump(meta, open(os.path.join(DATA, "meta_audit.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("dihitung ulang:", changed, "URL")
    contoh = [v for v in meta.values() if "error" not in v and v["keyword"]][:3]
    for v in contoh:
        print("\n  %s | %s" % (v["client"], v["keyword"]))
        print("    lama : %s (%d)" % (v["title"], len(v["title"])))
        print("    saran: %s (%d)" % (v["saran_title"], len(v["saran_title"])))


if __name__ == "__main__":
    main()
