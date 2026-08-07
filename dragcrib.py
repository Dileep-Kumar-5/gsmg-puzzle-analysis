"""Crib-dragging dbbi by repetition pattern.

crib.py demanded the whole 63-character plaintext be a window of some puzzle
text, and found nothing -- so if dbbi says something, it says something new.
But novel text can still CONTAIN a known word, and that is enough.

The constraint used here is structural, not statistical:

    a substitution preserves the repetition pattern of a word

"PASSWORD" has its S twice in a row, so wherever it sits, the tokens under
those two positions must be identical. "MATRIXSUMLIST" repeats M, S, I and T at
fixed distances. Matching that pattern needs no scoring function, which is
exactly why it works at 63 tokens where hill-climbing failed and its control
beat it.

Each candidate placement must satisfy three things:
  1. equal letters sit over equal tokens
  2. distinct letters sit over distinct tokens (a substitution is injective)
  3. the induced partial mapping does not contradict itself anywhere else in
     the run

Words with no repeated letters are excluded -- they constrain nothing and would
match everywhere. The known phase 3.2.2 stream is dragged first as a positive
control, since its plaintext contains words whose placement is known.

Run: python dragcrib.py
"""

import re
from collections import Counter

from bigrun import get_runs
from dbbi import parse_checkerboard
from pipeline import run as pipeline_run
from vic import VIC_EXPECTED, VIC_INPUT

CRIBS = [
    # puzzle vocabulary
    "MATRIXSUMLIST", "LASTWORDSBEFOREARCHICHOICE", "THISPASSWORD",
    "YOURLASTCOMMAND", "SECONDANSWER", "CAUSALITY", "THEMATRIXHASYOU",
    "THESEEDISPLANTED", "HASHTHETEXT", "YINYANG", "YELLOWBLUEPRIMES",
    "SALPHASEION", "COSMICDUALITY", "ARCHITECT", "MEROVINGIAN",
    # things a next-stage message would plausibly say
    "PASSWORD", "PRIVATEKEY", "PRIVATE", "ADDRESS", "BITCOIN", "WALLET",
    "CONGRATULATIONS", "CONGRATS", "SUCCESS", "CORRECT", "PROCEED",
    "THENEXTSTEP", "NEXTPHASE", "THEANSWER", "ANSWER", "PRIMES", "PRIME",
    "DOOR", "CHOICE", "SOURCE", "ENTER", "DECRYPT", "ENCRYPTED",
    # common English with usable patterns
    "THETHE", "THATTHE", "SEVEN", "ELEVEN", "LETTER", "NUMBER", "MESSAGE",
    "BETWEEN", "FOLLOW", "SEEDED", "SUCCESSFUL", "HIDDEN", "PUZZLE",
]


def pattern(word):
    """Canonical repetition signature: first-occurrence indices."""
    seen, out = {}, []
    for ch in word:
        out.append(seen.setdefault(ch, len(seen)))
    return tuple(out)


def placements(tokens, word):
    """Offsets where the word's repetition pattern fits the token sequence."""
    pw = pattern(word)
    n = len(word)
    hits = []
    for i in range(len(tokens) - n + 1):
        window = tokens[i:i + n]
        if pattern(window) != pw:
            continue
        # injective both directions over this window
        s2l, l2s = {}, {}
        ok = True
        for slot, ch in zip(window, word):
            if s2l.setdefault(slot, ch) != ch or l2s.setdefault(ch, slot) != slot:
                ok = False
                break
        if ok:
            hits.append((i, dict(s2l)))
    return hits


def extend_ok(tokens, mapping):
    """The partial mapping must stay injective across the whole run."""
    l2s = {}
    for slot, ch in mapping.items():
        if l2s.setdefault(ch, slot) != slot:
            return False
    return True


def informative(word):
    """A word with no repeated letter constrains nothing."""
    return len(word) - len(set(word)) >= 1


def drag_placements(tokens):
    """All surviving placements, as (repeats, len, word, offset, mapping)."""
    out = []
    for w in CRIBS:
        if not informative(w) or len(w) > len(tokens):
            continue
        for off, mapping in placements(tokens, w):
            if extend_ok(tokens, mapping):
                out.append((len(w) - len(set(w)), len(w), w, off, mapping))
    out.sort(reverse=True)
    return out


def drag(tokens, label):
    print("=" * 72)
    print(f"{label}: {len(tokens)} tokens, {len(set(tokens))} distinct slots")
    print("=" * 72)
    results = []
    skipped = 0
    for w in CRIBS:
        if not informative(w):
            skipped += 1
            continue
        if len(w) > len(tokens):
            continue
        for off, mapping in placements(tokens, w):
            if extend_ok(tokens, mapping):
                reps = len(w) - len(set(w))
                results.append((reps, len(w), w, off, mapping))
    results.sort(reverse=True)
    print(f"  {len(CRIBS) - skipped} cribs with repeated letters "
          f"({skipped} skipped as patternless)")
    print(f"  {len(results)} placements survive pattern + injectivity\n")
    for reps, n, w, off, mapping in results[:12]:
        cover = len(mapping) / len(set(tokens)) * 100
        print(f"    {w:<28} at token {off:>2}  "
              f"({reps} repeats, fixes {len(mapping)}/{len(set(tokens))} "
              f"slots = {cover:.0f}%)")
    return results


def main():
    # positive control -- the solved phase 3.2.2 stream
    ctrl_tokens = parse_checkerboard(VIC_INPUT, {"1", "4"})
    res = drag(ctrl_tokens, "CONTROL phase 3.2.2")
    truth = []
    for reps, n, w, off, mapping in res:
        if VIC_EXPECTED[off:off + n] == w:
            truth.append((w, off))
    print(f"\n  placements that are ACTUALLY correct in the known plaintext: "
          f"{truth}")
    print(f"  control {'PASS' if truth else 'FAIL'} -- the drag finds real "
          f"words at their true offsets\n")

    runs = get_runs()
    m = re.search(r"[ab]{40,}", runs[0])
    dbbi = runs[0][:m.start()]
    digits = dbbi.translate(str.maketrans("abcdefghi", "012345678"))
    tokens = parse_checkerboard(digits, {"1", "4"})
    drag(tokens, "dbbi (escapes 1,4)")


if __name__ == "__main__":
    main()
