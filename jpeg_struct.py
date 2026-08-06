"""JPEG structural analysis -- everything you can learn without decoding pixels.

Before reaching for DCT statistics it is worth knowing what produced the file.
Quantisation tables are a fingerprint: a standard-table JPEG straight out of a
known encoder has a very different provenance from one written by a stego tool,
and re-encoding by a chat app destroys any coefficient-domain payload anyway.

Run: python jpeg_struct.py <file.jpg>
"""

import struct
import sys
from pathlib import Path

MARKERS = {
    0xD8: "SOI", 0xD9: "EOI", 0xDA: "SOS", 0xDB: "DQT", 0xC4: "DHT",
    0xDD: "DRI", 0xFE: "COM", 0xC0: "SOF0 (baseline)", 0xC1: "SOF1",
    0xC2: "SOF2 (progressive)", 0xC3: "SOF3",
}
for i in range(16):
    MARKERS.setdefault(0xE0 + i, f"APP{i}")

# Annex K luminance table at quality 50, the reference every encoder scales.
STD_LUMA_Q50 = [
    16, 11, 10, 16, 24, 40, 51, 61, 12, 12, 14, 19, 26, 58, 60, 55,
    14, 13, 16, 24, 40, 57, 69, 56, 14, 17, 22, 29, 51, 87, 80, 62,
    18, 22, 37, 56, 68, 109, 103, 77, 24, 35, 55, 64, 81, 104, 113, 92,
    49, 64, 78, 87, 103, 121, 120, 101, 72, 92, 95, 98, 112, 100, 103, 99,
]


def quality_from(table):
    """Invert the Annex K scaling to recover the encoder's quality setting."""
    ratios = [t / s for t, s in zip(table, STD_LUMA_Q50) if s]
    scale = sum(ratios) / len(ratios)
    q = (100 - scale * 50) if scale > 1 else (50 / scale) if scale else 0
    return max(1, min(100, round(q)))


def walk(data):
    i, out = 2, []
    while i < len(data) - 1:
        if data[i] != 0xFF:
            i += 1
            continue
        m = data[i + 1]
        if m in (0xD8, 0xD9, 0x01) or 0xD0 <= m <= 0xD7:
            out.append((m, i, b""))
            i += 2
            continue
        if i + 4 > len(data):
            break
        (ln,) = struct.unpack(">H", data[i + 2:i + 4])
        out.append((m, i, data[i + 4:i + 2 + ln]))
        if m == 0xDA:      # entropy-coded data follows; jump to EOI
            end = data.find(b"\xff\xd9", i)
            out.append(("SCAN", i + 2 + ln, data[i + 2 + ln:end if end > 0 else len(data)]))
            i = end if end > 0 else len(data)
            continue
        i += 2 + ln
    return out


def main():
    path = Path(sys.argv[1])
    data = path.read_bytes()
    print(f"{path.name}  {len(data):,} bytes\n")

    qtables = []
    for m, off, body in walk(data):
        if m == "SCAN":
            print(f"  @{off:<8} entropy-coded scan, {len(body):,} bytes")
            continue
        name = MARKERS.get(m, f"0x{m:02X}")
        note = ""
        if m == 0xFE:
            note = f"  COMMENT: {body!r}"
        elif m == 0xDB:
            j = 0
            while j < len(body):
                prec, tid = body[j] >> 4, body[j] & 15
                n = 64 * (2 if prec else 1)
                tbl = list(body[j + 1:j + 1 + n])
                qtables.append((tid, tbl))
                note += f"  table {tid}: first8={tbl[:8]}"
                j += 1 + n
        elif m in (0xC0, 0xC1, 0xC2):
            h, w = struct.unpack(">HH", body[1:5])
            note = f"  {w}x{h}, {body[5]} components"
        elif 0xE0 <= m <= 0xEF and body:
            note = f"  {body[:24]!r}"
        print(f"  @{off:<8} {name:<20} len={len(body):<7}{note}")

    print()
    if qtables:
        tid, tbl = qtables[0]
        print(f"luma quantisation table {tid}, estimated quality ~{quality_from(tbl)}")
        print(f"  all-ones table (lossless-ish): {set(tbl) == {1}}")
        print(f"  matches Annex K q50 exactly:   {tbl == STD_LUMA_Q50}")
    eoi = data.rfind(b"\xff\xd9")
    print(f"\ntrailing bytes after EOI: {len(data) - (eoi + 2) if eoi >= 0 else 'no EOI'}")


if __name__ == "__main__":
    main()
