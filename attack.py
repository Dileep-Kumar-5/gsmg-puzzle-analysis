"""Large-scale password attack on the two unsolved GSMG blobs.

Two things make this much stronger than the earlier sweeps:

1. FAST PRE-FILTER. PKCS#7 padding lives entirely in the last block, and CBC
   decryption of the last block needs only the last two ciphertext blocks:
       P_n = D_k(C_n) XOR C_{n-1}
   So a candidate is rejected with ONE AES block operation instead of 83. Full
   decryption only happens for the ~1/256 that survive.

2. A REAL SIGNAL. The Cosmic Duality blob is 1328 bytes. If it decrypts to
   text, the printable ratio is ~0.99 against ~0.37 for noise -- an enormous
   margin. The earlier 96-byte blob gave no such leverage.

The candidate space treats the SalPhaseIon tokens as POINTERS rather than
literal passwords. "lastwordsbeforearchichoice" reads as an instruction to find
the last words before the Architect's choice, and the Beaufort plaintext IS the
Architect's speech -- so every phrase of every recovered plaintext gets swept.

Run: python attack.py
"""

import hashlib
import itertools
import re
import sys
from base64 import b64decode
from pathlib import Path

from Crypto.Cipher import AES

from cosmic import BLOB as COSMIC_B64
from pipeline import (SALPHASEION_BLOB, evp_bytestokey, parse_matrix, run,
                      sha256)

CORPUS = Path(__file__).with_name("corpus")
KEYLENS = (16, 24, 32)
DIGESTS = (hashlib.md5, hashlib.sha256)


class Blob:
    def __init__(self, name, b64):
        raw = b64decode("".join(b64.split()))
        assert raw[:8] == b"Salted__"
        self.name = name
        self.salt, self.ct = raw[8:16], raw[16:]
        self.penult = self.ct[-32:-16]
        self.last = self.ct[-16:]

    def pad_ok(self, key):
        """One AES block: recover only the final plaintext block."""
        d = AES.new(key, AES.MODE_ECB).decrypt(self.last)
        tail = bytes(a ^ b for a, b in zip(d, self.penult))
        pad = tail[-1]
        return 1 <= pad <= 16 and tail[-pad:] == bytes([pad]) * pad

    def full(self, key, iv):
        pt = AES.new(key, AES.MODE_CBC, iv).decrypt(self.ct)
        pad = pt[-1]
        if 1 <= pad <= 16 and pt[-pad:] == bytes([pad]) * pad:
            return pt[:-pad]
        return None


def printable_ratio(b):
    if not b:
        return 0.0
    return sum(1 for c in b if 32 <= c < 127 or c in (9, 10, 13)) / len(b)


# --- candidate corpus ---------------------------------------------------------

def norm(s):
    """The puzzle's own convention: lowercase, whitespace and punctuation
    stripped ('connected enf' in its wording)."""
    return re.sub(r"[^a-z0-9]", "", s.lower())


def phrases(text, max_words=12):
    """Every contiguous run of 1..max_words words, normalised. Sentence and line
    splits fall out of this automatically."""
    words = re.findall(r"[A-Za-z0-9']+", text)
    out = set()
    for n in range(1, max_words + 1):
        for i in range(len(words) - n + 1):
            p = norm(" ".join(words[i:i + n]))
            if 3 <= len(p) <= 120:
                out.add(p)
    return out


def corpus_texts():
    r = run()
    texts = {
        "beaufort": r["phase3.2.1_beaufort"],
        "vic": r["phase3.2.2_vic"],
        "phase3.2": r["phase3.2_plaintext"],
    }
    for f in CORPUS.glob("blob_*.txt"):
        texts[f.stem] = f.read_bytes().decode("cp437", "replace")
    return texts


def matrix_strings():
    m = parse_matrix()
    rows = [sum(x) for x in m]
    cols = [sum(c) for c in zip(*m)]
    flat = "".join(str(b) for r in m for b in r)
    out = {
        "".join(map(str, rows)), "".join(map(str, cols)),
        "".join(map(str, rows + cols)), "".join(map(str, cols + rows)),
        "".join(map(str, sorted(rows))), str(sum(rows)),
        "-".join(map(str, rows)), ",".join(map(str, rows)),
        flat,
    }
    return {s for s in out if s}


TOKENS = ["matrixsumlist", "enter", "lastwordsbeforearchichoice", "thispassword",
          "yourlastcommand", "secondanswer", "causality", "thematrixhasyou",
          "theseedisplanted", "hashthetext"]


def candidates():
    seen = set()

    def add(s):
        if s and 3 <= len(s) <= 200 and s not in seen:
            seen.add(s)
            return True
        return False

    for s in TOKENS:
        add(s)
    for s in matrix_strings():
        add(s)
    # Token orderings -- "our first hint is your last command" is an ordering
    # instruction whose referent is unknown, so sweep all of them.
    for n in range(2, 6):
        for p in itertools.permutations(TOKENS[:6], n):
            add("".join(p))
    for name, text in corpus_texts().items():
        for p in phrases(text):
            add(p)
    return list(seen)


def forms(s):
    """Encodings the puzzle has demonstrably used, plus the raw-bytes-of-a-hash
    trick that produced the PR #68 result."""
    h = sha256(s)
    yield s.encode()
    yield h.encode()
    yield h.upper().encode()
    yield sha256(h).encode()
    yield bytes.fromhex(h)


def main():
    blobs = [Blob("cosmic-1328", COSMIC_B64), Blob("salphaseion-96", SALPHASEION_BLOB)]
    cands = candidates()
    total = len(cands) * 5 * len(KEYLENS) * len(DIGESTS)
    print(f"{len(cands):,} candidate strings")
    print(f"{total:,} (key, params) pairs per blob, pre-filtered on one AES block\n")

    for blob in blobs:
        print("=" * 72)
        print(f"{blob.name}: {len(blob.ct)} bytes ciphertext")
        print("=" * 72)
        hits, checked = [], 0
        for i, s in enumerate(cands):
            if i % 2000 == 0:
                print(f"\r  {i:,}/{len(cands):,}  hits={len(hits)}",
                      end="", file=sys.stderr, flush=True)
            for pw in forms(s):
                for klen in KEYLENS:
                    for md in DIGESTS:
                        key, iv = evp_bytestokey(pw, blob.salt, md, klen=klen)
                        checked += 1
                        if not blob.pad_ok(key):
                            continue
                        pt = blob.full(key, iv)
                        if pt is None:
                            continue
                        pr = printable_ratio(pt)
                        hits.append((pr, s, pw[:16], klen * 8, md().name, pt))
        print(f"\r  {len(cands):,}/{len(cands):,}  ", file=sys.stderr)

        hits.sort(reverse=True, key=lambda h: h[0])
        rate = len(hits) / checked * 100 if checked else 0
        print(f"  {checked:,} trials, {len(hits)} passed padding "
              f"({rate:.3f}%, random ~0.39%)")
        real = [h for h in hits if h[0] > 0.90]
        if real:
            print(f"\n  *** {len(real)} DECRYPTION(S) THAT LOOK LIKE TEXT ***")
            for pr, s, pw, bits, md, pt in real:
                print(f"  printable={pr:.3f} aes-{bits} kdf={md} pw={s[:60]!r}")
                print(f"  {pt[:600]!r}\n")
        else:
            best = hits[0][0] if hits else 0
            print(f"  best printable ratio {best:.3f} -- all noise "
                  f"(text would be >0.95)")
        print()


if __name__ == "__main__":
    main()
