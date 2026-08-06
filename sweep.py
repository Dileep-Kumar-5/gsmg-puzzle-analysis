"""Password sweep against the final Salphaseion AES blob.

The blob is 5 AES blocks. A wrong password survives the PKCS#7 padding check
roughly 1 time in 256, so the padding check alone is a ~99.6% filter and the
survivors can be scored by hand. That makes a wide sweep cheap and decisive:
if a candidate space is exhausted with no plausible plaintext, that space is
genuinely dead rather than untried.

Candidate space swept here:
  strings  : puzzle tokens, every ordered permutation/subset of the core six,
             every word appearing in the README, and every word appearing in
             the decrypted phase-3.2 and Beaufort plaintexts
  forms    : raw, sha256 hex (lower/upper), double sha256 hex
  ciphers  : aes-{128,192,256}-cbc  x  KDF digest {md5, sha256}

Run: python sweep.py
"""

import hashlib
import itertools
import re
import sys
from base64 import b64decode

from Crypto.Cipher import AES

from pipeline import (README, SALPHASEION_BLOB, beaufort, evp_bytestokey,
                      openssl_dec_any, run, sha256, BEAUFORT_CT)

RAW = b64decode(SALPHASEION_BLOB)
assert RAW[:8] == b"Salted__"
SALT, CT = RAW[8:16], RAW[16:]

KEYLENS = (16, 24, 32)          # aes-128 / -192 / -256
DIGESTS = (hashlib.md5, hashlib.sha256)


def trial(pw_bytes):
    """Yield (keylen, digest_name, plaintext) for every parameter combination
    whose PKCS#7 padding is valid."""
    for klen in KEYLENS:
        for md in DIGESTS:
            key, iv = evp_bytestokey(pw_bytes, SALT, md, klen=klen)
            pt = AES.new(key, AES.MODE_CBC, iv).decrypt(CT)
            pad = pt[-1]
            if 1 <= pad <= 16 and pt[-pad:] == bytes([pad]) * pad:
                yield klen * 8, md().name, pt[:-pad]


def forms(s):
    """One candidate string -> the encodings the puzzle has actually used."""
    h = sha256(s)
    return (s, h, h.upper(), sha256(h))


def printable_score(b):
    if not b:
        return 0.0
    ok = sum(1 for c in b if 32 <= c < 127 or c in (9, 10, 13))
    return ok / len(b)


# --- candidate strings -------------------------------------------------------

CORE = ["matrixsumlist", "enter", "lastwordsbeforearchichoice", "thispassword",
        "yourlastcommand", "causality"]

EXTRA = [
    "theseedisplanted", "thematrixhasyou", "THEMATRIXHASYOU", "sha256", "shabef",
    "HASHTHETEXT", "hashthetext", "salphaseion", "SalPhaseIon", "cosmicduality",
    "halfandbetterhalf", "theflowerblossomsthroughwhatseemstobeaconcretesurface",
    "jacquefrescogiveitjustonesecondheisenbergsuncertaintyprinciple",
    "GSMGIO5BTCPUZZLECHALLENGE1GSMG1JC9wtdSwfwApgj2xcmJPAwx7prBe",
    "1GSMG1JC9wtdSwfwApgj2xcmJPAwx7prBe",
]


def candidate_strings():
    seen, out = set(), []

    def add(s):
        if s and s not in seen:
            seen.add(s)
            out.append(s)

    for s in CORE + EXTRA:
        add(s)

    # "our first hint is your last command" reads as an ordering instruction and
    # nobody knows which ordering, so sweep every one of them.
    for r in range(2, len(CORE) + 1):
        for p in itertools.permutations(CORE, r):
            add("".join(p))

    # Every word the puzzle ever put in front of a solver: the README itself,
    # plus the plaintexts this repo's pipeline decrypts out of it.
    corpus = README + "\n" + str(run()) + "\n" + beaufort(BEAUFORT_CT, "THEMATRIXHASYOU")
    for w in set(re.findall(r"[A-Za-z]{4,}", corpus)):
        add(w.lower())
        add(w)

    return out


if __name__ == "__main__":
    cands = candidate_strings()
    total = len(cands) * 4 * len(KEYLENS) * len(DIGESTS)
    print(f"{len(cands):,} strings x 4 forms x {len(KEYLENS)} keylens x "
          f"{len(DIGESTS)} digests = {total:,} trial decryptions\n")

    hits = []
    for i, s in enumerate(cands):
        if i % 1000 == 0:
            print(f"\r  {i:,}/{len(cands):,}", end="", file=sys.stderr, flush=True)
        for form_i, pw in enumerate(forms(s)):
            for bits, md, pt in trial(pw.encode()):
                hits.append((printable_score(pt), s, form_i, bits, md, pt))
    print(f"\r  {len(cands):,}/{len(cands):,}", file=sys.stderr)

    FORM = ("raw", "sha256", "SHA256-upper", "sha256(sha256)")
    hits.sort(reverse=True, key=lambda h: h[0])
    print(f"\n{len(hits)} survived PKCS#7 padding "
          f"(~{len(hits) / total * 100:.2f}%, random expectation ~0.4%)\n")
    for score, s, form_i, bits, md, pt in hits[:40]:
        print(f"  printable={score:.2f}  aes-{bits}  kdf={md}  "
              f"form={FORM[form_i]}  pw={s[:48]!r}")
        print(f"      {pt[:64]!r}")
