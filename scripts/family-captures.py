#!/usr/bin/env python3
"""family-captures.py -- remakes the documentation's stills of every set from a manifest that names
each one's set and frame. The attract is deterministic from a clean NVRAM, so a frame gives the
same image on any machine; a still that stops reproducing means the driver changed. They are
doubled with nearest neighbour, as pixel art is. The published names (`title`, `race`) are what
the documents link to.

Use:
    uv run scripts/family-captures.py             # all of them
    uv run scripts/family-captures.py wheelfir    # only one set
"""

import argparse
import pathlib
import shutil
import subprocess
import sys

from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCALE = 2

# set -> [(frame, file name, what that image is for)]
MANIFEST: dict[str, list[tuple[int, str, str]]] = {
    "wheelfir": [
        (120, "logo-tch", "the TCH logo and the PRESENTS"),
        (343, "car", "the presentation sports car crossing the screen"),
        (603, "porsches", "the two Porsches, with clean background behind them"),
        (771, "title", "the game title"),
        (1180, "race", "the whole video model: sea, mountains, road and scoreboard"),
        (1420, "race-palm", "the same race further on, with vegetation"),
    ],
    "pwball": [
        (600, "attract", "the board's CLEAN reference: digitised photos with no scaling"),
        (1200, "title", "the title over the starfield"),
    ],
    "kongball": [
        (399, "title", "the title over the two gorillas"),
    ],
    "rltennis": [
        (600, "title", "the title, on the family's earlier board"),
        (870, "match", "its match: the control a blitter change must not break"),
    ],
    "rltennisa": [
        (600, "title", "the title of rltennisa"),
        (870, "match", "its match"),
    ],
    "radendur": [
        (275, "title", "the title"),
        (1200, "attract", "the attract's globe"),
    ],
    "radendurh": [
        (275, "title", "the title of the clone that plays"),
    ],
}


def scale(source: pathlib.Path, dest: pathlib.Path, what_for: str) -> None:
    im = Image.open(source).convert("RGB")
    im = im.resize((im.width * SCALE, im.height * SCALE), Image.Resampling.NEAREST)
    dest.parent.mkdir(parents=True, exist_ok=True)
    # Quantise to 256 colours: the art is 8-bit indexed at source, so nothing real is lost and the
    # file weighs half.
    im.convert("P", palette=Image.Palette.ADAPTIVE, colors=256).save(dest, optimize=True)
    print(
        f"  {dest.relative_to(ROOT)}  {im.width}x{im.height}  "
        f"{dest.stat().st_size // 1024} KB  -- {what_for}"
    )


def capture_set(game: str, entries: list[tuple[int, str, str]], tmp: pathlib.Path) -> int:
    last = max(f for f, _, _ in entries)
    out = tmp / game
    command = ["./scripts/frame-series.sh", game, "0", str(last), str(out)]
    print(f"== {game}: up to frame {last}")
    r = subprocess.run(
        command, cwd=ROOT, capture_output=True, encoding="utf-8", errors="replace", check=False
    )
    if r.returncode != 0:
        print(r.stdout[-2000:], r.stderr[-2000:], file=sys.stderr)
        print(f"==> INVALID: the capture of {game} failed (rc={r.returncode})", file=sys.stderr)
        return 1
    for frame, name, what_for in entries:
        source = out / game / f"f{frame:05d}.png"
        if not source.exists():
            print(f"==> INVALID: frame {frame} of {game} is missing", file=sys.stderr)
            return 1
        scale(source, ROOT / "docs" / "img" / game / f"{name}.png", what_for)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("games", nargs="*", choices=list(MANIFEST), help="all of them by default")
    args = ap.parse_args()

    tmp = ROOT / "tmp" / "captures"
    shutil.rmtree(tmp, ignore_errors=True)
    failures = 0
    for game in args.games or list(MANIFEST):
        failures += capture_set(game, MANIFEST[game], tmp)
    print("==> RED" if failures else "==> every capture remade")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
