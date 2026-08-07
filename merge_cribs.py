"""Combine crib placements that agree, to separate signal from coincidence.

dragcrib.py's control is instructive in both directions: it DOES find the true
word ("PRIVATEKEY" at its real offset 29), and it also emits 31 false placements
alongside it. A single surviving placement is therefore worth almost nothing --
a one-repeat crib constrains too little.

The discriminator is mutual agreement. Two cribs at different offsets each
induce a partial slot->letter mapping. If those mappings agree wherever they
overlap AND stay jointly injective, that is a coincidence of a much higher
order, and the pair covers more slots than either alone.

So: build every pairwise-consistent set greedily, rank by slots covered, and
decode the run under the best combined mapping. Unknown slots print as '.'.

The same procedure runs on the solved phase 3.2.2 first, where the correct
answer is known, so the output can be judged rather than trusted.

Run: python merge_cribs.py
"""

import re

from dbbi import parse_checkerboard
from dragcrib import CRIBS, drag_placements
from vic import VIC_EXPECTED, VIC_INPUT


def compatible(a, b):
    """Two partial mappings agree on overlaps and stay injective together."""
    for slot, ch in b.items():
        if a.get(slot, ch) != ch:
            return False
    merged = dict(a)
    merged.update(b)
    if len(set(merged.values())) != len(merged):
        return False
    return merged


def greedy_sets(placements):
    """Seed on each placement, absorb every compatible one."""
    out = []
    for i, (reps_i, ni, wi, offi, mi) in enumerate(placements):
        cur = dict(mi)
        used = [(wi, offi)]
        for j, (reps_j, nj, wj, offj, mj) in enumerate(placements):
            if i == j or (wj, offj) in used:
                continue
            merged = compatible(cur, mj)
            if merged:
                cur = merged
                used.append((wj, offj))
        out.append((len(cur), len(used), used, cur))
    out.sort(reverse=True, key=lambda r: (r[0], r[1]))
    # de-duplicate identical mappings
    seen, uniq = set(), []
    for cov, nw, used, mapping in out:
        key = tuple(sorted(mapping.items()))
        if key in seen:
            continue
        seen.add(key)
        uniq.append((cov, nw, used, mapping))
    return uniq


def render(tokens, mapping):
    return "".join(mapping.get(t, ".") for t in tokens)


def analyse(tokens, label, truth=None):
    print("=" * 72)
    print(f"{label}: {len(tokens)} tokens, {len(set(tokens))} slots")
    print("=" * 72)
    placements = drag_placements(tokens)
    print(f"  {len(placements)} raw placements")
    sets = greedy_sets(placements)
    print(f"  {len(sets)} distinct consistent sets\n")
    for cov, nw, used, mapping in sets[:6]:
        pct = cov / len(set(tokens)) * 100
        words = ", ".join(f"{w}@{o}" for w, o in used)
        print(f"  {cov}/{len(set(tokens))} slots ({pct:.0f}%) from {nw} crib(s): "
              f"{words}")
        dec = render(tokens, mapping)
        print(f"    {dec}")
        if truth:
            agree = sum(1 for a, b in zip(dec, truth) if a == b)
            print(f"    agreement with true plaintext: {agree}/{len(truth)} "
                  f"({agree / len(truth) * 100:.0f}%)")
        print()


def main():
    ctrl = parse_checkerboard(VIC_INPUT, {"1", "4"})
    analyse(ctrl, "CONTROL phase 3.2.2", truth=VIC_EXPECTED)

    from bigrun import get_runs
    runs = get_runs()
    m = re.search(r"[ab]{40,}", runs[0])
    dbbi = runs[0][:m.start()]
    tokens = parse_checkerboard(
        dbbi.translate(str.maketrans("abcdefghi", "012345678")), {"1", "4"})
    analyse(tokens, "dbbi (escapes 1,4)")


if __name__ == "__main__":
    main()
