"""Refresh penuh: sheet -> GSC -> meta -> build -> smoke -> push.

Ponytail: satu entry point, tanpa argumen. Kalau ada tahap gagal, berhenti
sebelum push supaya dashboard live tidak pernah berisi data setengah jadi.
"""
import json, os, subprocess, sys, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
SHEET = ("https://docs.google.com/spreadsheets/d/"
         "1poUtrDRaYwTOi_PYMa4q3CvfwA_JXvwT9me2Is7nuFw/export?format=csv&gid=0")


def run(cmd, **kw):
    print("$", " ".join(cmd), flush=True)
    r = subprocess.run(cmd, cwd=HERE, **kw)
    if r.returncode:
        sys.exit("GAGAL: %s (exit %d)" % (" ".join(cmd), r.returncode))


def main():
    # 1) kertas kerja
    import urllib.request
    with urllib.request.urlopen(SHEET, timeout=60) as r:
        open(os.path.join(HERE, "sheet0.csv"), "wb").write(r.read())
    run([sys.executable, "build_data.py"])
    run([sys.executable, "parse_laporan.py"])

    # 2) GSC (butuh token lokal; kalau kedaluwarsa, jalankan auth_gsc.py manual)
    run([sys.executable, "gsc_pull.py", "--all", "--days", "90"])

    # 3) meta audit: hanya URL baru (script punya resume)
    run([sys.executable, "meta_audit.py"])
    run([sys.executable, "meta_fix.py"])

    # 4) semua URL artikel per brand dari sitemap -> data/posts.json
    # (gsc_raw.json sudah ada dari langkah 2; dipakai utk fallback + join metrik)
    run([sys.executable, "sitemap_posts.py"])
    run([sys.executable, "diagnose.py"])   # resume: hanya fetch URL baru

    # 5) build + test render
    run([sys.executable, "build.py"])
    run(["node", "smoke.js", "index.html"])

    # 5) push
    tok = json.load(open(os.path.join(HERE, "gh_token.json")))["access_token"]
    env = dict(os.environ, GH_TOKEN=tok)
    run(["git", "add", "-A"], env=env)
    msg = "refresh data " + datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    subprocess.run(["git", "-c", "user.name=erxy", "-c", "user.email=erxy@local",
                    "commit", "-qm", msg], cwd=HERE, env=env)
    run(["git", "push", "-q", "origin", "main"], env=env)
    print("\nselesai:", msg)


if __name__ == "__main__":
    main()
