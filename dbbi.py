"""Treat dbbi as a straddling checkerboard with unknown alphabet.

Evidence for the structure (from analyze_run0.py):
  * dbbi IoC = 0.1509, far above uniform 0.1111 -- not random
  * b = 27.5%, e = 19.8%; every other symbol is 3-11%
  * under a=0..i=8, b and e ARE digits 1 and 4 -- the exact escape digits of
    the solved phase 3.2.2 checkerboard

Escape digits dominate a checkerboard digit stream because they prefix 20 of
the 28 slots, so two symbols carrying ~47% of the text is the signature.

If the layout is a checkerboard but the ALPHABET is unknown, then parsing the
digits into slot indices reduces the problem to a simple substitution over at
most 28 symbols -- which frequency analysis and hill climbing can attack.

This script parses, then measures whether the slot distribution looks like a
natural language at all, before any alphabet is guessed.

Run: python dbbi.py
"""

import re
from collections import Counter

from bigrun import get_runs, rejoin

# English letter frequencies, descending, for shape comparison.
ENGLISH = [12.7, 9.1, 8.2, 7.5, 7.0, 6.7, 6.3, 6.1, 6.0, 4.3, 4.0, 2.8, 2.8,
           2.4, 2.4, 2.2, 2.0, 2.0, 1.9, 1.5, 1.0, 0.8, 0.2, 0.2, 0.1, 0.1]


def parse_checkerboard(digits, escapes):
    """Digits -> slot tokens. Escape digits consume the following digit."""
    out, i = [], 0
    while i < len(digits):
        c = digits[i]
        if c in escapes:
            if i + 1 >= len(digits):
                out.append(c + "_")
                break
            out.append(digits[i:i + 2])
            i += 2
        else:
            out.append(c)
            i += 1
    return out


def shape_distance(freqs):
    """How far the observed frequency profile is from English's shape."""
    obs = sorted(freqs, reverse=True)
    n = min(len(obs), len(ENGLISH))
    return sum(abs(obs[i] - ENGLISH[i]) for i in range(n)) / n


def try_escapes(run, mapping_name, table):
    digits = run.translate(table)
    results = []
    for e1 in range(10):
        for e2 in range(e1 + 1, 10):
            esc = {str(e1), str(e2)}
            if not esc <= set(digits):
                continue
            toks = parse_checkerboard(digits, esc)
            c = Counter(toks)
            # A valid checkerboard has at most 8 single + 20 double = 28 slots.
            if len(c) > 28:
                continue
            n = len(toks)
            freqs = [v / n * 100 for v in c.values()]
            results.append((shape_distance(freqs), (e1, e2), len(c), n,
                            mapping_name, c))
    return results


def main():
    runs = get_runs()
    m = re.search(r"[ab]{40,}", runs[0])
    dbbi, faed = runs[0][:m.start()], runs[0][m.end():]

    maps = {
        "a=0..i=8": str.maketrans("abcdefghi", "012345678"),
        "a=1..i=9": str.maketrans("abcdefghi", "123456789"),
    }

    for tname, run in (("dbbi", dbbi), ("faed", faed)):
        print("=" * 72)
        print(f"{tname}: {len(run)} symbols")
        print("=" * 72)
        allres = []
        for mname, tbl in maps.items():
            allres += try_escapes(run, mname, tbl)
        allres.sort(key=lambda r: r[0])
        print(f"  {len(allres)} escape-pair/mapping combinations give a legal "
              f"checkerboard (<=28 slots)\n")
        print(f"  {'esc':<8} {'map':<10} {'slots':<6} {'tokens':<7} "
              f"{'shape-dist':<11} top slots")
        for dist, esc, nslots, ntok, mname, c in allres[:8]:
            top = ", ".join(f"{k}:{v}" for k, v in c.most_common(5))
            print(f"  {str(esc):<8} {mname:<10} {nslots:<6} {ntok:<7} "
                  f"{dist:<11.2f} {top}")
        print()

        if allres:
            dist, esc, nslots, ntok, mname, c = allres[0]
            print(f"  best-shaped parse: escapes {esc} under {mname}")
            print(f"    {nslots} distinct slots over {ntok} tokens")
            n = ntok
            prof = [round(v / n * 100, 1) for _, v in c.most_common()]
            print(f"    observed profile: {prof}")
            print(f"    english profile : {ENGLISH[:len(prof)]}")
            print(f"    shape distance  : {dist:.2f} "
                  f"(0 = identical shape to English)")
        print()

    print("=" * 72)
    print("control: the SOLVED phase 3.2.2 stream through the same measurement")
    print("=" * 72)
    from vic import VIC_INPUT
    toks = parse_checkerboard(VIC_INPUT, {"1", "4"})
    c = Counter(toks)
    n = len(toks)
    prof = [v / n * 100 for v in c.values()]
    print(f"  {len(c)} slots over {n} tokens, shape distance "
          f"{shape_distance(prof):.2f}")
    print(f"  observed profile: {[round(v / n * 100, 1) for _, v in c.most_common()]}")


if __name__ == "__main__":
    main()
