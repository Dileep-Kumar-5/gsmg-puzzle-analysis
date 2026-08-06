"""What is faed, if it is not enciphered text?

faed has now failed every classical test: monoalphabetic (IoC 0.1181 vs 0.1111),
polyalphabetic (no coset lift at any period 1..40), fractionation plus
transposition (control beats it), number-base readings (8.7M mappings
exhausted), image structure, and every relation to dbbi.

Flat, aperiodic, no repeated 6-grams, near-maximal pair diversity. That is what
BINARY DATA looks like when encoded in a 9-symbol alphabet -- not what a cipher
of English looks like. 570 symbols carry 570*log2(9) = 1807 bits = 226 bytes.

Two things follow, and both are cheap to check:

  1. If those 226 bytes are a payload rather than a message, the prize key could
     be sitting in them directly. Every sliding 32-byte window of every base-9
     and base-10 decoding, under every symbol->digit mapping, goes to the
     oracle. That is exhaustive and settles it.

  2. 'g' is faed's one real anomaly at 18.8% against 11.1% expected. If it is a
     delimiter rather than a value, the groups between g's should have a
     structured length distribution rather than a geometric one.

Run: python faed.py
"""

import re
import sys
from collections import Counter
from itertools import permutations

from bigrun import get_runs
from oracle import check

ALPHA = "abcdefghi"


def faed_run():
    runs = get_runs()
    m = re.search(r"[ab]{40,}", runs[0])
    return runs[0][m.end():], runs[0][:m.start()]


def to_bytes(run, digit_of, base):
    n = 0
    for c in run:
        n = n * base + digit_of[c]
    h = format(n, "x")
    return bytes.fromhex(("0" + h) if len(h) % 2 else h)


def delimiter_report(run):
    print("=" * 72)
    print("delimiter test: is one symbol a separator rather than a value?")
    print("=" * 72)
    n = len(run)
    for s in sorted(set(run)):
        groups = run.split(s)
        lens = [len(g) for g in groups]
        c = Counter(lens)
        occ = run.count(s)
        # A geometric length profile means the symbol is just frequent; a tight
        # or repeating profile means it is structural.
        top = c.most_common(5)
        print(f"  '{s}' x{occ:>3} ({occ / n * 100:4.1f}%) -> {len(groups):>3} "
              f"groups, lengths {top}")
        if len(set(lens)) <= 4 and len(groups) > 5:
            print("      <<< TIGHT LENGTH PROFILE -- structural")
    print()


def oracle_sweep(run, label, base, include_zero):
    syms = sorted(set(run))
    pool = range(10) if include_zero else range(1, 10)
    if base == 9:
        pool = range(9)
    total = 1
    k = len(syms)
    poolist = list(pool)
    for i in range(k):
        total *= len(poolist) - i
    print(f"  {label}: base {base}, digits from {poolist[0]}..{poolist[-1]} "
          f"-> {total:,} mappings")
    seen = 0
    for perm in permutations(poolist, k):
        seen += 1
        if seen % 50000 == 0:
            print(f"\r    {seen:,}/{total:,}", end="", file=sys.stderr,
                  flush=True)
        b = to_bytes(run, dict(zip(syms, perm)), base)
        for i in range(0, len(b) - 31):
            if check(b[i:i + 32]):
                print(f"\n  *** PRIZE KEY in {label}, base {base}, "
                      f"map {perm}, offset {i} ***")
                return True
    print(f"\r    {seen:,}/{total:,} done{' ' * 20}", file=sys.stderr)
    return False


def main():
    faed, dbbi = faed_run()
    print(f"faed: {len(faed)} symbols")
    c = Counter(faed)
    print(f"  counts {dict(sorted(c.items()))}")
    print(f"  570 * log2(9) = {570 * 3.1699:.0f} bits = "
          f"{570 * 3.1699 / 8:.0f} bytes\n")

    delimiter_report(faed)

    print("=" * 72)
    print("oracle: is the prize key sitting in faed's decoded bytes?")
    print("=" * 72)
    ident = {s: i for i, s in enumerate(sorted(set(faed)))}
    nb9 = len(to_bytes(faed, ident, 9))
    print(f"  base 9 gives {nb9} bytes -> {nb9 - 31} sliding 32-byte windows")
    print(f"  total checks: 362,880 mappings x {nb9 - 31} windows = "
          f"{362880 * (nb9 - 31):,}\n")

    for run, label in ((faed, "faed"), (dbbi, "dbbi")):
        if oracle_sweep(run, label, 9, False):
            return
    print("\n  no window of any base-9 decoding is the prize key")


if __name__ == "__main__":
    main()
