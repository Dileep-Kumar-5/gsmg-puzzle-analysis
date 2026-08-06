"""Decode the undecoded bulk of the SalPhaseIon textarea.

The repo README decodes four small pieces of the first textarea (the two "abba"
binary runs, and the two z-delimited a-i/o segments) and explicitly says "only
some are currently decoded". The two LARGE a-i runs -- hundreds of characters,
the bulk of the payload -- are left alone.

The transform that works on the small segments is:
    a..i -> 1..9, o -> 0, read the whole run as one decimal integer,
    restate that integer in base 16, read the hex digits as ASCII

which is what produced "lastwordsbeforearchichoice" and "thispassword". This
applies the same transform, and its variants, to the big runs.

Run: python salpha.py
"""

import re
from collections import Counter
from pathlib import Path

PAGE = (Path(__file__).with_name("corpus")
        / "wb_gsmg_salphaseion_20260405154227.html")


def first_textarea():
    html = PAGE.read_text(encoding="utf-8", errors="replace")
    return re.findall(r"<textarea[^>]*>(.*?)</textarea>", html, re.S)[0]


def letters_only(s):
    return "".join(s.split())


def split_runs(seq):
    """The payload is: BIG1 [abba] BIG2 z SEG1 z SEG2 z <plain english>.
    'z' is the separator; an all-{a,b} stretch is a binary run."""
    parts = seq.split("z")
    return parts


def to_digits(run, mapping="abcdefghio", digits="1234567890"):
    return run.translate(str.maketrans(mapping, digits))


def dec_to_ascii(dec):
    """Decimal integer -> base 16 -> ASCII, the README's transform."""
    h = format(int(dec), "x")
    h = h.zfill(len(h) + len(h) % 2)
    return bytes.fromhex(h)


def abba_to_ascii(run):
    bits = run.translate(str.maketrans("ab", "01"))
    n = len(bits) - len(bits) % 8
    return bytes(int(bits[i:i + 8], 2) for i in range(0, n, 8))


def printable(b):
    return sum(1 for c in b if 32 <= c < 127) / len(b) if b else 0


def report(label, data):
    pr = printable(data)
    flag = "  <<< READABLE" if pr > 0.85 else ""
    print(f"    {label}: {len(data)} bytes, printable={pr:.2f}{flag}")
    print(f"      {data[:200]!r}")


def main():
    seq = letters_only(first_textarea())
    print(f"first textarea: {len(seq)} chars")
    print(f"alphabet: {''.join(sorted(set(seq)))}\n")

    # The base64 blob and the trailing english are not part of the a-i payload.
    payload = seq.split("shabef")[0]
    print(f"a-i payload before 'shabef': {len(payload)} chars")
    print(f"counts: {dict(sorted(Counter(payload).items()))}\n")

    runs = split_runs(payload)
    print(f"{len(runs)} z-delimited run(s)\n")

    for i, run in enumerate(runs):
        chars = set(run)
        print(f"run {i}: {len(run)} chars, alphabet {''.join(sorted(chars))}")

        if chars <= {"a", "b"}:
            print("    pure {a,b} -> binary")
            report("abba", abba_to_ascii(run))
            print()
            continue

        # A big run may have an abba stretch embedded in it; the README's own
        # decode of run 0 depends on pulling that out first.
        for m in re.finditer(r"[ab]{40,}", run):
            print(f"    embedded binary at {m.start()}..{m.end()}")
            report("  abba", abba_to_ascii(m.group(0)))
        rest = re.sub(r"[ab]{40,}", "|", run)
        for j, piece in enumerate(rest.split("|")):
            if not piece:
                continue
            print(f"    piece {j}: {len(piece)} chars")
            try:
                report("      a-i/o -> dec -> hex -> ascii",
                       dec_to_ascii(to_digits(piece)))
            except Exception as e:
                print(f"      decode failed: {e}")
            # Straight a1z26 as a control: the README notes it does not work,
            # so a readable result here would be a surprise worth seeing.
            try:
                alt = "".join(chr(ord(c) - ord("a") + ord("0")) for c in piece)
                report("      a=0 base-10 digits -> hex -> ascii", dec_to_ascii(alt))
            except Exception:
                pass
        print()


if __name__ == "__main__":
    main()
