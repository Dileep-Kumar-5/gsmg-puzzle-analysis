"""Oracle-check the 79-byte body recovered from the 96-byte SalPhaseIon blob.

Password `matrixsumlist enter lastwordsbeforearchichoice thispassword matrixsumlist`
(concatenated, MD5 KDF) reproduces sha256 1449a217... exactly, which matches the
value circulated in the repo issues.

But 79 bytes out of an 80-byte ciphertext means ONE padding byte, which a wrong
key produces 1 time in 256 -- the same weak confirmation that made
cosmic_decrypted.bin a false positive. Whether the plaintext is real is decided
by the on-chain public key, not by the padding.

Run: python check79.py
"""

import hashlib

from coincurve import PrivateKey

from oracle import TARGET_ADDR, check, p2pkh

BODY = bytes.fromhex(
    "9fa9db91a9dee0e38b93694ec874630b30f32f33671987543b1cf913f4746439"
    "1517389608d55021dc436b66ec513a617c4f14cb0fed4708b535641a6dfe8210"
    "38d4f4c90cb45fdfc8cff50d0ed1c5"
)

B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def b58check(payload):
    raw = payload + hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4]
    n, s = int.from_bytes(raw, "big"), ""
    while n:
        n, r = divmod(n, 58)
        s = B58[r] + s
    return "1" * (len(raw) - len(raw.lstrip(b"\x00"))) + s


def main():
    k = BODY[:32]
    print(f"body length      : {len(BODY)} bytes")
    print(f"body[0:32]       : {k.hex()}")
    wif = b58check(b"\x80" + k)
    print(f"  WIF uncompressed: {wif}")
    print(f"  its address     : {p2pkh(PrivateKey(k).public_key.format(False))}")
    print(f"  is the prize key: {check(k)}")
    print()

    windows = [BODY[i:i + 32] for i in range(len(BODY) - 31)]
    direct = [i for i, w in enumerate(windows) if check(w)]
    hashed = [i for i, w in enumerate(windows)
              if check(hashlib.sha256(w).digest())]
    print(f"{len(windows)} sliding 32-byte windows vs {TARGET_ADDR}")
    print(f"  direct      : {direct or 'no match'}")
    print(f"  sha256(win) : {hashed or 'no match'}")
    print(f"  sha256(body): {check(hashlib.sha256(BODY).digest())}")

    # The body is 79 bytes; a key could also be hiding reversed or byte-swapped.
    rev = BODY[::-1]
    revhits = [i for i in range(len(rev) - 31) if check(rev[i:i + 32])]
    print(f"  reversed body windows: {revhits or 'no match'}")


if __name__ == "__main__":
    main()
