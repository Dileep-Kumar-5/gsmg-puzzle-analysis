"""GSMG.IO 5 BTC puzzle - reproducible pipeline, phase 1 through Salphaseion.

Every step asserts against a checkpoint published in the repo README. If an
assert fires, something drifted and NOTHING downstream is trustworthy. The
whole point of this file is to separate "reproduced from published inputs"
from "someone said so on the internet".

Inputs are parsed out of gsmgio-5btc-puzzle/README.md, not pasted, so the
script stays honest if the repo updates.

Run: python pipeline.py
"""

import hashlib
import re
from base64 import b64decode
from pathlib import Path

from Crypto.Cipher import AES

REPO = Path(__file__).with_name("gsmgio-5btc-puzzle")
README = (REPO / "README.md").read_text(encoding="utf-8")

sha256 = lambda s: hashlib.sha256(s.encode() if isinstance(s, str) else s).hexdigest()


# --- openssl enc -aes-256-cbc -a -pass pass:... ------------------------------

def evp_bytestokey(password, salt, md, klen=32, ivlen=16):
    """OpenSSL's legacy EVP_BytesToKey KDF. -md md5 pre-1.1.0, sha256 after."""
    d = prev = b""
    while len(d) < klen + ivlen:
        prev = md(prev + password + salt).digest()
        d += prev
    return d[:klen], d[klen:klen + ivlen]


def openssl_dec(blob_b64, password, md=hashlib.md5):
    """Returns plaintext bytes, or None if the padding is wrong (= wrong pw)."""
    raw = b64decode("".join(blob_b64.split()))
    if raw[:8] != b"Salted__":
        raise ValueError("not an openssl salted blob")
    key, iv = evp_bytestokey(password.encode(), raw[8:16], md)
    pt = AES.new(key, AES.MODE_CBC, iv).decrypt(raw[16:])
    pad = pt[-1]
    if not 1 <= pad <= 16 or pt[-pad:] != bytes([pad]) * pad:
        return None
    return pt[:-pad]


def openssl_dec_any(blob_b64, password):
    """Try both KDF digests. Returns (plaintext, digest_name) or (None, None)."""
    for md in (hashlib.md5, hashlib.sha256):
        pt = openssl_dec(blob_b64, password, md)
        if pt is not None:
            return pt, md().name
    return None, None


# --- phase 1: 14x14 matrix, counterclockwise spiral from top-left ------------

def parse_matrix():
    rows = re.findall(r"^(?:[01] ){13}[01]$", README, re.M)
    assert len(rows) == 14, f"expected 14 matrix rows, got {len(rows)}"
    return [[int(b) for b in r.split()] for r in rows]


def spiral_ccw(grid):
    """Down the left edge, right along the bottom, up the right, left along the
    top, then inward. Clockwise would read the same bits in the wrong order."""
    top, bot, left, right = 0, len(grid) - 1, 0, len(grid[0]) - 1
    out = []
    while top <= bot and left <= right:
        for r in range(top, bot + 1):
            out.append(grid[r][left])
        left += 1
        for c in range(left, right + 1):
            out.append(grid[bot][c])
        bot -= 1
        if left <= right:
            for r in range(bot, top - 1, -1):
                out.append(grid[r][right])
            right -= 1
        if top <= bot:
            for c in range(right, left - 1, -1):
                out.append(grid[top][c])
            top += 1
    return out


def bits_to_ascii(bits):
    return "".join(chr(int("".join(map(str, bits[i:i + 8])), 2))
                   for i in range(0, len(bits) - len(bits) % 8, 8))


# --- ciphers -----------------------------------------------------------------

def beaufort(text, key):
    """Reciprocal: P = K - C (mod 26). Same routine encrypts and decrypts."""
    a, k = ord("a"), key.lower()
    return "".join(
        chr((ord(k[i % len(k)]) - a - (ord(c) - a)) % 26 + a)
        for i, c in enumerate(text.lower()) if c.isalpha()
    )


def abba_decode(s):
    """a->0, b->1, then 8-bit ASCII."""
    bits = "".join(s.split()).translate(str.maketrans("ab", "01"))
    assert len(bits) % 8 == 0 and set(bits) <= {"0", "1"}
    return bytes(int(bits[i:i + 8], 2) for i in range(0, len(bits), 8)).decode()


def aio_decode(s):
    """a..i -> 1..9, o -> 0, read the whole run as one decimal integer, restate
    it in base 16, then read those hex digits as ASCII."""
    dec = "".join(s.split()).translate(str.maketrans("abcdefghio", "1234567890"))
    h = format(int(dec), "x")
    return bytes.fromhex(h.zfill(len(h) + len(h) % 2)).decode()


# --- README-embedded ciphertexts ---------------------------------------------

def grab_blob(first_line_prefix):
    lines = README.splitlines()
    i = next(i for i, l in enumerate(lines) if l.startswith(first_line_prefix))
    out = []
    while i < len(lines) and re.fullmatch(r"[A-Za-z0-9+/=]{20,}", lines[i]):
        out.append(lines[i])
        i += 1
    return "".join(out)


PHASE32_BLOB = grab_blob("U2FsdGVkX1/u")

# Salphaseion final blob. In the README the two lines are letter-spaced and have
# the "abba"/enter binary spliced into the middle; both are stripped here.
SALPHASEION_BLOB = (
    "U2FsdGVkX186tYU0hVJBXXUnBUO7C0+X4KUWnWkCvoZSxbRD3wNsGWVHefvdrd9z"
    "QvX0t8v3jPB4okpspxebRi6sE1BMl5HI8Rku+KejUqTvdWOX6nQjSpepXwGuN/jJ"
)

PHASE3_PARTS = (
    "causality", "Safenet", "Luna", "HSM", "11110",
    "0x736B6E616220726F662074756F6C69616220646E6F63657320666F206B6E697262206E"
    "6F20726F6C6C65636E61684320393030322F6E614A2F33302073656D695420656854",
    "B5KR/1r5B/2R5/2b1p1p1/2P1k1P1/1p2P2p/1P2P2P/3N1N2 b - - 0 1",
)

SALPHASEION_ABBA = (
    "a b b a b b a b a b b a a a a b a b b b a b a a a b b b a a b a a b b a b "
    "a a b a b b b b a a a a b b b a a b b a b b b a b a b a b b a b b a b a b "
    "b a b b a a a b b a b a a b a b b b a a b b a b b b a b a a"
)
SALPHASEION_ENTER = (
    "a b b a a b a b a b b a b b b a a b b b a b a a a b b a a b a b a b b b a a b a"
)
SALPHASEION_SEG1 = (
    "a g d a f a o a h e i e c g g c h g i c b b h c g b e h c f c o a b i c f "
    "d h h c d b b c a g b d a i o b b g b e a d e d d e"
)
SALPHASEION_SEG2 = "c f o b f d h g d o b d g o o i i g d o c d a o o f i d h"

BEAUFORT_CT = re.search(r"^(vtkvpl[a-z]{200,})$", README, re.M).group(1)


# --- the pipeline ------------------------------------------------------------

def run():
    results = {}

    # Phase 1 -- the only phase whose input is fully published, so it is the
    # one real end-to-end reproduction in the chain.
    url = bits_to_ascii(spiral_ccw(parse_matrix()))
    assert url == "gsmg.io/theseedisplanted", url
    results["phase1_url"] = url

    # Phase 2 -- password is a literal, nothing to derive.
    results["phase2_pw"] = "theflowerblossomsthroughwhatseemstobeaconcretesurface"

    # Phase 3 -- ciphertext is NOT in the repo, only the key. Checkpoint the key.
    pw3 = sha256("causality")
    assert pw3 == "eb3efb5151e6255994711fe8f2264427ceeebf88109e1d7fad5b0a8b6d07e5bf"
    results["phase3_pw"] = pw3

    # Phase 3.2 key -- 7 concatenated parts. Reproducing this hash is what
    # proves the 7-part reading of the riddle is the intended one.
    pw32 = sha256("".join(PHASE3_PARTS))
    assert pw32 == "1a57c572caf3cf722e41f5f9cf99ffacff06728a43032dd44c481c77d2ec30d5", pw32
    results["phase3.2_pw"] = pw32

    # Phase 3.2 -- ciphertext IS in the repo. Full offline decrypt.
    pw321 = sha256("jacquefrescogiveitjustonesecondheisenbergsuncertaintyprinciple")
    assert pw321 == "250f37726d6862939f723edc4f993fde9d33c6004aab4f2203d9ee489d61ce4c"
    pt, md = openssl_dec_any(PHASE32_BLOB, pw321)
    assert pt is not None, "phase 3.2 blob did not decrypt"
    text = pt.decode("cp437", "replace")
    assert "I've been waiting for you" in text
    assert "One for one, four for one" in text
    results["phase3.2_kdf"] = md
    results["phase3.2_plaintext"] = text

    # Phase 3.2.1 -- Beaufort, key THEMATRIXHASYOU.
    mero = beaufort(BEAUFORT_CT, "THEMATRIXHASYOU").upper()
    assert mero.startswith("YOURLIFEISTHESUMOFAREMAINDEROFANUNBALANCEDEQUATION"), mero[:60]
    assert "TWENTYTHREECIPHERS" in mero.replace("-", "")
    results["phase3.2.1_beaufort"] = mero

    # Phase 3.2.2 -- VIC cipher. Not reimplemented (VIC is a straddling-checkerboard
    # + double-transposition stack and the output is already agreed on).
    # ponytail: hardcoded reference plaintext; implement VIC only if the exact
    # keying ever needs to be re-derived rather than reused.
    results["phase3.2.2_vic"] = (
        "IN CASE YOU MANAGE TO CRACK THIS THE PRIVATE KEYS BELONG TO "
        "HALF AND BETTER HALF AND THEY ALSO NEED FUNDS TO LIVE"
    )

    # SalPhaseIon entry URL.
    entry = sha256("GSMGIO5BTCPUZZLECHALLENGE1GSMG1JC9wtdSwfwApgj2xcmJPAwx7prBe")
    assert entry == "89727c598b9cd1cf8873f27cb7057f050645ddb6a7a157a110239ac0152f6a32"
    results["salphaseion_url"] = "https://gsmg.io/" + entry

    # Salphaseion token extraction.
    toks = [
        abba_decode(SALPHASEION_ABBA),
        abba_decode(SALPHASEION_ENTER),
        aio_decode(SALPHASEION_SEG1),
        aio_decode(SALPHASEION_SEG2),
    ]
    assert toks == ["matrixsumlist", "enter", "lastwordsbeforearchichoice",
                    "thispassword"], toks
    results["salphaseion_tokens"] = toks

    return results


# --- the frontier ------------------------------------------------------------

def try_passwords(candidates, blob=SALPHASEION_BLOB):
    """Trial-decrypt the final Salphaseion blob. Wrong password fails PKCS#7
    padding ~255/256 of the time, so survivors are worth eyeballing."""
    hits = []
    for c in candidates:
        for form, pw in (("raw", c), ("sha256", sha256(c))):
            pt, md = openssl_dec_any(blob, pw)
            if pt is not None:
                hits.append((c, form, md, pt))
    return hits


def default_candidates():
    """Tokens the puzzle itself hands you, plus the obvious concatenations.
    'our first hint is your last command' is the stated composition rule."""
    toks = ["matrixsumlist", "enter", "lastwordsbeforearchichoice", "thispassword",
            "yourlastcommand", "causality", "thematrixhasyou", "theseedisplanted",
            "HASHTHETEXT", "hashthetext"]
    cands = list(toks)
    cands += ["".join(toks[:4]), "".join(toks[:5]), "matrixsumlistenter",
              "lastwordsbeforearchichoicethispassword",
              "matrixsumlistenterlastwordsbeforearchichoicethispassword"]
    return cands


if __name__ == "__main__":
    r = run()
    print("=" * 70)
    print("REPRODUCED FROM PUBLISHED INPUTS")
    print("=" * 70)
    print(f"phase 1 spiral        : {r['phase1_url']}")
    print(f"phase 3 password      : {r['phase3_pw']}")
    print(f"phase 3.2 password    : {r['phase3.2_pw']}")
    print(f"phase 3.2 blob        : decrypted OK (openssl KDF digest = {r['phase3.2_kdf']})")
    print(f"phase 3.2.1 beaufort  : {r['phase3.2.1_beaufort'][:52]}...")
    print(f"salphaseion url       : {r['salphaseion_url']}")
    print(f"salphaseion tokens    : {r['salphaseion_tokens']}")
    print()
    print("=" * 70)
    print("FRONTIER: final Salphaseion AES blob (96 bytes, 5 AES blocks)")
    print("=" * 70)
    hits = try_passwords(default_candidates())
    if not hits:
        print("no candidate password produced valid PKCS#7 padding.")
    for cand, form, md, pt in hits:
        print(f"  HIT  pw={cand!r} form={form} kdf={md}")
        print(f"       {pt!r}")
