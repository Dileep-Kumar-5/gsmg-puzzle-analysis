"""Test faed for fractionation-plus-transposition (the ADFGVX family).

faed's profile is the giveaway that motivates this: IoC 0.1181 against 0.1111
uniform, no periodicity at any period 1..40, and zero repeated 6-grams. Flat and
structureless is exactly what fractionation PRODUCES -- splitting each letter
into two symbols and then transposing them apart is designed to destroy the
statistics that ordinary ciphers leak.

A 9-symbol alphabet is a natural fit: a 3x3 Polybius square gives every letter a
two-symbol code, and 570/2 = 285 letters, with 285 a divisor of 570.

The attack does not need the alphabet. If the symbols were transposed, then
UNDOING the transposition at the correct width restores adjacency, and pair
statistics snap back:

    fractionated English    ~26 distinct pairs of 81, highly skewed
    transposed (scrambled)  ~all 81 pairs, near-flat

So sweep every width the length admits, undo the rectangle, and measure pair
structure. A width that restores it is the transposition width -- a real
cryptanalytic hit that needs no guessing.

Every measurement is run against a shuffled control, since a sweep over many
widths will always produce some best value.

Run: python fraction.py
"""

import random
import re
from collections import Counter

from bigrun import get_runs


def divisors(n):
    return [d for d in range(2, n) if n % d == 0]


def pairs(seq, offset=0):
    s = seq[offset:]
    return [s[i:i + 2] for i in range(0, len(s) - 1, 2)]


def pair_stats(seq, offset=0):
    ps = pairs(seq, offset)
    if not ps:
        return 0, 0.0
    c = Counter(ps)
    n = len(ps)
    ioc = sum(v * (v - 1) for v in c.values()) / (n * (n - 1)) if n > 1 else 0
    return len(c), ioc


def undo_rect(seq, width):
    """Read the rectangle down its columns -- the keyless transposition."""
    if len(seq) % width:
        return None
    rows = [seq[i:i + width] for i in range(0, len(seq), width)]
    return "".join("".join(r[c] for r in rows) for c in range(width))


def do_rect(seq, width):
    """The inverse direction, in case the run is the transposed side."""
    if len(seq) % width:
        return None
    nrows = len(seq) // width
    cols = [seq[i * nrows:(i + 1) * nrows] for i in range(width)]
    return "".join("".join(c[r] for c in cols) for r in range(nrows))


def sweep(seq, label):
    """Best pair structure over every width and both directions."""
    out = []
    for name, fn in (("undo", undo_rect), ("do", do_rect)):
        for w in divisors(len(seq)):
            t = fn(seq, w)
            if t is None:
                continue
            for off in (0, 1):
                nd, ioc = pair_stats(t, off)
                out.append((ioc, nd, f"{name} w={w} off={off}", t))
    # Untransposed baseline.
    for off in (0, 1):
        nd, ioc = pair_stats(seq, off)
        out.append((ioc, nd, f"none off={off}", seq))
    out.sort(reverse=True, key=lambda r: r[0])
    return out


def main():
    runs = get_runs()
    m = re.search(r"[ab]{40,}", runs[0])
    targets = {"faed": runs[0][m.end():], "dbbi": runs[0][:m.start()]}

    print("reference points for pair statistics over 81 possible pairs")
    print("  fractionated English : few distinct pairs, high pair-IoC")
    print("  scrambled/random     : most of the 81 present, pair-IoC ~ 1/81 "
          f"= {1 / 81:.4f}\n")

    for tname, run in targets.items():
        npairs = len(run) // 2
        print("=" * 72)
        print(f"{tname}: {len(run)} symbols -> {npairs} pairs, "
              f"widths {divisors(len(run))}")
        print("=" * 72)

        real = sweep(run, tname)
        sh = list(run)
        random.Random(1234).shuffle(sh)
        ctrl = sweep("".join(sh), tname + "-shuffled")
        ceiling = ctrl[0][0]

        print(f"  control ceiling (shuffled, same sweep): pair-IoC "
              f"{ceiling:.4f}, {ctrl[0][1]} distinct")
        print(f"  {'pairIoC':<9} {'distinct':<9} layout")
        for ioc, nd, name, t in real[:8]:
            flag = "   <<< BEATS CONTROL" if ioc > ceiling * 1.25 else ""
            print(f"  {ioc:<9.4f} {nd:<9} {name}{flag}")
        print()

        best = real[0]
        if best[0] > ceiling * 1.25:
            c = Counter(pairs(best[3], int(best[2][-1])))
            print(f"  top layout pair frequencies: {c.most_common(12)}")
            print()

    print("=" * 72)
    print("A recovered transposition width would show a sharp drop in distinct")
    print("pairs and a pair-IoC well above the control. Anything within the")
    print("control band is the sweep finding its own maximum in noise.")


if __name__ == "__main__":
    main()
