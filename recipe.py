"""The creator's own 4-ingredient recipe, built from measured values.

The 2023-02-23 Telegram binary block decodes to:

    yellowblueprimes matrixsumlist lastwordsbeforearchichoice yinyang
    wewontgiveawaythepassword itsinfrontofyoureyesbutyourenotseeingit
    verylaststepisatruegiveaway promised

Read as FOUR ingredients, not six -- "yellowblueprimes" is one token. This is
the only creator-sourced statement of what the Cosmic Duality key is made of,
and "it's in front of your eyes but you're not seeing it" says the ingredients
are named and only the assembly is missing.

Existing public attempts guess at two of the four. This substitutes measured
values instead:

  yellowblueprimes  -- from colours.py: 15 blue and 9 yellow cells, every one
                       at spiral position = 7 (mod 8), i.e. the last bit of
                       each of the 24 URL characters. Their indices, positions
                       and counts are all real numbers, filtered by primality.
  matrixsumlist     -- from the 14x14 grid: row sums 610876654997879 and
                       column sums 8108108736759668, both totalling 101.

Targets all three unsolved ciphertexts, including the trailing blob at the end
of the phase 3.2 plaintext that nobody attacks.

Run: python recipe.py
"""

import hashlib
import itertools
import sys
from base64 import b64decode
from pathlib import Path

from attack import Blob, printable_ratio
from colours import IMG, N, cell_colour, grid_bottom, spiral_ccw_coords
from cosmic import BLOB as COSMIC_B64
from pipeline import SALPHASEION_BLOB, evp_bytestokey, parse_matrix, sha256
from PIL import Image

CORPUS = Path(__file__).with_name("corpus")
KEYLENS = (16, 24, 32)
DIGESTS = (hashlib.md5, hashlib.sha256)


def primes_upto(n):
    ok = [False, False] + [True] * (n - 1)
    for i in range(2, int(n ** 0.5) + 1):
        if ok[i]:
            for j in range(i * i, n + 1, i):
                ok[j] = False
    return [i for i, v in enumerate(ok) if v]


def colour_cells():
    img = Image.open(IMG).convert("RGB")
    w, _ = img.size
    bottom = grid_bottom(img)
    cw, ch = w / N, bottom / N
    grid = [[cell_colour(img, r, c, cw, ch) for c in range(N)] for r in range(N)]
    order = spiral_ccw_coords(N)
    out = {}
    for name in ("blue", "yellow"):
        cells = [(r, c) for r in range(N) for c in range(N) if grid[r][c] == name]
        out[name] = {
            "count": len(cells),
            "rowmajor": [r * N + c + 1 for r, c in cells],
            "spiral0": sorted(order.index(rc) for rc in cells),
            "chars": sorted({order.index(rc) // 8 for rc in cells}),
        }
    return out


def yellowblueprimes():
    """Every reading of 'yellow blue primes' the measured data supports."""
    c = colour_cells()
    y, b = c["yellow"], c["blue"]
    P = set(primes_upto(200))
    out = set()

    def j(xs):
        return ["".join(map(str, xs)), "-".join(map(str, xs)),
                ",".join(map(str, xs))]

    for ykey in ("chars", "spiral0", "rowmajor"):
        for bkey in ("chars", "spiral0", "rowmajor"):
            ys, bs = y[ykey], b[bkey]
            for form in (ys + bs, bs + ys):
                out.update(j(form))
                out.update(j([v for v in form if v in P]))
    # Counts, sums, and their prime filtrations.
    counts = [y["count"], b["count"]]                        # 9, 15
    out.update(j(counts))
    out.update(j(counts[::-1]))
    for k in ("chars", "spiral0", "rowmajor"):
        out.update(j([sum(y[k]), sum(b[k])]))
        out.update(j([sum(b[k]), sum(y[k])]))
    # First N primes, the plainest reading of the word "primes".
    ps = primes_upto(120)
    for k in (9, 15, 24, 10):
        out.update(j(ps[:k]))
        out.add("yellowblueprimes")
    out.add("7233147103127")   # the value circulating publicly, for comparison
    return {s for s in out if 1 <= len(s) <= 120}


def matrixsumlist():
    m = parse_matrix()
    rows = [sum(r) for r in m]
    cols = [sum(c) for c in zip(*m)]
    out = set()
    for a, b in ((rows, cols), (cols, rows)):
        out.add("".join(map(str, a)))
        out.add("".join(map(str, a + b)))
        out.add("".join(f"{v:02d}" for v in a))
        out.add("".join(f"{v:02d}" for v in a + b))
        out.add("-".join(map(str, a)))
    out.add("matrixsumlist")
    out.add(str(sum(rows)))
    return out


def lastwords(beaufort):
    """Literal token, plus the tail of the Architect speech -- the last words
    before the choice it describes."""
    out = {"lastwordsbeforearchichoice"}
    w = beaufort.split()
    for n in (2, 3, 4, 5, 6, 8, 10, 12, 16, 20):
        out.add("".join(w[-n:]).lower())
    for phrase in ("CIAOBELLAO", "IREALLYHOPEYOURETHEONECIAOBELLAO",
                   "REINSERTINGTHEPRIMEBASICS", "GOODLUCKNEVERTHELESS",
                   "RETURNTOTHESOURCECODES", "THEPROBLEMISCHOICE",
                   "HOPEYOURETHEONE"):
        out.add(phrase.lower())
        out.add(phrase)
    return out


YINYANG = ["yinyang", "yin-yang", "yingyang", "ying-yang", "YinYang",
           "YINYANG", "yin yang", "ying yang"]


def main():
    from pipeline import run as pipeline_run
    beaufort = pipeline_run()["phase3.2.1_beaufort"]

    ybp = sorted(yellowblueprimes())
    msl = sorted(matrixsumlist())
    lws = sorted(lastwords(beaufort))
    print(f"ingredient variants: yellowblueprimes={len(ybp)} "
          f"matrixsumlist={len(msl)} lastwords={len(lws)} yinyang={len(YINYANG)}")

    combos = []
    for a, b, c, d in itertools.product(ybp, msl, lws, YINYANG):
        combos.append(a + b + c + d)          # creator's stated order
        combos.append(a + b + d + c)          # "soup" order seen publicly
    combos = list(dict.fromkeys(combos))
    print(f"{len(combos):,} concatenations\n")

    p32 = (CORPUS / "blob_p32trailing.b64").read_text()
    blobs = [Blob("cosmic-1328", COSMIC_B64),
             Blob("p32-trailing-80", p32),
             Blob("salphaseion-96", SALPHASEION_BLOB)]

    for blob in blobs:
        hits, checked = [], 0
        for i, s in enumerate(combos):
            if i % 20000 == 0:
                print(f"\r  {blob.name} {i:,}/{len(combos):,}",
                      end="", file=sys.stderr, flush=True)
            h = sha256(s)
            for pw in (h.encode(), bytes.fromhex(h), s.encode()):
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
        print(f"\r  {blob.name}: done{' ' * 30}", file=sys.stderr)
        hits.sort(reverse=True, key=lambda x: x[0])
        rate = len(hits) / checked * 100 if checked else 0
        print(f"{blob.name}: {checked:,} trials, {len(hits)} padding passes "
              f"({rate:.3f}%, random 0.39%)")
        real = [h for h in hits if h[0] > 0.90]
        if real:
            print("  *** TEXT-LIKE DECRYPTION ***")
            for pr, s, bits, md, pt in real[:5]:
                print(f"  printable={pr:.3f} aes-{bits} {md}")
                print(f"  recipe = {s[:160]!r}")
                print(f"  {pt[:400]!r}\n")
        elif hits:
            print(f"  best printable {hits[0][0]:.3f} (noise)")
        print()


if __name__ == "__main__":
    main()
