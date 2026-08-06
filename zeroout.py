"""Which symbol is the zero?

The two runs that decode (RUN1 -> lastwordsbeforearchichoice, RUN2 ->
thispassword) do so under a..i = 1..9 with o = 0, read as one decimal integer,
restated base 16, then ASCII. dbbi and faed contain no 'o' at all -- they are
the only runs missing the zero symbol.

Creator, 2021-12-26:
    "...some characters need to be 'zeroed out'.."

Read literally, that says a symbol in these runs stands in for zero. This tries
every assignment: each single symbol as the zero, then every pair, under both
"keep the other values" and "re-rank the survivors" conventions.

Success is unambiguous and needs no fuzzy scoring -- RUN1 and RUN2 produce
clean lowercase ASCII words, so a correct assignment should too. Both known
runs are decoded here first as a positive control on the whole procedure.

Run: python zeroout.py
"""

import itertools
import re
from pathlib import Path

from bigrun import get_runs

ALPHA = "abcdefghi"


def to_ascii(digits):
    n = 0
    for d in digits:
        n = n * 10 + d
    if n == 0:
        return None
    h = format(n, "x")
    try:
        return bytes.fromhex(h.zfill(len(h) + len(h) % 2))
    except ValueError:
        return None


def score(b):
    """Fraction that is lowercase ascii letters -- what a correct decode of
    RUN1/RUN2 scores (1.00)."""
    if not b:
        return 0.0
    return sum(1 for c in b if 97 <= c <= 122) / len(b)


def printable(b):
    return sum(1 for c in b if 32 <= c < 127) / len(b) if b else 0.0


def assignments(symbols):
    """(label, {symbol: digit}) over every way to pick the zero symbol(s)."""
    present = sorted(set(symbols))
    for k in (1, 2):
        for zeros in itertools.combinations(present, k):
            rest = [s for s in present if s not in zeros]
            # keep: survivors retain their a=1..i=9 value
            keep = {s: ALPHA.index(s) + 1 for s in rest}
            keep.update({z: 0 for z in zeros})
            yield f"zero={''.join(zeros)} keep-values", keep
            # rank: survivors are renumbered 1..n in alphabet order
            rank = {s: i + 1 for i, s in enumerate(rest)}
            rank.update({z: 0 for z in zeros})
            yield f"zero={''.join(zeros)} re-ranked", rank


def decode(run, table):
    try:
        return to_ascii([table[c] for c in run])
    except KeyError:
        return None


def control():
    """RUN1 and RUN2 must decode under the known mapping, or the procedure is
    broken and nothing below means anything."""
    runs = get_runs()
    tbl = {c: ALPHA.index(c) + 1 for c in ALPHA}
    tbl["o"] = 0
    for name, r in (("RUN1", runs[1]), ("RUN2", runs[2])):
        out = decode(r, tbl)
        print(f"  {name}: {out!r}  lowercase-ratio {score(out):.2f}")
        assert out and score(out) == 1.0, "positive control failed"


def main():
    print("positive control -- the runs that are known to decode")
    control()
    print()

    runs = get_runs()
    m = re.search(r"[ab]{40,}", runs[0])
    targets = {"dbbi": runs[0][:m.start()], "faed": runs[0][m.end():]}

    for tname, run in targets.items():
        print("=" * 72)
        print(f"{tname}: {len(run)} symbols, alphabet "
              f"{''.join(sorted(set(run)))}")
        print("=" * 72)
        results = []
        for label, table in assignments(run):
            out = decode(run, table)
            if out:
                results.append((score(out), printable(out), label, out))
        results.sort(reverse=True)
        print(f"  {len(results)} assignments tried "
              f"(a correct one scores 1.00 like the control)\n")
        for sc, pr, label, out in results[:8]:
            flag = "   <<< WORDS" if sc > 0.85 else ""
            print(f"  lowercase={sc:.2f} printable={pr:.2f}  {label}{flag}")
            print(f"      {out[:96]!r}")
        print()

    print("=" * 72)
    print("also: does any assignment make the run a valid hex string directly?")
    print("=" * 72)
    for tname, run in targets.items():
        hits = []
        for label, table in assignments(run):
            s = "".join(str(table[c]) for c in run)
            if len(s) % 2 == 0:
                try:
                    b = bytes.fromhex(s)
                except ValueError:
                    continue
                if printable(b) > 0.9:
                    hits.append((label, b))
        print(f"  {tname}: {len(hits)} assignments give printable hex")
        for label, b in hits[:3]:
            print(f"    {label}: {b[:80]!r}")


if __name__ == "__main__":
    main()
