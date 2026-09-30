"""Cek kenapa artikel tidak muncul di GSC: status HTTP, noindex, ada di sitemap?"""
import json, os, re, urllib.request, collections
from urllib.parse import urlsplit

d = os.path.expanduser("~/AppData/Local/Temp/artikel2026/data")
g = json.load(open(f"{d}/gsc.json", encoding="utf-8"))
A = json.load(open(f"{d}/articles.json", encoding="utf-8"))

def norm(u):
    s = (u or "").strip().lower().replace("http://", "https://").split("#")[0]
    return s.rstrip("/")

gn = {norm(u) for u in g}
miss = [a for a in A if a["live_url"] and norm(a["live_url"]) not in gn]

# sitemap per domain (dibaca sekali)
sitemaps = {}
def sitemap_urls(dom):
    if dom in sitemaps:
        return sitemaps[dom]
    out = set()
    for sm in ("https://%s/sitemap_index.xml" % dom, "https://%s/sitemap.xml" % dom):
        try:
            req = urllib.request.Request(sm, headers={"User-Agent": "Mozilla/5.0"})
            body = urllib.request.urlopen(req, timeout=25).read().decode("utf-8", "replace")
            locs = re.findall(r"<loc>(.*?)</loc>", body)
            if "<sitemap>" in body:                      # index -> gali child (maks 6)
                for child in locs[:6]:
                    try:
                        b2 = urllib.request.urlopen(urllib.request.Request(
                            child, headers={"User-Agent": "Mozilla/5.0"}), timeout=25).read().decode("utf-8", "replace")
                        out.update(re.findall(r"<loc>(.*?)</loc>", b2))
                    except Exception:
                        pass
            else:
                out.update(locs)
            if out:
                break
        except Exception:
            pass
    sitemaps[dom] = out
    return out

rows = []
for a in miss:
    u = a["live_url"]
    dom = urlsplit(u).netloc
    st, noindex, insm = "?", "", "?"
    try:
        req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
        r = urllib.request.urlopen(req, timeout=25)
        st = r.status
        body = r.read(120000).decode("utf-8", "replace")
        m = re.search(r'<meta[^>]+robots[^>]+content="([^"]+)"', body, re.I)
        noindex = "noindex" if (m and "noindex" in m.group(1).lower()) else ""
    except urllib.error.HTTPError as e:
        st = e.code
    except Exception as e:
        st = "ERR"
    sm = sitemap_urls(dom)
    if sm:
        insm = "Y" if norm(u) in {norm(x) for x in sm} else "T"
    rows.append((dom, a["client"], st, noindex, insm, u))

c = collections.Counter((str(r[2]), r[3] or "-", r[4]) for r in rows)
print("status | robots | di sitemap | jumlah")
for (st, ni, sm), n in c.most_common():
    print(f"  {st:>5} | {ni:>7} | {sm:>2} | {n}")
print("\ncontoh per kategori:")
seen = set()
for r in rows:
    k = (str(r[2]), r[3] or "-", r[4])
    if k in seen:
        continue
    seen.add(k)
    print("  ", k, r[5])
json.dump([{"domain": r[0], "client": r[1], "http": str(r[2]), "noindex": r[3],
            "in_sitemap": r[4], "url": r[5]} for r in rows],
          open(os.path.join(d, "unindexed_audit.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("\nsimpan -> data/unindexed_audit.json")
