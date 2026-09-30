"""OAuth sekali jalan untuk Google Search Console API (scope webmasters.readonly).

Pakai client secret Desktop app yang sama dengan skill google-workspace.
Hasil: ~/AppData/Local/hermes/google_token.json (dibaca gsc_pull.py).

  python auth_gsc.py --url          # cetak URL consent
  python auth_gsc.py --code "<url atau code>"
  python auth_gsc.py --check
"""
import argparse, json, os, sys, urllib.parse, urllib.request

HERMES = os.environ.get("HERMES_HOME") or os.path.expanduser("~/AppData/Local/hermes")
SECRET = os.path.join(HERMES, "google_client_secret.json")
TOKEN = os.path.join(HERMES, "google_token.json")
SCOPE = "https://www.googleapis.com/auth/webmasters.readonly"
REDIRECT = "http://localhost"


def client():
    cs = json.load(open(SECRET, encoding="utf-8"))
    return cs.get("installed") or cs.get("web") or cs


def post(url, data):
    req = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode())
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def auth_url():
    c = client()
    q = urllib.parse.urlencode({
        "client_id": c["client_id"], "redirect_uri": REDIRECT,
        "response_type": "code", "scope": SCOPE,
        "access_type": "offline", "prompt": "consent"})
    return "https://accounts.google.com/o/oauth2/v2/auth?" + q


def exchange(code_or_url):
    if "code=" in code_or_url:
        code_or_url = urllib.parse.parse_qs(
            urllib.parse.urlparse(code_or_url).query)["code"][0]
    c = client()
    tok = post("https://oauth2.googleapis.com/token", {
        "code": code_or_url, "client_id": c["client_id"],
        "client_secret": c["client_secret"], "redirect_uri": REDIRECT,
        "grant_type": "authorization_code"})
    out = {"type": "authorized_user", "client_id": c["client_id"],
           "client_secret": c["client_secret"],
           "refresh_token": tok.get("refresh_token"),
           "token": tok.get("access_token"),
           "scopes": tok.get("scope", SCOPE).split()}
    if not out["refresh_token"]:
        sys.exit("Tidak dapat refresh_token — ulangi --url (pastikan prompt=consent).")
    json.dump(out, open(TOKEN, "w", encoding="utf-8"), indent=1)
    print("token tersimpan:", TOKEN)
    print("scopes:", out["scopes"])


def check():
    if not os.path.exists(TOKEN):
        print("NOT_AUTHENTICATED")
        return
    t = json.load(open(TOKEN, encoding="utf-8"))
    c = client()
    r = post("https://oauth2.googleapis.com/token", {
        "client_id": c["client_id"], "client_secret": c["client_secret"],
        "refresh_token": t["refresh_token"], "grant_type": "refresh_token"})
    at = r["access_token"]
    req = urllib.request.Request("https://searchconsole.googleapis.com/webmasters/v3/sites",
                                 headers={"Authorization": "Bearer " + at})
    with urllib.request.urlopen(req, timeout=60) as resp:
        sites = json.load(resp).get("siteEntry", [])
    print("AUTHENTICATED — %d properti Search Console:" % len(sites))
    for s in sites:
        print("  %-45s %s" % (s["siteUrl"], s.get("permissionLevel")))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", action="store_true")
    ap.add_argument("--code")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    if a.url:
        print(auth_url())
    elif a.code:
        exchange(a.code)
    elif a.check:
        check()
    else:
        ap.print_help()
