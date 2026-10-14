"""signatures.py -- the teams' signatures in the ROMs: credits, initials seeded into the high-score
tables, an e-mail address. The 68000 image interleaves two ROMs byte by byte, so text written into
both reads doubled in the combined image (`EESSTTEE JJUUEEGGOO`); each image is swept combined, as
its even half and as its odd half.

USE:
    uv run scripts/signatures.py                 the whole report
    uv run scripts/signatures.py --image kongball_maincpu
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMGDIR = ROOT / "disasm" / "img"

# What tells a SIGNATURE apart from the game's text. It is not a list of names (that would only
# find the ones already known): they are the words a team credits itself with, plus the marks of an
# email address and of a nineties year.
HINTS = re.compile(
    r"PRODUCER|ADVISER|HARDWARE DESIGN|PROGRAMM|GRAPHICS|A Game By|Programmer|Colleague|"
    r"REALIZADO|DISENADO|CREATED BY|CODED BY|ALL RIGHTS|DIGITAL DREAMS|dos\.library|"
    r"[a-z0-9._-]+@[a-z0-9.-]+\.[a-z]{2,}|"  # a real email, not a lone at sign
    r"\b(?:19[89][0-9])\b",  # a year, with word boundaries
    re.IGNORECASE,
)
MIN_LENGTH = 8
# The ROMs are full of character RAMPS (font test tables, `!"#$%&'()...`) containing at signs,
# years and any substring you care to look for. They are discarded by demanding the string has
# WORDS: at least two runs of three letters or more, and that it is not nearly all one character.
WORD = re.compile(r"[A-Za-z]{3,}")


def looks_like_text(t: str) -> bool:
    if len(WORD.findall(t)) < 2:
        return False
    # A ramp has nearly all its characters distinct and in order; text repeats letters.
    distinct = len(set(t))
    return distinct < len(t) * 0.75 or len(t) < 24


def printables(data: bytes, minlen: int) -> list[tuple[int, str]]:
    return [
        (m.start(), m.group().decode("latin1")) for m in re.finditer(rb"[ -~]{%d,}" % minlen, data)
    ]


def views(data: bytes) -> dict[str, tuple[bytes, int]]:
    """The three ways of reading an interleaved image, with the factor to get back to its offset."""
    return {"combined": (data, 1), "even half": (data[0::2], 2), "odd half": (data[1::2], 2)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--image", default=None)
    ap.add_argument("--length", type=int, default=MIN_LENGTH)
    args = ap.parse_args()

    binaries = sorted(IMGDIR.glob("*.bin"))
    if not binaries:
        print("INVALID: there are no images in disasm/img. Run ./scripts/disasm.sh")
        sys.exit(3)

    examined = 0
    with_signature = 0
    for b in binaries:
        if args.image and b.stem != args.image:
            continue
        examined += 1
        data = b.read_bytes()
        found: list[str] = []
        # A signature written into both ROMs comes out in all three views; the one reported is the
        # view where it reads CLEAN, which is the fact needed to find it again.
        for view_name, (view, factor) in views(data).items():
            for off, text in printables(view, args.length):
                if not HINTS.search(text) or not looks_like_text(text):
                    continue
                # In the combined view, text with every character duplicated is the same one
                # already read clean in one of the halves: it is said and not repeated in full.
                doubled = view_name == "combined" and all(
                    text[i] == text[i + 1] for i in range(0, len(text) - 1, 2)
                )
                mark = "  [duplicated by the interleaving]" if doubled else ""
                body = " ".join(text.split())[:150]
                found.append(f"    {view_name:12s} 0x{off * factor:06x}  {body}{mark}")
        print(f"{b.stem} ({len(data) // 1024} KB)")
        if found:
            with_signature += 1
            # Without duplicates: the same string may appear several times as filler.
            for line in dict.fromkeys(found):
                print(line)
        else:
            print("    no legible signatures or credits")
        print()

    if examined == 0:
        print(f"INVALID: --image {args.image} does not exist in disasm/img")
        sys.exit(3)
    print(f"==> {with_signature} of {examined} images carry a signature or credits")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
