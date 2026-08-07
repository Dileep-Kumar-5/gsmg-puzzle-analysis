"""Positive control for the crib attack.

crib.py reports zero consistent plaintexts for dbbi. That is only meaningful if
the same procedure FINDS the answer in a case where the answer is known.

Phase 3.2.2 is that case: its digit stream, escape pair and plaintext are all
established, and its plaintext is in the same candidate corpus crib.py searches.
So running the identical pipeline against it must produce exactly one hit, with
a mapping that reconstructs the published alphabet.

If this fails, crib.py's negative is an artifact and must be discarded.

Run: python crib_control.py
"""

import re

from crib import candidates, consistent, letters_only
from dbbi import parse_checkerboard
from vic import ALPHABET, VIC_EXPECTED, VIC_INPUT, build


def main():
    toks = parse_checkerboard(VIC_INPUT, {"1", "4"})
    nslots = len(set(toks))
    print(f"phase 3.2.2 stream: {len(VIC_INPUT)} digits -> {len(toks)} tokens, "
          f"{nslots} distinct slots")
    print(f"known plaintext   : {VIC_EXPECTED[:60]}...")
    print(f"  length {len(VIC_EXPECTED)}, "
          f"{len(set(VIC_EXPECTED))} distinct letters\n")

    # 1. Does the known plaintext itself pass the bijection test?
    direct = consistent(toks, VIC_EXPECTED)
    print(f"direct bijection check on the known plaintext: "
          f"{'PASS' if direct else 'FAIL'}")
    if direct:
        table = build(ALPHABET, 1, 4)
        agree = sum(1 for slot, ch in direct.items()
                    if table.get(slot, "?").upper() == ch)
        print(f"  recovered {len(direct)} slot->letter pairs; "
              f"{agree}/{len(direct)} match the published alphabet")
    print()

    # 2. Does the blind sweep find it among all corpus windows?
    print(f"blind sweep over the same corpus crib.py uses "
          f"(length {len(toks)}, {nslots} distinct):")
    tested = hits = 0
    found = []
    for plain, origin in candidates(len(toks)):
        if len(set(plain)) != nslots:
            continue
        tested += 1
        if consistent(toks, plain):
            hits += 1
            found.append((plain, origin))
    print(f"  {tested:,} candidates tested, {hits} consistent")
    for plain, origin in found[:5]:
        marker = "  <-- the true plaintext" if plain == VIC_EXPECTED else ""
        print(f"    [{origin}] {plain[:56]}...{marker}")

    print()
    if direct and any(p == VIC_EXPECTED for p, _ in found):
        print("CONTROL PASS -- the procedure recovers a known answer, so")
        print("crib.py's zero hits on dbbi is a real negative.")
    else:
        print("CONTROL FAIL -- crib.py's negative is an artifact, discard it.")


if __name__ == "__main__":
    main()
