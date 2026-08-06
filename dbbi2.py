"""Read dbbi literally as what its label says: a matrix, summed, into a list.

The binary spliced immediately after dbbi decodes to "matrixsumlist". Every
attempt so far has treated that as a password or a key length. The plainest
reading is an instruction:

    arrange as a MATRIX -> SUM it -> that is the LIST

and 91 = 7 x 13 gives exactly two rectangles, with no other factorisation.
Row sums of a 7x13 give 7 values; column sums give 13 -- and 13 is the length
of "matrixsumlist" itself.

Also tested here: dbbi's most frequent symbol as a DELIMITER. 'b' occurs 25
times (27.5%), which splits the run into 26 groups -- and 26 is the alphabet.
That is either the mechanism or a coincidence worth killing.

Everything that produces 32 bytes is thrown at the key oracle, and everything
that produces letters is scored for englishness against a shuffled control.

Run: python dbbi2.py
"""

import hashlib
import random
import re
from collections import Counter

from bigrun import get_runs
from oracle import check
from vic import englishness

ALPHA = "abcdefghi"


def dbbi_run():
    runs = get_runs()
    m = re.search(r"[ab]{40,}", runs[0])
    return runs[0][:m.start()]


def vals(run, base0):
    return [ALPHA.index(c) + (0 if base0 else 1) for c in run]


def a1z26(nums, mod=True):
    out = []
    for v in nums:
        n = v % 26 if mod else v
        if 1 <= n <= 26:
            out.append(chr(ord("A") + n - 1))
        elif n == 0:
            out.append(chr(ord("A") + 25))
        else:
            out.append("?")
    return "".join(out)


def matrix_sums(run, base0):
    """Every rectangle 91 admits, summed both ways, plus diagonals."""
    v = vals(run, base0)
    out = {}
    for ncols in (7, 13):
        nrows = len(v) // ncols
        grid = [v[r * ncols:(r + 1) * ncols] for r in range(nrows)]
        out[f"{nrows}x{ncols} rowsums"] = [sum(r) for r in grid]
        out[f"{nrows}x{ncols} colsums"] = [sum(c) for c in zip(*grid)]
        # Column-major fill is just as plausible as row-major.
        gridT = [v[c * nrows:(c + 1) * nrows] for c in range(ncols)]
        out[f"{nrows}x{ncols} colfill rowsums"] = [sum(r) for r in gridT]
        out[f"{nrows}x{ncols} colfill colsums"] = [sum(c) for c in zip(*gridT)]
    return out


def delimiter_splits(run, base0):
    """Treat each symbol in turn as a separator; summarise the groups."""
    out = {}
    for d in sorted(set(run)):
        groups = run.split(d)
        if not 3 <= len(groups) <= 40:
            continue
        sums = [sum(vals(g, base0)) if g else 0 for g in groups]
        lens = [len(g) for g in groups]
        out[f"split '{d}' ({len(groups)} groups) sums"] = sums
        out[f"split '{d}' ({len(groups)} groups) lens"] = lens
    return out


def report(name, nums, sink):
    s = a1z26(nums)
    sink.append((englishness(s), name, s, nums))


def sweep(run, sink):
    for base0 in (True, False):
        tag = "0..8" if base0 else "1..9"
        for k, nums in matrix_sums(run, base0).items():
            report(f"[{tag}] {k}", nums, sink)
        for k, nums in delimiter_splits(run, base0).items():
            report(f"[{tag}] {k}", nums, sink)


def main():
    run = dbbi_run()
    c = Counter(run)
    print(f"dbbi: {len(run)} symbols")
    print(f"  {run}")
    print(f"  counts: {dict(sorted(c.items()))}")
    print(f"  91 = 7 x 13 (only factorisation)\n")

    real, ctrl = [], []
    sweep(run, real)
    sh = list(run)
    random.Random(41).shuffle(sh)
    sweep("".join(sh), ctrl)

    real.sort(reverse=True, key=lambda r: r[0])
    ctrl.sort(reverse=True, key=lambda r: r[0])

    print("=" * 72)
    print("matrix sums -- the literal reading of the label")
    print("=" * 72)
    for base0 in (True, False):
        tag = "0..8" if base0 else "1..9"
        for k, nums in matrix_sums(run, base0).items():
            print(f"  [{tag}] {k:<26} {nums}")
            print(f"         concat={''.join(map(str, nums))}")
            print(f"         a1z26 ={a1z26(nums)}")
    print()

    print("=" * 72)
    print(f"ranked by englishness ({len(real)} readings) | real English 0.44")
    print("=" * 72)
    for e, name, s, nums in real[:10]:
        print(f"  {e:.3f}  {name}")
        print(f"         {s}")
    print()
    print(f"CONTROL ceiling (shuffled dbbi): {ctrl[0][0]:.3f}  {ctrl[0][1]}")
    print(f"         {ctrl[0][2]}")
    verdict = ("SIGNAL" if real[0][0] > ctrl[0][0] * 1.5 else "NO SEPARATION")
    print(f"\nbest real {real[0][0]:.3f} vs control {ctrl[0][0]:.3f} -> {verdict}")

    print()
    print("=" * 72)
    print("key oracle: every derived quantity, as-is and hashed")
    print("=" * 72)
    tried = 0
    for e, name, s, nums in real:
        cands = [
            "".join(map(str, nums)),
            "-".join(map(str, nums)),
            s,
            s.lower(),
        ]
        for cand in cands:
            tried += 1
            if check(hashlib.sha256(cand.encode()).digest()):
                print(f"  *** PRIZE KEY from sha256({cand!r}) via {name} ***")
                return
    print(f"  {tried} sha256 candidates checked against the prize pubkey: "
          f"no match")


if __name__ == "__main__":
    main()
