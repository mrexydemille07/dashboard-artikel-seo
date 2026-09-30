"""Scrape title/meta description/H1 dari URL artikel yang CTR-nya rendah,
lalu hasilkan rekomendasi meta siap-tempel.

Output: data/meta_audit.json  -> {url: {title, desc, h1, len_title, len_desc, issues[], saran_title, saran_desc}}

Ponytail: rule-based, tanpa LLM. Aturan panjang & pola judul sudah cukup untuk
90% kasus; kalau butuh kualitas copywriting, kirim hasilnya ke LLM belakangan.
"""
import json, os, re, sys, urllib.request, urllib.error, html, collections
from urllib.parse import urlsplit

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
UA = {"User-Agent": "Mozilla/5.0 (compatible; SEO-audit/1.0)"}

TITLE_MAX, DESC_MAX = 60, 155


def fetch(url, n=250000):
    try:
        r = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=25)
        return r.read(n).decode("utf-8", "replace")
    except Exception as e:
        return ""


def tag(body, pattern):
    m = re.search(pattern, body, re.I | re.S)
    return html.unescape(re.sub(r"\s+", " ", m.group(1)).strip()) if m else ""


def parse(body):
    title = tag(body, r"<title[^>]*>(.*?)</title>")
    desc = tag(body, r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']')
    if not desc:
        desc = tag(body, r'<meta[^>]+content=["\'](.*?)["\'][^>]+name=["\']description["\']')
    h1 = tag(body, r"<h1[^>]*>(.*?)</h1>")
    h1 = re.sub(r"<[^>]+>", "", h1)
    return title, desc, h1


def saran(title, desc, h1, queries):
    """Rekomendasi title/desc berbasis aturan + keyword GSC yang sudah terbukti."""
    kw = queries[0]["q"] if queries else ""
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
    if kw and kw.lower() not in (title or "").lower():
        issues.append('keyword "%s" tidak ada di title' % kw)
    if kw and kw.lower() not in (desc or "").lower():
        issues.append('keyword "%s" tidak ada di description' % kw)

    # saran title: pakai keyword utama + potong judul lama
    base = re.sub(r"\s*[|\-–—]\s*[^|\-–—]{0,30}$", "", title or h1 or "").strip()
    if kw and kw.lower() not in base.lower():
        st = (kw[:1].upper() + kw[1:]) + " — " + base
    else:
        st = base
    st = st[:TITLE_MAX].strip()
    sd = desc or ""
    if kw and kw.lower() not in sd.lower():
        sd = ("Panduan lengkap %s: " % kw) + sd
    sd = sd[:DESC_MAX].strip()
    return issues, st, sd


def main():
    gsc = json.load(open(os.path.join(DATA, "gsc.json"), encoding="utf-8"))
    A = json.load(open(os.path.join(DATA, "articles.json"), encoding="utf-8"))

    def norm(u):
        s = (u or "").strip().lower().replace("http://", "https://").split("#")[0]
        return s.rstrip("/")

    gm = {norm(u): m for u, m in gsc.items()}
    targets = []
    for a in A:
        m = gm.get(norm(a["live_url"]))
        if not m:
            continue
        if m["impr"] >= 100 and (m["ctr"] or 0) < 1.5:
            targets.append((a, m))
    targets.sort(key=lambda t: -t[1]["impr"])
    print("target:", len(targets), "URL")

    # resume: lewati URL yang sudah ada hasilnya (script bisa ke-kill di tengah)
    mpath = os.path.join(DATA, "meta_audit.json")
    out = json.load(open(mpath, encoding="utf-8")) if os.path.exists(mpath) else {}
    todo = [(a, m) for a, m in targets if a["live_url"] not in out]
    print("sudah ada: %d | sisa: %d" % (len(out), len(todo)), flush=True)

    def work(item):
        a, m = item
        url = a["live_url"]
        body = fetch(url)
        if not body:
            return url, {"error": "tidak bisa diakses", "judul": a["judul"], "client": a["client"]}
        title, desc, h1 = parse(body)
        issues, st, sd = saran(title, desc, h1, m.get("queries", []))
        return url, {"judul": a["judul"], "client": a["client"], "impr": m["impr"],
                     "clicks": m["clicks"], "ctr": m["ctr"], "pos": m["pos"],
                     "title": title, "desc": desc, "h1": h1,
                     "len_title": len(title), "len_desc": len(desc),
                     "issues": issues, "saran_title": st, "saran_desc": sd,
                     "keyword": (m.get("queries") or [{}])[0].get("q", "")}

    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=12) as ex:
        for i, (url, rec) in enumerate(ex.map(work, todo), 1):
            out[url] = rec
            if i % 40 == 0:
                print("  %d/%d" % (i, len(todo)), flush=True)
                json.dump(out, open(mpath, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    json.dump(out, open(mpath, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    ok = [v for v in out.values() if "error" not in v]
    print("\nselesai: %d URL dianalisis, %d gagal" % (len(ok), len(out) - len(ok)))
    c = collections.Counter()
    for v in ok:
        for i in v["issues"]:
            c[i.split(" (")[0].split(" —")[0]] += 1
    for k, n in c.most_common(10):
        print("  %-45s %d" % (k, n))


if __name__ == "__main__":
    main()
