"""Steganography sweep over the puzzle images.

Checks, cheapest first:
  1. trailing data after PNG IEND / JPEG EOI -- the most common hiding place
  2. PNG chunk inventory: text chunks, unknown chunks, chunks after IEND
  3. printable strings in the raw file
  4. LSB extraction across channel/bit-order/scan-order combinations
  5. alpha channel and palette anomalies

An LSB "hit" is only reported when the extracted bytes look like real content
(high printable ratio, or a base64/openssl/hex signature). Random pixels always
yield random bits, so anything less is noise.

Run: python stego.py [paths...]
"""

import re
import string
import struct
import sys
import zlib
from pathlib import Path

from PIL import Image

REPO = Path(__file__).with_name("gsmgio-5btc-puzzle")
CORPUS_IMG = Path(__file__).with_name("corpus") / "img"

PRINTABLE = set(bytes(string.printable, "ascii"))
# Signatures must be long enough not to fire on random bytes. A 2-byte pattern
# hits roughly 6% of any 4KB random buffer, which is why WIF prefixes are
# matched structurally below instead of as literals.
SIGNATURES = [
    (b"U2FsdGVkX1", "openssl salted base64"),
    (b"Salted__", "openssl salted raw"),
    (b"PK\x03\x04", "zip"),
    (b"\x89PNG\r\n\x1a\n", "nested png"),
    (b"-----BEGIN", "PEM/armour"),
    (b"\x1f\x8b\x08", "gzip"),
]

B58 = rb"[1-9A-HJ-NP-Za-km-z]"
# A WIF key is 51 chars (uncompressed, '5') or 52 ('K'/'L'), all base58.
WIF = re.compile(rb"(?<!" + B58 + rb")(5" + B58 + rb"{50}|[KL]" + B58 + rb"{51})(?!" + B58 + rb")")
# A raw private key written as hex.
HEX64 = re.compile(rb"(?<![0-9a-fA-F])[0-9a-fA-F]{64}(?![0-9a-fA-F])")


def key_shaped(buf):
    """Structural hits for things that could actually be a private key."""
    out = []
    for m in WIF.finditer(buf):
        out.append(f"WIF-shaped: {m.group(0).decode('ascii')}")
    for m in HEX64.finditer(buf):
        out.append(f"64-hex: {m.group(0).decode('ascii')}")
    return out


def printable_ratio(b):
    return sum(1 for c in b if c in PRINTABLE) / len(b) if b else 0.0


# --- 1 & 2: container-level checks -------------------------------------------

def png_chunks(data):
    """Walk the PNG chunk list. Returns (chunks, trailing_bytes)."""
    out, i = [], 8
    while i + 8 <= len(data):
        (ln,) = struct.unpack(">I", data[i:i + 4])
        typ = data[i + 4:i + 8]
        body = data[i + 8:i + 8 + ln]
        out.append((typ.decode("latin1"), ln, body))
        i += 12 + ln
        if typ == b"IEND":
            break
    return out, data[i:]


def container_check(path, data):
    hits = []
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        chunks, trailing = png_chunks(data)
        std = {"IHDR", "PLTE", "IDAT", "IEND", "tRNS", "gAMA", "cHRM", "sRGB",
               "iCCP", "bKGD", "pHYs", "sBIT", "tIME", "hIST", "sPLT", "eXIf"}
        for typ, ln, body in chunks:
            if typ in ("tEXt", "zTXt", "iTXt"):
                txt = body
                if typ == "zTXt":
                    try:
                        k, rest = body.split(b"\x00", 1)
                        txt = k + b": " + zlib.decompress(rest[1:])
                    except Exception:
                        pass
                hits.append(f"text chunk {typ}: {txt[:200]!r}")
            elif typ not in std:
                hits.append(f"NON-STANDARD chunk {typ} ({ln} bytes): {body[:80]!r}")
        if trailing:
            hits.append(f"*** {len(trailing)} BYTES AFTER IEND: {trailing[:120]!r}")
    elif data[:2] == b"\xff\xd8":
        end = data.rfind(b"\xff\xd9")
        if end != -1 and end + 2 < len(data):
            tail = data[end + 2:]
            hits.append(f"*** {len(tail)} BYTES AFTER JPEG EOI: {tail[:120]!r}")
    return hits


def strings_check(data, minlen=8):
    found = []
    for m in re.finditer(rb"[\x20-\x7e]{%d,}" % minlen, data):
        s = m.group(0)
        # Skip the boilerplate every exported PNG carries.
        if any(k in s for k in (b"Adobe", b"XMP", b"xmlns", b"http://ns.",
                                b"Photoshop", b"ICC", b"GIMP", b"Software")):
            continue
        found.append(s)
    return found


# --- 4: LSB extraction --------------------------------------------------------

def lsb_variants(img):
    """Yield (label, bytes) over the plausible LSB conventions."""
    px = img.convert("RGBA")
    w, h = px.size
    data = list(px.getdata())

    orders = {
        "row": [(x, y) for y in range(h) for x in range(w)],
        "col": [(x, y) for x in range(w) for y in range(h)],
    }
    channels = {"r": [0], "g": [1], "b": [2], "a": [3], "rgb": [0, 1, 2]}

    for oname, coords in orders.items():
        flat = [data[y * w + x] for x, y in coords]
        for cname, chans in channels.items():
            bits = [(p[c] & 1) for p in flat for c in chans]
            for msb in (True, False):
                out = bytearray()
                for i in range(0, len(bits) - 7, 8):
                    byte = bits[i:i + 8]
                    if not msb:
                        byte = byte[::-1]
                    out.append(int("".join(map(str, byte)), 2))
                yield f"lsb/{oname}/{cname}/{'msb' if msb else 'lsb'}", bytes(out)


def lsb_check(path):
    try:
        img = Image.open(path)
    except Exception as e:
        return [f"cannot open: {e}"]
    # JPEG stores DCT coefficients, not pixels. Decoded pixel LSBs are
    # quantisation artifacts, so nothing can survive there to be found.
    if img.format in ("JPEG", "MPO"):
        return ["skipped: lossy format, pixel LSBs carry no recoverable payload"]

    hits = []
    for label, out in lsb_variants(img):
        head = out[:512]
        pr = printable_ratio(head)
        for sig, desc in SIGNATURES:
            if sig in out[:8192]:
                hits.append(f"{label}: signature {desc} -> {out[:120]!r}")
        for k in key_shaped(out[:8192]):
            hits.append(f"{label}: {k}")
        if pr > 0.85:
            hits.append(f"{label}: printable={pr:.2f} -> {head[:160]!r}")
    return hits


def palette_check(path):
    hits = []
    try:
        img = Image.open(path)
    except Exception:
        return hits
    if img.mode == "P":
        pal = img.getpalette() or []
        used = len(set(img.getdata()))
        hits.append(f"palette image: {len(pal) // 3} entries, {used} used")
    if "A" in img.getbands():
        alphas = set(img.convert("RGBA").getchannel("A").getdata())
        if len(alphas) > 1:
            hits.append(f"alpha channel is not uniform: {len(alphas)} distinct values")
    return hits


def scan(path):
    data = path.read_bytes()
    print("=" * 72)
    print(f"{path.name}  ({len(data):,} bytes)")
    print("=" * 72)

    any_hit = False
    for label, hits in (("container", container_check(path, data)),
                        ("palette/alpha", palette_check(path)),
                        ("lsb", lsb_check(path))):
        for h in hits:
            any_hit = True
            print(f"  [{label}] {h}")

    for k in key_shaped(data):
        any_hit = True
        print(f"  [raw] {k}")

    # Printable runs inside compressed IDAT are normal and meaningless; only
    # report runs long enough to be deliberate text.
    strs = [s for s in strings_check(data, minlen=16)]
    if strs:
        any_hit = True
        print(f"  [strings] {len(strs)} run(s) of 16+ printable chars:")
        for s in strs[:12]:
            print(f"      {s[:150]!r}")

    if not any_hit:
        print("  nothing: no trailing data, no text/unknown chunks, "
              "no readable LSB plane, no strings")
    print()


def main():
    args = sys.argv[1:]
    if args:
        paths = [Path(a) for a in args]
    else:
        paths = sorted(REPO.glob("*.png")) + sorted(REPO.glob("*.jpg"))
        paths += sorted(CORPUS_IMG.glob("*"))
    for p in paths:
        if p.is_file():
            scan(p)


if __name__ == "__main__":
    main()
