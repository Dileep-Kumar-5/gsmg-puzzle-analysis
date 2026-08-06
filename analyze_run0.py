"""Cryptanalytic measurement of the two undecoded a-i runs.

Guessing ciphers has produced nothing, so measure the ciphertext instead. For
an unknown cipher over a 9-symbol alphabet the diagnostic questions are:

  * Is it monoalphabetic?          -> index of coincidence vs uniform
  * Is it polyalphabetic, period p?-> IoC of each coset when split p ways;
                                      a real period makes cosets jump toward
                                      the monoalphabetic value
  * Are there repeated blocks?     -> Kasiski: repeated n-grams and the GCD
                                      structure of their separations
  * Is it a rectangle?             -> divisors of the length

Reference points for a 9-symbol alphabet:
    uniform random          IoC = 1/9 = 0.1111
    English letter freqs remapped onto 9 symbols ~ 0.13-0.16

Run: python analyze_run0.py
"""

import re
from collections import Counter
from math import gcd

from bigrun import get_runs, rejoin


def ioc(s):
    n = len(s)
    if n < 2:
        return 0.0
    c = Counter(s)
    return sum(v * (v - 1) for v in c.values()) / (n * (n - 1))


def coset_ioc(s, period):
    cs = [s[i::period] for i in range(period)]
    vals = [ioc(c) for c in cs if len(c) > 5]
    return sum(vals) / len(vals) if vals else 0.0


def kasiski(s, n=3, top=12):
    pos = {}
    for i in range(len(s) - n + 1):
        pos.setdefault(s[i:i + n], []).append(i)
    reps = {g: p for g, p in pos.items() if len(p) > 1}
    gaps = []
    for g, p in reps.items():
        for a, b in zip(p, p[1:]):
            gaps.append(b - a)
    return reps, gaps


def divisors(n):
    return [d for d in range(2, n) if n % d == 0]


def report(name, s):
    print("=" * 72)
    print(f"{name}: {len(s)} chars, alphabet {''.join(sorted(set(s)))}")
    print("=" * 72)
    c = Counter(s)
    n = len(s)
    print(f"  frequencies: "
          f"{ {k: round(v / n * 100, 1) for k, v in sorted(c.items())} }")
    base = ioc(s)
    print(f"  IoC = {base:.4f}   (uniform over {len(c)} symbols = "
          f"{1 / len(c):.4f})")
    print(f"  divisors of {len(s)}: {divisors(len(s)) or 'PRIME'}")

    print("\n  periodicity -- coset IoC by assumed period")
    best = []
    for p in range(1, 41):
        v = coset_ioc(s, p)
        best.append((v, p))
    for v, p in sorted(best, reverse=True)[:8]:
        marker = "  <<<" if v > base * 1.25 else ""
        print(f"    period {p:>3}: coset IoC {v:.4f}{marker}")

    reps, gaps = kasiski(s, 3)
    print(f"\n  Kasiski: {len(reps)} repeated trigrams, {len(gaps)} gaps")
    if gaps:
        g = 0
        for x in gaps:
            g = gcd(g, x)
        print(f"    gcd of all gaps = {g}")
        common = Counter(gaps).most_common(6)
        print(f"    most common gaps = {common}")
    reps4, _ = kasiski(s, 4)
    print(f"    repeated 4-grams: {len(reps4)}")
    long_reps = {g: p for g, p in kasiski(s, 6)[0].items()}
    print(f"    repeated 6-grams: {len(long_reps)} "
          f"{list(long_reps)[:4] if long_reps else ''}")

    # A 9-symbol run that is really 8 symbols + a missing one is worth knowing.
    print(f"\n  symbol count: {len(c)} distinct")
    print()


def main():
    runs = get_runs()
    m = re.search(r"[ab]{40,}", runs[0])
    dbbi, faed = runs[0][:m.start()], runs[0][m.end():]
    joined, _ = rejoin(runs[0])

    report("dbbi (before the matrixsumlist splice)", dbbi)
    report("faed (after the splice)", faed)
    report("RUN0 rejoined", joined)

    print("=" * 72)
    print("controls: runs whose plaintext is known")
    print("=" * 72)
    for name, r in (("RUN1 -> lastwordsbeforearchichoice", runs[1]),
                    ("RUN2 -> thispassword", runs[2])):
        print(f"  {name}: len={len(r)} IoC={ioc(r):.4f} "
              f"alphabet={''.join(sorted(set(r)))}")


if __name__ == "__main__":
    main()
