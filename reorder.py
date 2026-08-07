"""Is faed an interleaving? Test its ORDER, not its values.

Everything so far transformed faed's values -- symbol->digit mappings, number
bases, container magics -- and all of it says the same thing: uniform, maximum
entropy, no structure. But uniformity is a property of the sequence AS READ. An
interleaving of two streams, or a stream read in the wrong direction, looks
uniform in aggregate while each component may not be.

So this reorders and re-measures. For each reordering the diagnostic is the same
one that worked before: chi-square against uniform, plus whether dropping a
single symbol collapses it to uniform (the signature that first revealed 'g').

Reorderings tried:
  REVERSE     the run backwards
  STRIDE k    every k-th symbol, all k offsets -- separates an interleaving
  COLUMNS w   written in rows of w, read down columns, at every divisor of 570

A component that is structured where the whole is uniform would be a real find.
Every measurement is compared against the same statistic on a shuffled copy,
since slicing a random sequence many ways will always produce some extreme.

Run: python reorder.py
"""

import random
import re
from collections import Counter

from bigrun import get_runs


def chi2(seq):
    c = Counter(seq)
    if len(c) < 2:
        return 0.0, 0
    n = len(seq)
    e = n / len(c)
    return sum((v - e) ** 2 / e for v in c.values()), len(c) - 1


def ioc(seq):
    n = len(seq)
    if n < 2:
        return 0.0
    c = Counter(seq)
    return sum(v * (v - 1) for v in c.values()) / (n * (n - 1))


def best_drop(seq):
    """Lowest chi2 achievable by removing one symbol -- the 'g' signature."""
    best = (1e9, None)
    for s in set(seq):
        rest = [x for x in seq if x != s]
        if len(set(rest)) < 2 or len(rest) < 30:
            continue
        v, df = chi2(rest)
        if v < best[0]:
            best = (v, s)
    return best


def divisors(n, lo=2, hi=60):
    return [d for d in range(lo, hi + 1) if n % d == 0]


def reorderings(seq):
    yield "whole", seq
    yield "reversed", seq[::-1]
    for k in range(2, 16):
        for off in range(k):
            sub = seq[off::k]
            if len(sub) >= 40:
                yield f"stride {k} offset {off}", sub
    for w in divisors(len(seq)):
        rows = [seq[i:i + w] for i in range(0, len(seq), w)]
        cols = "".join("".join(r[c] for r in rows) for c in range(w))
        yield f"columns w={w}", cols


def digraph_ioc(seq):
    """Order-SENSITIVE. Single-symbol chi2 and IoC measure the multiset, so a
    reversal or column-read leaves them identical by construction -- they
    cannot see order at all. Adjacent-pair repetition can."""
    pairs = [seq[i:i + 2] for i in range(len(seq) - 1)]
    n = len(pairs)
    if n < 2:
        return 0.0
    c = Counter(pairs)
    return sum(v * (v - 1) for v in c.values()) / (n * (n - 1))


def repeat_trigrams(seq):
    """Also order-sensitive: how many trigrams occur more than once."""
    c = Counter(seq[i:i + 3] for i in range(len(seq) - 2))
    return sum(1 for v in c.values() if v > 1)


def measure(seq, label):
    v, df = chi2(seq)
    dv, ds = best_drop(seq)
    return (digraph_ioc(seq), repeat_trigrams(seq), v, df, dv, ds,
            len(seq), label)


def sweep(seq, name):
    rows = [measure(s, lab) for lab, s in reorderings(seq)]
    return rows


def main():
    runs = get_runs()
    m = re.search(r"[ab]{40,}", runs[0])
    faed = runs[0][m.end():]

    print(f"faed: {len(faed)} symbols\n")

    real = sweep(faed, "faed")
    sh = list(faed)
    random.Random(20260807).shuffle(sh)
    ctrl = sweep("".join(sh), "shuffled")

    # Rank on the ORDER-sensitive statistic; chi2 is reported but cannot
    # distinguish permutations of the same run.
    real.sort(reverse=True, key=lambda r: r[0])
    ctrl.sort(reverse=True, key=lambda r: r[0])
    ceiling = ctrl[0][0]

    print("=" * 76)
    print(f"{len(real)} reorderings measured | shuffled control ceiling "
          f"digraph-IoC = {ceiling:.5f}")
    print("=" * 76)
    print(f"  {'digIoC':<9} {'rep3':<6} {'chi2':<8} {'n':<5} "
          f"{'drop-1':<12} reordering")
    for dig, rep, v, df, dv, ds, n, lab in real[:12]:
        flag = "  <<< BEATS CONTROL" if dig > ceiling * 1.3 else ""
        drop = f"{dv:.1f} (-{ds})" if ds else "-"
        print(f"  {dig:<9.5f} {rep:<6} {v:<8.1f} {n:<5} {drop:<12} "
              f"{lab}{flag}")

    print()
    print("  control top 3, for scale:")
    for dig, rep, v, df, dv, ds, n, lab in ctrl[:3]:
        print(f"    {dig:<9.5f} {rep:<6} {v:<8.1f} {n:<5} {lab}")

    print()
    print("A genuinely structured component would sit well above the control")
    print("ceiling. Slicing uniform data many ways always yields some maximum.")


if __name__ == "__main__":
    main()
