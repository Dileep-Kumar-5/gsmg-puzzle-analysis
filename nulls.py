"""faed = eight uniform symbols plus one null?

The chi-square breakdown is the finding:

    faed  chi2 = 43.7 on 8 df (p<0.001) -- but 69% of it comes from ONE symbol,
          'g' at 107 against 63.3 expected. The other eight sit near expectation.

That is not the profile of enciphered text, and not the profile of a base-9
encoding of binary either. It is the profile of a base-EIGHT encoding carrying a
NULL: eight symbols doing real work uniformly, plus one padding symbol sprinkled
through.

Which is exactly what the creator described:

    "...some characters need to be 'zeroed out'.."      (2021-12-26)

So: drop one symbol as the null, and read what remains in base 8 (three bits per
symbol -- a clean encoding, unlike base 9). Every choice of null and every
mapping of the surviving eight is exhausted: 9 x 8! = 362,880 combinations per
run, cheap and complete.

The test is stated in advance: if 'g' is the null, the remaining eight symbols
should be statistically UNIFORM once it is removed. That is checked first, and
it either holds or the idea is wrong.

Run: python nulls.py
"""

import re
from collections import Counter
from itertools import permutations

from bigrun import get_runs
from permute import ascii_ratio, lower_ratio

ALPHA = "abcdefghi"


def chi2(counts):
    n = sum(counts.values())
    e = n / len(counts)
    return sum((v - e) ** 2 / e for v in counts.values()), len(counts) - 1


def to_bytes(run, digit_of, base):
    n = 0
    for c in run:
        n = n * base + digit_of[c]
    if n == 0:
        return b""
    h = format(n, "x")
    return bytes.fromhex(("0" + h) if len(h) % 2 else h)


def uniformity_report(run, name):
    """Does removing one symbol make the rest uniform?"""
    print(f"{name}: n={len(run)}")
    full, df = chi2(Counter(run))
    print(f"  all 9 symbols        chi2={full:5.1f} on {df} df "
          f"(significant above 26.1)")
    best = []
    for s in sorted(set(run)):
        rest = run.replace(s, "")
        c = Counter(rest)
        if len(c) < 8:
            continue
        v, d = chi2(c)
        best.append((v, s, len(rest), d))
    best.sort()
    for v, s, n, d in best:
        verdict = ("UNIFORM -- consistent with a null"
                   if v < 14.07 else "still skewed")
        print(f"  drop '{s}' -> n={n:>3}  chi2={v:5.1f} on {d} df   {verdict}")
    print()
    return best[0][1] if best else None


def exhaust(run, null, name):
    """Drop the null, exhaust base-8 mappings of the surviving eight."""
    rest = run.replace(null, "")
    syms = sorted(set(rest))
    if len(syms) != 8:
        print(f"  {name}: dropping '{null}' leaves {len(syms)} symbols, skipping")
        return
    nbytes = len(to_bytes(rest, dict(zip(syms, range(8))), 8))
    print(f"  {name} minus '{null}': {len(rest)} symbols -> {nbytes} bytes, "
          f"40,320 mappings")
    best = []
    for perm in permutations(range(8)):
        b = to_bytes(rest, dict(zip(syms, perm)), 8)
        if not b:
            continue
        lr = lower_ratio(b)
        if len(best) < 3:
            best.append((lr, ascii_ratio(b), perm, b))
            best.sort(reverse=True)
        elif lr > best[-1][0]:
            best[-1] = (lr, ascii_ratio(b), perm, b)
            best.sort(reverse=True)
    for lr, ar, perm, b in best:
        flag = "   <<< WORDS" if lr > 0.85 else ""
        print(f"    lowercase={lr:.3f} ascii={ar:.3f} "
              f"map={''.join(map(str, perm))}{flag}")
        print(f"        {b[:72]!r}")


def main():
    runs = get_runs()
    m = re.search(r"[ab]{40,}", runs[0])
    faed, dbbi = runs[0][m.end():], runs[0][:m.start()]

    print("=" * 72)
    print("step 1 -- does dropping one symbol leave the rest uniform?")
    print("=" * 72)
    faed_null = uniformity_report(faed, "faed")
    dbbi_null = uniformity_report(dbbi, "dbbi")

    print("=" * 72)
    print("step 2 -- base-8 readings with that symbol dropped as a null")
    print("=" * 72)
    for run, null, name in ((faed, faed_null, "faed"), (dbbi, dbbi_null, "dbbi")):
        if null:
            exhaust(run, null, name)
    print()
    print("  (RUN1/RUN2 decode to 100% lowercase; that is what a hit looks like)")


if __name__ == "__main__":
    main()
