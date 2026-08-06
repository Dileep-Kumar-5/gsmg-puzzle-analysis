"""Apply the creator's 'zero out' + 'primes' hint to the undecoded a-i runs.

Creator, 2021-12-26 Telegram:
    "We've seen prime numbers being mentioned; well, that is definitely an
     aspect which is required to proceed. Furthermore, along the way, some
     characters need to be 'zeroed out'.."

RUN0 is the one run whose alphabet is {a..i} with NO 'o'. The two runs that DO
decode both contain 'o', and need it, because the decode maps o -> 0. So RUN0
is missing exactly the symbol the hint says has to be introduced.

"Primes" can select which characters get zeroed in two natural ways: by
POSITION (prime index) or by VALUE (a..i = 1..9, so b,c,e,g = 2,3,5,7 are the
prime-valued symbols). Both, and their complements, are tried here -- zeroing
in place, and deleting outright.

Decode is the README's own verified transform: digits -> one decimal integer
-> base 16 -> ASCII. Base 9 is tried alongside since RUN0 has 9 symbols.

Run: python primes.py
"""

import re
from pathlib import Path

from bigrun import get_runs, rejoin
from salpha import printable

ALPHA = "abcdefghi"
PRIME_DIGITS = {2, 3, 5, 7}


def sieve(n):
    ok = [False, False] + [True] * (n - 1)
    for i in range(2, int(n ** 0.5) + 1):
        if ok[i]:
            for j in range(i * i, n + 1, i):
                ok[j] = False
    return {i for i, v in enumerate(ok) if v}


def digits_of(run):
    """a..i -> 1..9 (the mapping the solved segments use)."""
    return [ALPHA.index(c) + 1 for c in run]


def variants(run):
    d = digits_of(run)
    P = sieve(len(d) + 1)

    def zero_pos(oneb, keep_prime, delete):
        out = []
        for i, v in enumerate(d):
            idx = i + 1 if oneb else i
            isp = idx in P
            hit = isp if keep_prime else not isp
            if hit:
                if not delete:
                    out.append(0)
            else:
                out.append(v)
        return out

    def zero_val(keep_prime, delete):
        out = []
        for v in d:
            hit = (v in PRIME_DIGITS) if keep_prime else (v not in PRIME_DIGITS)
            if hit:
                if not delete:
                    out.append(0)
            else:
                out.append(v)
        return out

    for oneb in (True, False):
        for kp in (True, False):
            for dele in (False, True):
                tag = (f"pos {'1' if oneb else '0'}-based, "
                       f"{'prime' if kp else 'composite'} idx "
                       f"{'deleted' if dele else 'zeroed'}")
                yield tag, zero_pos(oneb, kp, dele)
    for kp in (True, False):
        for dele in (False, True):
            tag = (f"value {'prime' if kp else 'non-prime'} "
                   f"{'deleted' if dele else 'zeroed'}")
            yield tag, zero_val(kp, dele)


def to_ascii(digits, base=10):
    n = 0
    for v in digits:
        if v >= base:
            raise ValueError("digit out of range")
        n = n * base + v
    if n == 0:
        raise ValueError("empty")
    h = format(n, "x")
    return bytes.fromhex(h.zfill(len(h) + len(h) % 2))


def main():
    runs = get_runs()
    joined, _ = rejoin(runs[0])
    m = re.search(r"[ab]{40,}", runs[0])
    dbbi, faed = runs[0][:m.start()], runs[0][m.end():]

    targets = {
        "RUN0 rejoined (661)": joined,
        "dbbi piece (91)": dbbi,
        "faed piece (570)": faed,
    }

    best = []
    for tname, run in targets.items():
        print("=" * 72)
        print(f"{tname}  alphabet={''.join(sorted(set(run)))}")
        print("=" * 72)
        for tag, digs in variants(run):
            for base, bname in ((10, "b10"), (9, "b9")):
                try:
                    out = to_ascii(digs, base)
                except Exception:
                    continue
                pr = printable(out)
                best.append((pr, tname, tag, bname, out))
                flag = "  <<< READABLE" if pr > 0.85 else ""
                if pr > 0.55:
                    print(f"  {pr:.2f} {len(out):>4}b [{bname}] {tag}{flag}")
                    print(f"        {out[:120]!r}")
        print()

    best.sort(reverse=True, key=lambda x: x[0])
    print("=" * 72)
    print("top 8 by printable ratio")
    print("=" * 72)
    for pr, tname, tag, bname, out in best[:8]:
        print(f"  {pr:.3f}  {tname} | {tag} | {bname} | {len(out)}b")
        print(f"         {out[:100]!r}")


if __name__ == "__main__":
    main()
