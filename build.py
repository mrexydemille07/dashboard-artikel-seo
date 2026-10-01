"""Inject data/*.json ke template.html -> index.html (self-contained, siap GitHub Pages).

Ponytail: satu file output, tanpa bundler. Jalankan ulang tiap kali data berubah.
"""
import json, os, datetime

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
    sites = load("sites.json", [])
    sites_status = load("sites_status.json", [])

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
        h = (s.get("wp") or "").split("//")[-1].split("/")[0].lower().replace("www.", "")
        if h:
            nama_by_dom.setdefault(h, s["nama"])
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
    portfolio.sort(key=lambda x: -x["impr"])
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
