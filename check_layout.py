#!/usr/bin/env python3
"""Static consistency check for the configurable distance-width patch.

The width is a compile-time switch (DIST_WORDS = 2 by default, 4 with
WIDE_DIST), and most of the affected code is hand-written offsets across the
CUDA kernel, the host readout and two wire formats. A compiler catches type
errors; it does NOT catch a DP written at word 9 and read at word 8, and it
only ever checks the width you happened to build. This parses the sources and
asserts producer and consumer agree at BOTH widths.
"""

import re
from pathlib import Path

_here = Path(__file__).resolve().parent
ROOT = _here.parent if (_here.parent / "HashTable.h").exists() else _here.parent / "Kangaroo"

WIDTHS = (2, 4)


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8", errors="replace")


def evaluate(expr, dw):
    """Evaluate a C constant expression that may mention DIST_WORDS."""
    expr = expr.replace("DIST_WORDS", str(dw))
    assert re.fullmatch(r"[\d\s()+*/-]+", expr), "unexpected tokens: %r" % expr
    return eval(expr)


def define_expr(src, name):
    m = re.search(r"^#define\s+%s\s+(.+?)\s*(?://.*)?$" % re.escape(name), src, re.M)
    assert m, "no #define %s" % name
    return m.group(1).strip()


def active_block(src, dw):
    """Strip the inactive arm of every `#if DIST_WORDS == 4` / #else block."""
    out, state = [], []
    for line in src.split("\n"):
        st = line.strip()
        if st.startswith("#if DIST_WORDS == 4"):
            state.append(dw == 4)
            continue
        if state and st == "#else":
            state[-1] = not state[-1]
            continue
        if state and st == "#endif":
            state.pop()
            continue
        if all(state):
            out.append(line)
    return "\n".join(out)


def check_item_layout(dw):
    """GPU DP output: OutputDP writer vs GPUEngine.cu reader."""
    eng_h = read("GPU/GPUEngine.h")
    item32 = evaluate(define_expr(eng_h, "ITEM_SIZE32"), dw)
    item_size = evaluate(define_expr(eng_h, "ITEM_SIZE").replace("ITEM_SIZE32", str(item32)), dw)

    # x[4 u64] + d[dw u64] + kIdx[1 u64]
    assert item_size == (4 + dw + 1) * 8, (dw, item_size)
    assert item32 == item_size // 4

    math_h = active_block(read("GPU/GPUMath.h"), dw)
    # inline DP_EXTRA_DIST_WORDS so the writer reads as one flat list
    m = re.search(r"#define DP_EXTRA_DIST_WORDS\(d\)(.*?)\n#(?:else|endif)",
                  read("GPU/GPUMath.h"), re.S)
    extra = m.group(1) if (m and dw == 4) else ""
    body = math_h[math_h.index("#define OutputDP"):]
    body = body[:body.index("\n}")].replace("DP_EXTRA_DIST_WORDS(d)", extra)

    slots = []
    for off, field, idx in re.findall(
            r"out\[pos\*ITEM_SIZE32 \+ ([^\]]+)\] = \(\(uint32_t \*\)(\w+)\)\[(\d+)\];", body):
        slots.append((evaluate(off, dw), field, int(idx)))

    # every uint32 of the item written exactly once; slot 0 is the found-counter
    written = sorted(s[0] for s in slots)
    assert len(written) == len(set(written)), (dw, "duplicate slot write", written)
    assert written == list(range(1, item32 + 1)), (dw, written, item32)

    # fields land contiguously and in order
    for field, base, count in (("x", 1, 8), ("d", 9, 2 * dw), ("idx", 9 + 2 * dw, 2)):
        got = sorted((o, i) for o, f, i in slots if f == field)
        assert got == [(base + i, i) for i in range(count)], (dw, field, got)

    # reader side must use the same offsets
    cu = read("GPU/GPUEngine.cu")
    assert "uint64_t *x = (uint64_t *)itemPtr;" in cu
    assert "uint64_t *d = (uint64_t *)(itemPtr + 8);" in cu, "d must be read at +8"
    m = re.search(r"it\.kIdx = \*\(\(uint64_t\*\)\(itemPtr \+ ([^)]+)\)\);", cu)
    assert m and evaluate(m.group(1), dw) == 8 + 2 * dw, (dw, m and m.group(1))
    return item_size


def check_kangaroo_slots(dw):
    """Device kangaroo record: px[4] py[4] dist[dw] (+lastJump) must fit KSIZE."""
    eng_h = read("GPU/GPUEngine.h")
    ks = re.findall(r"#define KSIZE\s+(.+)", eng_h)
    assert len(ks) == 2, ks
    ksize_sym, ksize = (evaluate(k.strip(), dw) for k in ks)
    assert ksize == 8 + dw, (dw, ksize)
    assert ksize_sym == ksize + 1, (dw, ksize_sym)

    math_h = active_block(read("GPU/GPUMath.h"), dw)
    used = set()
    for expr in re.findall(r"\(a\)\[IDX \+ ([^*]+)\* blockDim\.x \+ stride\]", math_h):
        used.add(evaluate(expr.strip(), dw))
    assert used, "no kangaroo slot accesses found"
    assert max(used) < ksize_sym, (dw, sorted(used), ksize_sym)
    assert used >= set(range(0, 8 + dw)), (dw, sorted(used))

    cu = active_block(read("GPU/GPUEngine.cu"), dw)
    host = set()
    for expr in re.findall(r"t \+ ([^*]+)\* nbThreadPerGroup", cu):
        host.add(evaluate(expr.strip(), dw))
    assert max(host) < ksize_sym, (dw, sorted(host), ksize_sym)
    return ksize


def check_add_carry(dw):
    """AddDist must select a carry chain covering exactly DIST_WORDS words."""
    math_h = read("GPU/GPUMath.h")
    sel = re.search(r"#if DIST_WORDS == 4\s*\n#define AddDist\(r,a\) (\w+)\(r,a\)\s*\n"
                    r"#else\s*\n#define AddDist\(r,a\) (\w+)\(r,a\)", math_h)
    assert sel, "AddDist selector missing"
    name = sel.group(1) if dw == 4 else sel.group(2)
    body = math_h[math_h.index("#define %s(r,a)" % name):]
    body = body[:body.index("}")]
    ops = re.findall(r"(UADDO1|UADDC1|UADD1)\(\(r\)\[(\d+)\], \(a\)\[(\d+)\]\)", body)
    assert len(ops) == dw, (dw, name, ops)
    assert [int(o[1]) for o in ops] == list(range(dw))
    assert [int(o[2]) for o in ops] == list(range(dw))
    # carry must start, chain, then terminate
    assert ops[0][0] == "UADDO1" and ops[-1][0] == "UADD1", ops
    assert all(o[0] == "UADDC1" for o in ops[1:-1]), ops

    comp = read("GPU/GPUCompute.h")
    assert "AddDist(dist[g],jD[jmp]);" in comp
    assert "uint64_t dist[GPU_GRP_SIZE][DIST_WORDS];" in comp
    assert "jD[NB_JUMP][DIST_WORDS]" in math_h


def check_host_sizes(dw):
    ht = read("HashTable.h")
    entry = evaluate(define_expr(ht, "ENTRY_SIZE"), dw)
    assert entry == 16 + 8 * dw, (dw, entry)
    assert evaluate(define_expr(ht, "DIST_MAG_BITS"), dw) == 64 * dw - 2

    net = read("Network.cpp")
    m = re.search(r"if\(sizeof\(DP\) != \(int\)\((.+?)\)\) \{", net)
    assert m, "DP size assertion missing"
    dp_size = evaluate(m.group(1), dw)
    assert dp_size == 8 + 16 + 8 * dw, (dw, dp_size)

    # kangaroo blocks sized from the type, not a literal
    assert net.count("nbK * (8*DIST_WORDS),ntimeout") == 4
    assert "memcpy(&KBuff[k],&kangs[pos],sizeof(dist_t));" in net
    assert "kangs.size()*(8*DIST_WORDS) + 16" in read("Backup.cpp")
    return entry, dp_size


def check_checksum_truncation():
    """Only 32 bytes go on the wire; the flags push a herd past 2^256."""
    net = read("Network.cpp")
    sends = len(re.findall(r'PUT\("check[Ss]um",\w+(?:->clientSock)?,checkSum\.bits64,32', net))
    compares = len(re.findall(r"if\(!K\.IsEqual\(&checkSum\)\)", net))
    truncs = len(re.findall(r"checkSum\.bits64\[4\] = 0;", net))
    assert sends + compares == 4, (sends, compares)
    assert truncs == 4, "checksum truncated at %d of 4 sites" % truncs
    for m in re.finditer(r"checkSum\.bits64\[4\] = 0;(.{0,400})", net, re.S):
        assert ("IsEqual(&checkSum)" in m.group(1)
                or "checkSum.bits64,32" in m.group(1)), "truncation not before use"
    loops = re.findall(r"for\(int w = 0; w < DIST_WORDS; w\+\+\)\s*\n\s*"
                       r"K\.bits64\[w\] = KBuff\[k\]\.i64\[w\];", net)
    assert len(loops) == 4, len(loops)


def check_format_magics():
    """A width mismatch must be refused by magic, never misparsed. The default
    build must keep upstream's values so its work files stay compatible."""
    kh = read("Kangaroo.h")
    m = re.search(r"#ifdef WIDE_DIST(.*?)#else(.*?)#endif", kh, re.S)
    assert m, "work-file magics are not width-dependent"
    wide, narrow = m.group(1), m.group(2)
    for name, upstream in (("HEADW", "0xfa6a8001"), ("HEADK", "0xfa6a8002"),
                           ("HEADKS", "0xfa6a8003")):
        w = re.search(r"#define %s\s+(0x[0-9A-Fa-f]+)" % name, wide).group(1)
        n = re.search(r"#define %s\s+(0x[0-9A-Fa-f]+)" % name, narrow).group(1)
        assert n.lower() == upstream, (name, n, "default must match upstream")
        assert w.lower() != n.lower(), (name, "wide magic must differ")

    net = read("Network.cpp")
    m = re.search(r"#ifdef WIDE_DIST\s*\n#define SERVER_HEADER (0x\w+)\s*\n#else\s*\n"
                  r"#define SERVER_HEADER (0x\w+)", net)
    assert m, "protocol magic is not width-dependent"
    assert m.group(1) != m.group(2)
    assert m.group(2).lower() == "0x67deddc1", (m.group(2), "default must match upstream")


def demo():
    results = {}
    for dw in WIDTHS:
        item = check_item_layout(dw)
        ksize = check_kangaroo_slots(dw)
        check_add_carry(dw)
        entry, dp = check_host_sizes(dw)
        results[dw] = (entry, item, ksize, dp, 8 * dw)
    check_checksum_truncation()
    check_format_magics()

    # the default width must reproduce upstream's layout exactly
    assert results[2] == (32, 56, 10, 40, 16), results[2]
    assert results[4] == (48, 72, 12, 56, 32), results[4]

    print("layout self-check OK (both widths)")
    print("  %-11s %8s %10s" % ("", "default", "WIDE_DIST"))
    print("  %-11s %8d %10d" % ("DIST_WORDS", 2, 4))
    for i, name in enumerate(("ENTRY", "ITEM", "KSIZE", "DP packet", "kangaroo")):
        print("  %-11s %8d %10d" % (name, results[2][i], results[4][i]))
    print("  default reproduces upstream exactly (ENTRY 32, ITEM 56, KSIZE 10, DP 40)")


if __name__ == "__main__":
    demo()
