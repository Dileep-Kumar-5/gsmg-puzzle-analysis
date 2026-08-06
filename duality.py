"""Look for the "duality" the puzzle keeps naming.

Constraints from the creator, which narrow this a lot:

  "Once you hit a 'ying yang', you'll be able to solve it the same day"   (2023)
  "It's the next phase, but I await the day someone finally gets there"   (2025)
  Q: is internet still required to solve it?  A: "Nope."               (2023-11)

The last one is decisive: yin-yang is NOT a hosted page. It is constructed from
data already in hand. And "you'll know it when you hit it" implies something
recognisable on sight, not a statistical nudge.

The puzzle names the duality three times over: the page is titled "SalPhaseIon
and Cosmic Duality", the VIC plaintext says the keys "BELONG TO HALF AND BETTER
HALF", and yin-yang is itself two complementary halves.

Concrete complementary pairs actually in hand:
  * two ciphertexts of EXACTLY 80 bytes each -- the SalPhaseIon blob and the
    blob trailing the phase 3.2 plaintext, from different stages
  * dbbi (structured, IoC 0.151) and faed (flat, IoC 0.118), same textarea
  * blue (15) and yellow (9), partitioning all 24 URL characters

This tests the first two directly, and renders candidates as bitmaps, since a
yin-yang is a shape and "you'd know it" argues for something visual.

Run: python duality.py
"""

import hashlib
import re
from base64 import b64decode
from pathlib import Path

from bigrun import get_runs
from oracle import check
from pipeline import SALPHASEION_BLOB

CORPUS = Path(__file__).with_name("corpus")


def blobs():
    a = b64decode("".join(SALPHASEION_BLOB.split()))
    b = b64decode((CORPUS / "blob_p32trailing.b64").read_text())
    return a, b


def xor(x, y):
    return bytes(p ^ q for p, q in zip(x, y))


def entropy(b):
    from collections import Counter
    import math
    n = len(b)
    return -sum((v / n) * math.log2(v / n) for v in Counter(b).values())


def bitmap(data, width, label):
    """Render bits as text. A yin-yang would be visible; noise will not be."""
    bits = "".join(f"{byte:08b}" for byte in data)
    rows = [bits[i:i + width] for i in range(0, len(bits) - width + 1, width)]
    print(f"  {label}  ({width} wide, {len(rows)} rows)")
    for r in rows:
        print("    " + r.replace("0", ".").replace("1", "#"))


def main():
    a, b = blobs()
    print("two 80-byte ciphertexts, from different stages")
    print(f"  SalPhaseIon   salt {a[8:16].hex()}  ct {len(a) - 16} bytes")
    print(f"  p32-trailing  salt {b[8:16].hex()}  ct {len(b) - 16} bytes")
    print(f"  identical length: {len(a) == len(b)}\n")

    ca, cb = a[16:], b[16:]
    x = xor(ca, cb)
    print("=" * 68)
    print("ciphertext XOR")
    print("=" * 68)
    print(f"  entropy {entropy(x):.3f} bits/byte  (random = ~7.9 at this size)")
    print(f"  printable {sum(1 for c in x if 32 <= c < 127) / len(x):.2f}")
    print(f"  first 32 bytes: {x[:32].hex()}")
    zeros = sum(1 for c in x if c == 0)
    print(f"  zero bytes: {zeros}/80  "
          f"(a shared plaintext prefix would show a run of these)")
    print()

    # Salts XOR -- if the two blobs are a deliberate pair, the salts may relate.
    sx = xor(a[8:16], b[8:16])
    print(f"  salt XOR: {sx.hex()}  printable "
          f"{sum(1 for c in sx if 32 <= c < 127) / 8:.2f}")
    print()

    print("=" * 68)
    print("key oracle on every 32-byte quantity these two produce")
    print("=" * 68)
    cands = {
        "xor(ct,ct)[:32]": x[:32],
        "xor(ct,ct)[-32:]": x[-32:],
        "sha256(xor)": hashlib.sha256(x).digest(),
        "sha256(ct_a+ct_b)": hashlib.sha256(ca + cb).digest(),
        "sha256(ct_b+ct_a)": hashlib.sha256(cb + ca).digest(),
        "sha256(salt_xor)": hashlib.sha256(sx).digest(),
        "sha256(a+b whole)": hashlib.sha256(a + b).digest(),
    }
    for name, k in cands.items():
        if check(k):
            print(f"  *** PRIZE KEY: {name} ***")
            return
    print(f"  {len(cands)} candidates: no match")
    print()

    print("=" * 68)
    print("bitmap view -- a yin-yang is a shape, and 'you'd know it'")
    print("=" * 68)
    runs = get_runs()
    m = re.search(r"[ab]{40,}", runs[0])
    dbbi = runs[0][:m.start()]
    # dbbi as bits under the two symbols that dominate it.
    bits = "".join("1" if c in "be" else "0" for c in dbbi)
    print(f"  dbbi, 'b'/'e' as 1 else 0  ({len(bits)} bits, 91 = 7x13)")
    for w in (7, 13):
        print(f"    width {w}:")
        for i in range(0, len(bits), w):
            print("      " + bits[i:i + w].replace("0", ".").replace("1", "#"))
        print()
    bitmap(x[:40], 16, "ciphertext XOR, first 40 bytes")


if __name__ == "__main__":
    main()
