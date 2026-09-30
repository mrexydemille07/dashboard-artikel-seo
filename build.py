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
    gsc = load("gsc.json", {})
    audit = load("unindexed_audit.json", [])
    meta_audit = load("meta_audit.json", {})
    # Pangkas ke URL artikel saja: gsc.json mentah ~33rb URL (10 MB), yang dipakai
    # dashboard cuma yang ada di kertas kerja. Mentah tetap disimpan sbg gsc_raw.json.
    if gsc:
        import shutil
        raw = os.path.join(DATA, "gsc_raw.json")
        if not os.path.exists(raw):
            shutil.copy(os.path.join(DATA, "gsc.json"), raw)
        def norm(u):
            s = (u or "").strip().lower().replace("http://", "https://").split("#")[0]
            return s.rstrip("/")
        want = {norm(a["live_url"]) for a in articles if a.get("live_url")}
        gsc = {u: m for u, m in gsc.items() if norm(u) in want}
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
