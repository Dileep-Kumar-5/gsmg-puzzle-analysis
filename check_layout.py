#!/usr/bin/env python3
"""Static consistency check for the 256-bit distance patch.

Phase 2 is mostly hand-edited offsets across the CUDA kernel, the host readout
and two wire formats. A compiler catches type errors; it does NOT catch a DP
written at word 9 and read at word 8. This parses the actual sources and
asserts producer and consumer agree.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent / "Kangaroo"


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8", errors="replace")


def define(src, name):
    m = re.search(r"^#define\s+%s\s+(\d+)" % re.escape(name), src, re.M)
    assert m, "no #define %s" % name
    return int(m.group(1))


def check_item_layout():
    """GPU DP output: OutputDP writer vs GPUEngine.cu reader."""
    eng_h = read("GPU/GPUEngine.h")
    item_size = define(eng_h, "ITEM_SIZE")
    item32 = item_size // 4

    # x[4 u64] + d[4 u64] + kIdx[1 u64]
    assert item_size == (4 + 4 + 1) * 8 == 72, item_size

    math_h = read("GPU/GPUMath.h")
    body = math_h[math_h.index("#define OutputDP"):]
    body = body[:body.index("\n}")]
    slots = [(int(o), field, int(i))
             for o, field, i in re.findall(
                 r"out\[pos\*ITEM_SIZE32 \+ (\d+)\] = \(\(uint32_t \*\)(\w+)\)\[(\d+)\];",
                 body)]
    assert slots, "OutputDP body not parsed"

    # Every uint32 of the item is written exactly once, contiguous from 1.
    written = [s[0] for s in slots]
    assert written == list(range(1, item32 + 1)), \
        "OutputDP writes %s, expected 1..%d" % (written, item32)

    # Each source field is written low word first, no gaps.
    for field, count in (("x", 8), ("d", 8), ("idx", 2)):
        idxs = [i for _, f, i in slots if f == field]
        assert idxs == list(range(count)), "%s writes %s" % (field, idxs)

    # Reader side: itemPtr = out + i*ITEM_SIZE32 + 1, so writer slot N -> itemPtr[N-1].
    eng_cu = read("GPU/GPUEngine.cu")
    x_off = [int(n) for n in re.findall(r"it\.x\.bits64\[(\d)\] = x\[\d\];", eng_cu)]
    d_base = int(re.search(r"uint64_t \*d = \(uint64_t \*\)\(itemPtr \+ (\d+)\);",
                           eng_cu).group(1))
    d_words = re.findall(r"it\.d\.bits64\[(\d)\] = d\[(\d)\];", eng_cu)
    k_off = int(re.search(r"it\.kIdx = \*\(\(uint64_t\*\)\(itemPtr \+ (\d+)\)\);",
                          eng_cu).group(1))

    assert x_off == [0, 1, 2, 3], x_off
    assert d_base == 8, "d read at u32 offset %d, writer put it at 8" % d_base
    assert [(int(a), int(b)) for a, b in d_words] == [(0, 0), (1, 1), (2, 2), (3, 3)], \
        "distance words not read 1:1: %s" % d_words
    assert k_off == 16, "kIdx read at u32 %d, writer put it at 16" % k_off
    # kIdx is the last 2 u32 of the item
    assert k_off + 2 == item32, "kIdx at %d + 2 != item32 %d" % (k_off, item32)
    return item_size


def check_kangaroo_slots():
    """Device kangaroo record: every slot used must fit inside KSIZE."""
    eng_h = read("GPU/GPUEngine.h")
    ksize_sym = int(re.search(r"#ifdef USE_SYMMETRY\s*\n#define KSIZE (\d+)", eng_h).group(1))
    ksize = int(re.search(r"#else\s*\n#define KSIZE (\d+)", eng_h).group(1))
    assert (ksize, ksize_sym) == (12, 13), (ksize, ksize_sym)

    math_h = read("GPU/GPUMath.h")
    used = {int(n) for n in re.findall(r"IDX \+ (\d+) \* blockDim\.x \+ stride", math_h)}
    assert used == set(range(13)), "device slots used: %s" % sorted(used)
    assert max(used) < ksize_sym

    # Non-symmetry build must not touch slot 12 (that is the lastJump word).
    non_sym = re.sub(r"#ifdef USE_SYMMETRY.*?#endif", "", math_h, flags=re.S)
    used_ns = {int(n) for n in re.findall(r"IDX \+ (\d+) \* blockDim\.x \+ stride", non_sym)}
    assert max(used_ns) < ksize, "non-symmetry uses slot %d, KSIZE=%d" % (max(used_ns), ksize)

    # Host side writes the same slots.
    eng_cu = read("GPU/GPUEngine.cu")
    host = {int(n) for n in re.findall(r"t \+ (\d+) \* nbThreadPerGroup", eng_cu)}
    assert host == set(range(13)), "host slots: %s" % sorted(host)

    # dist is 4 words everywhere it is declared.
    assert "dist[GPU_GRP_SIZE][2]" not in math_h
    assert "dist[GPU_GRP_SIZE][2]" not in read("GPU/GPUCompute.h")
    # and accumulated with the 4-word carry chain
    assert "Add256(dist[g],jD[jmp]);" in read("GPU/GPUCompute.h")
    assert "jD[NB_JUMP][4]" in math_h
    return ksize


def check_add256():
    """Carry must chain through all four words: add.cc / addc.cc / addc.cc / addc."""
    math_h = read("GPU/GPUMath.h")
    body = math_h[math_h.index("#define Add256"):]
    body = body[:body.index("(a)[3]);}") + len("(a)[3]);}")]
    ops = re.findall(r"(UADDO1|UADDC1|UADD1)\(\(r\)\[(\d)\], \(a\)\[(\d)\]\)", body)
    assert [o[0] for o in ops] == ["UADDO1", "UADDC1", "UADDC1", "UADD1"], ops
    assert [o[1] for o in ops] == list("0123") and [o[2] for o in ops] == list("0123")


def check_wire():
    """DP packet and kangaroo block sizes agree with their runtime assertions."""
    kh = read("Kangaroo.h")
    dp = kh[kh.index("// DP transfered over the network"):]
    dp = dp[:dp.index("} DP;")]
    assert "int128_t x;" in dp and "int256_t d;" in dp, dp
    dp_size = 4 + 4 + 16 + 32                     # kIdx + h + x + d
    assert dp_size == 56

    net = read("Network.cpp")
    asserted = int(re.search(r"if\(sizeof\(DP\) != (\d+)\)", net).group(1))
    assert asserted == dp_size, "runtime check says %d, struct is %d" % (asserted, dp_size)

    # All four distance words are packed into the outgoing DP.
    packed = re.findall(r"dp\[i\]\.d\.i64\[(\d)\] = D\.i64\[(\d)\];", net)
    assert [(int(a), int(b)) for a, b in packed] == [(0, 0), (1, 1), (2, 2), (3, 3)], packed

    # Kangaroo block: 32 bytes per kangaroo on every path, none left at 16.
    assert "int128_t* KBuff" not in net and "int128_t *KBuff" not in net
    # Declaration, cast and allocation size must all agree -- a stale cast here
    # is a type error the eye slides right over.
    allocs = re.findall(r"KBuff = \((\w+) ?\*\)malloc\(KANG_PER_BLOCK ?\* ?sizeof\((\w+)\)\)", net)
    assert len(allocs) == 4, allocs
    assert all(c == "int256_t" and t == "int256_t" for c, t in allocs), allocs
    for pat in (r"::fread\(&KBuff\[k\],(\d+),1,f\);",
                r"::fwrite\(&KBuff\[k\],(\d+),1,f\);",
                r"memcpy\(&KBuff\[k\],&kangs\[pos\],(\d+)\);"):
        sizes = re.findall(pat, net)
        assert sizes and all(s == "32" for s in sizes), (pat, sizes)
    pkt = re.findall(r"KBuff,nbK \* (\d+),ntimeout", net)
    assert pkt and all(s == "32" for s in pkt), pkt

    # Checksum must cover all four words wherever it is computed.
    blocks = re.findall(r"K\.SetInt32\(0\);(.*?)checkSum\.Add\(&K\);", net, re.S)
    assert blocks, "no checksum blocks found"
    for b in blocks:
        got = sorted(int(n) for n in re.findall(r"K\.bits64\[(\d)\] = KBuff", b))
        assert got == [0, 1, 2, 3], "checksum covers words %s" % got

    # The checksum accumulator is a 5-word Int but only 32 bytes go on the wire,
    # and the distance now carries flags at b254/b255, so a herd overflows past
    # 256 bits. Both sides must truncate or every transfer fails its checksum.
    sends = len(re.findall(r'PUT\("check[Ss]um",\w+(?:->clientSock)?,checkSum\.bits64,32', net))
    compares = len(re.findall(r"if\(!K\.IsEqual\(&checkSum\)\)", net))
    truncs = len(re.findall(r"checkSum\.bits64\[4\] = 0;", net))
    assert sends + compares == 4, (sends, compares)
    assert truncs == 4, "checksum truncated at %d of 4 sites" % truncs
    for m in re.finditer(r"checkSum\.bits64\[4\] = 0;(.{0,400})", net, re.S):
        assert ("IsEqual(&checkSum)" in m.group(1)
                or "checkSum.bits64,32" in m.group(1)), "truncation not before use"

    assert "kangs.size()*32 + 16" in read("Backup.cpp")
    return dp_size, len(blocks)


def check_entry():
    ht = read("HashTable.h")
    assert define(ht, "ENTRY_SIZE") == 16 + 32 == 48
    assert define(ht, "MAX_INTERVAL_BITS") == 253
    assert "int256_t  d;" in ht
    # Every ENTRY-sized transfer goes through ENTRY_SIZE, and the two halves of
    # an ENTRY are read/written at their own widths. Bare 32s elsewhere in these
    # files are 256-bit Int header fields (range start/end, key x/y) -- correct
    # as-is, so this checks the ENTRY sites specifically rather than banning 32.
    htc = read("HashTable.cpp")
    assert "::fread(items+i,ENTRY_SIZE,1,f);" in read("Check.cpp")
    for pat in (r"::fread\(&e1,ENTRY_SIZE,1,f1\)", r"::fread\(&e2,ENTRY_SIZE,1,f2\)",
                r"::fwrite\(output,ENTRY_SIZE,nbd,fd\)",
                r"uint64_t hSize = \(uint64_t\)ENTRY_SIZE \* E\[h\]\.nbItem;"):
        assert re.search(pat, htc), pat
    assert len(re.findall(r"memcpy\(output ?\+ ?nbd,&e\d,ENTRY_SIZE\)", htc)) == 5
    for half, width in (("x", "int128_t"), ("d", "int256_t")):
        assert ("fwrite(&(E[h].items[i]->%s),sizeof(%s),1,f)" % (half, width)) in htc
        assert ("fread(&(e->%s),sizeof(%s),1,f)" % (half, width)) in htc
    # The truncating mask is gone; the guard replaced it.
    htc = read("HashTable.cpp")
    assert "exit(-1);" in htc and "0xC000000000000000ULL" in htc


def check_format_magic():
    """Old files and old peers must be rejected, not misparsed."""
    kh = read("Kangaroo.h")
    for name, old in (("HEADW", "0xFA6A8001"), ("HEADK", "0xFA6A8002"),
                      ("HEADKS", "0xFA6A8003")):
        m = re.search(r"#define %s\s+(0x[0-9A-Fa-f]+)" % name, kh)
        assert m and m.group(1).lower() != old.lower(), "%s not bumped" % name
    net = read("Network.cpp")
    m = re.search(r"#define SERVER_HEADER (0x[0-9A-Fa-f]+)", net)
    assert m and m.group(1).lower() != "0x67deddc1", "SERVER_HEADER not bumped"


def main():
    item = check_item_layout()
    ksize = check_kangaroo_slots()
    check_add256()
    dp_size, nblocks = check_wire()
    check_entry()
    check_format_magic()
    print("layout self-check OK")
    print("  ENTRY      48 bytes (was 32)   x:16 d:32")
    print("  ITEM       %d bytes (was 56)   x:32 d:32 kIdx:8" % item)
    print("  KSIZE      %d words (was 10)   px:4 py:4 dist:4" % ksize)
    print("  DP packet  %d bytes (was 40)" % dp_size)
    print("  kangaroo   32 bytes (was 16),  %d checksum sites widened" % nblocks)


if __name__ == "__main__":
    sys.exit(main())
