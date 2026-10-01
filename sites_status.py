"""Cek status teknis 17 website: DNS, HTTP, sitemap, properti GSC.
Output: data/sites_status.json -> [{no, nama, domain, wp, dns, http, sitemap, gsc, artikel}]
"""
import json, os, socket, ssl, urllib.request, urllib.error, re, collections

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
UA = {"User-Agent": "Mozilla/5.0 (compatible; status-check/1.0)"}


def domain_of(url):
    m = re.search(r"https?://([^/\s]+)", url or "")
    return m.group(1).lower() if m else (url or "").split("/")[0].lower()


def head(url):
    try:
        r = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=15)
        return r.status, r.geturl()
    except urllib.error.HTTPError as e:
        return e.code, url
    except Exception:
        return None, url


def main():
    sites = json.load(open(os.path.join(DATA, "sites.json"), encoding="utf-8"))
    gsc = json.load(open(os.path.join(DATA, "gsc.json"), encoding="utf-8"))
    arts = json.load(open(os.path.join(DATA, "articles.json"), encoding="utf-8"))

    # domain yang punya data GSC (dari URL yang ter-cocok)
    gsc_dom = {urllib.parse.urlsplit(u).netloc.lower() for u in gsc}
    n_art = collections.Counter()
    for a in arts:
        if a.get("live_url"):
            n_art[domain_of(a["live_url"])] += 1

    # 17 website dari sheet + semua domain yang muncul di kertas kerja
    # (strategy/digital/infrasec/academy.proxsisgroup.com tidak ada di sheet tapi dikerjakan)
    brands = json.load(open(os.path.join(DATA, "brands.json"), encoding="utf-8"))
    seen = {domain_of(s["wp"]) for s in sites if s.get("wp")}
    extra = [{"no": 90 + i, "nama": b["client"], "wp": "https://" + b["domain"] + "/",
              "laporan": ""}
             for i, b in enumerate(brands) if b["domain"] not in seen]
    sites = sites + extra

    out = []
    for s in sites:
        dom = domain_of(s["wp"])
        row = {"no": s["no"], "nama": s["nama"], "domain": dom, "wp": s["wp"],
               "laporan": bool(s["laporan"]), "artikel": n_art.get(dom, 0)}
        try:
            socket.getaddrinfo(dom, None)
            row["dns"] = True
        except Exception:
            row["dns"] = False
        row["http"] = row["sitemap"] = None
        if row["dns"]:
            st, final = head("https://" + dom + "/")
            row["http"] = st
            st2, _ = head("https://" + dom + "/sitemap_index.xml")
            if st2 == 200:
                row["sitemap"] = "index"
            else:
                st3, _ = head("https://" + dom + "/sitemap.xml")
                row["sitemap"] = "yes" if st3 == 200 else None
        row["gsc"] = dom in gsc_dom
        out.append(row)
        print("%2d %-32s dns=%-5s http=%-4s sitemap=%-6s gsc=%-5s art=%d" % (
            s["no"], s["nama"][:32], row["dns"], row["http"], row["sitemap"],
            row["gsc"], row["artikel"]), flush=True)

    json.dump(out, open(os.path.join(DATA, "sites_status.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("\nsimpan -> data/sites_status.json")


if __name__ == "__main__":
    import urllib.parse
    main()
