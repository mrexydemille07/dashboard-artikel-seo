"""Ambil SEMUA URL artikel/post per domain dari child sitemap bertipe post.

WP (Yoast/RankMath) memisahkan sitemap per post-type: post-sitemap.xml = artikel,
page/category/tag = bukan artikel. Child tanpa penanda post-type (custom post type,
mis. /insight/, /artikel-qhse/) dideteksi dari URL child-nya sendiri.

Output: data/sitemap_posts.json  {domain: [url, ...]}  (dinormalisasi, tanpa /)
"""
import json, os, re, sys, urllib.request
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
UA = {"User-Agent": "Mozilla/5.0"}

NOT_POST = re.compile(r"/(page|category|tag|author|post_tag|product|products|course|"
                      r"courses|course-category|testimonial|help|profile|member|"
                      r"partner|solution|solutions|services|case-study|event|events|"
                      r"attachment|library|document|faq|testimoni|karir|job)\b", re.I)

# Sitemap kadang berisi host alternatif (Framer/CDN). Kunci = host di sitemap,
# nilai = host live yang dipakai GSC. Hanya alias yang dikonfirmasi sendiri.
HOST_ALIAS = {"proxsis-strategy.framer.ai": "strategy.proxsisgroup.com"}

# Fallback domain tanpa sitemap bisa diakses: kenali artikel dari GSC (slug akar
# yang mirip judul: 1 segmen, ada tanda -, panjang).
def looks_like_post_url(u):
    p = urlsplit(u).path.strip("/")
    if "/" in p:
        return False
    low = p.lower()
    return "-" in low and len(low) >= 20 and not low.endswith(".xml")


def get(u, t=25):
    try:
        body = urllib.request.urlopen(
            urllib.request.Request(u, headers=UA), timeout=t).read().decode("utf-8", "replace")
        # Yoast membungkus <loc> dalam <![CDATA[ ... ]]>
        return re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", body)
    except Exception:
        return ""


def norm(u):
    s = (u or "").strip().lower().replace("http://", "https://").split("#")[0]
    return s.rstrip("/")


def child_kind(url):
    """post | notpost dari nama child sitemap."""
    low = url.lower()
    if re.search(r"(^|[-_/])(post|blog|article|artikel|insight|berita|news|story|stories|"
                 r"articles|insights)([-.]|$)", low) or "post-archive" in low:
        return "post"
    if NOT_POST.search(low) or re.search(r"(page|category|tag|author)[-_.]?\d*\.xml", low):
        return "notpost"
    return "unknown"


def to_live_host(dom, urls):
    """Sitemap bisa berisi host Framer/CDN -> tulis ulang ke host live (dipakai GSC)."""
    out = []
    for u in urls:
        parts = urlsplit(u)
        h = parts.netloc.lower().replace("www.", "")
        alias = HOST_ALIAS.get(h)          # host asing TANPA alias = dibuang, bukan ditebak
        if alias:
            u = u.replace(parts.netloc, alias)
        if urlsplit(u).netloc.lower().replace("www.", "") == dom:
            out.append(u)
    return sorted(set(out))


def posts_for(dom):
    urls, children = set(), []
    for idx in ("https://%s/sitemap_index.xml" % dom, "https://%s/sitemap.xml" % dom,
                "https://%s/wp-sitemap.xml" % dom):
        body = get(idx)
        if not body:
            continue
        locs = re.findall(r"<loc>(.*?)</loc>", body)
        if "<sitemap>" in body:
            children = locs
            break
        # sitemap tunggal: langsung isi URL
        for u in locs:
            if not NOT_POST.search(urlsplit(u).path):
                urls.add(norm(u))
        if urls:
            return dom, to_live_host(dom, urls), idx
    if not children:
        return dom, [], None
    # ambil child 'post' + 'unknown' yang URL di dalamnya bukan pola non-post
    def fetch_child(c):
        k = child_kind(c)
        body = get(c)
        locs = [norm(x) for x in re.findall(r"<loc>(.*?)</loc>", body)]
        if k == "notpost":
            return []
        if k == "post":
            return locs
        # unknown: filter per URL (path non-post dibuang)
        return [u for u in locs if not NOT_POST.search(urlsplit(u).path)]
    with ThreadPoolExecutor(max_workers=8) as ex:
        for got in ex.map(fetch_child, children):
            urls.update(got)
    # buang URL yang jelas arsip (tag/category/author di path)
    urls = {u for u in urls if not NOT_POST.search(urlsplit(u).path)}
    return dom, to_live_host(dom, urls), "%d child" % len(children)


def main():
    brands = json.load(open(os.path.join(DATA, "brands.json"), encoding="utf-8"))
    doms = sorted({b["domain"] for b in brands if b.get("domain")})
    out = {}
    with ThreadPoolExecutor(max_workers=6) as ex:
        for dom, urls, src in ex.map(posts_for, doms):
            out[dom] = urls
            print("%-32s %6d artikel   (%s)" % (dom, len(urls), src or "TAK ADA SITEMAP"))
    # Fallback: domain yang sitemapnya tak terbaca -> kenali artikel dari GSC
    raw = json.load(open(os.path.join(DATA, "gsc_raw.json"), encoding="utf-8"))
    from collections import defaultdict
    bydom = defaultdict(list)
    for u in raw:
        h = urlsplit(u).netloc.lower().replace("www.", "")
        if looks_like_post_url(u):
            bydom[h].append("https://%s/%s" % (h, urlsplit(u).path.strip("/")))
    for dom in doms:
        if not out[dom] and bydom.get(dom):
            out[dom] = sorted(set(map(norm, bydom[dom])))
            print("%-32s %6d artikel   (FALLBACK dari GSC: slug akar)" % (dom, len(out[dom])))
    json.dump(out, open(os.path.join(DATA, "sitemap_posts.json"), "w", encoding="utf-8"),
              ensure_ascii=False)
    tot = sum(len(v) for v in out.values())
    print("\ntotal: %d URL artikel di %d domain -> data/sitemap_posts.json" % (tot, len(out)))


if __name__ == "__main__":
    main()
