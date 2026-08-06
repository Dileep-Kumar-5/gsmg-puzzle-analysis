#!/usr/bin/env python3
"""Model of HashTable's distance packing, at both compiled widths.

Mirrors HashTable::Convert / CalcDistAndType mask-for-mask so the bit layout
can be exercised without a C++ toolchain. If this fails, the C++ is wrong too.

DIST_WORDS = 2 is the default build (126-bit magnitude, 125-bit intervals);
DIST_WORDS = 4 is -DWIDE_DIST (254-bit magnitude, 253-bit intervals). The flags
live in the top two bits of the top word at either width, which is what lets
one implementation serve both.
"""

N_ORDER = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
NB64BLOCK = 5

SIGN = 0x8000000000000000  # top bit of the top word
TYPE = 0x4000000000000000
MAG = 0x3FFFFFFFFFFFFFFF


class Overflow(Exception):
    pass


def words(v, n):
    return [(v >> (64 * i)) & 0xFFFFFFFFFFFFFFFF for i in range(n)]


def max_interval_bits(dw):
    return 253 if dw == 4 else 125


def convert(d_signed, type_bit, dw):
    """HashTable::Convert -- pack a signed distance into DIST_WORDS words."""
    d = d_signed % N_ORDER
    w = words(d, NB64BLOCK)
    sign = 0
    if w[3] > 0x7FFFFFFFFFFFFFFF:               # upper half means negative
        d = (-d_signed) % N_ORDER               # ModNegK1order
        w = words(d, NB64BLOCK)
        sign = SIGN
    # magnitude must fit in DIST_MAG_BITS: flag bits clear in the top word,
    # and nothing at all above it
    if w[dw - 1] & (SIGN | TYPE) or any(w[i] for i in range(dw, NB64BLOCK)):
        raise Overflow("distance exceeds %d bits" % (64 * dw - 2))
    out = w[:dw]
    out[dw - 1] = (out[dw - 1] & MAG) | sign | (type_bit << 62)
    return out


def calc_dist_and_type(D, dw):
    """HashTable::CalcDistAndType -- unpack it again."""
    ktype = 1 if (D[dw - 1] & TYPE) else 0
    sign = 1 if (D[dw - 1] & SIGN) else 0
    top = D[dw - 1] & MAG
    mag = sum((top if i == dw - 1 else D[i]) << (64 * i) for i in range(dw))
    return ((-mag) % N_ORDER if sign else mag), ktype


def roundtrip(d_signed, type_bit, dw):
    got, ktype = calc_dist_and_type(convert(d_signed, type_bit, dw), dw)
    return got == d_signed % N_ORDER and ktype == type_bit


def demo():
    for dw in (2, 4):
        limit = max_interval_bits(dw)

        # Distances up to the documented interval limit survive, both signs,
        # both kangaroo types.
        for bits in (8, 64, 100, limit - 1, limit):
            for t in (0, 1):
                v = (1 << bits) - 12345
                assert roundtrip(v, t, dw), (dw, bits, t, "positive")
                assert roundtrip(-v, t, dw), (dw, bits, t, "negative")

        # Exactly at the magnitude boundary is fine; one bit past is refused,
        # never truncated. This is the whole point -- the original code masked
        # here and returned a wrong key with no error.
        mag_bits = 64 * dw - 2
        assert roundtrip((1 << mag_bits) - 1, 0, dw), dw
        try:
            convert(1 << mag_bits, 0, dw)
            raise AssertionError("dw=%d: %d-bit magnitude must be rejected"
                                 % (dw, mag_bits + 1))
        except Overflow:
            pass

        # Flags must never collide with magnitude bits.
        assert SIGN | TYPE | MAG == 0xFFFFFFFFFFFFFFFF
        assert SIGN & MAG == 0 and TYPE & MAG == 0 and SIGN & TYPE == 0

        # ENTRY layout: 16-byte x + 8*DIST_WORDS distance, no padding.
        assert 16 + 8 * dw == (32 if dw == 2 else 48)

    # A puzzle #140 distance (2^139) is exactly what the default build must
    # refuse and the wide build must accept.
    try:
        convert(1 << 139, 0, 2)
        raise AssertionError("default width must refuse a 139-bit distance")
    except Overflow:
        pass
    assert roundtrip(1 << 139, 0, 4)
    assert roundtrip(1 << 139, 1, 4)

    # Puzzle #120 (2^119) is inside both.
    assert roundtrip(1 << 119, 0, 2) and roundtrip(1 << 119, 0, 4)

    print("distance-field self-check OK")
    print("  default    magnitude 126 bits, intervals to 125")
    print("  WIDE_DIST  magnitude 254 bits, intervals to 253")


if __name__ == "__main__":
    demo()
