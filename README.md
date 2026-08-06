# GSMG.IO 5 BTC Puzzle — reproducible analysis

Tooling and results for the [GSMG.IO 5 BTC puzzle](https://github.com/puzzlehunt/gsmgio-5btc-puzzle).

**The puzzle is not solved here.** What this repo provides is a verified,
reproducible base and a large body of *eliminated* space — including disproof of
the two artifacts the solver community currently treats as its frontier.

Prize address [`1GSMG1JC9wtdSwfwApgj2xcmJPAwx7prBe`](https://www.blockchain.com/btc/address/1GSMG1JC9wtdSwfwApgj2xcmJPAwx7prBe)
holds ~1.256 BTC, unmoved. (5 BTC halved twice, per the creator's rules.)

---

## Setup

```bash
pip install coincurve pycryptodome pillow jpeglib brotli
git clone https://github.com/puzzlehunt/gsmgio-5btc-puzzle.git
python pipeline.py     # reproduce phases 1 -> 3.2 from real ciphertext
python oracle.py       # verify the on-chain public key, arm the key test
```

`corpus/` is rebuilt from the Wayback Machine (`fetch_wayback.py`) because
**gsmg.io is a parked, for-sale domain** — every live path now returns the same
~28KB parking page. The puzzle text exists only in archived snapshots.

---

## The one test that matters

The prize address has spent, so its public key is on-chain:

```
04f4d1bbd91e65e2a019566a17574e97dae908b784b388891848007e4f55d5a464
  9c73d25fc5ed8fd7227cab0be4e576c0c6404db5aa546286563e4be12bf33559
```

`oracle.py` verifies this hashes back to the prize address (**uncompressed**
serialisation — checking compressed-only makes every candidate silently fail),
then gives you a network-free test at libsecp256k1 speed:

```python
from oracle import check, search
check(some_32_bytes)        # True iff it is the prize key
search(candidate_generator) # returns the winner or None
```

Use it before believing any claimed solution, including your own. A self-test
pins address derivation against privkey=1 so a broken base58 routine can never
masquerade as "candidate was wrong".

---

## Verified chain

`pipeline.py` reproduces every solved stage from published inputs, asserting
against a known checkpoint at each step. If an assert fires, nothing downstream
is trustworthy.

| Stage | Checkpoint |
|---|---|
| 14×14 matrix, counterclockwise spiral | `gsmg.io/theseedisplanted` |
| `SHA256(causality)` | `eb3efb51…` |
| `SHA256(7 concatenated parts)` | `1a57c572…` |
| Phase 3.2 AES blob | full decrypt from real ciphertext |
| Beaufort, key `THEMATRIXHASYOU` | Architect speech |
| SalPhaseIon entry hash | `89727c59…` |
| Token extraction (abba + a-i/o) | `matrixsumlist`, `enter`, `lastwordsbeforearchichoice`, `thispassword` |

**Practical finding:** the phase 3.2 blob needs `-md sha256`, not MD5. A bare
`openssl enc` on 1.0.x gives `bad decrypt` with the correct password. Anyone who
tried this in 2020 and gave up hit that, not a wrong answer.

---

## The ciphertexts

Five exist. The repo README publishes only two of them.

| blob | salt | ct bytes | status |
|---|---|---|---|
| phase 2/3 | `06286612d43ed7ed` | 656 | solved — `sha256(causality)` |
| phase 3 | `9fbc451d13d071f4` | 4096 | solved — `sha256(7 parts)` |
| **Cosmic Duality** | `2d3f6fe06dc950e6` | 1328 | **unsolved** |
| **SalPhaseIon** | `3ab585348552415d` | 80 | **unsolved** |
| **phase 3.2 trailing** | `b45a5e3d827593ca` | 80 | **unsolved** |

The 656- and 4096-byte ciphertexts were recovered from archived pages
(`blobs.py`, `decrypt_recovered.py`) — the repo published their *plaintexts* but
never their ciphertexts, so until now nobody could check the published passwords
actually worked. Both decrypt cleanly, and the phase-3 plaintext's embedded
phase-3.2 blob is byte-identical to the README's. Nothing was truncated.

The **phase 3.2 trailing blob** sat in the repo README for years, unattacked.

---

## Disproved

### `cosmic_decrypted.bin` is a padding false positive

The community's frontier artifact (sha256 `4f7a1e4e…`, 1327 bytes) reproduces
exactly from PR #68's master key — and is noise.

```
entropy 7.870 bits/byte   (os.urandom of same length: 7.876)
255/256 byte values present, longest ASCII run 7 chars
0.33% of RANDOM keys produce an identical-looking 1327-byte "success"
```

1327 bytes from 1328 means **one** padding byte, which a wrong key yields 1 time
in 256. The community has tried far more than 256 passwords, so survivors are
expected, not evidence. Corroborated three independent ways.

### The 96-byte blob's `1449a217…` milestone is the same class

Password `matrixsumlist enter lastwordsbeforearchichoice thispassword matrixsumlist`
(MD5 KDF) reproduces it exactly. Also 1 padding byte, printable 0.38.
`body[0:32]` gives address `1GKJzHQkgTBwwEGeXetsTMDoUzvwzs9yb4` — not the prize.
48 sliding windows, their SHA256s, and the reversed body: no match.

### PR #68's master key rests on invented tokens

`yourlastcommand` and `secondanswer` originate from on-chain OP_RETURN dust
posted by solvers — messages **the creator explicitly disavowed**. Two of the
five tokens are fabricated. Combined with the entropy result, every
`chain4` / `cosmic_A` / `row1-4` / Phase-5/6 derivation downstream is unfounded.

The creator confirmed this independently (2025-04-28): *"Did anyone found
yingyang? I don't think so… It's the next phase, but I await the day someone
finally gets there."* **Nobody has passed SalPhaseIon.**

### Blue/yellow encodes nothing

`colours.py` measures the original image (byte-identical to the archived
`gsmg.io/puzzle`, sha256 `38125bbdf1ea…`) and verifies the extracted bit matrix
against the README's before drawing conclusions.

```
census: white 86, black 86, blue 15, yellow 9   (196 cells)
```

All 24 coloured squares sit at spiral position ≡ 7 (mod 8) — the **last bit of
each of the 24 URL characters**, each marked exactly once. Blue = bit 1,
yellow = bit 0. It is exactly the ASCII parity of `gsmg.io/theseedisplanted`,
carrying zero information beyond the URL.

Also identifies the cell that has confused every census in the issue tracker:
**(6,7) is a white cell overlaid by the rabbit drawing**, reading 50/50.

### No steganography in the images

`stego.py` — 19 recovered originals plus 6 repo images. Trailing data after
PNG `IEND` / JPEG `EOI`, full chunk inventory, LSB across
R/G/B/A/RGB × row/column × MSB/LSB (20 extractions each), WIF- and hex64-shaped
runs, palette and alpha anomalies. Nothing. Only Adobe XMP boilerplate on the
favicons and logo.

`dct.py` — the Decentraland JPEG at the DCT-coefficient level (libjpeg), where
real JPEG stego lives. 12 coefficient LSB streams, all noise (printable
0.23–0.39 against ~0.37 for random). The file has no EXIF and a bare JFIF header
at q≈85 — a re-encode fingerprint, and coefficient payloads don't survive
re-encoding.

> Two histogram indicators I initially flagged (`|1|/|2|` ratio, a chi-square on
> Cb) did **not** survive a control: re-encoding the same image swings both
> further than the original. They're dominated by compression history, not
> embedding. Withdrawn — the conclusion rests on the extraction test and
> provenance alone.

---

## RUN0 — the largest unanalyzed object

The SalPhaseIon textarea's first run. The repo README decodes four small pieces
and says *"only some are currently decoded"*; the bulk is untouched, and no
issue, PR, or external writeup analyzes it.

Structure: `RUN0  z  RUN1  z  RUN2  z  "shabef our first hint is your last command"`,
where RUN1/RUN2 decode to `lastwordsbeforearchichoice` / `thispassword`.

RUN0 splits at a spliced binary run decoding to `matrixsumlist` — so that token
is a **label naming the run**, not a password.

| | `dbbi` (91) | `faed` (570) |
|---|---|---|
| IoC | **0.1509** | 0.1181 |
| uniform baseline (9 symbols) | 0.1111 | 0.1111 |
| top symbols | `b` 27.5%, `e` 19.8% | `g` 18.8% (flat) |
| periodicity (coset IoC, p=1…40) | no lift | no lift |
| repeated 6-grams | 0 | 0 |

- Alphabet is exactly `{a..i}` — the **only run with no `o`**, and the creator's
  hint says *"some characters need to be 'zeroed out'"*.
- Under `a=0…i=8`, `b` and `e` are digits **1 and 4** — the exact escape digits
  of the solved phase-3.2.2 checkerboard, recovered independently from frequency
  shape alone (best of 72 combinations).
- **661 is prime** — the rejoined run cannot form a rectangle under any width,
  which argues `dbbi` and `faed` are separate runs, not one spliced run.

### Eliminated, each with a control where one was meaningful

| hypothesis | scope | control | result |
|---|---|---|---|
| direct checkerboard | 4 mappings × 5 targets | — | noise |
| columnar transposition by token length | 114 pipelines | — | 0.044 vs 0.440 |
| substitution hill-climb | 300 restarts | shuffled scored **higher** | refuted |
| `dbbi` as index/key into `faed` | ~38 constructions × 3 decoders | 0.208 vs 0.250 | refuted |
| `dbbi` as book cipher into puzzle plaintexts | 7 modes × 5 targets × 2 mappings | 0.286 vs 0.342 | refuted |

The length coincidences are real but unexploited:
`91 = 7×13` and `len("matrixsumlist") = 13`;
`570 = 15×38` and `len("lastwordsbeforearchichoice"+"thispassword") = 38`.

---

## Password search: ~38.5M trials, all negative

Everything sat on the random padding floor (0.39%), best printable ratio 0.646
against >0.95 for real text.

| run | scope |
|---|---|
| `sweep.py` | every word in the README and all decrypted plaintexts |
| `attack.py` | 1–12 word phrase windows of every recovered plaintext |
| `creator.py` | the creator's element list, 6k orderings |
| `recipe.py` | the 4-ingredient recipe with **measured** values, 417k concatenations × 3 blobs |
| `assembly.py` | XOR-of-hashes, `sha256(xor)`, double-`sha256`, chained folding; raw AES key with 6 IV derivations |

### Why this was structurally doomed

The creator's 2023-02-23 Telegram hint decodes to the only first-party statement
of what the key contains:

```
yellowblueprimes  matrixsumlist  lastwordsbeforearchichoice  yinyang
wewontgiveawaythepassword itsinfrontofyoureyesbutyourenotseeingit
verylaststepisatruegiveaway promised
```

Four ingredients (`yellowblueprimes` is one token). Three are computable. The
fourth — `yinyang` — is by the creator's own account **the output of a phase
nobody has reached**. It was never going to fall out of spelling variants.
Every public attempt at this recipe, including this one, guesses at a value that
is by construction not guessable.

```
RUN0 (unsolved) -> yin-yang -> 4-ingredient recipe -> Cosmic key -> private key
```

**No shortcut exists.** The prize address is a *vanity* address (`1GSMG1`
brute-forced), so its private key is random — no brainwallet, no split-key, no
derivation. The key exists only as plaintext inside a blob.

---

## Method notes

Two things did most of the work and are worth reusing:

**Controls.** Every "hit" was re-run with shuffled input. Three separate false
positives died this way, including one that produced legible English
(`PWALMSSETURCEEARETTDOOFYRORRIGLPREIISPWISSSTLEDTHEPSALLITATENCE` — from
shuffled input, scoring *better* than the real run). At 63 letters, substitution
hill-climbing manufactures plausible English from anything.

**Padding is weak evidence.** A wrong AES key passes PKCS#7 about 1 time in 256.
Any search over more than a few hundred candidates *will* produce survivors.
Treat "it decrypted without error" as no evidence at all unless the plaintext is
independently checkable.

`attack.py` exploits the same fact for speed: padding lives only in the final
block, so a candidate is rejected with **one** AES block operation instead of 83.
For CBC, that check is also IV-independent — one test covers every IV variant.

---

## Files

**Core** — `pipeline.py` (verified chain) · `oracle.py` (key test) ·
`vic.py` (straddling-checkerboard decoder, validated exactly against solved
phase 3.2.2) · `attack.py` (fast sweep harness)

**Corpus** — `fetch_wayback.py` · `fetch_corpus.ps1` · `fetch_images.py` ·
`blobs.py` · `decrypt_recovered.py`

**Analysis** — `analyze.py` (entropy) · `cosmic.py` · `keycheck.py` ·
`check79.py` · `colours.py` · `stego.py` · `dct.py` · `jpeg_struct.py`

**RUN0** — `salpha.py` · `bigrun.py` · `analyze_run0.py` · `dbbi.py` ·
`transpose.py` · `solve_sub.py` · `indexed.py` · `bookcipher.py` · `primes.py`

**Sweeps** — `sweep.py` · `creator.py` · `recipe.py` · `assembly.py`

**Not part of this work.** `kangaroo_est.py`, `check_layout.py`,
`test_distfield.py`, `verify_target.py` concern Pollard-kangaroo attacks on the
*other* Bitcoin puzzle series (75–160), against the `Kangaroo/` solver and
`cuda-toolkit/` also present in this working tree. Both are gitignored —
third-party, ~420 MB combined, and `Kangaroo/` carries its own `.git`.
Unrelated to GSMG; provenance unestablished.

Note that a kangaroo attack is irrelevant to GSMG regardless: the prize key is a
uniformly random 256-bit scalar, not confined to a small interval, so there is
no reduced search space to exploit.

---

## If you continue

Do not resume password sweeping. The remaining leverage is in the **assembly
rule** and in **RUN0**, not in search space.

`dbbi` is the tractable object: 91 symbols, clearly non-random (IoC 0.1509),
labelled `matrixsumlist` by the binary spliced next to it. A "matrix sum list"
of `91 = 7×13` values in range 1–9 literally describes a table of sums. `faed`
is flat, aperiodic and free of long repeats — which is what modern ciphertext
looks like, and if it is that, classical analysis will not touch it.

Verify anything you find with `oracle.check()` before believing it, and control
anything that looks like a partial decryption before reporting it.

## Sources

[puzzlehunt/gsmgio-5btc-puzzle](https://github.com/puzzlehunt/gsmgio-5btc-puzzle) ·
[gsmg-archive.org](https://gsmg-archive.org/) (mirror of the dead site) ·
[bitcointalk 5151725](https://bitcointalk.org/index.php?topic=5151725.0) ·
[r/bitcoinpuzzles](https://www.reddit.com/r/bitcoinpuzzles/comments/dfwcqk/gsmgio_5_btc_puzzle/) ·
[privatekeys.pw](https://privatekeys.pw/puzzles/gsmg-puzzle)

Creator hints are quoted from a parsed Telegram export circulating in the issue
tracker and mirrors; treat any single quote as second-hand unless you can see
the screenshot.
