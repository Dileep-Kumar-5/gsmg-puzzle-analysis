"""Throw every 32-byte quantity this project has derived at the key oracle.

Cheap and worth doing at every stage: the master key is 32 bytes, a SHA256 is
32 bytes, and a secp256k1 private key is 32 bytes. If any derived value IS the
prize key, this finds it in milliseconds rather than after another week of
cipher archaeology.

Run: python keycheck.py
"""

import hashlib
import itertools

from cosmic import BLOB, CT, MASTER_KEY_HEX, RAW, SALT
from oracle import check
from pipeline import (PHASE32_BLOB, SALPHASEION_BLOB, PHASE3_PARTS, run,
                      openssl_dec_any, evp_bytestokey, sha256)

from Crypto.Cipher import AES


def cosmic_plaintext():
    key, iv = evp_bytestokey(bytes.fromhex(MASTER_KEY_HEX), SALT, hashlib.md5, klen=32)
    return AES.new(key, AES.MODE_CBC, iv).decrypt(CT)[:-1]


def candidates():
    """(label, 32 bytes) for everything derived so far."""
    r = run()
    master = bytes.fromhex(MASTER_KEY_HEX)
    cos = cosmic_plaintext()

    yield "PR#68 master key", master
    yield "sha256(master key)", hashlib.sha256(master).digest()
    yield "cosmic plaintext sha256", hashlib.sha256(cos).digest()

    # Every 32-byte window of the cosmic plaintext, and every 32-byte block on
    # its natural boundaries read from both ends.
    for i in range(0, len(cos) - 31):
        yield f"cosmic[{i}:{i + 32}]", cos[i:i + 32]
    for i in range(0, len(cos) - 31, 32):
        yield f"cosmic sha256 blk {i}", hashlib.sha256(cos[i:i + 32]).digest()

    # Published hashes and token hashes.
    for label, s in [
        ("phase3 pw", r["phase3_pw"]), ("phase3.2 pw", r["phase3.2_pw"]),
        ("salphaseion url hash", r["salphaseion_url"].rsplit("/", 1)[1]),
    ]:
        yield label, bytes.fromhex(s)

    toks = ["matrixsumlist", "enter", "lastwordsbeforearchichoice", "thispassword",
            "yourlastcommand", "secondanswer", "causality"]
    for n in range(1, len(toks) + 1):
        for c in itertools.permutations(toks, n):
            yield f"sha256({'+'.join(c)[:40]})", hashlib.sha256("".join(c).encode()).digest()

    # XOR of every subset of the token digests -- the construction that produced
    # the master key in the first place.
    digs = [hashlib.sha256(t.encode()).digest() for t in toks]
    for n in range(2, len(toks) + 1):
        for c in itertools.combinations(range(len(toks)), n):
            acc = bytes(32)
            for i in c:
                acc = bytes(a ^ b for a, b in zip(acc, digs[i]))
            yield f"xor({c})", acc

    # Raw ciphertext material.
    yield "cosmic blob sha256", hashlib.sha256(RAW).digest()
    yield "salphaseion blob sha256", hashlib.sha256(SALPHASEION_BLOB.encode()).digest()
    yield "phase3.2 blob sha256", hashlib.sha256(PHASE32_BLOB.encode()).digest()


def main():
    n = 0
    for label, priv in candidates():
        n += 1
        if check(priv):
            print(f"\n*** PRIVATE KEY FOUND ***\n  {label}\n  {priv.hex()}")
            return
    print(f"{n:,} derived 32-byte candidates checked against the on-chain pubkey.")
    print("None is the prize key.")


if __name__ == "__main__":
    main()
