"""Can a partial decode be scored well enough to pick the true crib set?

merge_cribs.py showed the merge surfaces the right answer on the control -- the
set containing PRIVATEKEY@29 agrees 51% with the true plaintext while the rest
score 0-24% -- but it ranks SECOND by slot coverage. The top-ranked set is
entirely wrong. So coverage cannot be the selector.

The question this settles: is there a blind score that ranks the true set first?
If yes, it can be trusted on dbbi. If no, crib-dragging cannot discriminate at
this length and should be reported as such rather than used.

The score works only on fully-revealed runs of letters, since a partial decode
is mostly gaps. Two components:

  TRIGRAMS   log-probability of revealed trigrams, from the puzzle's own English
  WORDS      total length of dictionary words appearing in revealed fragments

Judged on the control, where the correct answer is known independently.

Run: python score_partial.py
"""

import math
import re
from collections import defaultdict

from dbbi import parse_checkerboard
from dragcrib import drag_placements
from merge_cribs import greedy_sets, render
from pipeline import run as pipeline_run
from vic import VIC_EXPECTED, VIC_INPUT

WORDS = ["THE", "AND", "YOU", "THIS", "THAT", "WITH", "FROM", "HAVE", "YOUR",
         "WILL", "THEY", "BEEN", "MORE", "WHAT", "WHEN", "THERE", "THEIR",
         "PRIVATE", "KEY", "PASSWORD", "ANSWER", "PROCEED", "ENTER", "NEXT",
         "PRIME", "DOOR", "CHOICE", "SOURCE", "MATRIX", "BITCOIN", "WALLET",
         "MESSAGE", "LETTER", "FOLLOW", "HIDDEN", "PUZZLE", "CRACK", "BELONG"]


def corpus():
    r = pipeline_run()
    text = " ".join([r["phase3.2.1_beaufort"], r["phase3.2.2_vic"],
                     r["phase3.2_plaintext"]]).upper()
    return re.sub(r"[^A-Z]", "", text)


def trigram_model(text):
    counts = defaultdict(int)
    for i in range(len(text) - 2):
        counts[text[i:i + 3]] += 1
    total = sum(counts.values())
    floor = math.log10(0.01 / total)
    return {k: math.log10(v / total) for k, v in counts.items()}, floor


def score(decoded, model, floor):
    """Only fully-revealed trigrams and word hits count; gaps are ignored."""
    tri = n = 0
    for i in range(len(decoded) - 2):
        chunk = decoded[i:i + 3]
        if "." in chunk:
            continue
        tri += model.get(chunk, floor)
        n += 1
    tri = tri / n if n else floor
    wordscore = 0
    for frag in decoded.split("."):
        if len(frag) < 3:
            continue
        for w in WORDS:
            if w in frag:
                wordscore += len(w)
    return tri, wordscore, n


def evaluate(tokens, label, truth=None):
    model, floor = trigram_model(corpus())
    sets = greedy_sets(drag_placements(tokens))
    rows = []
    for cov, nw, used, mapping in sets:
        dec = render(tokens, mapping)
        tri, ws, n = score(dec, model, floor)
        agree = (sum(1 for a, b in zip(dec, truth) if a == b) / len(truth) * 100
                 if truth else None)
        rows.append((ws, tri, cov, nw, used, dec, agree, n))
    # rank by word evidence, then trigram quality
    rows.sort(reverse=True, key=lambda r: (r[0], r[1]))

    print("=" * 72)
    print(f"{label}: {len(sets)} consistent sets, ranked BLIND")
    print("=" * 72)
    for ws, tri, cov, nw, used, dec, agree, n in rows[:5]:
        words = ", ".join(f"{w}@{o}" for w, o in used)
        extra = f"  TRUE-AGREEMENT {agree:.0f}%" if agree is not None else ""
        print(f"  wordscore={ws:<4} tri={tri:+.2f} ({n} tri) cov={cov}"
              f"{extra}")
        print(f"    {words}")
        print(f"    {dec}")
    return rows


def main():
    ctrl = parse_checkerboard(VIC_INPUT, {"1", "4"})
    rows = evaluate(ctrl, "CONTROL phase 3.2.2", truth=VIC_EXPECTED)
    best_agree = rows[0][6]
    top_agree = max(r[6] for r in rows)
    print()
    print(f"  blind top-ranked set agrees {best_agree:.0f}% with truth")
    print(f"  best set available agrees   {top_agree:.0f}%")
    ok = best_agree >= top_agree - 1e-9
    print(f"  DISCRIMINATOR {'PASS' if ok else 'FAIL'} -- blind ranking "
          f"{'does' if ok else 'does NOT'} pick the best set\n")

    if not ok:
        print("  Crib-dragging cannot be trusted to select on dbbi. Stopping.")
        return

    from bigrun import get_runs
    runs = get_runs()
    m = re.search(r"[ab]{40,}", runs[0])
    dbbi = runs[0][:m.start()]
    tokens = parse_checkerboard(
        dbbi.translate(str.maketrans("abcdefghi", "012345678")), {"1", "4"})
    evaluate(tokens, "dbbi (escapes 1,4)")


if __name__ == "__main__":
    main()
