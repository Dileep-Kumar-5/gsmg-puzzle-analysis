"""Targeted key search: every mapping, but only structurally plausible offsets.

The exhaustive sweep (faed.py) checks all 195 sliding 32-byte windows of every
base-9 decoding -- 70.7M elliptic-curve operations, about four hours at the
measured 4,800 checks/sec. Most of that cost buys very little: 165 of the 195
offsets are positions a key would only occupy if it had been hidden at a
deliberately misaligned boundary.

This covers the realistic cases instead: offsets on 16-byte boundaries (the
natural alignment for anything AES-adjacent), plus the first and last windows.
14 offsets rather than 195, so ~5M checks.

One correctness detail the exhaustive version glosses over: converting the
decoded integer with format(n,'x') DROPS leading zeros, so the byte length --
and therefore what "offset 0" means -- shifts between mappings. Here the result
is left-padded to a fixed 226 bytes so offsets are comparable across the sweep.

dbbi decodes to only 36 bytes (5 windows), so it is checked exhaustively.

Run: python oracle_aligned.py
"""

import re
import sys
from itertools import permutations

from bigrun import get_runs
from oracle import check

ALPHA = "abcdefghi"


def byte_width(nsyms, base):
    """Exact bytes needed for the largest value the run can hold.
    91 base-9 digits need 37 bytes, not 36 -- 91*log2(9) = 288.5 bits."""
    return ((base ** nsyms - 1).bit_length() + 7) // 8


def fixed_bytes(run, digit_of, base, width):
    n = 0
    for c in run:
        n = n * base + digit_of[c]
    return n.to_bytes(width, "big")


def offsets_for(nbytes, stride=16):
    """16-byte boundaries, plus the first and last possible windows."""
    last = nbytes - 32
    offs = {0, last}
    offs.update(o for o in range(0, last + 1, stride))
    return sorted(o for o in offs if 0 <= o <= last)


def sweep(run, name, width, stride):
    syms = sorted(set(run))
    offs = offsets_for(width, stride)
    total = 362880
    print(f"{name}: {len(run)} symbols -> {width} bytes")
    print(f"  offsets checked: {offs}")
    print(f"  {total:,} mappings x {len(offs)} offsets = "
          f"{total * len(offs):,} checks")

    seen = 0
    for perm in permutations(range(9), len(syms)):
        seen += 1
        if seen % 20000 == 0:
            print(f"\r    {seen:,}/{total:,}", end="", file=sys.stderr,
                  flush=True)
        b = fixed_bytes(run, dict(zip(syms, perm)), 9, width)
        for o in offs:
            if check(b[o:o + 32]):
                print(f"\n\n  *** PRIZE KEY FOUND ***")
                print(f"  run={name} mapping={perm} offset={o}")
                print(f"  key={b[o:o + 32].hex()}")
                return True
    print(f"\r    {seen:,}/{total:,} done{' ' * 20}", file=sys.stderr)
    print(f"  no match\n")
    return False


def main():
    runs = get_runs()
    m = re.search(r"[ab]{40,}", runs[0])
    faed, dbbi = runs[0][m.end():], runs[0][:m.start()]

    # dbbi is small enough to check every window.
    if sweep(dbbi, "dbbi", byte_width(len(dbbi), 9), 1):
        return
    if sweep(faed, "faed", byte_width(len(faed), 9), 16):
        return
    print("Neither run contains the prize key at any 16-byte-aligned offset "
          "under any base-9 mapping.")


if __name__ == "__main__":
    main()
