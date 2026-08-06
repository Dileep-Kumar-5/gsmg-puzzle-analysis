"""Non-concatenation assembly, and raw key/IV usage, for the creator's four
ingredients.

Concatenation is exhausted (~23.5M trials, all at the random padding floor).
Two structural alternatives remain, both grounded in what the puzzle actually
does elsewhere:

  ASSEMBLY -- the puzzle's own master-key construction is an XOR of SHA-256
  digests, not a concatenation. XOR is order-independent, which also explains
  why no ordering of the ingredients ever mattered. `shabef` appears TWICE on
  the SalPhaseIon page, which argues for a nested/double hash.

  USAGE -- "the solver will find a way to 'decrypt' it" (creator, 2021-08-11).
  If the 32-byte value is used as the AES key DIRECTLY, EVP_BytesToKey is
  bypassed entirely and the `Salted__` header is just a decoy prefix.

Key optimisation: in CBC, the IV affects only the FIRST plaintext block, and
PKCS#7 padding lives in the LAST. So the padding check is IV-INDEPENDENT --
one AES block test covers every IV variant at once. IVs are only enumerated
for candidates that already pass.

Run: python assembly.py
"""

import hashlib
import itertools
import sys
from base64 import b64decode
from functools import reduce
from pathlib import Path

from Crypto.Cipher import AES

from attack import printable_ratio
from cosmic import BLOB as COSMIC_B64
from pipeline import SALPHASEION_BLOB, evp_bytestokey, sha256
from recipe import YINYANG, lastwords, matrixsumlist, yellowblueprimes

CORPUS = Path(__file__).with_name("corpus")


def h(s):
    return hashlib.sha256(s.encode() if isinstance(s, str) else s).digest()


def xor(*bs):
    return bytes(reduce(lambda a, b: a ^ b, x) for x in zip(*bs))


class Target:
    """One ciphertext, with both readings of where the ciphertext starts."""

    def __init__(self, name, b64):
        raw = b64decode("".join(b64.split()))
        self.name = name
        self.salt = raw[8:16]
        self.variants = {}
        if (len(raw) - 16) % 16 == 0:
            self.variants["after-header"] = raw[16:]
        if len(raw) % 16 == 0:
            self.variants["whole-blob"] = raw

    def pad_ok(self, key, ct):
        """IV-independent: padding is in the last block only."""
        d = AES.new(key, AES.MODE_ECB).decrypt(ct[-16:])
        tail = xor(d, ct[-32:-16])
        pad = tail[-1]
        return 1 <= pad <= 16 and tail[-pad:] == bytes([pad]) * pad

    def ivs(self, key):
        z = bytes(16)
        return {
            "zeros": z,
            "salt+salt": self.salt * 2,
            "salt+zeros": self.salt + bytes(8),
            "key[:16]": key[:16],
            "key[16:]": key[16:],
            "sha256(key)[:16]": hashlib.sha256(key).digest()[:16],
        }

    def decrypt(self, key, ct, iv):
        pt = AES.new(key, AES.MODE_CBC, iv).decrypt(ct)
        pad = pt[-1]
        if 1 <= pad <= 16 and pt[-pad:] == bytes([pad]) * pad:
            return pt[:-pad]
        return None


def assemblies(a, b, c, d):
    """32-byte key candidates from the four ingredients."""
    ha, hb, hc, hd = h(a), h(b), h(c), h(d)
    cat = a + b + c + d
    yield "xor-of-hashes", xor(ha, hb, hc, hd)
    yield "sha256(xor-of-hashes)", hashlib.sha256(xor(ha, hb, hc, hd)).digest()
    yield "double-sha256(concat)", h(h(cat))
    # Sequential chaining: hash the first, fold in the next, and so on.
    acc = ha
    for nxt in (b, c, d):
        acc = hashlib.sha256(acc + nxt.encode()).digest()
    yield "chained-sha256", acc


def main():
    ybp = sorted(yellowblueprimes())
    msl = sorted(matrixsumlist())
    from pipeline import run as prun
    lws = sorted(lastwords(prun()["phase3.2.1_beaufort"]))
    combos = list(itertools.product(ybp, msl, lws, YINYANG))
    print(f"{len(combos):,} ingredient combinations "
          f"({len(ybp)}x{len(msl)}x{len(lws)}x{len(YINYANG)})")

    p32 = (CORPUS / "blob_p32trailing.b64").read_text()
    targets = [Target("cosmic-1328", COSMIC_B64),
               Target("p32-trailing", p32),
               Target("salphaseion-96", SALPHASEION_BLOB)]
    for t in targets:
        print(f"  {t.name}: ct readings {list(t.variants)} salt={t.salt.hex()}")
    print("\nXOR is order-independent, so no permutations are needed.\n")

    for t in targets:
        found, checked = [], 0
        for i, (a, b, c, d) in enumerate(combos):
            if i % 20000 == 0:
                print(f"\r  {t.name} {i:,}/{len(combos):,}",
                      end="", file=sys.stderr, flush=True)
            for aname, key in assemblies(a, b, c, d):
                for vname, ct in t.variants.items():
                    checked += 1
                    if not t.pad_ok(key, ct):
                        continue
                    for ivname, iv in t.ivs(key).items():
                        pt = t.decrypt(key, ct, iv)
                        if pt is not None:
                            found.append((printable_ratio(pt), aname, vname,
                                          ivname, (a, b, c, d), pt))
                # The same 32 bytes, used as an EVP password rather than a key.
                for md in (hashlib.md5, hashlib.sha256):
                    for vname, ct in t.variants.items():
                        k2, iv2 = evp_bytestokey(key, t.salt, md, klen=32)
                        checked += 1
                        if not t.pad_ok(k2, ct):
                            continue
                        pt = t.decrypt(k2, ct, iv2)
                        if pt is not None:
                            found.append((printable_ratio(pt), aname + "/evp-"
                                          + md().name, vname, "evp",
                                          (a, b, c, d), pt))
        print(f"\r  {t.name}: done{' ' * 40}", file=sys.stderr)
        found.sort(reverse=True, key=lambda x: x[0])
        print(f"{t.name}: {checked:,} pad checks, {len(found)} full decrypts")
        real = [f for f in found if f[0] > 0.90]
        if real:
            print("  *** TEXT-LIKE DECRYPTION ***")
            for pr, aname, vname, ivname, ing, pt in real[:5]:
                print(f"  printable={pr:.3f} {aname} ct={vname} iv={ivname}")
                print(f"  ingredients = {ing}")
                print(f"  {pt[:400]!r}\n")
        elif found:
            pr, aname, vname, ivname, ing, _ = found[0]
            print(f"  best printable {pr:.3f} (noise) via {aname} "
                  f"ct={vname} iv={ivname}")
        print()


if __name__ == "__main__":
    main()
