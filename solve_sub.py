"""Hill-climb the checkerboard slot->letter substitution for dbbi and faed.

dbbi.py established the layout: parsing with escapes (1,4) under a=0..i=8 is
the best-shaped of 72 combinations and yields 19 slots over 63 tokens, which is
what 63 letters of English looks like. The phase 3.2.2 alphabet does not fit,
so the slot->letter map is unknown -- i.e. a simple substitution.

Scoring uses trigram statistics built from the puzzle's OWN recovered English
(the Architect speech, the VIC line, the phase 2/3/3.2 plaintexts) plus a
generic English sample. Using the puzzle's register is deliberate: the expected
plaintext is more likely to resemble its other stages than newspaper prose.

Honest caveat: 63 letters is short for automated substitution cracking. A
converged solution must be legible to the eye, not merely high-scoring --
so the top candidates are printed for judgement rather than auto-accepted.

Run: python solve_sub.py
"""

import random
import re
from collections import Counter, defaultdict

from dbbi import parse_checkerboard
from bigrun import get_runs, rejoin
from pipeline import run as pipeline_run

ALPHA = "ETAOINSHRDLCUMWFGYPBVKJXQZ"

GENERIC = """
THE QUICK BROWN FOX JUMPS OVER THE LAZY DOG AND THE ANSWER TO THIS PUZZLE IS
NOT WHAT YOU THINK IT IS BECAUSE THE PRIVATE KEY IS HIDDEN IN THE MATRIX AND
YOU MUST FIND THE DOOR THAT LEADS TO THE SOURCE OF ALL THINGS THERE IS ANOTHER
DOOR AND THE PRIME NUMBERS ARE THE WAY TO PROCEED WITH THIS FINAL STEP OF THE
PUZZLE SO THAT YOU CAN TAKE THE PRIZE THAT HAS BEEN WAITING FOR YOU ALL THIS
TIME PLEASE ENTER THE PASSWORD NOW AND THE NEXT PHASE WILL BE REVEALED TO YOU
"""


def corpus():
    r = pipeline_run()
    parts = [r["phase3.2.1_beaufort"], r["phase3.2.2_vic"],
             r["phase3.2_plaintext"], GENERIC]
    from pathlib import Path
    for f in (Path(__file__).with_name("corpus")).glob("blob_*.txt"):
        parts.append(f.read_bytes().decode("cp437", "replace"))
    text = " ".join(parts).upper()
    return re.sub(r"[^A-Z]", "", text)


def trigram_model(text):
    counts = defaultdict(int)
    for i in range(len(text) - 2):
        counts[text[i:i + 3]] += 1
    total = sum(counts.values())
    import math
    floor = math.log10(0.01 / total)
    model = {k: math.log10(v / total) for k, v in counts.items()}
    return model, floor


def score(text, model, floor):
    return sum(model.get(text[i:i + 3], floor) for i in range(len(text) - 2))


def hill_climb(tokens, model, floor, restarts=400, seed=0):
    slots = [s for s, _ in Counter(tokens).most_common()]
    rng = random.Random(seed)
    best_overall = (-1e18, None)
    for r in range(restarts):
        # Seed by frequency order: most common slot -> most common letter.
        letters = list(ALPHA[:len(slots)])
        if r:
            rng.shuffle(letters)
        mapping = dict(zip(slots, letters))
        cur = score("".join(mapping[t] for t in tokens), model, floor)
        improved = True
        while improved:
            improved = False
            for i in range(len(slots)):
                for j in range(i + 1, len(slots)):
                    a, b = slots[i], slots[j]
                    mapping[a], mapping[b] = mapping[b], mapping[a]
                    s = score("".join(mapping[t] for t in tokens), model, floor)
                    if s > cur:
                        cur, improved = s, True
                    else:
                        mapping[a], mapping[b] = mapping[b], mapping[a]
        if cur > best_overall[0]:
            best_overall = (cur, dict(mapping))
    return best_overall


def main():
    text = corpus()
    model, floor = trigram_model(text)
    print(f"trigram model: {len(model):,} trigrams from {len(text):,} letters\n")

    runs = get_runs()
    m = re.search(r"[ab]{40,}", runs[0])
    pieces = {
        "dbbi": (runs[0][:m.start()], {"1", "4"}),
        "faed": (runs[0][m.end():], {"4", "6"}),
    }
    tbl = str.maketrans("abcdefghi", "012345678")

    # Calibrate: what does the model score on real English of each length?
    for name, (run, esc) in pieces.items():
        toks = parse_checkerboard(run.translate(tbl), esc)
        n = len(toks)
        ref = text[:n]
        ref_score = score(ref, model, floor) / max(1, n - 2)
        print("=" * 72)
        print(f"{name}: {n} tokens, {len(set(toks))} distinct slots, "
              f"escapes {sorted(esc)}")
        print(f"  real English of this length scores {ref_score:.3f}/trigram")
        best, mapping = hill_climb(toks, model, floor,
                                   restarts=300 if n < 100 else 60)
        out = "".join(mapping[t] for t in toks)
        per = best / max(1, n - 2)
        print(f"  best hill-climb score      {per:.3f}/trigram")
        print(f"  ratio to real English      {per / ref_score:.2f}")
        print(f"  PLAINTEXT: {out}")
        print()

    print("=" * 72)
    print("control: hill-climb a SHUFFLED copy of dbbi (should look like this")
    print("         run's output if the result above is meaningless)")
    print("=" * 72)
    run, esc = pieces["dbbi"]
    d = list(run.translate(tbl))
    random.Random(7).shuffle(d)
    toks = parse_checkerboard("".join(d), esc)
    best, mapping = hill_climb(toks, model, floor, restarts=300, seed=3)
    print(f"  score {best / max(1, len(toks) - 2):.3f}/trigram")
    print(f"  PLAINTEXT: {''.join(mapping[t] for t in toks)}")


if __name__ == "__main__":
    main()
