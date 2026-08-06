"""Decrypt the archive-recovered blobs with the passwords the pipeline derives.

The repo README publishes the phase 2/3 *plaintexts* but not their ciphertexts,
so until now there was no way to check the published passwords actually work.
These blobs came off the archived pages, so now there is.

Run: python decrypt_recovered.py
"""

import hashlib
from base64 import b64decode
from pathlib import Path

from pipeline import PHASE32_BLOB, SALPHASEION_BLOB, openssl_dec_any, run, sha256

CORPUS = Path(__file__).with_name("corpus")


def main():
    r = run()
    passwords = {
        "sha256(causality)": r["phase3_pw"],
        "sha256(7 parts)": r["phase3.2_pw"],
        "sha256(jacquefresco...)": sha256(
            "jacquefrescogiveitjustonesecondheisenbergsuncertaintyprinciple"),
    }

    print(f"repo README phase3.2 blob: {len(b64decode(PHASE32_BLOB))} bytes")
    print(f"repo README salphaseion blob: {len(b64decode(SALPHASEION_BLOB))} bytes\n")

    for f in sorted(CORPUS.glob("blob_*.b64")):
        b64 = f.read_text(encoding="utf-8")
        raw = b64decode(b64)
        same = ""
        if b64 == PHASE32_BLOB:
            same = "  == repo phase3.2 blob"
        elif b64 == SALPHASEION_BLOB:
            same = "  == repo salphaseion blob"
        print("=" * 72)
        print(f"{f.name}  ({len(raw) - 16} bytes ciphertext){same}")
        print("=" * 72)
        hit = False
        for label, pw in passwords.items():
            pt, md = openssl_dec_any(b64, pw)
            if pt is None:
                continue
            hit = True
            text = pt.decode("cp437", "replace")
            print(f"  DECRYPTS with {label} (kdf={md}), {len(pt)} bytes:\n")
            print("  " + text[:1500].replace("\n", "\n  "))
            if len(text) > 1500:
                print(f"  ... [{len(text) - 1500} more bytes]")
            out = CORPUS / (f.stem + ".txt")
            out.write_bytes(pt)
            print(f"\n  saved {out.name}")
            break
        if not hit:
            print("  no known password decrypts this blob")
        print()


if __name__ == "__main__":
    main()
