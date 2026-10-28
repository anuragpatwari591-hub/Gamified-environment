"""Automated link REACHABILITY check for seeded resources.

    python scripts/verify_links.py [--apply]

What it does: sends a HEAD/GET request to each resource URL and prints the HTTP status.
With --apply it records the result in `verification_notes` and sets `last_verified_at` to today for reachable links
(2xx/3xx), and flags confirmed-dead links (404/410) as 'broken'.

What it does NOT do: it does not check that the content is still accurate, the price is current, or the course is good.
Many sites return 403/999 to scripts; those are reported as 'blocked, needs manual check' and left unverified.
Only an admin's manual Verify action in the admin panel should be treated as a content check.
"""
import sqlite3
import sys
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import Config  # noqa: E402

UA = {"User-Agent": "Mozilla/5.0 (compatible; NavoraLinkCheck/1.0; +educational project)"}


def check(url):
    for method in ("HEAD", "GET"):
        try:
            req = urllib.request.Request(url, method=method, headers=UA)
            with urllib.request.urlopen(req, timeout=12) as r:
                return r.status
        except urllib.error.HTTPError as e:
            if method == "HEAD" and e.code in (400, 403, 404, 405, 501):   # some servers answer HEAD wrongly; retry with GET
                continue
            return e.code
        except Exception as e:                      # DNS failure, timeout, TLS error ...
            if method == "HEAD":
                continue
            return f"error:{type(e).__name__}"
    return "error"


def main():
    apply = "--apply" in sys.argv
    db = sqlite3.connect(Config.DATABASE)
    db.row_factory = sqlite3.Row
    today = date.today().isoformat()
    rows = db.execute("SELECT id, title, url FROM resources ORDER BY id").fetchall()
    ok = blocked = dead = err = 0
    for r in rows:
        st = check(r["url"])
        if isinstance(st, int) and 200 <= st < 400:
            ok += 1
            label, note = "OK", f"Automated reachability check {today}: HTTP {st}. Content not reviewed."
            if apply:
                db.execute("UPDATE resources SET last_verified_at=?, verification_notes=?, "
                           "status=CASE WHEN status='unverified' THEN 'active' ELSE status END WHERE id=?", (today, note, r["id"]))
        elif st in (404, 410):
            dead += 1
            label, note = "DEAD", f"Automated check {today}: HTTP {st} - link appears broken."
            if apply:
                db.execute("UPDATE resources SET status='broken', verification_notes=? WHERE id=?", (note, r["id"]))
        else:
            if isinstance(st, int) and st in (401, 403, 429, 999):
                blocked += 1
                label, note = "BLOCKED", f"Automated check {today}: HTTP {st} (site blocks scripts) - needs manual check."
            else:
                err += 1
                label, note = "ERROR", f"Automated check {today}: {st} - needs manual check."
            if apply:
                db.execute("UPDATE resources SET verification_notes=? WHERE id=?", (note, r["id"]))
        print(f"{label:8} {str(st):>6}  {r['id']:>3}  {r['title'][:60]}")
    if apply:
        db.commit()
    print(f"\nreachable={ok} blocked={blocked} dead={dead} error={err} total={len(rows)} applied={apply}")


if __name__ == "__main__":
    main()
