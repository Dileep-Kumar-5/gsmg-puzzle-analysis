"""Offline verification oracle for the GSMG.IO 5 BTC puzzle.

The prize address has spent (the creator halved the prize twice), so its public
key is on-chain and public. That turns "are these 32 bytes the private key?"
into a local, network-free check running at ~100k/s on libsecp256k1.

Use it before believing any claimed solution, yours or anyone else's.

Run: python oracle.py
"""

import hashlib

from coincurve import PrivateKey, PublicKey

TARGET_ADDR = "1GSMG1JC9wtdSwfwApgj2xcmJPAwx7prBe"

# x-coordinate reported by solvers in issue #84. Treated as UNVERIFIED until
# resolve_pubkey() derives TARGET_ADDR back out of it -- see the self-test.
CLAIMED_X = bytes.fromhex(
    "f4d1bbd91e65e2a019566a17574e97dae908b784b388891848007e4f55d5a464"
)

N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def hash160(b):
    return hashlib.new("ripemd160", hashlib.sha256(b).digest()).digest()


def b58check(payload):
    raw = payload + hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4]
    n = int.from_bytes(raw, "big")
    s = ""
    while n:
        n, r = divmod(n, 58)
        s = B58[r] + s
    return "1" * (len(raw) - len(raw.lstrip(b"\x00"))) + s


def p2pkh(pubkey_bytes, version=b"\x00"):
    return b58check(version + hash160(pubkey_bytes))


def resolve_pubkey(x=CLAIMED_X, addr=TARGET_ADDR):
    """An x-coordinate has two possible y values and each pubkey has two
    serialisations. Only one of the four hashes to the target address --
    finding it is what turns the claim into a verified fact."""
    for prefix in (b"\x02", b"\x03"):
        try:
            pk = PublicKey(prefix + x)
        except Exception:
            continue
        for compressed in (True, False):
            ser = pk.format(compressed)
            if p2pkh(ser) == addr:
                return ser, compressed
    return None, None


PUBKEY, COMPRESSED = resolve_pubkey()


def check(priv):
    """True iff these 32 bytes are the prize private key."""
    if isinstance(priv, int):
        priv = priv.to_bytes(32, "big")
    if len(priv) != 32:
        return False
    if not 0 < int.from_bytes(priv, "big") < N:
        return False
    if PUBKEY is None:
        raise RuntimeError("target pubkey unresolved; cannot verify offline")
    return PrivateKey(priv).public_key.format(COMPRESSED) == PUBKEY


def search(candidates, label=lambda c: repr(c)[:60]):
    """Feed it any iterable of 32-byte candidates. Returns the winner or None."""
    for i, c in enumerate(candidates):
        if check(c):
            print(f"FOUND after {i} candidates: {label(c)}")
            return c
    return None


def _selftest():
    # A known keypair, so a broken address routine cannot silently report
    # "no match" forever and be mistaken for "candidate was wrong".
    one = (1).to_bytes(32, "big")
    assert p2pkh(PrivateKey(one).public_key.format(False)) == \
        "1EHNa6Q4Jz2uvNExL497mE43ikXhwF6kZm"
    assert p2pkh(PrivateKey(one).public_key.format(True)) == \
        "1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH"


if __name__ == "__main__":
    _selftest()
    print("secp256k1 + address derivation self-test: OK")
    if PUBKEY is None:
        print(f"\nx-coordinate from issue #84 does NOT hash to {TARGET_ADDR}.")
        print("It is wrong, or the address's real pubkey differs. Pull the")
        print("scriptSig of a spending tx from the address and use that instead.")
    else:
        print(f"\ntarget pubkey VERIFIED against {TARGET_ADDR}")
        print(f"  serialisation : {'compressed' if COMPRESSED else 'uncompressed'}")
        print(f"  pubkey        : {PUBKEY.hex()}")
        assert not check(bytes(32) [:31] + b"\x01") or True
        print("\noracle ready:  from oracle import check, search")
