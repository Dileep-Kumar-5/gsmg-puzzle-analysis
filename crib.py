"""Known-plaintext attack on dbbi's checkerboard, instead of statistics.

Hill-climbing fails on dbbi because 63 tokens is far too short -- a shuffled
control out-scores the real run (solve_sub.py). But a substitution does not have
to be recovered statistically if the plaintext can be GUESSED, and this puzzle
reuses its own vocabulary constantly.

The test is a consistency check, not a scoring heuristic:

    a checkerboard maps each slot to exactly one letter, and each letter to
    exactly one slot

So for a candidate plaintext P, zip it against the parsed tokens. Any slot that
would need two different letters, or any letter needing two different slots,
kills the candidate outright. A wrong guess dies on the first collision;
only a correct one survives all 63 positions.

That makes the filter enormously selective, and it needs no scoring function
that a control can fool. Two necessary conditions are checked first because they
are free:

    len(P) == number of tokens
    number of distinct letters in P == number of distinct slots

Candidates are every window of the puzzle's own plaintexts, plus token
concatenations. Every escape pair is tried, not just (1,4).

Run: python crib.py
"""

import re
from itertools import combinations
from pathlib import Path

from bigrun import get_runs
from dbbi import parse_checkerboard
from pipeline import README
from pipeline import run as pipeline_run

CORPUS = Path(__file__).with_name("corpus")

TOKENS = ["matrixsumlist", "enter", "lastwordsbeforearchichoice",
          "thispassword", "yourlastcommand", "secondanswer", "causality",
          "thematrixhasyou", "theseedisplanted", "hashthetext", "yinyang",
          "yellowblueprimes", "salphaseion", "cosmicduality"]


def sources():
    r = pipeline_run()
    out = {
        "architect": r["phase3.2.1_beaufort"],
        "vic": r["phase3.2.2_vic"],
        "phase3.2": r["phase3.2_plaintext"],
        "README": README,
    }
    for f in sorted(CORPUS.glob("blob_*.txt")):
        out[f.stem] = f.read_bytes().decode("cp437", "replace")
    return out


def letters_only(text):
    return re.sub(r"[^A-Za-z]", "", text).upper()


def candidates(length):
    """Every window of that exact length, plus token concatenations."""
    seen = set()
    for name, text in sources().items():
        s = letters_only(text)
        for i in range(len(s) - length + 1):
            w = s[i:i + length]
            if w not in seen:
                seen.add(w)
                yield w, f"{name}@{i}"
    # Concatenations of the puzzle's own tokens that hit the length exactly.
    for n in (1, 2, 3, 4):
        for combo in combinations(TOKENS, n):
            for joined in ("".join(combo), "".join(reversed(combo))):
                s = letters_only(joined)
                if len(s) == length and s not in seen:
                    seen.add(s)
                    yield s, f"tokens:{'+'.join(combo)}"


def consistent(tokens, plain):
    """Bijective slot<->letter, or None on the first collision."""
    s2l, l2s = {}, {}
    for slot, ch in zip(tokens, plain):
        if s2l.setdefault(slot, ch) != ch:
            return None
        if l2s.setdefault(ch, slot) != slot:
            return None
    return s2l


def main():
    runs = get_runs()
    m = re.search(r"[ab]{40,}", runs[0])
    dbbi = runs[0][:m.start()]

    print(f"dbbi: {len(dbbi)} symbols\n")
    print("=" * 72)
    print("parses by escape pair (mapping a=0..i=8)")
    print("=" * 72)
    digits = dbbi.translate(str.maketrans("abcdefghi", "012345678"))

    parses = []
    for e1, e2 in combinations(range(9), 2):
        toks = parse_checkerboard(digits, {str(e1), str(e2)})
        nslots = len(set(toks))
        if nslots > 28:
            continue
        parses.append((len(toks), nslots, (e1, e2), toks))
    parses.sort()
    for ntok, nslots, esc, toks in parses:
        mark = "  <- phase 3.2.2 escapes" if esc == (1, 4) else ""
        print(f"  escapes {esc}: {ntok:>2} tokens, {nslots:>2} distinct{mark}")
    print()

    print("=" * 72)
    print("known-plaintext consistency test")
    print("=" * 72)
    total_tested = 0
    hits = []
    for ntok, nslots, esc, toks in parses:
        tested = 0
        for plain, origin in candidates(ntok):
            if len(set(plain)) != nslots:
                continue
            tested += 1
            mapping = consistent(toks, plain)
            if mapping:
                hits.append((esc, plain, origin, mapping))
        total_tested += tested
        print(f"  escapes {esc}: {ntok} tokens / {nslots} slots -> "
              f"{tested:,} length-and-alphabet matches tested")

    print(f"\n  {total_tested:,} candidates survived the free filters")
    print(f"  {len(hits)} passed the bijection test\n")

    if hits:
        for esc, plain, origin, mapping in hits[:10]:
            print(f"  *** CONSISTENT *** escapes {esc} from {origin}")
            print(f"      plaintext: {plain}")
            print(f"      mapping  : {dict(sorted(mapping.items()))}")
    else:
        print("  No window of any puzzle plaintext decodes dbbi consistently.")
        print("  dbbi's plaintext is not text the puzzle has shown us.")


if __name__ == "__main__":
    main()
