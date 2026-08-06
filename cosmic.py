"""Attack the Cosmic Duality blob recovered from the archived SalPhaseIon page.

This ciphertext is NOT in the puzzlehunt repo README -- only the 96-byte
SalPhaseIon blob is. It comes from the Wayback snapshot of
gsmg.io/89727c598b9c...f6a32 (see fetch_wayback.py), and its size is the reason
it matters:

    1344 bytes decoded - 16 (Salted__ + salt) = 1328 bytes ciphertext
    1328 - 1 byte of PKCS#7 padding            = 1327 bytes plaintext

1327 is exactly the size issue #99 reports for `cosmic_decrypted.bin`. So this
is the source of that artifact, and sha256 == 4f7a1e4e... is a hard oracle: any
correct decryption must produce it.

Three things get tested here:
  1. can PR #68's master key be reproduced as an XOR of SHA256s, as claimed?
  2. does that master key decrypt the blob, as a password or as a raw AES key?
  3. does any password in the sweep corpus decrypt it?

Run: python cosmic.py
"""

import hashlib
import itertools
import re
import sys
from base64 import b64decode
from pathlib import Path

from Crypto.Cipher import AES

from pipeline import evp_bytestokey, sha256
from sweep import candidate_strings, forms, printable_score

PAGE = max(Path(__file__).with_name("corpus").glob("wb_*salphaseion*.html"),
           key=lambda p: p.stat().st_size)

# PR #68's claims, treated as unverified until reproduced here.
MASTER_KEY_HEX = "a795de117e472590e572dc193130c763e3fb555ee5db9d34494e156152e50735"
EXPECTED_SHA256 = "4f7a1e4efe4bf6c5581e32505c019657cb7b030e90232d33f011aca6a5e9c081"

KEYLENS = (16, 24, 32)
DIGESTS = (hashlib.md5, hashlib.sha256)


def load_blob():
    html = PAGE.read_text(encoding="utf-8", errors="replace")
    # Second textarea on the page; the first is the SalPhaseIon letter-spaced text.
    areas = re.findall(r"<textarea[^>]*>(.*?)</textarea>", html, re.S)
    for a in areas:
        body = "".join(a.split())
        if body.startswith("U2FsdGVkX1") and len(body) > 200:
            return body
    raise SystemExit("Cosmic Duality blob not found in the archived page")


BLOB = load_blob()
RAW = b64decode(BLOB)
assert RAW[:8] == b"Salted__", "not an openssl salted blob"
SALT, CT = RAW[8:16], RAW[16:]


def unpad(pt):
    pad = pt[-1]
    if 1 <= pad <= 16 and pt[-pad:] == bytes([pad]) * pad:
        return pt[:-pad]
    return None


def try_password(pw_bytes):
    for klen in KEYLENS:
        for md in DIGESTS:
            key, iv = evp_bytestokey(pw_bytes, SALT, md, klen=klen)
            pt = unpad(AES.new(key, AES.MODE_CBC, iv).decrypt(CT))
            if pt is not None:
                yield f"aes-{klen * 8}/{md().name}", pt


def try_rawkey(key):
    """Key used directly, skipping the KDF -- PR #68 describes 'bypassing the
    legacy KDF', so the IV has to come from somewhere else."""
    ivs = {
        "salt+salt": SALT * 2,
        "zeros": bytes(16),
        "key[:16]": key[:16],
        "sha256(key)[:16]": hashlib.sha256(key).digest()[:16],
        "ct[:16]": CT[:16],
    }
    for name, iv in ivs.items():
        for mode, cipher in (("cbc", AES.new(key, AES.MODE_CBC, iv)),
                             ("ecb", AES.new(key, AES.MODE_ECB))):
            pt = unpad(cipher.decrypt(CT))
            if pt is not None:
                yield f"raw-{mode}/iv={name}", pt


def report(tag, how, pt):
    h = hashlib.sha256(pt).hexdigest()
    mark = "  <<< MATCHES ISSUE #99" if h == EXPECTED_SHA256 else ""
    print(f"  {tag} [{how}] len={len(pt)} printable={printable_score(pt):.2f}{mark}")
    print(f"      sha256={h}")
    print(f"      {pt[:72]!r}")
    return h == EXPECTED_SHA256


# --- 1. is the master key reproducible at all? -------------------------------

def xor_search(target_hex, pool, sizes=range(2, 9)):
    """PR #68 says the master key is 'a reconstructed XOR Master Key derived
    from 7 thematic tokens'. XOR is commutative, so this is a subset search,
    not a permutation search."""
    target = bytes.fromhex(target_hex)
    digests = {t: hashlib.sha256(t.encode()).digest() for t in pool}
    for n in sizes:
        for combo in itertools.combinations(pool, n):
            acc = bytes(32)
            for t in combo:
                acc = bytes(a ^ b for a, b in zip(acc, digests[t]))
            if acc == target:
                return combo
    return None


POOL = ["matrixsumlist", "enter", "lastwordsbeforearchichoice", "thispassword",
        "yourlastcommand", "causality", "thematrixhasyou", "theseedisplanted",
        "Safenet", "Luna", "HSM", "11110", "secondanswer", "shabef", "sha256",
        "hashthetext", "HASHTHETEXT", "salphaseion", "cosmicduality", "enterthe",
        "thispasswordis", "firsthint", "ourfirsthint", "halfandbetterhalf"]


def main():
    print(f"Cosmic Duality blob: {len(RAW)} bytes decoded, {len(CT)} bytes ciphertext")
    print(f"  max plaintext {len(CT) - 1} bytes (issue #99 reports 1327)")
    print(f"  blob sha256 {hashlib.sha256(RAW).hexdigest()}\n")

    print("=" * 72)
    print("1. reproduce PR #68 master key as XOR of SHA256 digests")
    print("=" * 72)
    combo = xor_search(MASTER_KEY_HEX, POOL)
    if combo:
        print(f"  REPRODUCED from {len(combo)} tokens: {combo}")
    else:
        print(f"  NOT reproducible from a {len(POOL)}-token pool, subset size 2-8.")
        print("  PR #68's master key has no published derivation that checks out.")

    print()
    print("=" * 72)
    print("2. master key against the blob")
    print("=" * 72)
    found = False
    key = bytes.fromhex(MASTER_KEY_HEX)
    for how, pt in try_rawkey(key):
        found |= report("rawkey", how, pt)
    for form_name, pw in (("hex", MASTER_KEY_HEX), ("HEX", MASTER_KEY_HEX.upper())):
        for how, pt in try_password(pw.encode()):
            found |= report(f"pw/{form_name}", how, pt)
    for how, pt in try_password(key):
        found |= report("pw/rawbytes", how, pt)
    if not found:
        print("  no valid padding from any master-key variant")

    print()
    print("=" * 72)
    print("3. password sweep against the blob")
    print("=" * 72)
    cands = candidate_strings()
    print(f"  {len(cands):,} strings x 4 forms x {len(KEYLENS)}x{len(DIGESTS)} params")
    hits = []
    for i, s in enumerate(cands):
        if i % 500 == 0:
            print(f"\r  {i:,}/{len(cands):,}", end="", file=sys.stderr, flush=True)
        for pw in forms(s):
            for how, pt in try_password(pw.encode()):
                hits.append((printable_score(pt), s, how, pt))
    print(f"\r  {len(cands):,}/{len(cands):,}", file=sys.stderr)

    hits.sort(reverse=True, key=lambda h: h[0])
    print(f"\n  {len(hits)} survived PKCS#7 padding")
    for score, s, how, pt in hits[:15]:
        h = hashlib.sha256(pt).hexdigest()
        star = "  <<< MATCHES ISSUE #99" if h == EXPECTED_SHA256 else ""
        print(f"  printable={score:.2f} len={len(pt)} [{how}] pw={s[:40]!r}{star}")
        print(f"      {pt[:64]!r}")


if __name__ == "__main__":
    main()
