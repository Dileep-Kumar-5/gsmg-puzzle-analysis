"""Is dbbi the pairwise sum list of the 14x14 puzzle matrix?

The arithmetic that motivates this:

    len(dbbi) = 91        C(14,2) = 14*13/2 = 91

91 is exactly the number of unordered pairs of the 14 rows -- or of the 14
columns -- of the phase-1 matrix. And the binary spliced immediately after dbbi
decodes to "matrixsumlist": a list, over a matrix, of sums. Under that reading
dbbi is the upper triangle of a pairwise relation matrix, read in the standard
lexicographic order (0,1),(0,2),...,(0,13),(1,2),...

Every pairwise combiner that yields small integers is tried, for rows and for
columns, and compared to dbbi two ways:

  DISTRIBUTION  does the multiset of 91 values match dbbi's symbol counts?
  SEQUENCE      does the ordered list match dbbi position by position, under
                some monotone symbol->value assignment?

Distribution is the weaker test but survives any relabelling; sequence is
decisive. Both are reported so a partial match is not mistaken for a hit.

Run: python pairsum.py
"""

import re
from collections import Counter
from itertools import combinations

from bigrun import get_runs
from pipeline import parse_matrix

ALPHA = "abcdefghi"


def dbbi_run():
    runs = get_runs()
    m = re.search(r"[ab]{40,}", runs[0])
    return runs[0][:m.start()]


def combiners():
    """Pairwise operations on two 14-bit rows that produce a small integer."""
    return {
        "AND popcount": lambda a, b: sum(x & y for x, y in zip(a, b)),
        "OR popcount": lambda a, b: sum(x | y for x, y in zip(a, b)),
        "XOR popcount (Hamming)": lambda a, b: sum(x ^ y for x, y in zip(a, b)),
        "XNOR popcount (agree)": lambda a, b: sum(1 - (x ^ y) for x, y in zip(a, b)),
        "AND-NOT popcount": lambda a, b: sum(x & (1 - y) for x, y in zip(a, b)),
        "sum of both, mod 9": lambda a, b: (sum(a) + sum(b)) % 9,
        "sum of both, mod 10": lambda a, b: (sum(a) + sum(b)) % 10,
        "abs diff of sums": lambda a, b: abs(sum(a) - sum(b)),
        "dot product mod 9": lambda a, b: sum(x * y for x, y in zip(a, b)) % 9,
    }


def pair_list(vectors, fn):
    return [fn(vectors[i], vectors[j])
            for i, j in combinations(range(len(vectors)), 2)]


def dist_match(values, target_counts):
    """Compare sorted multisets, ignoring what the symbols are called."""
    obs = sorted(Counter(values).values(), reverse=True)
    exp = sorted(target_counts.values(), reverse=True)
    if len(obs) != len(exp):
        return 0.0
    total = sum(exp)
    return 1.0 - sum(abs(o - e) for o, e in zip(obs, exp)) / (2 * total)


def seq_match(values, run):
    """Best position-by-position agreement under a value->symbol map derived
    from rank order (the only relabelling a 'sum list' could plausibly use)."""
    vals_rank = {v: i for i, v in enumerate(sorted(set(values)))}
    syms_rank = {s: i for i, s in enumerate(sorted(set(run)))}
    if len(vals_rank) != len(syms_rank):
        return 0.0, None
    inv = {i: s for s, i in syms_rank.items()}
    mapped = "".join(inv[vals_rank[v]] for v in values)
    hits = sum(1 for a, b in zip(mapped, run) if a == b)
    return hits / len(run), mapped


def main():
    run = dbbi_run()
    counts = Counter(run)
    m = parse_matrix()
    rows = m
    cols = [list(c) for c in zip(*m)]

    print(f"dbbi: {len(run)} symbols")
    print(f"  counts: {dict(sorted(counts.items()))}")
    print(f"  C(14,2) = {14 * 13 // 2}   len(dbbi) = {len(run)}   "
          f"match: {14 * 13 // 2 == len(run)}\n")

    results = []
    for vname, vectors in (("rows", rows), ("cols", cols)):
        for cname, fn in combiners().items():
            vals = pair_list(vectors, fn)
            d = dist_match(vals, counts)
            s, mapped = seq_match(vals, run)
            results.append((s, d, f"{vname} | {cname}", vals, mapped))

    results.sort(reverse=True, key=lambda r: (r[0], r[1]))
    print("=" * 72)
    print("ranked by sequence agreement (1.00 = exact match)")
    print("=" * 72)
    print(f"  {'seq':<7} {'dist':<7} operation")
    for s, d, name, vals, mapped in results:
        flag = "   <<< EXACT" if s > 0.95 else ("  <<<" if s > 0.5 else "")
        print(f"  {s:<7.3f} {d:<7.3f} {name}{flag}")

    best = results[0]
    print()
    print("=" * 72)
    print(f"best: {best[2]}")
    print("=" * 72)
    print(f"  values : {best[3][:40]}{' ...' if len(best[3]) > 40 else ''}")
    print(f"  range  : {min(best[3])}..{max(best[3])}, "
          f"{len(set(best[3]))} distinct")
    print(f"  dbbi   : {run[:40]} ...")
    if best[4]:
        print(f"  mapped : {best[4][:40]} ...")
    print(f"  counts : {dict(sorted(Counter(best[3]).items()))}")
    print(f"  dbbi   : {dict(sorted(counts.items()))}")

    print()
    print("=" * 72)
    print("distribution-only ranking (survives any relabelling)")
    print("=" * 72)
    for s, d, name, vals, mapped in sorted(results, reverse=True,
                                           key=lambda r: r[1])[:5]:
        print(f"  dist={d:.3f} seq={s:.3f}  {name}  "
              f"range {min(vals)}..{max(vals)}, {len(set(vals))} distinct")


if __name__ == "__main__":
    main()
