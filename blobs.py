"""Inventory every AES blob recovered from the archive, deduped.

The point is to find ciphertext the puzzlehunt repo never had. Blobs are keyed
by content hash so the same blob appearing on five snapshots counts once, and
anything that does not match a known stage gets flagged.

Run: python blobs.py
"""

import hashlib
import re
from base64 import b64decode
from pathlib import Path

from pipeline import PHASE32_BLOB, SALPHASEION_BLOB

CORPUS = Path(__file__).with_name("corpus")

KNOWN = {
    hashlib.sha256(b64decode(PHASE32_BLOB)).hexdigest(): "phase 3.2 (in repo README)",
    hashlib.sha256(b64decode(SALPHASEION_BLOB)).hexdigest():
        "salphaseion 96-byte (in repo README)",
}


def blobs_in(text):
    """openssl base64 blobs, tolerating the newlines the pages wrap them in."""
    for m in re.finditer(r"U2FsdGVkX1[A-Za-z0-9+/=\s]{40,}", text):
        b64 = "".join(m.group(0).split())
        # Trim to a decodable length; the regex can swallow trailing markup text.
        while len(b64) >= 24:
            try:
                raw = b64decode(b64, validate=True)
                if len(raw) > 16 and (len(raw) - 16) % 16 == 0:
                    yield b64, raw
                    break
            except Exception:
                pass
            b64 = b64[:-1]


def main():
    found = {}
    for f in sorted(CORPUS.glob("wb_*.html")):
        text = f.read_text(encoding="utf-8", errors="replace")
        for b64, raw in blobs_in(text):
            h = hashlib.sha256(raw).hexdigest()
            found.setdefault(h, {"raw": raw, "b64": b64, "files": []})
            found[h]["files"].append(f.name)

    print(f"{len(found)} distinct AES blobs across {len(list(CORPUS.glob('wb_*.html')))} archived pages\n")
    for h, d in sorted(found.items(), key=lambda kv: len(kv[1]["raw"])):
        raw, ct = d["raw"], len(d["raw"]) - 16
        tag = KNOWN.get(h, "*** NOT IN THE REPO ***")
        print(f"{ct:>5} bytes ciphertext  (max plaintext {ct - 1})  {tag}")
        print(f"  sha256 {h}")
        print(f"  seen in {len(d['files'])} page(s): {d['files'][0]}"
              + (f" (+{len(d['files']) - 1} more)" if len(d["files"]) > 1 else ""))
        out = CORPUS / f"blob_{ct}_{h[:12]}.b64"
        out.write_text(d["b64"], encoding="utf-8")
        print(f"  saved {out.name}\n")


if __name__ == "__main__":
    main()
