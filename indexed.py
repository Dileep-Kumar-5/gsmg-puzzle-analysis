"""Test dbbi as an index/key table operating on faed.

Why this reading: dbbi (91 symbols) is structured -- IoC 0.1509, with 47% of
its mass on two symbols -- while faed (570 symbols) is nearly flat at IoC
0.1181. One structured, one flat, is what a key and its payload look like. And
the binary spliced immediately after dbbi decodes to "matrixsumlist", which
describes a table of sums, not a message.

Three families are tested:

  KEYSTREAM  faed combined with dbbi repeated, in the Vigenere family
             (add / subtract / Beaufort) over mod 9 and mod 10.
  WALK       dbbi values as step sizes, walking through faed and collecting
             the landed-on symbols.
  SELECT     dbbi values as offsets within fixed-size groups of faed.

Each result is then pushed through every decoder that has ever worked on this
puzzle -- the validated straddling checkerboard (all legal escape pairs), the
decimal->base16->ASCII transform that solved RUN1/RUN2, and direct a-i letters
-- and scored. Real English scores ~0.44 on englishness; the known-good phase
3.2.2 plaintext is the reference.

Run: python indexed.py
"""

import re
from itertools import product

from bigrun import get_runs, rejoin
from dbbi import parse_checkerboard
from vic import englishness

ALPHA = "abcdefghi"


def pieces():
    runs = get_runs()
    m = re.search(r"[ab]{40,}", runs[0])
    return runs[0][:m.start()], runs[0][m.end():]


def vals(run, base0):
    off = 0 if base0 else 1
    return [ALPHA.index(c) + off for c in run]


# --- decoders -----------------------------------------------------------------

def dec_to_ascii(digits):
    n = 0
    for v in digits:
        if v < 0 or v > 9:
            return None
        n = n * 10 + v
    if n == 0:
        return None
    h = format(n, "x")
    try:
        return bytes.fromhex(h.zfill(len(h) + len(h) % 2))
    except ValueError:
        return None


def as_letters(digits):
    return "".join(chr(ord("A") + (v % 26)) for v in digits)


def checkerboard_best(digits):
    """Best englishness over every legal escape pair, using the phase 3.2.2
    alphabet as the only alphabet the puzzle has ever used."""
    from vic import build, decode
    s = "".join(str(v % 10) for v in digits)
    best = (0.0, None, None)
    for e1, e2 in product(range(10), repeat=2):
        if e1 >= e2:
            continue
        try:
            table = build(d1=e1, d2=e2)
            out = decode(s, table, e1, e2)
        except Exception:
            continue
        e = englishness(out)
        if e > best[0]:
            best = (e, (e1, e2), out)
    return best


def printable(b):
    return sum(1 for c in b if 32 <= c < 127) / len(b) if b else 0.0


def evaluate(label, digits, results):
    if not digits:
        return
    e, esc, out = checkerboard_best(digits)
    results.append((e, f"{label} | checkerboard esc={esc}", out))
    lt = as_letters(digits)
    results.append((englishness(lt), f"{label} | direct letters", lt))
    b = dec_to_ascii(digits)
    if b:
        results.append((printable(b) * 0.5, f"{label} | dec->hex->ascii",
                        repr(b[:90])))


def main():
    dbbi, faed = pieces()
    print(f"dbbi {len(dbbi)} symbols, faed {len(faed)} symbols")
    for b0 in (True, False):
        d = vals(dbbi, b0)
        print(f"  dbbi as {'0..8' if b0 else '1..9'}: sum={sum(d)} "
              f"mean={sum(d) / len(d):.2f}")
    print(f"  faed length / dbbi length = {len(faed) / len(dbbi):.2f}")
    print(f"  570 = 91*6 + {570 - 91 * 6}\n")

    results = []

    for b0 in (True, False):
        dv, fv = vals(dbbi, b0), vals(faed, b0)
        tag = "0..8" if b0 else "1..9"

        # --- KEYSTREAM ---
        for mod in (9, 10):
            for opname, op in (("add", lambda a, k: a + k),
                               ("sub", lambda a, k: a - k),
                               ("beaufort", lambda a, k: k - a)):
                out = [op(fv[i], dv[i % len(dv)]) % mod for i in range(len(fv))]
                evaluate(f"keystream {opname} mod{mod} [{tag}]", out, results)
                # Key applied in reverse, in case dbbi reads backwards.
                rev = [op(fv[i], dv[(-1 - i) % len(dv)]) % mod
                       for i in range(len(fv))]
                evaluate(f"keystream {opname} mod{mod} revkey [{tag}]", rev,
                         results)

        # --- WALK ---
        for wrap in (True, False):
            pos, picked = 0, []
            for step in dv:
                pos += max(1, step)
                if pos >= len(fv):
                    if not wrap:
                        break
                    pos %= len(fv)
                picked.append(fv[pos])
            evaluate(f"walk {'wrap' if wrap else 'stop'} [{tag}]", picked,
                     results)
        # Cumulative index without the max(1,..) guard.
        pos, picked = 0, []
        for step in dv:
            pos = (pos + step) % len(fv)
            picked.append(fv[pos])
        evaluate(f"walk cumulative [{tag}]", picked, results)

        # --- SELECT ---
        for g in (6, 9, 10):
            picked = []
            for i, off in enumerate(dv):
                idx = i * g + (off % g)
                if idx < len(fv):
                    picked.append(fv[idx])
            evaluate(f"select group={g} [{tag}]", picked, results)
        # dbbi values as direct absolute indices.
        evaluate(f"select direct [{tag}]",
                 [fv[v % len(fv)] for v in dv], results)

    results.sort(reverse=True, key=lambda r: r[0])
    print("=" * 72)
    print("ranked (englishness; real English = 0.44, phase 3.2.2 = 0.440)")
    print("=" * 72)
    for sc, label, out in results[:18]:
        flag = "   <<< ENGLISH" if sc > 0.35 else ""
        print(f"  {sc:.3f}  {label}{flag}")
        print(f"         {str(out)[:96]}")

    print()
    print("=" * 72)
    print("CONTROL: same pipeline with dbbi replaced by a shuffled copy")
    print("=" * 72)
    import random
    sh = list(dbbi)
    random.Random(11).shuffle(sh)
    ctrl = []
    dv, fv = vals("".join(sh), True), vals(faed, True)
    for opname, op in (("add", lambda a, k: a + k), ("sub", lambda a, k: a - k)):
        out = [op(fv[i], dv[i % len(dv)]) % 9 for i in range(len(fv))]
        evaluate(f"control keystream {opname}", out, ctrl)
    ctrl.sort(reverse=True, key=lambda r: r[0])
    for sc, label, out in ctrl[:3]:
        print(f"  {sc:.3f}  {label}")
        print(f"         {str(out)[:96]}")


if __name__ == "__main__":
    main()
