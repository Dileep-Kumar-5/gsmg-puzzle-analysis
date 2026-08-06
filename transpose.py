"""Columnar transposition on RUN0, keyed by the decoded SalPhaseIon tokens,
followed by the validated straddling checkerboard.

The length coincidence is too exact to ignore:

    dbbi = 91  = 7 x 13     len("matrixsumlist")                        = 13
    faed = 570 = 15 x 38    len("lastwordsbeforearchichoice"+"thispassword") = 38

Both pieces factor exactly into a rectangle whose width is the length of the
token sitting next to them, which is what a columnar transposition key looks
like. Under that reading the decoded words are not passwords at all -- they are
key lengths, and "enter" is the instruction to apply them.

Pipeline tested here:  RUN0 piece -> columnar transposition -> a..i to digits
-> straddling checkerboard (proven against phase 3.2.2 in vic.py) -> English?

Run: python transpose.py
"""

import re
from itertools import product

from bigrun import get_runs, rejoin
from vic import build, decode, englishness, validate

KEYS = {
    "matrixsumlist": "matrixsumlist",
    "lastwords+thispassword": "lastwordsbeforearchichoicethispassword",
    "lastwordsbeforearchichoice": "lastwordsbeforearchichoice",
    "thispassword": "thispassword",
    "enter": "enter",
    "matrixsumlistenter": "matrixsumlistenter",
}

MAPS = {
    "a=1..i=9": str.maketrans("abcdefghio", "1234567890"),
    "a=0..i=8": str.maketrans("abcdefghio", "0123456780"),
    "a=9..i=1": str.maketrans("abcdefghio", "9876543210"),
}


def key_order(key):
    """Column read order: alphabetical rank of each key letter, ties broken
    left to right -- the standard columnar convention."""
    return [i for i, _ in sorted(enumerate(key), key=lambda p: (p[1], p[0]))]


def undo_columnar(text, key):
    """Inverse of a complete columnar transposition."""
    ncols = len(key)
    if len(text) % ncols:
        return None
    nrows = len(text) // ncols
    order = key_order(key)
    cols = [None] * ncols
    pos = 0
    for c in order:
        cols[c] = text[pos:pos + nrows]
        pos += nrows
    return "".join(cols[c][r] for r in range(nrows) for c in range(ncols))


def do_columnar(text, key):
    """Forward columnar, in case the run is the plaintext side."""
    ncols = len(key)
    if len(text) % ncols:
        return None
    order = key_order(key)
    rows = [text[i:i + ncols] for i in range(0, len(text), ncols)]
    return "".join("".join(r[c] for r in rows) for c in order)


def rail(text, n):
    """Plain rectangle read-out, no key: write rows, read columns."""
    if len(text) % n:
        return None
    rows = [text[i:i + n] for i in range(0, len(text), n)]
    return "".join("".join(r[c] for r in rows) for c in range(n))


def main():
    validate()

    runs = get_runs()
    m = re.search(r"[ab]{40,}", runs[0])
    joined, _ = rejoin(runs[0])
    targets = {
        "dbbi (91)": runs[0][:m.start()],
        "faed (570)": runs[0][m.end():],
        "RUN0 rejoined (661)": joined,
        "RUN0 raw (765)": runs[0],
    }

    print("factorisations:")
    for name, t in targets.items():
        fac = [d for d in range(2, len(t)) if len(t) % d == 0]
        print(f"  {name:<22} len={len(t):<4} divisors={fac[:12]}")
    print()

    results = []
    for (tname, text), (kname, key) in product(targets.items(), KEYS.items()):
        for op, fn in (("undo", undo_columnar), ("do", do_columnar)):
            t2 = fn(text, key)
            if t2 is None:
                continue
            for mname, tbl in MAPS.items():
                out = decode(t2.translate(tbl))
                results.append((englishness(out), tname, f"{op} {kname}",
                                mname, out))
    # Keyless rectangle read-outs at every divisor, as a control.
    for tname, text in targets.items():
        for n in range(2, len(text)):
            if len(text) % n:
                continue
            t2 = rail(text, n)
            for mname, tbl in MAPS.items():
                out = decode(t2.translate(tbl))
                results.append((englishness(out), tname, f"rect w={n}",
                                mname, out))
    # Untransposed control.
    for tname, text in targets.items():
        for mname, tbl in MAPS.items():
            results.append((englishness(decode(text.translate(tbl))), tname,
                            "none", mname, decode(text.translate(tbl))))

    results.sort(reverse=True, key=lambda r: r[0])
    print(f"{len(results):,} pipelines tested "
          f"(known-good phase 3.2.2 scores 0.440)\n")
    print("top 15 by englishness")
    print("-" * 72)
    for e, tname, op, mname, out in results[:15]:
        flag = "   <<< ENGLISH" if e > 0.35 else ""
        print(f"  {e:.3f}  {tname:<20} {op:<28} {mname}{flag}")
        print(f"         {out[:92]}")


if __name__ == "__main__":
    main()
