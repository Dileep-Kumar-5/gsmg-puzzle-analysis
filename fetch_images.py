"""Pull the ORIGINAL puzzle images from the archive.

The repo's PNGs are re-saved copies -- gsmg.io/img/puzzle.png is 12,560 bytes
archived versus 29,931 in the repo. Re-encoding rewrites every pixel's low bits
and drops ancillary chunks, so LSB or chunk-based steganography can only be
tested against the originals.

/shared/*.png is skipped: hundreds of ~100KB files with random-hex names, which
is a user share-image bucket, not puzzle content.

Run: python fetch_images.py
"""

import re
from pathlib import Path

from fetch_wayback import cdx, get, OUT

IMGDIR = OUT / "img"
IMGDIR.mkdir(exist_ok=True)

WANTED = re.compile(
    r"gsmg\.io/(img/(?!\.png)[^?]*\.(png|jpg|jpeg|gif)|[a-z_]+\.(png|jpg|gif))$",
    re.I)


def main():
    rows = cdx("gsmg.io", "&matchType=domain&collapse=urlkey")
    imgs = [r for r in rows if WANTED.search(r[1]) and "/shared/" not in r[1]]
    print(f"{len(imgs)} original image URLs to pull\n")

    for ts, url, n in imgs:
        name = re.sub(r"[^\w.-]", "_", url.split("gsmg.io/", 1)[1])
        dest = IMGDIR / f"{name}"
        if dest.exists():
            print(f"  have {name}")
            continue
        body = get(f"https://web.archive.org/web/{ts}id_/{url}")
        if body:
            dest.write_bytes(body)
            print(f"  {ts} {len(body):>7}b -> {name}")


if __name__ == "__main__":
    main()
