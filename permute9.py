"""Exhaust base-9 symbol->digit mappings for dbbi and faed.

permute.py exhausted base 10. But RUN1/RUN2 are base 10 only because they carry
'o' = 0, giving ten symbols. dbbi and faed have exactly NINE distinct symbols,
so base 9 is the more natural encoding for them -- and it was the one gap left
in the "encoding is right, mapping is wrong" argument.

9 symbols -> the 9 digits of base 9 is 9! = 362,880 mappings per run. Exhausting
it closes the question completely: together with permute.py, no positional
number-base reading of these runs produces ASCII text under ANY assignment.

Run: python permute9.py
"""

import re
from itertools import permutations

from bigrun import get_runs
from permute import ascii_ratio, lower_ratio


def to_bytes_base(run, digit_of, base):
    n = 0
    for c in run:
        n = n * base + digit_of[c]
    if n == 0:
        return None
    h = format(n, "x")
    return bytes.fromhex(("0" + h) if len(h) % 2 else h)


def main():
    runs = get_runs()
    m = re.search(r"[ab]{40,}", runs[0])
    targets = {"dbbi": runs[0][:m.start()], "faed": runs[0][m.end():]}

    for tname, run in targets.items():
        syms = sorted(set(run))
        ident = dict(zip(syms, range(9)))
        nbytes = len(to_bytes_base(run, ident, 9))
        print(f"{tname}: {len(run)} symbols -> {nbytes} bytes, "
              f"362,880 base-9 mappings")

        best = []
        for perm in permutations(range(9), len(syms)):
            b = to_bytes_base(run, dict(zip(syms, perm)), 9)
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
            mapping = "".join(map(str, perm))
            flag = "   <<< WORDS" if lr > 0.85 else ""
            print(f"  lowercase={lr:.3f} ascii={ar:.3f} map={mapping}{flag}")
            print(f"      {b[:70]!r}")
        print()


if __name__ == "__main__":
    main()
