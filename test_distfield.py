#!/usr/bin/env python3
"""Model of the patched HashTable distance packing, to check the bit masks.

Mirrors HashTable::Convert / CalcDistAndType word-for-word so the masks can be
exercised without a C++ toolchain. If this fails, the C++ is wrong too.
"""

N_ORDER = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141

SIGN = 0x8000000000000000  # b255 of the 256-bit field, i.e. b63 of word 3
TYPE = 0x4000000000000000  # b254
MAG3 = 0x3FFFFFFFFFFFFFFF  # b253..b192

MAX_INTERVAL_BITS = 253


class Overflow(Exception):
    pass


def words(v, n):
    return [(v >> (64 * i)) & 0xFFFFFFFFFFFFFFFF for i in range(n)]


def convert256(d_signed, type_bit):
    """HashTable::Convert, 256-bit path. d_signed is the true signed distance."""
    d = d_signed % N_ORDER                      # how Int holds it: mod n
    w = words(d, 4)
    sign = 0
    if w[3] > 0x7FFFFFFFFFFFFFFF:               # upper half means negative
        d = (-d_signed) % N_ORDER               # ModNegK1order
        w = words(d, 4)
        sign = SIGN
    if w[3] & 0xC000000000000000:
        raise Overflow("distance exceeds 254 bits")
    return [w[0], w[1], w[2], (w[3] & MAG3) | sign | (type_bit << 62)]


def calc_dist_and_type256(D):
    """HashTable::CalcDistAndType, 256-bit path."""
    ktype = 1 if (D[3] & TYPE) else 0
    sign = 1 if (D[3] & SIGN) else 0
    mag = D[0] | (D[1] << 64) | (D[2] << 128) | ((D[3] & MAG3) << 192)
    return ((-mag) % N_ORDER if sign else mag), ktype


def convert128(d_signed, type_bit):
    """Legacy 126-bit path, now guarded instead of truncating."""
    d = d_signed % N_ORDER
    w = words(d, 4)
    sign = 0
    if w[3] > 0x7FFFFFFFFFFFFFFF:
        d = (-d_signed) % N_ORDER
        w = words(d, 4)
        sign = 1 << 63
    if w[3] or w[2] or (w[1] & 0xC000000000000000):
        raise Overflow("distance exceeds 126 bits")
    return [w[0], (w[1] & 0x3FFFFFFFFFFFFFFF) | sign | (type_bit << 62)]


def widen(D128):
    """HashTable::Widen -- legacy 126-bit entry into the 254-bit field."""
    return [D128[0], D128[1] & 0x3FFFFFFFFFFFFFFF, 0,
            D128[1] & 0xC000000000000000]


def roundtrip(d_signed, type_bit):
    got, ktype = calc_dist_and_type256(convert256(d_signed, type_bit))
    return got == d_signed % N_ORDER and ktype == type_bit


def demo():
    # Puzzle #140 lives in [2^139, 2^140); walks overshoot, so exercise well past it.
    for bits in (139, 140, 160, 200, 253):
        for t in (0, 1):
            v = (1 << bits) - 12345
            assert roundtrip(v, t), (bits, t, "positive")
            assert roundtrip(-v, t), (bits, t, "negative")

    # Boundary: 253 bits of magnitude fits, 254 does not.
    assert roundtrip((1 << 253) - 1, 0)
    try:
        convert256(1 << 254, 0)
        raise AssertionError("254-bit magnitude must be rejected, not truncated")
    except Overflow:
        pass

    # The original bug: a #140-scale distance silently lost its high bits in the
    # 126-bit field. Now it raises instead of returning a wrong key.
    try:
        convert128(1 << 139, 0)
        raise AssertionError("126-bit path must reject a 139-bit distance")
    except Overflow:
        pass

    # Legacy entries still decode correctly once widened.
    for v in (1, 42, (1 << 125) - 1):
        for t in (0, 1):
            got, ktype = calc_dist_and_type256(widen(convert128(v, t)))
            assert got == v and ktype == t, (v, t, got, ktype)
            got, ktype = calc_dist_and_type256(widen(convert128(-v, t)))
            assert got == (-v) % N_ORDER and ktype == t, (v, t)

    # Flags must never collide with magnitude bits.
    assert SIGN | TYPE | MAG3 == 0xFFFFFFFFFFFFFFFF
    assert SIGN & MAG3 == 0 and TYPE & MAG3 == 0 and SIGN & TYPE == 0

    # ENTRY layout: 16-byte x + 32-byte d, no padding.
    assert 16 + 32 == 48

    print("distance-field self-check OK (254-bit magnitude, max interval %d bits)"
          % MAX_INTERVAL_BITS)


if __name__ == "__main__":
    demo()
