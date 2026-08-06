"""Exhaust the symbol->digit mapping for dbbi and faed.

The two runs that decode pin the encoding exactly:

    RUN1  63 symbols -> 26 chars      RUN2  29 symbols -> 12 chars
    63/26 = 2.42     29/12 = 2.42     log(10)/log(16) = 2.41

That ratio is just base-10-to-base-16 conversion, and dbbi's 91 symbols do
produce 38 bytes under every mapping tried. So the pipeline
(symbols -> decimal integer -> base 16 -> ASCII) is CORRECT, and the only
unknown left is which digit each of the nine symbols stands for.

That space is finite and small:
    9 symbols -> digits 1..9        9!      =   362,880
    9 symbols -> any 9 of 0..9      10P9    = 3,628,800

This exhausts both. If nothing emerges, the encoding hypothesis for these runs
is dead rather than merely untested -- which is worth knowing either way.

Success needs no fuzzy scoring: RUN1 and RUN2 yield 100% lowercase ASCII, so a
correct mapping should stand out absolutely. Both are re-derived here as a
positive control.

Run: python permute.py
"""

import re
import sys
from itertools import permutations

from bigrun import get_runs

ALPHA = "abcdefghi"


def to_bytes(run, digit_of):
    n = 0
    for c in run:
        n = n * 10 + digit_of[c]
    if n == 0:
        return None
    h = format(n, "x")
    if len(h) % 2:
        h = "0" + h
    return bytes.fromhex(h)


def lower_ratio(b):
    return sum(1 for c in b if 97 <= c <= 122) / len(b) if b else 0.0


def ascii_ratio(b):
    return sum(1 for c in b if 32 <= c < 127) / len(b) if b else 0.0


def control():
    runs = get_runs()
    d = {c: ALPHA.index(c) + 1 for c in ALPHA}
    d["o"] = 0
    for name, r in (("RUN1", runs[1]), ("RUN2", runs[2])):
        b = to_bytes(r, d)
        print(f"  {name}: {len(r)} symbols -> {b!r}  lowercase {lower_ratio(b):.2f}")
        assert lower_ratio(b) == 1.0


def exhaust(name, run, include_zero, best_n=6):
    symbols = sorted(set(run))
    k = len(symbols)
    pool = "0123456789" if include_zero else "123456789"
    total = 1
    for i in range(k):
        total *= len(pool) - i
    print(f"  {name}: {k} distinct symbols, digits from {pool!r} "
          f"-> {total:,} mappings")

    best = []
    seen = 0
    for perm in permutations(pool, k):
        seen += 1
        if seen % 200000 == 0:
            print(f"\r    {seen:,}/{total:,}", end="", file=sys.stderr,
                  flush=True)
        digit_of = dict(zip(symbols, (int(x) for x in perm)))
        b = to_bytes(run, digit_of)
        if not b:
            continue
        lr = lower_ratio(b)
        if len(best) < best_n:
            best.append((lr, ascii_ratio(b), "".join(perm), b))
            best.sort(reverse=True)
        elif lr > best[-1][0]:
            best[-1] = (lr, ascii_ratio(b), "".join(perm), b)
            best.sort(reverse=True)
    print(f"\r    {seen:,}/{total:,} done{' ' * 20}", file=sys.stderr)
    return best


def main():
    print("positive control -- the runs known to decode")
    control()
    print()

    runs = get_runs()
    m = re.search(r"[ab]{40,}", runs[0])
    targets = {"dbbi": runs[0][:m.start()], "faed": runs[0][m.end():]}

    for tname, run in targets.items():
        print("=" * 72)
        print(f"{tname}: {len(run)} symbols -> "
              f"{len(to_bytes(run, {c: ALPHA.index(c) + 1 for c in ALPHA}))} bytes")
        print("=" * 72)
        for include_zero in (False, True):
            best = exhaust(tname, run, include_zero)
            for lr, ar, perm, b in best[:3]:
                flag = "   <<< WORDS" if lr > 0.85 else ""
                print(f"    lowercase={lr:.3f} ascii={ar:.3f} "
                      f"map={perm}{flag}")
                print(f"        {b[:80]!r}")
            print()


if __name__ == "__main__":
    main()
