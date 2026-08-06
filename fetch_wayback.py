"""Rebuild the gsmg.io puzzle corpus from the Wayback Machine.

gsmg.io is now a parked for-sale domain, so the live site is worthless: every
path returns the same ~28KB parking page. The puzzle text only exists in
archived snapshots.

Covers both hosts. alpha.gsmg.io is a separate archived host carrying its own
copies of puzzle stages, and it is not referenced anywhere in the puzzlehunt
repo.

Passes:
  1. CDX inventory of every archived URL per host
  2. raw fetch (`id_`, no Wayback toolbar injection) of EVERY non-furniture
     snapshot of each known puzzle path -- pages were edited over the years, so
     the newest or biggest snapshot is not necessarily the interesting one
  3. dedupe by content hash and report which files carry AES blobs

Run: python fetch_wayback.py
"""

import gzip
import hashlib
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

OUT = Path(__file__).with_name("corpus")
OUT.mkdir(exist_ok=True)

UA = {"User-Agent": "Mozilla/5.0 (compatible; puzzle-archive-reader/1.0)"}
DELAY = 4.0

HOSTS = ["gsmg.io", "alpha.gsmg.io"]

PATHS = [
    ("root", ""),
    ("puzzle", "puzzle"),
    ("theseedisplanted", "theseedisplanted"),
    ("choiceisanillusion",
     "choiceisanillusioncreatedbetweenthosewithpowerandthosewithout"
     "averyspecialdessertiwroteitmyself"),
    ("salphaseion",
     "89727c598b9cd1cf8873f27cb7057f050645ddb6a7a157a110239ac0152f6a32"),
    ("cosmic_hash",
     "4f7a1e4efe4bf6c5581e32505c019657cb7b030e90232d33f011aca6a5e9c081"),
]

# Snapshot sizes that are known to be furniture, not puzzle content.
JUNK = ((0, 400),         # empty / error stubs
        (700, 1300),      # FingerprintJS redirect shim
        (11700, 13100),   # older parking page
        (27000, 29000))   # current abovedomains parking page


def get(url, tries=4):
    """archive.org throttles hard under load; back off rather than give up."""
    for i in range(tries):
        try:
            time.sleep(DELAY * (i + 1))
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=120) as r:
                body = r.read()
            # `id_` snapshots are served exactly as archived, which means the
            # original Content-Encoding is still on them.
            if body[:2] == b"\x1f\x8b":
                body = gzip.decompress(body)
            return body
        except Exception as e:
            if i == tries - 1:
                print(f"      FAIL {e}")
    return None


def cdx(url, extra=""):
    q = (f"https://web.archive.org/cdx/search/cdx?url={url}{extra}"
         f"&output=text&fl=timestamp,original,statuscode,length"
         f"&filter=statuscode:200&limit=6000")
    data = get(q)
    if not data:
        return []
    rows = []
    for line in data.decode("utf-8", "replace").splitlines():
        parts = line.split(" ")
        if len(parts) >= 4 and parts[-1].isdigit():
            rows.append((parts[0], " ".join(parts[1:-2]), int(parts[-1])))
    return rows


def is_junk(n):
    return any(lo <= n <= hi for lo, hi in JUNK)


def main():
    seen_hashes = {}

    for host in HOSTS:
        print("=" * 72)
        print(f"PASS 1: CDX inventory for {host}")
        print("=" * 72)
        rows = cdx(host, "&matchType=domain&collapse=urlkey")
        (OUT / f"_cdx_{host}.txt").write_text(
            "\n".join(f"{t} {u} {n}" for t, u, n in rows), encoding="utf-8")
        live = [r for r in rows if not is_junk(r[2])]
        print(f"  {len(rows)} archived URLs, {len(live)} with non-furniture payloads")
        for t, u, n in live[:25]:
            print(f"    {t}  {n:>7}  {u[:92]}")

        print()
        print("=" * 72)
        print(f"PASS 2: every non-furniture snapshot per path on {host}")
        print("=" * 72)
        for name, path in PATHS:
            snaps = [r for r in cdx(f"{host}/{path}") if not is_junk(r[2])]
            if not snaps:
                print(f"  {name:<20} none")
                continue
            # One fetch per distinct payload size: same size, same page.
            by_size = {}
            for ts, orig, n in snaps:
                by_size.setdefault(n, (ts, orig))
            print(f"  {name:<20} {len(snaps):>3} snaps, {len(by_size)} distinct sizes")
            for n, (ts, orig) in sorted(by_size.items()):
                body = get(f"https://web.archive.org/web/{ts}id_/{orig}")
                if not body:
                    continue
                h = hashlib.sha256(body).hexdigest()
                if h in seen_hashes:
                    print(f"      {ts} {n:>7} dup of {seen_hashes[h]}")
                    continue
                tag = host.split(".")[0] if host != "gsmg.io" else "gsmg"
                fn = f"wb_{tag}_{name}_{ts}.html"
                seen_hashes[h] = fn
                (OUT / fn).write_bytes(body)
                blob = "  <-- HAS AES BLOB" if b"U2FsdGVkX1" in body else ""
                print(f"      {ts} {n:>7} -> {fn}{blob}")
        print()

    print("=" * 72)
    print("files carrying AES blobs")
    print("=" * 72)
    for f in sorted(OUT.glob("wb_*.html")):
        data = f.read_bytes()
        blobs = re.findall(rb"U2FsdGVkX1[A-Za-z0-9+/=\s]{40,}", data)
        if blobs:
            sizes = [len(b"".join(b.split())) for b in blobs]
            print(f"  {f.name:<44} {len(blobs)} blob(s), b64 chars {sizes}")


if __name__ == "__main__":
    main()
