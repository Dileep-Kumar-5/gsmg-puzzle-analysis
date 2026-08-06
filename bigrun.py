"""Attack the large undecoded a-i run in the SalPhaseIon textarea.

Structure of the first textarea, as the README half-describes it:

    RUN0  z  RUN1  z  RUN2  z  "shabef our first hint is your last command"

RUN1 and RUN2 decode (a..i=1..9, o=0, decimal -> base 16 -> ASCII) to
"lastwordsbeforearchichoice" and "thispassword". RUN0 is 765 characters and
nobody has decoded it.

Two facts shape the attack:

  * RUN0 contains a 104-char pure-{a,b} stretch that decodes to "matrixsumlist".
    Elsewhere on this page the same trick is used on the base64 blob: a binary
    run is SPLICED INTO the middle and the two halves must be rejoined. So the
    91-char and 570-char pieces around it are almost certainly one 661-char run,
    not two.

  * RUN0's alphabet is exactly {a..i} -- NO 'o'. RUN1 and RUN2 both contain 'o'
    and need it, because o=0. A 661-symbol run over nine symbols with no zero is
    not a decimal number; it is base 9, or symbol pairs into a 9x9 grid.

Run: python bigrun.py
"""

import re
from collections import Counter
from itertools import permutations
from pathlib import Path

from salpha import abba_to_ascii, first_textarea, letters_only, printable

ALPHA = "abcdefghi"


def get_runs():
    seq = letters_only(first_textarea())
    payload = seq.split("shabef")[0]
    return payload.split("z")


def rejoin(run):
    """Drop the spliced binary stretch and glue the halves back together."""
    m = re.search(r"[ab]{40,}", run)
    if not m:
        return run, None
    return run[:m.start()] + run[m.end():], run[m.start():m.end()]


def from_base(seq, base, offset):
    """Interpret the run as a big integer in the given base, then as bytes."""
    n = 0
    for ch in seq:
        d = ALPHA.index(ch) + offset
        if d >= base:
            raise ValueError(f"digit {d} out of range for base {base}")
        n = n * base + d
    out = n.to_bytes((n.bit_length() + 7) // 8, "big")
    return out


def report(label, data):
    pr = printable(data)
    flag = "   <<< READABLE" if pr > 0.85 else ""
    print(f"  {pr:.2f}  {len(data):>4}b  {label}{flag}")
    if pr > 0.60:
        print(f"          {data[:180]!r}")
    return pr


def pair_grid(seq):
    """Digit pairs into a 9x9 Polybius-style grid. 661 is odd, so try both
    alignments."""
    out = []
    for skip in (0, 1):
        s = seq[skip:]
        pairs = [(ALPHA.index(s[i]), ALPHA.index(s[i + 1]))
                 for i in range(0, len(s) - 1, 2)]
        idx = [r * 9 + c for r, c in pairs]
        out.append((skip, idx))
    return out


def main():
    runs = get_runs()
    run0 = runs[0]
    joined, binary = rejoin(run0)

    print(f"RUN0 raw      : {len(run0)} chars")
    print(f"  spliced binary: {len(binary)} chars -> {abba_to_ascii(binary)!r}")
    print(f"  rejoined      : {len(joined)} chars")
    print(f"  alphabet      : {''.join(sorted(set(joined)))}")
    print(f"  counts        : {dict(sorted(Counter(joined).items()))}")
    print(f"  contains 'o'  : {'o' in joined}  (RUN1/RUN2 need o=0; this run has none)")
    print()

    print("numeric readings of the rejoined 661-char run")
    print("-" * 72)
    for base, offset, label in [
        (10, 1, "a..i = 1..9, base 10 (the README's transform)"),
        (10, 0, "a..i = 0..8, base 10"),
        (9, 0, "a..i = 0..8, BASE 9"),
        (9, 1, "a..i = 1..9, base 9 (a=1 means no true zero digit)"),
    ]:
        try:
            report(label, from_base(joined, base, offset))
        except Exception as e:
            print(f"  ----  ----  {label}: {e}")

    # Reversed, in case the run reads the other way.
    print()
    print("same, reversed")
    print("-" * 72)
    for base, offset, label in [(10, 1, "base 10, a=1"), (9, 0, "BASE 9, a=0")]:
        try:
            report(label, from_base(joined[::-1], base, offset))
        except Exception as e:
            print(f"  ----  ----  {label}: {e}")

    print()
    print("9x9 grid readings (digit pairs -> index 0..80)")
    print("-" * 72)
    charsets = {
        "A-Z0-9.?!/ +*#": "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.?!/ +*#-=:;,'\"()[]{}<>@$%^&_|~`\\",
        "a-z0-9 ...": "abcdefghijklmnopqrstuvwxyz0123456789 .,?!/-+*#:;'\"()[]{}<>@$%^&_|~`\\",
    }
    for skip, idx in pair_grid(joined):
        print(f"  alignment skip={skip}, {len(idx)} pairs, "
              f"index range {min(idx)}..{max(idx)}, distinct {len(set(idx))}")
        for name, cs in charsets.items():
            if max(idx) < len(cs):
                s = "".join(cs[i] for i in idx)
                print(f"    {name}: {s[:120]!r}")

    print()
    print("single-symbol substitution sanity check")
    print("-" * 72)
    print(f"  9 distinct symbols over {len(joined)} positions -> index of "
          f"coincidence {ic(joined):.4f}")
    print("  (uniform random over 9 symbols = 0.1111; English letters = 0.0667)")


def ic(s):
    n = len(s)
    c = Counter(s)
    return sum(v * (v - 1) for v in c.values()) / (n * (n - 1))


if __name__ == "__main__":
    main()
