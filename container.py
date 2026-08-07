"""Does any decoding of faed produce a recognisable container?

faed is uniform high-entropy data once 'g' is removed, and the key is not in it
(exhausted, 70.7M checks). So the open question is not which cipher was used but
what KIND of object it is. If it is a container rather than raw bytes, it should
announce itself: openssl blobs start "Salted__", gzip starts 1f 8b, and so on --
and every other stage of this puzzle used openssl base64 blobs.

This sweeps every symbol mapping and asks whether the decoded bytes are
recognisable as anything, by five independent tests that need no key:

  MAGIC       known file/container signatures at offset 0 or anywhere
  PRINTABLE   a high ASCII fraction, which raw ciphertext will not have
  BASE64/HEX  the decoded bytes being themselves an encoded string
  COMPRESSIBLE  zlib shrinking it, which encrypted data will not allow
  NULL RUNS   long zero runs, which indicate structure or padding

Two decodings are covered: base 9 over all 570 symbols (362,880 mappings) and
base 8 over the 463 symbols left after dropping 'g' (40,320 mappings).

No elliptic-curve work, so this is minutes rather than hours.

Run: python container.py
"""

import re
import sys
import zlib
from itertools import permutations

from bigrun import get_runs

MAGICS = [
    (b"Salted__", "openssl salted blob"),
    (b"\x1f\x8b\x08", "gzip"),
    (b"PK\x03\x04", "zip"),
    (b"\x89PNG\r\n\x1a\n", "png"),
    (b"BZh", "bzip2"),
    (b"\xfd7zXZ", "xz"),
    (b"\x78\x9c", "zlib default"),
    (b"\x78\x01", "zlib low"),
    (b"\x78\xda", "zlib best"),
    (b"-----BEGIN", "PEM"),
    (b"\x04\x22\x4d\x18", "lz4"),
    (b"\x28\xb5\x2f\xfd", "zstd"),
    (b"GIF8", "gif"),
    (b"\xff\xd8\xff", "jpeg"),
]

B64 = set(b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=")
HEXC = set(b"0123456789abcdefABCDEF")


def byte_width(nsyms, base):
    return ((base ** nsyms - 1).bit_length() + 7) // 8


def decode(run, digit_of, base, width):
    n = 0
    for c in run:
        n = n * base + digit_of[c]
    return n.to_bytes(width, "big")


def longest_run(b, val=0):
    best = cur = 0
    for x in b:
        cur = cur + 1 if x == val else 0
        best = max(best, cur)
    return best


def inspect(b):
    """Return a list of reasons this byte string looks like something.

    A magic counts only at offset 0, or anywhere if it is at least 4 bytes
    long. Short signatures on high-entropy data are worthless: a given 2-byte
    pattern occurs in 174 random bytes with probability ~0.27%, so the three
    zlib headers alone yield hundreds of hits across 40,320 mappings purely by
    chance."""
    hits = []
    for magic, name in MAGICS:
        if b.startswith(magic):
            hits.append(f"{name} magic at offset 0")
        elif len(magic) >= 4:
            i = b.find(magic)
            if i != -1:
                hits.append(f"{name} magic at offset {i}")
    pr = sum(1 for c in b if 32 <= c < 127) / len(b)
    if pr > 0.95:
        hits.append(f"printable {pr:.2f}")
    if sum(1 for c in b if c in B64) / len(b) > 0.98:
        hits.append("entirely base64 charset")
    if sum(1 for c in b if c in HEXC) / len(b) > 0.98:
        hits.append("entirely hex charset")
    comp = len(zlib.compress(b, 9))
    if comp < len(b) * 0.92:
        hits.append(f"compressible to {comp / len(b):.2f}")
    nr = longest_run(b)
    if nr >= 8:
        hits.append(f"{nr}-byte zero run")
    return hits


def sweep(run, base, label):
    syms = sorted(set(run))
    width = byte_width(len(run), base)
    pool = list(range(base))
    total = 1
    for i in range(len(syms)):
        total *= len(pool) - i
    print(f"{label}: {len(run)} symbols, base {base} -> {width} bytes, "
          f"{total:,} mappings")

    found, seen = [], 0
    for perm in permutations(pool, len(syms)):
        seen += 1
        if seen % 20000 == 0:
            print(f"\r    {seen:,}/{total:,}", end="", file=sys.stderr,
                  flush=True)
        b = decode(run, dict(zip(syms, perm)), base, width)
        hits = inspect(b)
        if hits:
            found.append((perm, hits, b))
    print(f"\r    {seen:,}/{total:,} done{' ' * 20}", file=sys.stderr)
    print(f"  {len(found)} mappings produced a recognisable signature")
    for perm, hits, b in found[:8]:
        print(f"    map={''.join(map(str, perm))}: {'; '.join(hits)}")
        print(f"        {b[:56]!r}")
    if not found:
        print("    none")
    print()
    return found


def main():
    runs = get_runs()
    m = re.search(r"[ab]{40,}", runs[0])
    faed = runs[0][m.end():]

    print("=" * 72)
    print("control -- what a real openssl blob looks like to this detector")
    print("=" * 72)
    from base64 import b64decode
    from pipeline import SALPHASEION_BLOB
    ctrl = b64decode("".join(SALPHASEION_BLOB.split()))
    print(f"  SalPhaseIon blob: {inspect(ctrl)}\n")

    sweep(faed.replace("g", ""), 8, "faed minus 'g'")
    sweep(faed, 9, "faed whole")


if __name__ == "__main__":
    main()
