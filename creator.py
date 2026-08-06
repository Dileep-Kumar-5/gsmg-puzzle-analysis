"""Sweep the creator's own element list against both unsolved blobs.

On 2023-02-23 the creator posted a binary block that decodes to:

  yellowblueprimesmatrixsumlistlastwordsbeforearchichoiceyinyang
  wewontgiveawaythepassworditsinfrontofyoureyesbutyourenotseeingit
  verylaststepisatruegiveawaypromised

The first part is an ORDERED ELEMENT LIST -- yellow, blue, primes,
matrixsumlist, lastwordsbeforearchichoice, yinyang -- and it conspicuously
omits enter / thispassword / yourlastcommand / secondanswer, the tokens the
community builds its passwords from. "It's in front of your eyes but you're
not seeing it" reads as: the elements are named, the assembly is not.

So: sweep orderings and joinings of those elements, with the variants the
puzzle has actually used (yin-yang vs yinyang, the image's yellow/blue counts
as numbers, prime lists), against both ciphertexts.

Run: python creator.py
"""

import hashlib
import itertools
import sys

from attack import Blob, printable_ratio
from cosmic import BLOB as COSMIC_B64
from pipeline import SALPHASEION_BLOB, evp_bytestokey, parse_matrix, sha256

KEYLENS = (16, 24, 32)
DIGESTS = (hashlib.md5, hashlib.sha256)

CREATOR_LINE = ("yellowblueprimesmatrixsumlistlastwordsbeforearchichoiceyinyang"
                "wewontgiveawaythepassworditsinfrontofyoureyesbutyourenotseeingit"
                "verylaststepisatruegiveawaypromised")

# The six named elements, each with the spelling variants seen in the puzzle.
ELEMENTS = [
    ["yellow"],
    ["blue"],
    ["primes", "prime"],
    ["matrixsumlist"],
    ["lastwordsbeforearchichoice"],
    ["yinyang", "yin-yang", "yingyang", "ying-yang"],
]

# Tokens the element list omits but the community uses; a couple of orderings
# may still need them.
EXTRA = ["enter", "thispassword", "yourlastcommand", "secondanswer", "causality"]


def colour_numbers():
    """'Yellow has a number and so does Blue.' The 14x14 grid's own counts are
    the only numbers the puzzle attaches to those colours."""
    m = parse_matrix()
    ones = sum(sum(r) for r in m)
    return {str(ones), str(196 - ones), "15", "9", "490", "497", "87", "84"}


def prime_strings(n=30):
    ps, x = [], 2
    while len(ps) < n:
        if all(x % p for p in ps if p * p <= x):
            ps.append(x)
        x += 1
    out = set()
    for k in (5, 7, 10, 14, 24, 30):
        out.add("".join(map(str, ps[:k])))
        out.add(",".join(map(str, ps[:k])))
        out.add("-".join(map(str, ps[:k])))
    return out


def candidates():
    seen = set()

    def add(s):
        if s and 3 <= len(s) <= 400:
            seen.add(s)

    add(CREATOR_LINE)
    add(CREATOR_LINE.split("wewont")[0])

    # Every ordering of the six elements, across spelling variants.
    for combo in itertools.product(*ELEMENTS):
        for perm in itertools.permutations(combo):
            add("".join(perm))
        add("".join(combo))
    # Element list with each extra token appended or inserted at the end.
    for combo in itertools.product(*ELEMENTS):
        base = "".join(combo)
        for e in EXTRA:
            add(base + e)
            add(e + base)
    # Numeric substitutions for yellow/blue and for primes.
    for num in colour_numbers():
        for combo in itertools.product(*ELEMENTS):
            add("".join(combo).replace("yellow", num))
            add("".join(combo).replace("blue", num))
    for pr in prime_strings():
        for combo in itertools.product(*ELEMENTS):
            add("".join(combo).replace("primes", pr).replace("prime", pr))
    return list(seen)


def forms(s):
    h = sha256(s)
    yield s.encode()
    yield h.encode()
    yield h.upper().encode()
    yield bytes.fromhex(h)
    yield sha256(h).encode()


def main():
    blobs = [Blob("cosmic-1328", COSMIC_B64),
             Blob("salphaseion-96", SALPHASEION_BLOB)]
    cands = candidates()
    print(f"{len(cands):,} candidate strings from the creator's element list\n")

    for blob in blobs:
        hits, checked = [], 0
        for i, s in enumerate(cands):
            if i % 5000 == 0:
                print(f"\r  {blob.name} {i:,}/{len(cands):,}",
                      end="", file=sys.stderr, flush=True)
            for pw in forms(s):
                for klen in KEYLENS:
                    for md in DIGESTS:
                        key, iv = evp_bytestokey(pw, blob.salt, md, klen=klen)
                        checked += 1
                        if not blob.pad_ok(key):
                            continue
                        pt = blob.full(key, iv)
                        if pt is not None:
                            hits.append((printable_ratio(pt), s, klen * 8,
                                         md().name, pt))
        print(f"\r  {blob.name}: {checked:,} trials", file=sys.stderr)
        hits.sort(reverse=True, key=lambda h: h[0])
        rate = len(hits) / checked * 100 if checked else 0
        print(f"{blob.name}: {len(hits)} padding passes of {checked:,} "
              f"({rate:.3f}%, random 0.39%)")
        real = [h for h in hits if h[0] > 0.90]
        if real:
            print("  *** TEXT-LIKE DECRYPTION ***")
            for pr, s, bits, md, pt in real:
                print(f"  printable={pr:.3f} aes-{bits} {md} pw={s[:80]!r}")
                print(f"  {pt[:400]!r}")
        elif hits:
            print(f"  best printable {hits[0][0]:.3f} (noise) "
                  f"pw={hits[0][1][:60]!r}")
        print()


if __name__ == "__main__":
    main()
