"""Inject data/*.json ke template.html -> index.html (self-contained, siap GitHub Pages).

Ponytail: satu file output, tanpa bundler. Jalankan ulang tiap kali data berubah.
"""
import json, os, datetime, re

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")


def load(name, default):
    p = os.path.join(DATA, name)
    if not os.path.exists(p):
        return default
    return json.load(open(p, encoding="utf-8"))


def js(obj):
    # '<' di-escape supaya '</script>' di dalam string tidak menutup tag
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")


def main():
    tpl = open(os.path.join(HERE, "template.html"), encoding="utf-8").read()
    articles = load("articles.json", [])
    brands = load("brands.json", [])
    audit = load("unindexed_audit.json", [])
    meta_audit = load("meta_audit.json", {})
    # sites.json sudah bersih (tanpa link REDACTED) — lihat sanitize di sites_status.py
    sites = load("sites.json", [])
    sites_status = load("sites_status.json", [])
    laporan = load("laporan.json", {})

    # gsc_raw.json = semua URL semua situs (~33rb, 30 MB). Dashboard butuh dua bentuk:
    #   gsc.json        -> hanya URL artikel di kertas kerja (tab artikel)
    #   domain_perf.json-> agregat per domain + halaman teratas (tab performa brand)
    raw = load("gsc_raw.json", {})
    if not raw:
        raw = load("gsc.json", {})

    def norm(u):
        s = (u or "").strip().lower().replace("http://", "https://").split("#")[0]
        return s.rstrip("/")

    want = {norm(a["live_url"]) for a in articles if a.get("live_url")}
    gsc = {u: m for u, m in raw.items() if norm(u) in want}

    # agregat per domain dari SEMUA URL (bukan cuma artikel kertas kerja)
    from urllib.parse import urlsplit
    dom = {}
    for u, m in raw.items():
        h = urlsplit(u).netloc.lower().replace("www.", "")
        d = dom.setdefault(h, {"urls": 0, "impr": 0, "clicks": 0, "posW": 0.0, "posN": 0,
                               "top": [], "weeks": {}})
        d["urls"] += 1
        d["impr"] += m.get("impr", 0)
        d["clicks"] += m.get("clicks", 0)
        if m.get("pos"):
            d["posW"] += m["pos"] * m.get("impr", 0)
            d["posN"] += m.get("impr", 0)
        d["top"].append({"u": u, "impr": m.get("impr", 0), "clicks": m.get("clicks", 0),
                         "ctr": m.get("ctr", 0), "pos": m.get("pos", 0)})
        for w in m.get("weeks", []):
            a = d["weeks"].setdefault(w["w"], {"impr": 0, "clicks": 0, "posW": 0.0})
            a["impr"] += w.get("impr", 0)
            a["clicks"] += w.get("clicks", 0)
            a["posW"] += w.get("pos", 0) * w.get("impr", 0)
    for h, d in dom.items():
        d["ctr"] = round(100 * d["clicks"] / d["impr"], 2) if d["impr"] else 0
        d["pos"] = round(d["posW"] / d["posN"], 1) if d["posN"] else 0
        d.pop("posW"); d.pop("posN")
        d["top"].sort(key=lambda x: -x["impr"])
        d["top"] = d["top"][:40]
        d["weeks"] = [{"w": k, "impr": v["impr"], "clicks": v["clicks"],
                       "ctr": round(100 * v["clicks"] / v["impr"], 2) if v["impr"] else 0,
                       "pos": round(v["posW"] / v["impr"], 1) if v["impr"] else 0}
                      for k, v in sorted(d["weeks"].items())]
    domain_perf = dom

    # Portfolio: satu baris per DOMAIN yang benar-benar dikerjakan.
    st_by_dom = {s["domain"].replace("www.", ""): s for s in sites_status}
    nama_by_dom = {}
    for s in sites:
        if s.get("domain"):
            nama_by_dom.setdefault(s["domain"], s["nama"])
    portfolio = []
    for b in brands:
        h = b["domain"]
        st = st_by_dom.get(h, {})
        dp = dom.get(h, {})
        la = [a for a in articles if a.get("domain") == h]
        portfolio.append({
            "domain": h,
            "nama": nama_by_dom.get(h) or b["client"],
            "client": b["client"],
            "artikel": len(la),
            "posted": sum(1 for a in la if a.get("live_url")),
            "dns": st.get("dns"), "http": st.get("http"),
            "sitemap": st.get("sitemap"),
            # punya properti GSC = ada data GSC untuk domain ini (lebih andal daripada
            # baris sheet, karena 4 domain Proxsis tidak terdaftar di sheet portofolio)
            "gsc_properti": bool(dp.get("urls")) or st.get("gsc"),
            "laporan": st.get("laporan"),
            "impr": dp.get("impr", 0), "clicks": dp.get("clicks", 0),
            "ctr": dp.get("ctr", 0), "pos": dp.get("pos", 0), "urls_gsc": dp.get("urls", 0),
            # link REDACTED sengaja TIDAK ikut: repo ini publik, URL admin tidak perlu tayang
            "url": "https://" + h + "/",
        })
    # LAPORAN: laporan manual -> peta keyword-nya-keyword -> posisi manual, per domain.
    # Bukan sumber metrik (GSC yang resmi); dipakai sebagai kolom pembanding di tab Keyword.
    def nkw(s):
        return re.sub(r"\s+", " ", str(s or "").strip().lower())

    # Metrik GSC ditempel di sini (dari raw = semua URL) karena GSC di HTML sudah
    # dipangkas ke URL artikel kertas kerja -> landing produk tidak akan ketemu.
    raw_by_url = {norm(u): m for u, m in raw.items()}
    laporan_map = {}
    for d, rows in laporan.items():
        m = {}
        for r in rows:
            k = nkw(r["keyword"])
            if k and k not in m:      # baris pertama = paling baru dilaporkan
                gm = raw_by_url.get(norm(r.get("landing") or ""), {})
                m[k] = [r["posisi"], r["vol"], r["priority"], r["landing"], r["produk"],
                        gm.get("pos"), gm.get("impr"), gm.get("clicks")]
        if m:
            laporan_map[d] = m
    print("laporan: %d domain, %d keyword" % (
        len(laporan_map), sum(len(v) for v in laporan_map.values())))

    portfolio.sort(key=lambda x: -x["impr"])

    # IDEAS: query GSC yang halaman terbaiknya BUKAN artikel kertas kerja
    # (produk/kategori/tag yang kebetulan ranking) -> belum ada artikel yang menyasar.
    import re as _re
    NOISE = _re.compile(r"^(site|inurl|intitle|link|cache|related):", _re.I)
    mine = {}
    for a in articles:
        if a.get("domain") and a.get("live_url"):
            mine.setdefault(a["domain"], set()).add(norm(a["live_url"]))
    qagg = {}
    for u, m in raw.items():
        h = urlsplit(u).netloc.lower().replace("www.", "")
        for q in m.get("queries", []):
            k = (q.get("q") or "").strip().lower()
            if len(k) < 6 and " " not in k:
                continue
            if NOISE.match(k) or k in {"ya", "iya", "tidak"}:
                continue
            e = qagg.setdefault((h, k), {"impr": 0, "clicks": 0, "pos": 99.0, "url": u})
            e["impr"] += q.get("impr", 0)
            e["clicks"] += q.get("clicks", 0)
            if q.get("pos") and q["pos"] < e["pos"]:
                e["pos"] = q["pos"]; e["url"] = u
    ideas = []
    for (h, k), v in qagg.items():
        if v["impr"] < 200:
            continue
        if norm(v["url"]) in mine.get(h, ()):      # sudah ada artikelnya -> tab 'perbaiki'
            continue
        w = 1.6 if 4 <= v["pos"] <= 20 else 0.5 if v["pos"] < 4 else 0.3
        ideas.append({"domain": h, "q": k, "impr": v["impr"], "clicks": v["clicks"],
                      "pos": round(v["pos"], 1), "url": v["url"],
                      "score": int(v["impr"] * w / 1000)})
    ideas.sort(key=lambda x: -x["score"])
    ideas = ideas[:600]

    # LANDING_GAP: halaman yang dilaporkan ke klien (kolom Landing Page di laporan manual)
    # tapi tidak muncul sama sekali di GSC 90 hari -> laporan tidak akurat.
    gurl = {}
    for u in raw:
        gurl.setdefault(urlsplit(u).netloc.lower().replace("www.", ""), set()).add(norm(u))
    # satu halaman bisa dilaporkan untuk banyak keyword -> dedup per halaman,
    # keyword-nya digabung supaya tidak ada 6 baris identik
    gap_acc = {}
    for dom, rows in (load("laporan.json", {}) or {}).items():
        for row in rows:
            landing = (row.get("landing") or "").strip()
            if not landing.lower().startswith("http"):
                continue
            if norm(landing) in gurl.get(dom, set()):
                continue
            e = gap_acc.setdefault((dom, norm(landing)),
                                   {"domain": dom, "landing": landing,
                                    "produk": row.get("produk", ""), "kw": [],
                                    "pos_manual": None})
            if row.get("keyword") and row["keyword"] not in e["kw"]:
                e["kw"].append(row["keyword"])
            p_ = row.get("posisi")
            if isinstance(p_, (int, float)) and (e["pos_manual"] is None or p_ < e["pos_manual"]):
                e["pos_manual"] = p_
    landing_gap = [{"domain": v["domain"], "landing": v["landing"], "produk": v["produk"],
                    "keyword": ", ".join(v["kw"][:4]) + ("…" if len(v["kw"]) > 4 else ""),
                    "n_kw": len(v["kw"]), "pos_manual": v["pos_manual"]}
                   for v in gap_acc.values()]
    landing_gap.sort(key=lambda x: (-x["n_kw"], x["domain"]))
    def norm(u):
        s = (u or "").strip().lower().replace("http://", "https://").split("#")[0]
        return s.rstrip("/")
    matched = sum(1 for a in articles
                  if a.get("live_url") and norm(a["live_url"]) in {norm(u) for u in gsc})
    stamp = "Data per %s • %d artikel • %d klien • %d artikel terhubung GSC (%d URL di ekspor)" % (
        datetime.datetime.now().strftime("%d %b %Y %H:%M"),
        len(articles),
        len({a["client"] for a in articles if a.get("client")}),
        matched, len(gsc))
    meta = {"stamp": stamp, "generated": datetime.datetime.now().isoformat(timespec="seconds")}

    # GSC bisa puluhan ribu URL -> jangan ditanam di HTML, biarkan di-fetch dari data/gsc.json.
    # Kalau file:// (fetch diblokir), dashboard tetap jalan tanpa metrik.
    for token, val in (("/*__ARTICLES__*/[]", js(articles)),
                       ("/*__BRANDS__*/[]", js(brands)),
                       ("/*__GSC__*/{}", js(gsc)),
                       ("/*__AUDIT__*/[]", js(audit)),
                      ("/*__META_AUDIT__*/{}", js(meta_audit)),
                      ("/*__SITES__*/[]", js(sites)),
                      ("/*__SITES_STATUS__*/[]", js(sites_status)),
                      ("/*__DOMAIN_PERF__*/{}", js(domain_perf)),
                      ("/*__PORTFOLIO__*/[]", js(portfolio)),
                      ("/*__IDEAS__*/[]", js(ideas)),
                      ("/*__LANDING_GAP__*/[]", js(landing_gap)),
                      ("/*__LAPORAN__*/{}", js(laporan_map)),
                       ("/*__META__*/{}", js(meta))):
        assert token in tpl, "token hilang dari template: " + token
        tpl = tpl.replace(token, val)

    json.dump(gsc, open(os.path.join(DATA, "gsc.json"), "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))

    out = os.path.join(HERE, "index.html")
    open(out, "w", encoding="utf-8").write(tpl)
    print("index.html:", len(tpl), "bytes |", stamp)


if __name__ == "__main__":
    main()
