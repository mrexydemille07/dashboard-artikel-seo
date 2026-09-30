"""Audit ulang: gali SEMUA child sitemap (bukan 6 pertama) untuk URL yang kemarin
dikira 'tidak ada di sitemap'. Yoast sitemap_index bisa punya >6 child.
"""
import json, os, re, collections, urllib.request
from urllib.parse import urlsplit

d = os.path.expanduser("~/AppData/Local/Temp/artikel2026/data")
UA = {"User-Agent": "Mozilla/5.0"}


def get(u, t=30):
    try:
        return urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=t).read().decode("utf-8", "replace")
    except Exception:
        return ""


def norm(u):
    s = (u or "").strip().lower().replace("http://", "https://").split("#")[0]
    return s.rstrip("/")


def all_sitemap_urls(dom):
    out = set()
    for idx in ("https://%s/sitemap_index.xml" % dom, "https://%s/sitemap.xml" % dom):
        body = get(idx)
        if not body:
            continue
        locs = re.findall(r"<loc>(.*?)</loc>", body)
        if "<sitemap>" in body:
            for child in locs:
                out.update(norm(x) for x in re.findall(r"<loc>(.*?)</loc>", get(child)))
        else:
            out.update(norm(x) for x in locs)
        if out:
            break
    return out


rows = json.load(open(f"{d}/unindexed_audit.json", encoding="utf-8"))
sus = [r for r in rows if r["http"] == "200" and r["in_sitemap"] == "T"]
doms = sorted({r["domain"] for r in sus})
sm = {dm: all_sitemap_urls(dm) for dm in doms}
print("domain | total URL di sitemap (semua child)")
for dm in doms:
    print("  %-30s %6d" % (dm, len(sm[dm])))

fixed, still = [], []
for r in sus:
    (fixed if norm(r["url"]) in sm[r["domain"]] else still).append(r)
print("\nKOREKSI: %d ternyata ADA di sitemap (audit lama salah), %d memang tidak ada"
      % (len(fixed), len(still)))
print("per domain (yang masih tidak ada):", collections.Counter(r["domain"] for r in still).most_common())

# update audit file
by_url = {r["url"]: r for r in rows}
for r in fixed:
    by_url[r["url"]]["in_sitemap"] = "Y"
    by_url[r["url"]]["note"] = "audit ulang: ada di child sitemap"
json.dump(list(by_url.values()), open(f"{d}/unindexed_audit.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("\n-> data/unindexed_audit.json diperbarui")
for r in still[:15]:
    print("   STILL", r["domain"], r["url"])
