"""before-after.py -- measures a before/after pair, so its caption is written from the image: the
share of pixels that change, the box they change in (an object, or the whole screen), the bands
with most change, and a contrast image with the change in red. A pair that barely changes is
reported, since it illustrates nothing.

USE:
    uv run scripts/before-after.py before.png after.png
    uv run scripts/before-after.py before.png after.png --contrast /tmp/compare.png
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from image_diff import MINIMUM_PCT, box, changed
from image_diff import load as load_image
from PIL import Image


def load(p: Path) -> np.ndarray:
    if not p.exists():
        print(f"INVALID: {p} does not exist")
        sys.exit(3)
    return load_image(p)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("before", type=Path)
    ap.add_argument("after", type=Path)
    ap.add_argument("--contrast", type=Path, default=None, help="writes a contrast image")
    ap.add_argument("--bands", type=int, default=4)
    args = ap.parse_args()

    a, b = load(args.before), load(args.after)
    # A DIFFERENT SIZE IS A RESULT, not an error: the "before" captures come from a driver that
    # declares fewer visible lines than this one, and a pair that aborts on that is a pair whose
    # caption nothing measured.
    # It crops to the common area and SAYS how much was cropped.
    crop_note = ""
    if a.shape != b.shape:
        height = min(a.shape[0], b.shape[0])
        width = min(a.shape[1], b.shape[1])
        if (height, width) == (0, 0):
            print(f"INVALID: there is no common area between {a.shape} and {b.shape}")
            sys.exit(3)
        crop_note = (
            f"  WATCH OUT: different sizes ({a.shape[1]}x{a.shape[0]} against "
            f"{b.shape[1]}x{b.shape[0]}). The common area of {width}x{height} is compared, and "
            "that size difference IS itself a change of the visible area."
        )
        a, b = a[:height, :width], b[:height, :width]

    mask = changed(a, b)
    total = mask.size
    n = int(mask.sum())
    pct = 100.0 * n / total

    print(f"before  : {args.before}")
    print(f"after   : {args.after}")
    print(f"size    : {a.shape[1]}x{a.shape[0]}")
    if crop_note:
        print(crop_note)
    print(f"changing: {n} pixels of {total} ({pct:.2f}%)")

    if n:
        print(f"box     : {box(mask)}")
        height = a.shape[0]
        step = max(1, height // args.bands)
        print("by horizontal bands:")
        for y0 in range(0, height, step):
            band = mask[y0 : y0 + step]
            p = 100.0 * band.sum() / band.size
            bar = "#" * int(p / 2)
            print(f"  y {y0:3d}..{min(y0 + step, height) - 1:3d}  {p:5.1f}%  {bar}")

    if args.contrast:
        # The change is painted IN RED over the "after": looking at two images side by side and
        # guessing what moved is exactly what failed. Here it is pointed at.
        marked = b.copy()
        marked[mask] = [255, 0, 0]
        strip = np.concatenate([a, b, marked], axis=1).astype(np.uint8)
        args.contrast.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(strip).save(args.contrast)
        print(f"contrast: {args.contrast} (before | after | what changes, in red)")

    if pct < MINIMUM_PCT:
        print(
            f"\n==> WARNING: only {pct:.2f}% changes. This pair is NO good as a before/after: "
            "look for the frame where the artefact really shows."
        )
        return 1
    print(f"\n==> the pair shows a change of {pct:.2f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
