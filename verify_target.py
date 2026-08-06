#!/usr/bin/env python3
"""Verify a puzzle target before spending GPU time on it.

Derives the P2PKH address from the compressed public key and checks it against
the published puzzle address, and checks the range is the canonical
[2^(n-1), 2^n - 1]. A wrong pubkey pasted from a forum makes an entire run
worthless, and nothing in the solver would tell you.

Pure stdlib: secp256k1 point decompression + hash160 + base58check.
"""

import hashlib
import sys

P = 2**256 - 2**32 - 977
N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def decompress(pub_hex):
    """Compressed SEC pubkey -> (x, y), verified on-curve."""
    raw = bytes.fromhex(pub_hex)
    if len(raw) != 33 or raw[0] not in (2, 3):
        raise ValueError("not a 33-byte compressed pubkey")
    x = int.from_bytes(raw[1:], "big")
    if x >= P:
        raise ValueError("x out of field")
    y = pow((x * x * x + 7) % P, (P + 1) // 4, P)      # P % 4 == 3
    if (y * y - (x * x * x + 7)) % P != 0:
        raise ValueError("x is not on the curve")
    if y % 2 != raw[0] % 2:
        y = P - y
    return x, y


def hash160(b):
    return hashlib.new("ripemd160", hashlib.sha256(b).digest()).digest()


def b58check(payload):
    chk = hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4]
    n = int.from_bytes(payload + chk, "big")
    out = ""
    while n:
        n, r = divmod(n, 58)
        out = B58[r] + out
    return "1" * (len(payload + chk) - len((payload + chk).lstrip(b"\0"))) + out


def address(pub_hex):
    return b58check(b"\x00" + hash160(bytes.fromhex(pub_hex)))


def check(puzzle, pub_hex, addr, start_hex, stop_hex):
    ok = True
    x, y = decompress(pub_hex)                          # raises if off-curve

    derived = address(pub_hex)
    match = derived == addr
    ok &= match
    print("puzzle #%d" % puzzle)
    print("  pubkey on curve   yes")
    print("  address expected  %s" % addr)
    print("  address derived   %s   %s" % (derived, "MATCH" if match else "MISMATCH"))

    start, stop = int(start_hex, 16), int(stop_hex, 16)
    want_start, want_stop = 2 ** (puzzle - 1), 2 ** puzzle - 1
    rng = (start == want_start and stop == want_stop)
    ok &= rng
    print("  range             2^%d .. 2^%d-1   %s"
          % (puzzle - 1, puzzle, "OK" if rng else "UNEXPECTED"))
    print("  interval bits     %d" % (puzzle - 1))
    if stop >= N:
        print("  WARNING: range exceeds the curve order")
        ok = False
    return ok


def demo():
    # Puzzle #105, solved, key published in the repo's puzzle32.txt. If the
    # address derivation is right, this key's pubkey must yield #105's address.
    priv = 0x16F14FC2054CD87EE6396B33DF3
    assert 2**104 <= priv < 2**105

    # k*G by double-and-add, to get the pubkey from the known private key.
    GX = 0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798
    GY = 0x483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8

    def add(p, q):
        if p is None:
            return q
        if q is None:
            return p
        if p[0] == q[0]:
            if (p[1] + q[1]) % P == 0:
                return None
            l = 3 * p[0] * p[0] * pow(2 * p[1], -1, P) % P
        else:
            l = (q[1] - p[1]) * pow(q[0] - p[0], -1, P) % P
        rx = (l * l - p[0] - q[0]) % P
        return rx, (l * (p[0] - rx) - p[1]) % P

    r, base, k = None, (GX, GY), priv
    while k:
        if k & 1:
            r = add(r, base)
        base = add(base, base)
        k >>= 1
    pub = "%02x%064x" % (2 + (r[1] & 1), r[0])
    assert address(pub) == "1CMjscKB3QW7SDyQ4c3C3DEUHiHRhiZVib", address(pub)

    # Round-trip: decompressing our own encoding returns the same point.
    assert decompress(pub) == r

    # An off-curve x must be rejected, not silently accepted. Find one honestly:
    # x is on the curve iff x^3+7 is a quadratic residue mod p.
    bad_x = next(x for x in range(1, 200)
                 if pow((x * x * x + 7) % P, (P - 1) // 2, P) != 1)
    try:
        decompress("02" + "%064x" % bad_x)
        raise AssertionError("x=%d is off-curve; should have raised" % bad_x)
    except ValueError:
        pass

    print("verify_target self-check OK (derives #105 from its published key)")


TARGETS = {
    135: ("02145D2611C823A396EF6712CE0F712F09B9B4F3135E3E0AA3230FB9B6D08D1E16",
          "16RGFo6hjq9ym6Pj7N5H7L1NR1rVPJyw2v",
          "4000000000000000000000000000000000",
          "7FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF"),
    120: ("02CEB6CBBCDBDF5EF7150682150F4CE2C6F4807B349827DCDBDD1F2EFA885A2630",
          "17s2b9ksz5y7abUm92cHwG8jEPCzK3dLnT",
          "800000000000000000000000000000",
          "FFFFFFFFFFFFFFFFFFFFFFFFFFFFFF"),
    140: ("031F6A332D3C5C4F2DE2378C012F429CD109BA07D69690C6C701B6BB87860D6640",
          "1QKBaU6WAeycb3DbKbLBkX7vJiaS8r42Xo",
          "80000000000000000000000000000000000",
          "FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF"),
}

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--self-check":
        demo()
        raise SystemExit(0)
    bad = 0
    for n in (int(a) for a in (sys.argv[1:] or ["135", "140"])):
        if not check(n, *TARGETS[n]):
            bad += 1
        print()
    raise SystemExit(1 if bad else 0)
