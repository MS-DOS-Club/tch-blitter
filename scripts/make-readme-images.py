#!/usr/bin/env python3
"""make-readme-images.py -- the light images of Radical Enduro's page, from the originals, so the
page loads quickly without losing anything.

Two craft rules it applies:

- **Arcade captures are SCALED UP with nearest neighbour.** They are 336x252 of pixel art: at
  native size they look like a thumbnail, and any interpolation smudges them. At double and
  unfiltered the pixel stays hard, which is how the machine looks.
- **Maps are SCALED DOWN with Lanczos** and bounded by HEIGHT, not width: they are winding, very
  vertical strips (up to 1400x2336) and limiting only the width leaves disproportionate table rows.

The originals stay where they were and the page links to them.

Use: uv run scripts/make-readme-images.py
"""

import os
import sys

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs/img/radendur/readme")


SHOTS = [  # MAME captures, scaled up
    "docs/img/radendur/starts/L0s0_sec00_EASY_start.png",
    "docs/img/radendur/starts/L0s1_sec01_EASY_start.png",
    "docs/img/radendur/starts/L0s2_sec02_EASY_start.png",
    "docs/img/radendur/starts/L1s0_sec04_MEDIUM_start.png",
    "docs/img/radendur/starts/L2s0_sec08_HARD_start.png",
]
MAPS = [  # maps from the ROM, scaled down
    "docs/img/radendur/tracks/L0-seg0_start.png",
    "docs/img/radendur/tracks/L0-seg1.png",
    "docs/img/radendur/tracks/L0-seg2.png",
    "docs/img/radendur/tracks/L1-seg0_start.png",
    "docs/img/radendur/tracks/L2-seg0_start.png",
]
BROKEN = [  # unfinished sections, rendered from the ROM
    "docs/img/radendur/sections/sec05_L1s1.png",
    "docs/img/radendur/sections/sec12_L3s0.png",
    "docs/img/radendur/sections/sec13_L3s1.png",
]
# Zooms illustrating the drawing order: (source, output name).
# radendur-track-details.py (name_for) names the source and it may change; the output name is what
# the page links to, so it is fixed here.
IMG = "docs/img/radendur"

DETAIL = [
    (f"{IMG}/detail/detail_L0_seg0_start_desert.png", "detail-L0_start_desert.png"),
    (f"{IMG}/detail/detail_L1_seg0_start_jungle.png", "detail-L1_start_jungle.png"),
    (f"{IMG}/detail/detail_L2_seg0_start_mountain.png", "detail-L2_start_mountain.png"),
]
MAP_MAX_H, BROKEN_MAX_H, DETAIL_MAX_H = 620, 420, 460


def upscale(src, scale):
    im = Image.open(os.path.join(ROOT, src)).convert("RGB")
    return im.resize((im.width * scale, im.height * scale), Image.NEAREST)


def fit_height(src, max_h):
    im = Image.open(os.path.join(ROOT, src)).convert("RGB")
    if im.height <= max_h:
        return im
    return im.resize((max(1, im.width * max_h // im.height), max_h), Image.LANCZOS)


def save(im, name):
    # 256 colours, as the original art is: Lanczos's gradients would otherwise make the scaled-down
    # image weigh more than its source.
    path = os.path.join(OUT, name)
    im.convert("P", palette=Image.ADAPTIVE, colors=256).save(path, optimize=True)
    kb = os.path.getsize(path) // 1024
    print(f"  {name:34} {im.width:>5}x{im.height:<5} {kb:>5} KB")


def check_inputs():
    """Fails before writing anything if a source is missing, so no half-regenerated set is left."""
    sources = SHOTS + MAPS + BROKEN + [d for d, _ in DETAIL]
    missing = [f for f in sources if not os.path.exists(os.path.join(ROOT, f))]
    if missing:
        print("Sources are missing. The catalogue is not versioned: regenerate it first with")
        print("  uv run scripts/radendur_tracks_all.py")
        print("  uv run scripts/radendur-track-details.py")
        print("  uv run scripts/radendur-sections-broken.py")
        for f in missing:
            print(f"  missing: {f}")
        return False
    return True


def main():
    if not check_inputs():
        return 1
    os.makedirs(OUT, exist_ok=True)
    print("MAME captures (x2, nearest neighbour):")
    for s in SHOTS:
        save(upscale(s, 2), "shot-" + os.path.basename(s).replace("_start", ""))
    print("maps from the ROM (scaled down):")
    for m in MAPS:
        save(fit_height(m, MAP_MAX_H), "map-" + os.path.basename(m))
    print("unfinished sections:")
    for b in BROKEN:
        save(fit_height(b, BROKEN_MAX_H), "broken-" + os.path.basename(b))
    print("detail zooms:")
    for d, out_name in DETAIL:
        save(fit_height(d, DETAIL_MAX_H), out_name)
    total = sum(os.path.getsize(os.path.join(OUT, f)) for f in os.listdir(OUT)) // 1024
    print(f"\ntotal of what the README loads: {total} KB")


if __name__ == "__main__":
    sys.exit(main())
