"""Render the undecoded runs as bitmaps and test for image-like structure.

Rationale: this creator's signature move is "render data as a picture, read the
picture" -- phase 1 is a bitmap read as bits, and the Decentraland hint is an
audio file whose spectrogram draws hex digits. He says yin-yang is reachable
offline and recognisable on sight ("2 hours max"). A yin-yang is a shape.

So: lay each run out at every width its length admits, binarise it several ways,
and measure whether the result looks drawn rather than random.

Detector -- VERTICAL CONTINUITY. In a drawing, a pixel usually matches the pixel
above it; in noise it does not. For a binary image of density p, random
agreement between adjacent rows is p^2 + (1-p)^2. The excess over that is the
signal, and it is scale-free, so widths and densities can be compared directly.

Every run is measured against a SHUFFLED copy of itself. Shuffling preserves
length and symbol counts and destroys only the arrangement, so any excess that
survives shuffling is an artifact of the metric rather than a picture.

Run: python bitmaps.py
"""

import random
import re

from bigrun import get_runs

ALPHA = "abcdefghi"


def divisors(n, lo=4, hi=200):
    return [d for d in range(lo, min(n, hi) + 1) if n % d == 0]


def binarisers():
    """Ways to turn a..i into one bit."""
    out = {}
    for t in range(1, 9):
        out[f">= {ALPHA[t]}"] = lambda c, t=t: ALPHA.index(c) >= t
    out["in {b,e}"] = lambda c: c in "be"
    out["odd value"] = lambda c: (ALPHA.index(c) + 1) % 2 == 1
    out["prime value"] = lambda c: (ALPHA.index(c) + 1) in (2, 3, 5, 7)
    for s in ALPHA:
        out[f"== {s}"] = lambda c, s=s: c == s
    return out


def vertical_excess(rows):
    """Observed minus expected agreement between vertically adjacent cells."""
    if len(rows) < 2:
        return 0.0
    w = len(rows[0])
    n = sum(len(r) for r in rows)
    ones = sum(sum(r) for r in rows)
    p = ones / n if n else 0
    expected = p * p + (1 - p) * (1 - p)
    agree = tot = 0
    for a, b in zip(rows, rows[1:]):
        for x, y in zip(a, b):
            agree += (x == y)
            tot += 1
    return (agree / tot - expected) if tot else 0.0


def layout(run, width, fn):
    bits = [1 if fn(c) else 0 for c in run]
    rows = [bits[i:i + width] for i in range(0, len(bits), width)]
    return [r for r in rows if len(r) == width]


def art(rows):
    return ["".join("#" if v else "." for v in r) for r in rows]


def sweep(run, name):
    results = []
    for width in divisors(len(run)):
        for bname, fn in binarisers().items():
            rows = layout(run, width, fn)
            if len(rows) < 3:
                continue
            ones = sum(sum(r) for r in rows)
            dens = ones / (len(rows) * width)
            if not 0.15 <= dens <= 0.85:      # all-on/all-off is not a picture
                continue
            results.append((vertical_excess(rows), width, bname, dens, rows))
    results.sort(reverse=True, key=lambda r: r[0])
    return results


def main():
    runs = get_runs()
    m = re.search(r"[ab]{40,}", runs[0])
    targets = {
        "faed": runs[0][m.end():],
        "dbbi": runs[0][:m.start()],
        "RUN0 raw": runs[0].replace("a", "a"),
    }
    # RUN0 raw still contains the spliced binary; drop it for a clean grid.
    targets["RUN0 rejoined"] = runs[0][:m.start()] + runs[0][m.end():]
    del targets["RUN0 raw"]

    for tname, run in targets.items():
        real = sweep(run, tname)
        sh = list(run)
        random.Random(97).shuffle(sh)
        ctrl = sweep("".join(sh), tname + "-shuffled")

        print("=" * 72)
        print(f"{tname}: {len(run)} symbols, widths "
              f"{divisors(len(run))}")
        print("=" * 72)
        if not real:
            print("  no usable layouts\n")
            continue
        best_ctrl = ctrl[0][0] if ctrl else 0.0
        print(f"  {len(real)} layouts measured | control ceiling "
              f"{best_ctrl:+.4f}")
        print(f"  {'excess':<9} {'width':<6} {'density':<8} binarisation")
        for exc, width, bname, dens, rows in real[:6]:
            flag = "   <<< BEATS CONTROL" if exc > best_ctrl * 1.5 else ""
            print(f"  {exc:+.4f}   {width:<6} {dens:.2f}     {bname}{flag}")
        print()

        exc, width, bname, dens, rows = real[0]
        if exc > best_ctrl * 1.5 and len(rows) <= 40:
            print(f"  top layout ({bname}, width {width}):")
            for line in art(rows):
                print("    " + line)
            print()

    print("=" * 72)
    print("A drawn image gives vertical excess well above 0.10.")
    print("Values at or below the shuffled control are noise.")


if __name__ == "__main__":
    main()
