"""Test dbbi (and faed) as book-cipher indices into the puzzle's own plaintexts.

Why this text: the SalPhaseIon page hands you the token
"lastwordsbeforearchichoice", and the phase 3.2.1 Beaufort plaintext IS the
Architect's speech, ending in the choice it describes. A token that names a
passage, sitting beside a run of small integers, is the shape of a book cipher.

Single digits 1-9 cannot address a 1,100-character passage directly, so the
constructions that can are:

  WALK       cumulative steps through the characters (or the words)
  GROUPED    digits taken 2 or 3 at a time as absolute offsets
  WORDSTEP   cumulative steps through the word list, taking each word's
             first letter -- the classic newspaper book cipher

Every extraction is scored for englishness against the same reference the rest
of this session uses (real English ~0.44), and every family is run again with a
SHUFFLED copy of the index run as a control. A result only counts if it beats
its own control.

Run: python bookcipher.py
"""

import random
import re

from bigrun import get_runs, rejoin
from pipeline import run as pipeline_run
from vic import englishness

ALPHA = "abcdefghi"


def pieces():
    runs = get_runs()
    m = re.search(r"[ab]{40,}", runs[0])
    return runs[0][:m.start()], runs[0][m.end():]


def vals(run, base0):
    off = 0 if base0 else 1
    return [ALPHA.index(c) + off for c in run]


def targets():
    r = pipeline_run()
    out = {
        "architect (beaufort)": r["phase3.2.1_beaufort"],
        "vic line": r["phase3.2.2_vic"],
        "phase3.2 plaintext": r["phase3.2_plaintext"],
    }
    from pathlib import Path
    for f in sorted((Path(__file__).with_name("corpus")).glob("blob_*.txt")):
        out[f.stem] = f.read_bytes().decode("cp437", "replace")
    return out


def letters(text):
    return re.sub(r"[^A-Za-z]", "", text).upper()


def words(text):
    return re.findall(r"[A-Za-z]+", text.upper())


def extract(dv, text, mode):
    L, W = letters(text), words(text)
    out = []
    if mode == "walk-char":
        pos = 0
        for s in dv:
            pos = (pos + max(1, s)) % len(L)
            out.append(L[pos])
    elif mode == "walk-char-0":
        pos = 0
        for s in dv:
            pos = (pos + s) % len(L)
            out.append(L[pos])
    elif mode == "walk-word":
        pos = 0
        for s in dv:
            pos = (pos + max(1, s)) % len(W)
            out.append(W[pos][0])
    elif mode == "walk-word-full":
        pos = 0
        for s in dv:
            pos = (pos + max(1, s)) % len(W)
            out.append(W[pos])
        return " ".join(out)
    elif mode == "direct-word":
        for s in dv:
            out.append(W[s % len(W)][0])
    elif mode.startswith("group"):
        n = int(mode[-1])
        for i in range(0, len(dv) - n + 1, n):
            idx = int("".join(str(d) for d in dv[i:i + n]))
            out.append(L[idx % len(L)])
    else:
        return ""
    return "".join(out)


MODES = ["walk-char", "walk-char-0", "walk-word", "walk-word-full",
         "direct-word", "group2", "group3"]


def sweep(index_run, label, results):
    for b0 in (True, False):
        dv = vals(index_run, b0)
        tag = "0..8" if b0 else "1..9"
        for tname, text in targets().items():
            for mode in MODES:
                try:
                    out = extract(dv, text, mode)
                except Exception:
                    continue
                if len(out) < 8:
                    continue
                results.append((englishness(out),
                                f"{label} [{tag}] -> {tname} | {mode}", out))
            # Reversed index run, in case it reads the other way.
            for mode in ("walk-char", "walk-word"):
                out = extract(dv[::-1], text, mode)
                results.append((englishness(out),
                                f"{label} rev [{tag}] -> {tname} | {mode}",
                                out))


def main():
    dbbi, faed = pieces()
    print(f"dbbi {len(dbbi)}, faed {len(faed)}")
    for tname, text in targets().items():
        print(f"  target {tname:<22} {len(letters(text)):>5} letters, "
              f"{len(words(text)):>4} words")
    print()

    real = []
    sweep(dbbi, "dbbi", real)
    sweep(faed, "faed", real)
    real.sort(reverse=True, key=lambda r: r[0])

    ctrl = []
    for name, run in (("dbbi", dbbi), ("faed", faed)):
        sh = list(run)
        random.Random(23).shuffle(sh)
        sweep("".join(sh), f"CONTROL-{name}", ctrl)
    ctrl.sort(reverse=True, key=lambda r: r[0])

    print("=" * 72)
    print(f"{len(real)} real extractions | real English = 0.44")
    print("=" * 72)
    for sc, label, out in real[:12]:
        flag = "   <<< ENGLISH" if sc > 0.35 else ""
        print(f"  {sc:.3f}  {label}{flag}")
        print(f"         {out[:96]}")

    print()
    print("=" * 72)
    print(f"CONTROL ceiling from {len(ctrl)} shuffled-index extractions")
    print("=" * 72)
    for sc, label, out in ctrl[:5]:
        print(f"  {sc:.3f}  {label}")
        print(f"         {out[:96]}")

    print()
    best_real = real[0][0] if real else 0
    best_ctrl = ctrl[0][0] if ctrl else 0
    print(f"best real {best_real:.3f} vs best control {best_ctrl:.3f} -> "
          f"{'SIGNAL' if best_real > best_ctrl * 1.5 else 'NO SEPARATION'}")


if __name__ == "__main__":
    main()
