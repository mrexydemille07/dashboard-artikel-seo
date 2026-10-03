"""Diagnosis konten per artikel: FAQ JSON-LD + outline H2 siap-tempel.

Scrape <h2> & schema FAQ yang sudah ada di halaman live, lalu sarankan yang
kurang. Rule-based + jawaban diambil dari meta description halaman itu sendiri
(bukan template kosong). Sifatnya DRAFT — cek dulu sebelum tempel.

Output: data/diagnose.json
  {url: {desc, h2[], has_faq, faq (string JSON-LD), h2_suggest[], issues[]}}
Resume: URL yang sudah ada file dilewati (fetch cuma URL baru). --force = ulang semua.

Jalankan manual:  python diagnose.py            (tambah URL baru)
                  python diagnose.py --force    (crawl ulang semua)
"""
import json, os, re, sys, html, urllib.request
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
OUT = os.path.join(DATA, "diagnose.json")
UA = {"User-Agent": "Mozilla/5.0 (compatible; content-audit/1.0)"}
MAX_FAQ_ANS = 180


def load(name, default):
    p = os.path.join(DATA, name)
    if not os.path.exists(p):
        return default
    return json.load(open(p, encoding="utf-8"))


def fetch(url, n=300000):
    try:
        return urllib.request.urlopen(
            urllib.request.Request(url, headers=UA), timeout=25).read(n).decode("utf-8", "replace")
    except Exception:
        return ""


def strip(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html.unescape(s or ""))).strip()


def norm(u):
    s = (u or "").strip().lower().replace("http://", "https://").split("#")[0]
    return s.rstrip("/")


def cut(s, n):
    s = (s or "").strip()
    if len(s) <= n:
        return s
    cut_i = s[:n].rfind(" ")
    return (s[:cut_i] if cut_i > 20 else s[:n]).rstrip(" ,;:.") + "."


def intro_para(body):
    """Paragraf pertama isi artikel (bahan jawaban FAQ ke-2, beda dari desc)."""
    for m in re.finditer(r"<p[^>]*>(.*?)</p>", body, re.I | re.S):
        txt = strip(m.group(1))
        if len(txt) >= 60 and "cookie" not in txt.lower():
            return txt
    return ""


def faq_json(kw, judul, desc, body):
    """2 Q&A grounded: jawaban #1 = meta description, #2 = paragraf pembuka."""
    a1 = cut(desc, MAX_FAQ_ANS)
    a2 = cut(intro_para(body), MAX_FAQ_ANS)
    if not a1 or not a2 or a1.lower() == a2.lower():
        return None
    q1 = "Apa itu %s?" % (kw.strip().capitalize() if kw else (judul or "artikel ini").strip().rstrip("."))
    q2 = "Bagaimana penerapannya di perusahaan?" if kw else (judul or "").strip().rstrip(".!") + "?"
    if q1.lower() == q2.lower():
        q2 = "Mengapa ini penting bagi perusahaan?"
    items = [
        {"@type": "Question", "name": q1, "acceptedAnswer": {"@type": "Answer", "text": a1}},
        {"@type": "Question", "name": q2, "acceptedAnswer": {"@type": "Answer", "text": a2}},
    ]
    return json.dumps({"@context": "https://schema.org", "@type": "FAQPage",
                       "mainEntity": items}, indent=2, ensure_ascii=False)


def outline(kw, judul, queries):
    """Outline H2 kalau halaman punya <3 H2. Pakai keyword query GSC bila ada."""
    kw = (kw or "").strip()
    judul = (judul or "").strip().rstrip(".")
    tops = [q["q"] for q in (queries or [])[:2] if q.get("q")]
    out = ["Apa Itu %s dan Mengapa Penting" % (kw or judul),
           "Poin Utama %s" % (judul[:60] if judul else kw)]
    for t in tops:
        if t.lower() != (kw or "").lower():
            out.append(t.capitalize())
    out += ["Langkah Penerapan di Perusahaan",
            "Kesalahan yang Sering Terjadi",
            "Kesimpulan dan Langkah Berikutnya"]
    return out


def one(a, gsc):
    url = a.get("live_url")
    m = gsc.get(norm(url)) or {}
    body = fetch(url)
    if not body:
        return None  # jangan timpa entry lama karena sekali timeout
    desc = ""
    dm = re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']', body, re.I | re.S)
    if not dm:
        dm = re.search(r'<meta[^>]+content=["\'](.*?)["\'][^>]+name=["\']description["\']', body, re.I | re.S)
    if dm:
        desc = strip(dm.group(1))
    h2 = [strip(x) for x in re.findall(r"<h2[^>]*>(.*?)</h2>", body, re.I | re.S)]
    h2 = [h for h in h2 if h]
    has_faq = bool(re.search(r'"@type"\s*:\s*"FAQPage"|itemtype="?https?://schema\.org/FAQPage', body, re.I))
    issues = []
    if not has_faq:
        issues.append("FAQPage schema belum ada")
    if len(h2) < 3:
        issues.append("H2 cuma %d (ideal ≥3)" % len(h2))
    faq = None if has_faq else faq_json(a.get("keyword"), a.get("judul"), desc, body)
    h2_s = [] if len(h2) >= 3 else outline(a.get("keyword"), a.get("judul"), m.get("queries"))
    return {"judul": a.get("judul"), "client": a.get("client"),
            "impr": m.get("impr", 0), "desc": desc, "h2": h2[:12], "has_faq": has_faq,
            "faq": faq, "h2_suggest": h2_s, "issues": issues}


def main():
    force = "--force" in sys.argv
    arts = [a for a in load("articles.json", []) if a.get("live_url")]
    raw = load("gsc_raw.json", {})
    gsc = {norm(u): m for u, m in raw.items()}
    out = load("diagnose.json", {}) if not force else {}
    todo = [a for a in arts if norm(a["live_url"]) not in
            {norm(u) for u in out}]
    limit = int(os.environ.get("DIAG_LIMIT", "0"))
    if limit:
        todo = todo[:limit]
    print("total %d artikel tayang, %d sudah di-audit, %d perlu fetch" % (
        len(arts), len(out), len(todo)))
    done = fail = 0
    with ThreadPoolExecutor(max_workers=10) as ex:
        for a, res in zip(todo, ex.map(
                lambda a: one(a, gsc), todo)):
            if res is None:
                fail += 1
                continue
            out[a["live_url"]] = res
            done += 1
            if done % 50 == 0:
                json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
    perlu_faq = sum(1 for v in out.values() if not v.get("has_faq"))
    perlu_h2 = sum(1 for v in out.values() if len(v.get("h2", [])) < 3)
    print("baru di-audit: %d (gagal fetch: %d) | total %d" % (done, fail, len(out)))
    print("kurang FAQ schema: %d | H2 <3: %d" % (perlu_faq, perlu_h2))
    print("-> data/diagnose.json")


if __name__ == "__main__":
    main()
