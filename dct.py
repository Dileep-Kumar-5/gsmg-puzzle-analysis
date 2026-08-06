"""DCT-coefficient steganalysis of the Decentraland hint JPEG.

Pixel-domain LSB is meaningless in a JPEG. Real JPEG stego (JSteg, F5, OutGuess,
steghide) hides in the quantised DCT coefficients, which is what this reads.

Tests:
  1. coefficient histogram shape -- clean JPEGs are Laplacian around zero
  2. chi-square pair test (Westfeld-Pfitzmann): JSteg-style LSB embedding
     equalises the pairs (2k, 2k+1); untouched images leave h(2k) >> h(2k+1)
  3. direct LSB extraction from non-zero, non-one AC coefficients, in the scan
     orders the common tools use, checked for readable content
  4. F5 signature: F5 decrements magnitudes, inflating the zero bin relative to
     the +/-1 bins

Run: python dct.py [file.jpg]
"""

import sys
from collections import Counter
from pathlib import Path

import jpeglib
import numpy as np

from stego import SIGNATURES, key_shaped, printable_ratio

DEFAULT = (Path(__file__).with_name("gsmgio-5btc-puzzle")
           / "photo_2020-04-26_09-24-30.jpg")


def coeffs(path):
    d = jpeglib.read_dct(str(path))
    planes = {"Y": d.Y}
    if d.Cb is not None:
        planes["Cb"], planes["Cr"] = d.Cb, d.Cr
    return planes


def ac_values(plane):
    """All AC coefficients (everything but the DC term of each 8x8 block)."""
    blocks = plane.reshape(-1, 64)
    return blocks[:, 1:].ravel()


def histogram_report(name, ac):
    c = Counter(ac.tolist())
    total = len(ac)
    zeros = c.get(0, 0)
    print(f"  {name}: {total:,} AC coeffs, {zeros / total * 100:.1f}% zero")
    row = "     "
    for v in range(-4, 5):
        row += f"{v:>4}:{c.get(v, 0) / total * 100:5.2f}%  "
    print(row)
    # F5 shrinkage indicator.
    ones = c.get(1, 0) + c.get(-1, 0)
    twos = c.get(2, 0) + c.get(-2, 0)
    print(f"     |1|/|2| ratio = {ones / twos:.2f} "
          f"(natural images ~2.0-3.5; F5 pushes this up)")
    return c


def chi_square(c, pairs=32):
    """Westfeld-Pfitzmann. Under LSB embedding the two members of each pair
    (2k, 2k+1) converge to their mean, so observed ~ expected and chi2 collapses.
    A clean image gives a large chi2."""
    obs, exp = [], []
    for k in range(1, pairs + 1):
        n0, n1 = c.get(2 * k, 0), c.get(2 * k + 1, 0)
        if n0 + n1 < 10:
            continue
        obs.append(n0)
        exp.append((n0 + n1) / 2)
    if not obs:
        return None, 0
    chi2 = sum((o - e) ** 2 / e for o, e in zip(obs, exp) if e > 0)
    return chi2, len(obs)


def extract_lsb(planes):
    """JSteg convention: embed in the LSB of AC coefficients, skipping 0 and 1
    because changing those would be visible in the histogram."""
    results = {}
    for pname, plane in planes.items():
        blocks = plane.reshape(-1, 64)
        for order in ("blockwise", "zigzag-column"):
            seq = blocks[:, 1:].ravel() if order == "blockwise" else \
                blocks[:, 1:].T.ravel()
            usable = seq[(seq != 0) & (seq != 1)]
            bits = (usable & 1).astype(np.uint8)
            n = (len(bits) // 8) * 8
            if n == 0:
                continue
            for msb in (True, False):
                b = bits[:n].reshape(-1, 8)
                if not msb:
                    b = b[:, ::-1]
                out = np.packbits(b, axis=1).ravel().tobytes()
                results[f"{pname}/{order}/{'msb' if msb else 'lsb'}"] = out
    return results


def main():
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT
    print(f"{path.name}\n")
    planes = coeffs(path)

    print("1-2. coefficient histograms and F5 indicator")
    print("-" * 72)
    counters = {n: histogram_report(n, ac_values(p)) for n, p in planes.items()}

    print("\n3. chi-square pair test (high = clean, near zero = LSB embedded)")
    print("-" * 72)
    for name, c in counters.items():
        chi2, npairs = chi_square(c)
        if chi2 is None:
            print(f"  {name}: too few coefficients")
            continue
        verdict = "CLEAN" if chi2 > 10 * npairs else "*** SUSPICIOUS ***"
        print(f"  {name}: chi2={chi2:,.0f} over {npairs} pairs  -> {verdict}")

    print("\n4. direct LSB extraction from AC coefficients")
    print("-" * 72)
    any_hit = False
    for label, out in extract_lsb(planes).items():
        pr = printable_ratio(out[:512])
        for sig, desc in SIGNATURES:
            if sig in out[:16384]:
                any_hit = True
                print(f"  {label}: signature {desc} -> {out[:100]!r}")
        for k in key_shaped(out[:16384]):
            any_hit = True
            print(f"  {label}: {k}")
        if pr > 0.85:
            any_hit = True
            print(f"  {label}: printable={pr:.2f} -> {out[:160]!r}")
        else:
            print(f"  {label}: {len(out):,} bytes, printable={pr:.2f} (noise)")
    if not any_hit:
        print("\n  no readable payload in any coefficient LSB stream")


if __name__ == "__main__":
    main()
