"""Straddling checkerboard (monome-dinome) decoder, validated then applied to RUN0.

Phase 3.2.2 is solved and gives a known input/output pair, so the decoder can be
PROVEN correct before it is pointed at anything unknown:

    alphabet FUBCDORA.LETHINGKYMVPS.JQZXW, escape digits 1 and 4
    15165943121972409169171213758951813141543...
      -> IN CASE YOU MANAGE TO CRACK THIS THE PRIVATE KEYS BELONG TO ...

Layout that produces it: the first 8 alphabet symbols occupy row 0 at the
digits that are NOT escapes; the next 10 occupy row `d1`; the last 10 occupy
row `d2`.

    row 0 :  0=F 2=U 3=B 5=C 6=D 7=O 8=R 9=A      (1 and 4 are escapes)
    row 1 : 10=. 11=L 12=E 13=T 14=H 15=I 16=N 17=G 18=K 19=Y
    row 4 : 40=M 41=V 42=P 43=S 44=. 45=J 46=Q 47=Z 48=X 49=W

Why this matters for RUN0: the checkerboard NEEDS the digit 0 (row 0 slot 0,
and the 40/10 prefixes). RUN0's alphabet is exactly {a..i} with NO 'o' -- the
one run in the puzzle missing a zero. The creator's hint says "some characters
need to be 'zeroed out'". So the two candidate mappings are a=1..i=9 (needs
zeros introduced) and a=0..i=8 (zeros already present, no 9).

Run: python vic.py
"""

import re
import sys
from pathlib import Path

from bigrun import get_runs, rejoin

ALPHABET = "FUBCDORA.LETHINGKYMVPS.JQZXW"
D1, D2 = 1, 4

VIC_INPUT = ("15165943121972409169171213758951813141543131412428154191312181219"
             "433121171617137149110916631213131281491109166131412199114371612"
             "126021664313711154112")
VIC_EXPECTED = ("INCASEYOUMANAGETOCRACKTHISTHEPRIVATEKEYSBELONGTOHALFANDBETTER"
                "HALFANDTHEYALSONEEDFUNDSTOLIVE")


def build(alphabet=ALPHABET, d1=D1, d2=D2):
    table, i = {}, 0
    for d in range(10):
        if d in (d1, d2):
            continue
        table[str(d)] = alphabet[i]
        i += 1
    for prefix in (d1, d2):
        for d in range(10):
            table[f"{prefix}{d}"] = alphabet[i]
            i += 1
    return table


def decode(digits, table=None, d1=D1, d2=D2):
    table = table or build()
    out, i = [], 0
    s = "".join(digits)
    while i < len(s):
        c = s[i]
        if int(c) in (d1, d2):
            if i + 1 >= len(s):
                break
            out.append(table.get(s[i:i + 2], "?"))
            i += 2
        else:
            out.append(table.get(c, "?"))
            i += 1
    return "".join(out)


WORDS = ["THE", "AND", "YOU", "THIS", "KEY", "PRIVATE", "PASSWORD", "IS", "OF",
         "TO", "FOR", "YOUR", "WITH", "THAT", "NOT", "ARE", "HAVE", "WILL",
         "FROM", "ONE", "ALL", "CAN", "HAS", "BEEN", "MORE", "WHAT", "WHICH",
         "THERE", "THEIR", "WOULD", "ABOUT", "DOOR", "CHOICE", "PRIME", "YIN",
         "YANG", "MATRIX", "SOURCE", "ANSWER", "FINAL", "STEP", "BITCOIN"]


def englishness(s):
    """Fraction of the text covered by common English words. Random letters
    score ~0.1; real English scores >0.4."""
    if not s:
        return 0.0
    hits = sum(len(w) * len(re.findall(w, s)) for w in WORDS)
    return min(1.0, hits / len(s))


def validate():
    got = decode(VIC_INPUT)
    ok = got == VIC_EXPECTED
    print(f"VALIDATION against solved phase 3.2.2: {'PASS' if ok else 'FAIL'}")
    print(f"  decoded : {got[:70]}")
    if not ok:
        print(f"  expected: {VIC_EXPECTED[:70]}")
        sys.exit(1)
    print(f"  englishness of the known-good plaintext: {englishness(got):.3f}\n")
    return True


def mappings(run):
    """a..i as 1..9 (zeros absent, must be introduced) or as 0..8."""
    return {
        "a=1..i=9": run.translate(str.maketrans("abcdefghi", "123456789")),
        "a=0..i=8": run.translate(str.maketrans("abcdefghi", "012345678")),
        "a=9..i=1": run.translate(str.maketrans("abcdefghi", "987654321")),
        "a=8..i=0": run.translate(str.maketrans("abcdefghi", "876543210")),
    }


def main():
    validate()

    runs = get_runs()
    joined, _ = rejoin(runs[0])
    m = re.search(r"[ab]{40,}", runs[0])
    targets = {
        "RUN0 rejoined (661)": joined,
        "dbbi (91)": runs[0][:m.start()],
        "faed (570)": runs[0][m.end():],
        "RUN1 (63)": runs[1],
        "RUN2 (29)": runs[2],
    }

    results = []
    for tname, run in targets.items():
        print("=" * 72)
        print(f"{tname}")
        print("=" * 72)
        for mname, digits in mappings(run).items():
            out = decode(digits)
            e = englishness(out)
            results.append((e, tname, mname, out))
            flag = "   <<< ENGLISH" if e > 0.35 else ""
            print(f"  {mname:<10} eng={e:.3f} {out[:88]}{flag}")
        print()

    results.sort(reverse=True)
    print("=" * 72)
    print("ranked by englishness (known-good phase 3.2.2 scores ~0.5)")
    print("=" * 72)
    for e, tname, mname, out in results[:6]:
        print(f"  {e:.3f}  {tname} | {mname}")
        print(f"         {out[:100]}")


if __name__ == "__main__":
    main()
