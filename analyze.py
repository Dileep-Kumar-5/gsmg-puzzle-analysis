"""Is cosmic_decrypted.bin signal or a padding-check false positive?

The master key decrypts the Cosmic Duality blob to 1327 bytes whose sha256
matches issue #99 exactly -- so the community artifact is now reproducible.
But the output looks like noise, and the confirmation is weak: 1327 bytes means
exactly one byte of PKCS#7 padding (0x01), which a wrong key produces by chance
1 time in 256.

So the question is whether the master-key output is distinguishable from the
hundreds of junk decryptions the sweep also produced. If it is not, "reproducible"
does not imply "correct".

Run: python analyze.py
"""

import hashlib
import math
import os
from collections import Counter

from Crypto.Cipher import AES

from cosmic import CT, MASTER_KEY_HEX, SALT, unpad
from pipeline import evp_bytestokey


def entropy(b):
    c = Counter(b)
    n = len(b)
    return -sum((v / n) * math.log2(v / n) for v in c.values())


def chi2_uniform(b):
    """Chi-square against a flat byte distribution. ~255 for random data."""
    exp = len(b) / 256
    c = Counter(b)
    return sum((c.get(i, 0) - exp) ** 2 / exp for i in range(256))


def describe(name, b):
    printable = sum(1 for x in b if 32 <= x < 127 or x in (9, 10, 13)) / len(b)
    print(f"  {name:<28} len={len(b):>5}  H={entropy(b):.3f}  "
          f"chi2={chi2_uniform(b):7.1f}  printable={printable:.3f}")


def decrypt_with(pw_bytes, klen, md):
    key, iv = evp_bytestokey(pw_bytes, SALT, md, klen=klen)
    return unpad(AES.new(key, AES.MODE_CBC, iv).decrypt(CT))


def main():
    master = decrypt_with(bytes.fromhex(MASTER_KEY_HEX), 32, hashlib.md5)
    assert master is not None
    print(f"master-key plaintext sha256 = {hashlib.sha256(master).hexdigest()}\n")

    print("byte-distribution comparison")
    print("-" * 72)
    describe("master key (issue #99)", master)

    # Control group: wrong keys that happened to pass the padding check.
    ctrl, tries = [], 0
    while len(ctrl) < 5 and tries < 20000:
        tries += 1
        pt = decrypt_with(os.urandom(32), 32, hashlib.md5)
        if pt is not None and len(pt) == 1327:
            ctrl.append(pt)
    for i, pt in enumerate(ctrl):
        describe(f"random key #{i + 1} (junk)", pt)
    describe("os.urandom(1327)", os.urandom(1327))
    print("-" * 72)

    rate = len(ctrl) / tries if tries else 0
    print(f"\n{len(ctrl)} usable controls from {tries:,} random keys "
          f"({rate * 100:.2f}% land on exactly 1327 bytes; 1/256 = 0.39%)")

    # If the plaintext were a further ciphertext, its length should still be a
    # sane block multiple. 1327 is prime-ish territory, not 16-aligned.
    print(f"\n1327 = 16*{1327 // 16} + {1327 % 16}   -> not an AES block multiple")
    print(f"1327 = 32*{1327 // 32} + {1327 % 32}   -> not 32-byte aligned either "
          f"(issue #99 claims '39 blocks')")


if __name__ == "__main__":
    main()
