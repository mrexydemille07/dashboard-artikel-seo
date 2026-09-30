"""Tarik data Google Search Console per URL artikel -> data/gsc.json.

Pakai kredensial OAuth Hermes yang sama dengan skill google-workspace
(~/.hermes/google_token.json + google_client_secret.json).

Contoh:
  python gsc_pull.py --site https://grc-indonesia.com/ --days 90
  python gsc_pull.py --all --days 90          # semua domain dari data/brands.json

Ponytail: satu request per (site, dimensi page) + satu per (site, page+date) untuk
tren mingguan. Kalau kuota GSC jadi masalah, naikkan --days atau pecah per bulan.
"""
import argparse, datetime, json, os, sys, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
HERMES = os.environ.get("HERMES_HOME") or os.path.expanduser("~/AppData/Local/hermes")
TOKEN = os.path.join(HERMES, "google_token.json")
SECRET = os.path.join(HERMES, "google_client_secret.json")
API = "https://searchconsole.googleapis.com/webmasters/v3/sites/%s/searchAnalytics/query"


def access_token():
    tok = json.load(open(TOKEN, encoding="utf-8"))
    if not tok.get("refresh_token"):
        sys.exit("google_token.json tidak punya refresh_token — jalankan setup google-workspace dulu.")
    cs = json.load(open(SECRET, encoding="utf-8"))
    cs = cs.get("installed") or cs.get("web") or cs
    body = urllib.parse.urlencode({
        "client_id": cs["client_id"], "client_secret": cs["client_secret"],
        "refresh_token": tok["refresh_token"], "grant_type": "refresh_token"}).encode()
    req = urllib.request.Request("https://oauth2.googleapis.com/token", data=body)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)["access_token"]


def query(token, site, payload):
    req = urllib.request.Request(
        API % urllib.parse.quote(site, safe=""),
        data=json.dumps(payload).encode(),
        headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        print("  ! %s -> %s %s" % (site, e.code, e.read()[:200].decode("utf-8", "replace")))
        return None


def iso(d):
    return d.isoformat()


def iso_week(datestr):
    """2026-09-30 -> 2026W40 (penomoran ISO, sama seperti dashboard mas Syafii)."""
    y, w, _ = datetime.date.fromisoformat(datestr).isocalendar()
    return "%dW%02d" % (y, w)


def pull_site(token, site, days):
    end = datetime.date.today() - datetime.timedelta(days=2)   # GSC lag ~2 hari
    start = end - datetime.timedelta(days=days)
    out = {}

    # 1) agregat per halaman
    res = query(token, site, {"startDate": iso(start), "endDate": iso(end),
                              "dimensions": ["page"], "rowLimit": 25000})
    if not res:
        return out
    for row in res.get("rows", []):
        url = row["keys"][0]
        out[url] = {"impr": row.get("impressions", 0), "clicks": row.get("clicks", 0),
                    "ctr": round(row.get("ctr", 0) * 100, 2),
                    "pos": round(row.get("position", 0), 1), "weeks": []}

    # 2) tren harian per halaman -> diagregasi jadi ISO-week di sini
    #    (API GSC tidak punya dimensi "week", dan filter per-URL akan makan 500 request)
    r2 = query(token, site, {"startDate": iso(start), "endDate": iso(end),
                             "dimensions": ["date", "page"], "rowLimit": 25000})
    if r2:
        acc = {}
        for row in r2.get("rows", []):
            d, url = row["keys"][0], row["keys"][1]
            m = out.get(url)
            if m is None:
                continue
            wk = iso_week(d)
            a = acc.setdefault((url, wk), {"impr": 0, "clicks": 0, "posW": 0.0})
            a["impr"] += row.get("impressions", 0)
            a["clicks"] += row.get("clicks", 0)
            a["posW"] += row.get("position", 0) * row.get("impressions", 0)
        for (url, wk), a in acc.items():
            ctr = round(100 * a["clicks"] / a["impr"], 2) if a["impr"] else 0
            pos = round(a["posW"] / a["impr"], 1) if a["impr"] else 0
            out[url]["weeks"].append({"w": wk, "impr": a["impr"], "clicks": a["clicks"],
                                      "ctr": ctr, "pos": pos})
        for m in out.values():
            m["weeks"].sort(key=lambda x: x["w"])

    # 3) query per halaman -> keyword apa yang mendatangkan impresi.
    #    Dimensi page+query: satu request, tapi baris bisa banyak -> rowLimit tinggi.
    r3 = query(token, site, {"startDate": iso(start), "endDate": iso(end),
                             "dimensions": ["page", "query"], "rowLimit": 25000})
    if r3:
        for row in r3.get("rows", []):
            url, q = row["keys"][0], row["keys"][1]
            m = out.get(url)
            if m is None:
                continue
            m.setdefault("queries", []).append({
                "q": q, "impr": row.get("impressions", 0), "clicks": row.get("clicks", 0),
                "ctr": round(row.get("ctr", 0) * 100, 2),
                "pos": round(row.get("position", 0), 1)})
        for m in out.values():
            if m.get("queries"):
                m["queries"].sort(key=lambda x: -x["impr"])
                m["queries"] = m["queries"][:25]      # 25 keyword teratas per URL
    return out


def list_sites(token):
    """domain -> siteUrl persis seperti yang terdaftar di GSC (URL-prefix atau sc-domain)."""
    req = urllib.request.Request("https://searchconsole.googleapis.com/webmasters/v3/sites",
                                 headers={"Authorization": "Bearer " + token})
    with urllib.request.urlopen(req, timeout=60) as r:
        sites = json.load(r).get("siteEntry", [])
    out = {}
    for s in sites:
        u = s["siteUrl"]
        d = u.replace("sc-domain:", "").rstrip("/").replace("https://", "").replace("http://", "")
        out.setdefault(d, u)          # URL-prefix menang kalau ada dua-duanya
        if u.startswith("sc-domain:"):
            out[d] = u
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", action="append", default=[], help="mis. https://grc-indonesia.com/")
    ap.add_argument("--all", action="store_true", help="semua domain dari data/brands.json")
    ap.add_argument("--days", type=int, default=90)
    a = ap.parse_args()

    token = access_token()
    registered = list_sites(token)
    print("%d properti terdaftar di GSC" % len(registered))

    sites = list(a.site)
    if a.all:
        brands = json.load(open(os.path.join(DATA, "brands.json"), encoding="utf-8"))
        for b in brands:
            d = b["domain"]
            if d in ("drive.google.com",):
                continue
            if d in registered:
                sites.append(registered[d])
            else:
                print("  ! %s tidak ada properti GSC-nya — dilewati" % d)
    if not sites:
        sys.exit("kasih --site atau --all")

    gsc_path = os.path.join(DATA, "gsc.json")
    gsc = json.load(open(gsc_path, encoding="utf-8")) if os.path.exists(gsc_path) else {}
    for s in sites:
        print("→", s)
        got = pull_site(token, s, a.days)
        print("   %d URL" % len(got))
        gsc.update(got)
    json.dump(gsc, open(gsc_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("total %d URL di data/gsc.json" % len(gsc))


if __name__ == "__main__":
    main()
