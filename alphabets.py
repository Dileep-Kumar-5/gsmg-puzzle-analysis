"""Hunt for alphabet-shaped hint sentences in the puzzle's own text.

Phase 3.2.2's checkerboard alphabet was not given directly -- it was built from
a hint sentence embedded in ordinary prose:

    "A fubcd-king & oracle-queen, thingky mvps, on a sad board but as wide as
     the first one seen"
      -> FUBCD ORACLE THINGKY MVPS      (the nonsense words only)
      -> dedupe, repeats become '.'      FUBCDORA.LETHINGKYMVPS
      -> append the unused letters       FUBCDORA.LETHINGKYMVPS.JQZXW

A first attempt scored whole phrases by letter diversity. It FAILED its own
control: the real sentence scores 0.333 because "on a sad board but as wide as
the first one seen" dilutes the signal. The diversity lives in the nonsense
words, not the sentence.

So the real signature is: RARE words (hapax legomena -- appearing once in the
puzzle's vocabulary), with high distinct-letter ratio, CLUSTERED together inside
otherwise-normal English. That is what fubcd / thingky / mvps are.

The corpus deliberately excludes this project's README and the upstream repo's:
both quote the solved alphabet, which would make any hit circular.

dbbi's distribution says it is checkerboard-encoded (two symbols carrying 47%,
the escape-digit signature) under an unknown alphabet. If that alphabet has a
hint, it should look like this.

Run: python alphabets.py
"""

import re
import string
from collections import Counter
from pathlib import Path

from bigrun import get_runs
from pipeline import run as pipeline_run
from vic import build, decode, englishness

CORPUS = Path(__file__).with_name("corpus")

KNOWN_SENTENCE = ("A fubcd-king & oracle-queen, thingky mvps, on a sad board "
                  "but as wide as the first one seen")
KNOWN_ALPHABET = "FUBCDORA.LETHINGKYMVPS.JQZXW"

CREATOR_HINTS = [
    "yellowblueprimes matrixsumlist lastwordsbeforearchichoice yinyang "
    "wewontgiveawaythepassword itsinfrontofyoureyesbutyourenotseeingit "
    "verylaststepisatruegiveaway promised",
    "Roses are White but often Red. Yellow has a number and so does Blue. "
    "Go back to the first puzzle piece without further ado. It might have "
    "shown you only one door, beware that the rabbits nest may contain a "
    "whole lot more. Hush hush.",
    "There is Another D O O R",
    "We have seen prime numbers being mentioned well that is definitely an "
    "aspect which is required to proceed Furthermore along the way some "
    "characters need to be zeroed out",
    "Breaking salphation, should be giving the feeling of the phase's name",
    "Have you tried the purple pill already",
    "Once you hit a ying yang, you will be able to solve it the same day",
    "Carrots were originally purple, until the Dutch turned them orange in "
    "the 1600s to kiss up to their royal family",
    "another door might be found on 1 4 21",
    "I will be going for ASCII 127",
    "You only need the last number of pi and it might get you somewhere",
]


def corpus_texts():
    """Puzzle plaintexts and creator hints only -- no README, no walkthrough."""
    r = pipeline_run()
    out = {
        "phase3.2 plaintext": r["phase3.2_plaintext"],
        "architect": r["phase3.2.1_beaufort"],
        "vic": r["phase3.2.2_vic"],
    }
    for f in sorted(CORPUS.glob("blob_*.txt")):
        out[f.stem] = f.read_bytes().decode("cp437", "replace")
    for i, h in enumerate(CREATOR_HINTS):
        out[f"creator-hint-{i}"] = h
    return out


def strip_blobs(text):
    """The plaintexts carry base64 AES blobs inline. Tokenising those produces
    hundreds of high-diversity pseudo-words that swamp the real signal, so cut
    them out before looking for hint sentences."""
    text = re.sub(r"U2FsdGVkX1[A-Za-z0-9+/=\s]{40,}", " ", text)
    # Any remaining long run of mixed-case base64-ish text is also a blob.
    return re.sub(r"[A-Za-z0-9+/]{24,}", " ", text)


def wordify(text):
    return re.findall(r"[A-Za-z]{2,}", strip_blobs(text))


def build_vocab(texts):
    c = Counter()
    for t in texts.values():
        c.update(w.lower() for w in wordify(t))
    return c


def oddness(word):
    """How unlike an ordinary English word: all-distinct letters, and a poor
    vowel ratio. 'thingky' and 'mvps' both score high; 'board' does not."""
    w = word.lower()
    if len(w) < 3:
        return 0.0
    distinct = len(set(w)) / len(w)
    vowels = sum(1 for c in w if c in "aeiou") / len(w)
    # English words sit near 0.38 vowels; nonsense keys are far off.
    vowel_penalty = 1.0 - min(1.0, abs(vowels - 0.38) / 0.38)
    return distinct * (1.0 - vowel_penalty * 0.6)


def find_clusters(text, vocab, span=8):
    """Runs of rare, odd-looking words within a short window of each other."""
    ws = wordify(text)
    flags = []
    for i, w in enumerate(ws):
        rare = vocab[w.lower()] <= 2
        if rare and oddness(w) > 0.62 and len(w) >= 3:
            flags.append(i)
    clusters, cur = [], []
    for i in flags:
        if cur and i - cur[-1] > span:
            clusters.append(cur)
            cur = []
        cur.append(i)
    if cur:
        clusters.append(cur)
    out = []
    for cl in clusters:
        if len(cl) < 2:
            continue
        picked = [ws[i] for i in cl]
        letters = "".join(picked).upper()
        distinct = len(set(letters))
        out.append((distinct, picked, " ".join(ws[max(0, cl[0] - 3):cl[-1] + 4])))
    return out


def to_alphabet(words):
    letters = re.sub(r"[^A-Za-z]", "", "".join(words)).upper()
    seen, slots = set(), []
    for c in letters:
        if c in seen:
            if slots.count(".") < 2:
                slots.append(".")
        else:
            seen.add(c)
            slots.append(c)
    rest = [c for c in string.ascii_uppercase if c not in seen]
    alpha = "".join(slots) + "".join(rest)
    while alpha.count(".") < 2:
        alpha += "."
    return alpha[:28]


def main():
    texts = corpus_texts()
    vocab = build_vocab(texts)

    print("positive control -- can the detector find the KNOWN hint?")
    ctrl_clusters = find_clusters(KNOWN_SENTENCE,
                                  build_vocab({"x": KNOWN_SENTENCE}))
    found = False
    for distinct, picked, ctx in ctrl_clusters:
        print(f"  cluster {picked} -> {distinct} distinct letters")
        if {"fubcd", "thingky", "mvps"} <= {w.lower() for w in picked}:
            found = True
    print(f"  rebuilt from those words: {to_alphabet(['fubcd','oracle','thingky','mvps'])}")
    print(f"  target                  : {KNOWN_ALPHABET}")
    print(f"  CONTROL {'PASS' if found else 'FAIL'}\n")
    if not found:
        print("  detector cannot find the one known example; results below are"
              " not meaningful.\n")

    all_clusters = []
    for tname, text in texts.items():
        for distinct, picked, ctx in find_clusters(text, vocab):
            all_clusters.append((distinct, picked, ctx, tname))
    all_clusters.sort(reverse=True, key=lambda c: c[0])

    print("=" * 72)
    print(f"{len(all_clusters)} nonsense-word clusters found")
    print("=" * 72)
    for distinct, picked, ctx, tname in all_clusters[:15]:
        print(f"  {distinct:>2} distinct  [{tname}]  {picked}")
        print(f"      ...{ctx[:84]}...")
    print()

    runs = get_runs()
    m = re.search(r"[ab]{40,}", runs[0])
    dbbi = runs[0][:m.start()]
    digits = dbbi.translate(str.maketrans("abcdefghi", "012345678"))

    print("=" * 72)
    print("candidate alphabets applied to dbbi (escapes 1,4)")
    print("=" * 72)
    scored = []
    for distinct, picked, ctx, tname in all_clusters:
        alpha = to_alphabet(picked)
        try:
            txt = decode(digits, build(alpha, 1, 4), 1, 4)
        except Exception:
            continue
        scored.append((englishness(txt), alpha, txt, picked, tname))
    ref = decode(digits, build(KNOWN_ALPHABET, 1, 4), 1, 4)
    scored.append((englishness(ref), KNOWN_ALPHABET, ref, ["(known 3.2.2)"], "-"))
    scored.sort(reverse=True, key=lambda s: s[0])
    for e, alpha, txt, picked, tname in scored[:10]:
        flag = "   <<< ENGLISH" if e > 0.35 else ""
        print(f"  eng={e:.3f} [{tname}] {alpha}{flag}")
        print(f"      {txt[:76]}")
        print(f"      from {picked}")
    print()
    print("real English = 0.44; the solved VIC plaintext scores 0.440")


if __name__ == "__main__":
    main()
