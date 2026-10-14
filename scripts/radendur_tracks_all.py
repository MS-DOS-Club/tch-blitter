#!/usr/bin/env python3
"""radendur_tracks_all.py -- renders ALL of radendur's tracks (complete maps) from the ROM with
the real hardware model (see radendur_track_render.py), for verification and documentation.
It saves the ORIGINAL at full resolution in docs/img/radendur/tracks/full/ and a RESCALED version
(for the README) in docs/img/radendur/tracks/.

Use: uv run scripts/radendur_tracks_all.py
"""

import os
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image
from radendur_track_render import Renderer, load_gfx, load_maincpu

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs/img/radendur/tracks")
FULL = os.path.join(OUT, "full")
README_MAXW = 1400  # maximum width of the README's rescaled version

# Only the sections with COHERENT data (0% rubbish entries). Verified with section_is_clean():
# sections L1 seg1+, L2 seg1+ and L3 have ~49% of entries with impossible coords (an interleaved
# 2-good-2-rubbish pattern) = a different/incomplete format of the prototype (never finished); they
# do not form tracks and are NOT rendered as maps. Only L0 is finished (segs 0-2; seg 3 = a
# byte-identical duplicate of 2) plus the starts of L1 and L2.
MAPS = [
    (0, "L0-seg0_start", "Level 0, seg 0 -- Start (desert / Egyptian motifs)"),
    (1, "L0-seg1", "Level 0, seg 1 -- Desert"),
    (2, "L0-seg2", "Level 0, seg 2 -- Desert (seg 3 = duplicate)"),
    (4, "L1-seg0_start", "Level 1, seg 0 -- Jungle (start, KANGAROO MOTOCROSS billboard)"),
    (8, "L2-seg0_start", "Level 2, seg 0 -- Mountain (pines, rock, cabin)"),
]


def section_is_clean(rd, section, probe=200):
    """True if the first `probe` entries have sane coords (<5% rubbish). The prototype's
    unfinished sections give ~49% (a corrupt interleaved format)."""
    from radendur_track_render import SECTION_TABLE

    ptr = rd.u32(SECTION_TABLE + section * 4)
    cur, count1 = ptr + 0xC, rd.u32(ptr) & 0xFFFF
    bad = n = 0
    for i in range(min(probe, count1)):
        a = cur + i * 6
        if a + 6 > len(rd.rom):
            break
        x, y = rd.s16(a), rd.s16(a + 2)
        n += 1
        if not (-16 <= x <= 4096 and -16 <= y <= 4096):
            bad += 1
    return n > 0 and bad * 100 // n < 5


def content_crop(rd, section, lo=0.01, hi=0.99):
    """The real content's bbox (percentile lo..hi), to exclude outlier entries that inflate the
    bounding box with empty cells."""
    ents, _, _ = rd.parse(section)
    xs = sorted(e[0] for e in ents)
    ys = sorted(e[1] for e in ents)
    n = len(xs)

    def p(v, q):
        return v[min(n - 1, int(n * q))]

    return (p(xs, lo), p(ys, lo), p(xs, hi), p(ys, hi))


def main():
    z = zipfile.ZipFile(os.path.join(ROOT, "run/mame_roms/radendur.zip"))
    rd = Renderer(load_maincpu(z), load_gfx(z))
    os.makedirs(FULL, exist_ok=True)
    for sec, fid, name in MAPS:
        if not section_is_clean(rd, sec):
            print(f"{fid}: SKIPPED (section {sec} incomplete/interleaved in the prototype)")
            continue
        crop = content_crop(rd, sec)
        res = rd.render(sec, crop=crop)
        if res is None:
            print(f"{fid}: no entries")
            continue
        img = res[0]
        full_path = os.path.join(FULL, f"{fid}.png")
        img.save(full_path)
        # rescaled for the README (maximum width README_MAXW, keeping the aspect ratio)
        small = img.copy()
        if small.width > README_MAXW:
            small = small.resize(
                (README_MAXW, round(img.height * README_MAXW / img.width)), Image.LANCZOS
            )
        small_path = os.path.join(OUT, f"{fid}.png")
        small.save(small_path)
        print(
            f"{fid}: {img.size[0]}x{img.size[1]}px original -> {small.size[0]}x{small.size[1]} "
            f"README  ({name})"
        )


if __name__ == "__main__":
    main()
