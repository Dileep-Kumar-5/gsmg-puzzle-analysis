"""Extract the yellow and blue square positions from the original puzzle image.

Two creator hints point here and nobody in the repo agrees on the numbers:

  "Roses are White but often Red. Yellow has a number and so does Blue.
   Go back to the first puzzle piece without further ado."          (2020 hint)

  "yellow blue primes matrixsumlist lastwordsbeforearchichoice yinyang"
                                                    (2023-02-23 binary block)

The grid uses FOUR colours, not two: black and blue both read as bit 1, white
and yellow both read as bit 0. Blue and yellow are a second channel carried on
top of the binary matrix that spells the phase-1 URL.

The image is 1048x1556: the 14x14 grid occupies only the square top portion,
above a red divider, with logo/title/QR/address below. A white rabbit is drawn
over the middle of the grid, so cells are classified by their MODAL colour
rather than a centre pixel.

The file is byte-identical to the archived gsmg.io/puzzle original
(sha256 38125bbdf1ea...), so these are the creator's actual pixels. The decoded
bit matrix is asserted against the README's, which is the correctness check.

Run: python colours.py
"""

from collections import Counter
from pathlib import Path

from PIL import Image

from pipeline import bits_to_ascii, parse_matrix, spiral_ccw

IMG = Path(__file__).with_name("gsmgio-5btc-puzzle") / "puzzle.png"
N = 14


def classify(rgb):
    r, g, b = rgb
    if r > 200 and g < 90 and b < 90:
        return "red"
    if b > 120 and b > r + 40 and b > g + 40:
        return "blue"
    if r > 200 and g > 170 and b < 110:
        return "yellow"
    if r > 190 and g > 190 and b > 190:
        return "white"
    if r < 90 and g < 90 and b < 90:
        return "black"
    return "edge"


def grid_bottom(img):
    """The red divider marks the end of the grid."""
    w, h = img.size
    for y in range(h):
        row = [classify(img.getpixel((x, y))) for x in range(0, w, 40)]
        if row.count("red") > len(row) * 0.8:
            return y
    return w


def cell_colour(img, r, c, cw, ch):
    """Modal colour over an inset sample, so cell borders and the rabbit
    drawing cannot dominate a cell."""
    x0, y0 = int(c * cw), int(r * ch)
    x1, y1 = int((c + 1) * cw), int((r + 1) * ch)
    ix, iy = int((x1 - x0) * 0.30), int((y1 - y0) * 0.30)
    votes = Counter()
    for y in range(y0 + iy, y1 - iy, 3):
        for x in range(x0 + ix, x1 - ix, 3):
            votes[classify(img.getpixel((x, y)))] += 1
    votes.pop("edge", None)
    if not votes:
        return "edge"
    # The white rabbit is drawn as black strokes over white cells, which can
    # push a cell to ~50% black. A genuinely black cell is near-uniform, so
    # require a clear majority before calling black.
    total = sum(votes.values())
    if votes.get("black", 0) / total < 0.70 and votes.get("white", 0) > 0:
        votes.pop("black", None)
    return votes.most_common(1)[0][0]


def main():
    img = Image.open(IMG).convert("RGB")
    w, h = img.size
    bottom = grid_bottom(img)
    print(f"{IMG.name}: {w}x{h}, grid occupies y=0..{bottom}")
    cw, ch = w / N, bottom / N
    print(f"cell size {cw:.1f} x {ch:.1f}\n")

    grid = [[cell_colour(img, r, c, cw, ch) for c in range(N)] for r in range(N)]
    census = Counter(v for row in grid for v in row)
    print(f"colour census: {dict(census)}  (total {sum(census.values())})\n")

    # Correctness check: black+blue = 1, white+yellow = 0 must reproduce the
    # README's matrix and therefore the phase-1 URL.
    bits = [[1 if grid[r][c] in ("black", "blue") else 0 for c in range(N)]
            for r in range(N)]
    ref = parse_matrix()
    assert bits == ref, "extracted bit matrix does not match the README matrix"
    url = bits_to_ascii(spiral_ccw(bits))
    assert url == "gsmg.io/theseedisplanted", url
    print(f"CHECK: extracted matrix reproduces the README matrix and "
          f"decodes to {url!r}\n")

    order = spiral_ccw_coords(N)
    for name in ("blue", "yellow"):
        cells = [(r, c) for r in range(N) for c in range(N) if grid[r][c] == name]
        rm = [r * N + c + 1 for r, c in cells]
        sp = sorted(order.index((r, c)) for r, c in cells)
        print(f"{name}: {len(cells)} cells")
        print(f"  (row,col)                 : {cells}")
        print(f"  row-major 1-based          : {rm}  sum={sum(rm)}")
        print(f"  spiral 0-based             : {sp}  sum={sum(sp)}")
        print(f"  spiral 1-based             : {[p + 1 for p in sp]}  "
              f"sum={sum(sp) + len(sp)}")
        mult8 = [p for p in sp if p % 8 == 0]
        print(f"  multiples of 8 (bit 0 of a char): {len(mult8)}/{len(sp)}")
        print(f"  bit position within char   : {sorted(p % 8 for p in sp)}")
        print(f"  character index in URL     : {sorted(p // 8 for p in sp)}")
        chars = "".join("gsmg.io/theseedisplanted"[p // 8] for p in sp)
        print(f"  URL chars hit              : {chars!r}")
        print()


def spiral_ccw_coords(n):
    top, bot, left, right = 0, n - 1, 0, n - 1
    out = []
    while top <= bot and left <= right:
        for r in range(top, bot + 1):
            out.append((r, left))
        left += 1
        for c in range(left, right + 1):
            out.append((bot, c))
        bot -= 1
        if left <= right:
            for r in range(bot, top - 1, -1):
                out.append((r, right))
            right -= 1
        if top <= bot:
            for c in range(right, left - 1, -1):
                out.append((top, c))
            top += 1
    return out


if __name__ == "__main__":
    main()
