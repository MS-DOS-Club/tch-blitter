#!/usr/bin/env python3
"""radendur-track-details.py -- zoomed details of each radendur level's START and STRETCHES, from
the ROM (never run-time data), for docs/img/radendur/detail/. It complements
radendur_tracks_all.py (complete maps). The crop is chosen AUTOMATICALLY: each section's densest
window in content (= stands/START/billboards), at native resolution.

Data model (read from the 68000; see disasm/):
  section = (level<<2) + segment ; section table at 0xA2A62 ; 16 sections (0..15).
  The menu IS wired: EASY/MEDIUM/HARD/EXPERT select the 4 levels (desert/jungle/mountain/n3) and
  the race starts at seg 0 of the chosen level.
  Seg 3 is a duplicate of seg 2 and is not loaded (the loop wraps at seg 3 -> next level).
  The stretches that hang do so because of the prototype's malformed data, not for want of wiring.

Use: uv run --with pillow --with numpy scripts/radendur-track-details.py
"""

import os
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image
from radendur_track_render import Renderer, load_gfx, load_maincpu
from radendur_tracks_all import content_crop, section_is_clean

Image.MAX_IMAGE_PIXELS = None

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs/img/radendur/detail")
WIN_W, WIN_H = 1500, 950  # the detail's size in native px
DS = 32  # downsample of the density map

# manifest of the 16 sections: sec -> (level, seg, theme, difficulty, role, state)
# state: clean | undecorated | interleaved (the prototype's incomplete format)
# `undecorated`: a continuous, coherent layout with none of its scenery (section 13).
# The theme, role and state VALUES are also what the published PNG names are built from
# (`name_for`), and they are shown verbatim: the table and the file names are the same words.
SECTIONS = {
    0: (0, 0, "desert", "EASY", "start", "clean"),
    1: (0, 1, "desert", "EASY", "stretch", "clean"),
    2: (0, 2, "desert", "EASY", "stretch", "clean"),
    3: (0, 3, "desert", "EASY", "dup-seg2 (unused)", "clean"),
    4: (1, 0, "jungle", "MEDIUM", "start", "clean"),
    5: (1, 1, "jungle", "MEDIUM", "stretch", "interleaved"),
    6: (1, 2, "jungle", "MEDIUM", "stretch", "interleaved"),
    7: (1, 3, "jungle", "MEDIUM", "dup-seg2 (unused)", "interleaved"),
    8: (2, 0, "mountain", "HARD", "start", "clean"),
    9: (2, 1, "mountain", "HARD", "stretch", "interleaved"),
    10: (2, 2, "mountain", "HARD", "stretch", "interleaved"),
    11: (2, 3, "mountain", "HARD", "dup-seg2 (unused)", "interleaved"),
    12: (3, 0, "(no theme)", "EXPERT", "start", "interleaved"),
    13: (3, 1, "(no theme)", "EXPERT", "stretch", "undecorated"),
    14: (3, 2, "(no theme)", "EXPERT", "stretch", "interleaved"),
    15: (3, 3, "(no theme)", "EXPERT", "dup-seg2 (unused)", "interleaved"),
}
# only the sections with coherent content get a detail render
RENDER = [0, 1, 2, 4, 8]


def densest_box(img):
    """The WIN_W x WIN_H window (native px) with the most content (non-black) in the image."""
    a = np.asarray(img.convert("RGB"))
    mask = (a.sum(2) > 24).astype(np.float32)
    height, width = mask.shape
    dh, dw = height // DS, width // DS
    small = mask[: dh * DS, : dw * DS].reshape(dh, DS, dw, DS).sum((1, 3))
    wh, ww = max(1, WIN_H // DS), max(1, WIN_W // DS)
    ii = np.pad(small.cumsum(0).cumsum(1), ((1, 0), (1, 0)))
    best, by, bx = -1, 0, 0
    for y in range(0, dh - wh + 1):
        for x in range(0, dw - ww + 1):
            s = ii[y + wh, x + ww] - ii[y, x + ww] - ii[y + wh, x] + ii[y, x]
            if s > best:
                best, by, bx = s, y, x
    px, py = bx * DS, by * DS
    return (px, py, min(px + WIN_W, width), min(py + WIN_H, height))


def name_for(sec):
    lvl, seg, theme, _dif, role, _st = SECTIONS[sec]
    return f"detail_L{lvl}_seg{seg}_{role}_{theme}"


def write_manifest():
    lines = [
        "# Track details (docs/img/radendur/detail/)",
        "",
        "A zoom into the densest area (stands/START/signs) of each section, rendered from the ROM",
        "with `scripts/radendur-track-details.py` (never from data captured at run time).",
        "",
        "Structure: `section = (level<<2) + segment`, table at `0xA2A62`, 16 sections.",
        "The menu paints EASY/MEDIUM/HARD (difficulty) plus a desert/jungle/mountain stretch",
        "(= Level 0/1/2). Seg 3 = a duplicate of seg 2 that the menu never selects; forced in RAM,",
        "it ends within seconds (`../starts/README.md`).",
        "",
        "| Sec | Level | Seg | Theme | Difficulty | Role | State | Detail |",
        "|----:|:-----:|:---:|-------|------------|------|-------|--------|",
    ]
    for sec in range(16):
        lvl, seg, theme, difficulty, role, st = SECTIONS[sec]
        det = f"`{name_for(sec)}.png`" if sec in RENDER else "-"
        lines.append(f"| {sec} | {lvl} | {seg} | {theme} | {difficulty} | {role} | {st} | {det} |")
    lines += [
        "",
        "State: **clean** = renders coherently; **undecorated** = the layout is continuous and",
        "coherent and what is missing is ALL the scenery (that is section 13, and it is a",
        'different development stage from "corrupt data": see `../sections/sec13_L3s1.png`);',
        "**interleaved** = the prototype's incomplete format (a 2-good-2-garbage pattern; the",
        "share of broken entries per section is in `../sections/README.md`).",
        "Only Level 0 (desert) is complete (segs 0-2); Level 1 (jungle) and 2 (mountain) only",
        "have their start; Level 3 is unfinished, although **EXPERT can be chosen in the menu**:",
        "what does not exist is a finished track behind it.",
        "",
        "The empirical sweep of the 16 sections (which draw, which hang, which are playable) "
        "is in `../starts/README.md`; the maps of all of them rendered from the ROM are in "
        "`../sections/README.md`.",
        "",
        "## Regenerating",
        "",
        "They are versioned, and regenerate from the ROM with "
        "`uv run scripts/radendur-track-details.py` (the other renders: "
        "`../sections/README.md`).",
        "",
    ]
    with open(os.path.join(OUT, "README.md"), "w") as f:
        f.write("\n".join(lines))


def main():
    os.makedirs(OUT, exist_ok=True)
    z = zipfile.ZipFile(os.path.join(ROOT, "run/mame_roms/radendur.zip"))
    rd = Renderer(load_maincpu(z), load_gfx(z))
    for sec in RENDER:
        if not section_is_clean(rd, sec):
            print(f"sec {sec}: not clean, skipped")
            continue
        img = rd.render(sec, crop=content_crop(rd, sec))[0]
        box = densest_box(img)
        det = img.crop(box)
        path = os.path.join(OUT, name_for(sec) + ".png")
        det.save(path)
        lvl, seg, theme, difficulty, role, _ = SECTIONS[sec]
        print(
            f"sec {sec:2d} L{lvl} seg{seg} {difficulty:6s} {theme:9s} {role:6s}: "
            f"{box} {det.size} -> {os.path.basename(path)}"
        )
    write_manifest()
    print(f"manifest -> {os.path.join(OUT, 'README.md')}")


if __name__ == "__main__":
    main()
