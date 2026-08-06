"""Do the null positions in faed carry the information?

nulls.py established that faed is eight uniform symbols plus 'g' as a null:
removing 'g' drops chi2 from 43.7 to 10.8 on 7 df, while removing any other
symbol leaves it at 39 or above. That is a clean, single-candidate result.

Nulls exist to be discarded -- but 107 of them in 570 positions is a lot of
padding, and where they sit is itself 570 bits of choice. So this checks whether
the null MASK is the payload rather than the symbols around it.

Also tested: the gaps between nulls, since a run of small integers is the shape
the rest of this puzzle keeps using.

Prime positions were already ruled out (24/107 g-positions prime against 18.4%
expected by chance).

Run: python gmask.py
"""

import hashlib
import re
from collections import Counter

from bigrun import get_runs
from oracle import check


def main():
    runs = get_runs()
    m = re.search(r"[ab]{40,}", runs[0])
    faed = runs[0][m.end():]

    mask = "".join("1" if c == "g" else "0" for c in faed)
    ones = mask.count("1")
    print(f"g-mask: {len(mask)} bits, {ones} ones "
          f"({ones / len(mask) * 100:.1f}%)")

    b = bytes(int(mask[i:i + 8], 2) for i in range(0, len(mask) - 7, 8))
    pr = sum(1 for c in b if 32 <= c < 127) / len(b)
    print(f"  as bytes : {len(b)} bytes, printable {pr:.2f}")
    print(f"  {b[:48]!r}")

    inv = bytes(~x & 0xFF for x in b)
    print(f"  inverted : printable "
          f"{sum(1 for c in inv if 32 <= c < 127) / len(inv):.2f}")

    pos = [i for i, c in enumerate(faed) if c == "g"]
    gaps = [y - x for x, y in zip(pos, pos[1:])]
    print(f"\n  gaps between nulls: n={len(gaps)}, range "
          f"{min(gaps)}..{max(gaps)}, mean {sum(gaps) / len(gaps):.2f}")
    print(f"  gap distribution: {sorted(Counter(gaps).items())[:12]}")
    # A geometric gap profile means the nulls are scattered at random; a tight
    # or repeating one means the positions were chosen.
    c = Counter(gaps)
    top = c.most_common(1)[0]
    print(f"  most common gap {top[0]} occurs {top[1]}x "
          f"({top[1] / len(gaps) * 100:.0f}%) -- geometric decay means random"
          f" placement")

    gap_bytes = bytes(g % 256 for g in gaps)
    print(f"\n  gaps as bytes: printable "
          f"{sum(1 for x in gap_bytes if 32 <= x < 127) / len(gap_bytes):.2f}")
    print(f"  {gap_bytes[:40]!r}")

    cands = {
        "mask bytes[:32]": b[:32],
        "mask bytes[-32:]": b[-32:],
        "sha256(mask bits)": hashlib.sha256(mask.encode()).digest(),
        "sha256(mask bytes)": hashlib.sha256(b).digest(),
        "sha256(gaps)": hashlib.sha256(gap_bytes).digest(),
        "sha256(positions)": hashlib.sha256(
            ",".join(map(str, pos)).encode()).digest(),
    }
    print("\n  key oracle:")
    for name, k in cands.items():
        if check(k):
            print(f"    *** PRIZE KEY: {name} ***")
            return
    print(f"    {len(cands)} candidates, no match")


if __name__ == "__main__":
    main()
