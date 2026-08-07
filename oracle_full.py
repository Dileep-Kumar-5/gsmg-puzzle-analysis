"""Exhaustive key search over faed: every base-9 mapping, every window.

oracle_aligned.py already settled dbbi completely (37 bytes, 6 windows, all
362,880 mappings) and covered faed at every 16-byte boundary. This closes the
remaining 181 offsets.

Why the misaligned offsets are worth the compute: converting a base-9 digit
string to binary does not respect byte boundaries. Where a key would land in the
decoded output depends on the total digit count, which is arbitrary. So there is
no reason to expect it at a multiple of 16, and "aligned" was the wrong prior in
the first place.

Single-threaded this is ~4 hours at the measured 4,800 checks/sec. Split across
workers it is ~25 minutes, so it is parallelised by chunking the permutation
space. Each worker builds its own oracle state; coincurve objects do not survive
pickling.

Byte width is computed exactly -- 570 base-9 digits need 226 bytes -- and the
result is left-padded to it, so an offset means the same thing in every worker.

Run: python oracle_full.py
"""

import multiprocessing as mp
import re
import sys
from itertools import islice, permutations

BASE = 9
WORKERS = max(1, mp.cpu_count() - 2)
CHUNK = 4000


def byte_width(nsyms, base=BASE):
    return ((base ** nsyms - 1).bit_length() + 7) // 8


def _init():
    """Per-worker setup: the oracle cannot be pickled across processes."""
    global _check, _run, _syms, _width, _offsets
    import re as _re
    from bigrun import get_runs
    from oracle import check as chk

    runs = get_runs()
    m = _re.search(r"[ab]{40,}", runs[0])
    faed = runs[0][m.end():]
    _check = chk
    _run = faed
    _syms = sorted(set(faed))
    _width = byte_width(len(faed))
    _offsets = list(range(0, _width - 31))


def _work(perms):
    for perm in perms:
        digit_of = dict(zip(_syms, perm))
        n = 0
        for c in _run:
            n = n * BASE + digit_of[c]
        b = n.to_bytes(_width, "big")
        for o in _offsets:
            if _check(b[o:o + 32]):
                return (perm, o, b[o:o + 32].hex())
    return None


def chunks(it, size):
    it = iter(it)
    while True:
        block = list(islice(it, size))
        if not block:
            return
        yield block


def main():
    from bigrun import get_runs

    runs = get_runs()
    m = re.search(r"[ab]{40,}", runs[0])
    faed = runs[0][m.end():]
    width = byte_width(len(faed))
    nwin = width - 31
    total = 362880

    print(f"faed: {len(faed)} symbols -> {width} bytes, {nwin} windows")
    print(f"  {total:,} mappings x {nwin} windows = {total * nwin:,} checks")
    print(f"  {WORKERS} workers, chunks of {CHUNK}\n")

    done = 0
    with mp.Pool(WORKERS, initializer=_init) as pool:
        for res in pool.imap_unordered(
                _work, chunks(permutations(range(BASE), len(set(faed))), CHUNK)):
            done += CHUNK
            if res:
                perm, off, key = res
                print(f"\n\n  *** PRIZE KEY FOUND ***")
                print(f"  mapping={perm} offset={off}")
                print(f"  key={key}")
                pool.terminate()
                return
            pct = min(100.0, done / total * 100)
            print(f"\r  {min(done, total):,}/{total:,} ({pct:.1f}%)",
                  end="", file=sys.stderr, flush=True)
    print(f"\r  {total:,}/{total:,} done{' ' * 20}", file=sys.stderr)
    print("\nNo window of any base-9 decoding of faed is the prize key.")
    print("Combined with oracle_aligned.py, dbbi and faed are both exhausted.")


if __name__ == "__main__":
    main()
