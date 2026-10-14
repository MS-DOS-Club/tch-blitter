#!/usr/bin/env python3
"""radendur-sections-broken.py -- renders ALL sections from the ROM, including the ones
`radendur_tracks_all.py` discards for having impossible coordinates.

It exists to answer ONE question with a proof independent of the emulator: when a section
cannot be played, is it because its DATA is unfinished, or because the emulation fails?
The percentage of impossible coordinates is a number; this is the drawing.
And since it comes straight out of the ROM with no MAME involved, it cannot be contaminated
by a bug in the driver.

Entries with out-of-range coordinates are OMITTED (not clipped to an edge, which would
falsify the map by bunching rubbish against one side), and how many there were is counted.

Use: uv run --with pillow --with numpy scripts/radendur-sections-broken.py
"""

import os
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image
from radendur_track_render import ROOT, SECTION_TABLE, Renderer, load_gfx, load_maincpu

# where docs/img/radendur/sections/README.md says the renders live
OUT = os.path.join(ROOT, "docs/img/radendur/sections")
MAXW = 1100


def render_section(rd, sec):
    """Returns (image, total_entries, skipped_entries), or None if there is nothing."""
    ptr = rd.u32(SECTION_TABLE + sec * 4)
    count1 = rd.u32(ptr) & 0xFFFF
    ents, good, bad = [], 0, 0
    for i in range(count1):
        a = ptr + 0xC + i * 6
        if a + 6 > len(rd.rom):
            break
        x, y, ref = rd.s16(a), rd.s16(a + 2), rd.u16(a + 4)
        if -16 <= x <= 4096 and -16 <= y <= 4096:
            ents.append((x, y, ref))
            good += 1
        else:
            bad += 1
    if not ents:
        return None, good, bad
    res = rd.render(sec)
    if res is None:
        return None, good, bad
    return res[0], good, bad


def main():
    failures = 0
    z = zipfile.ZipFile(os.path.join(ROOT, "run/mame_roms/radendur.zip"))
    rd = Renderer(load_maincpu(z), load_gfx(z))
    os.makedirs(OUT, exist_ok=True)
    print(f"{'sec':>3} {'level/seg':>9} {'good':>7} {'rubbish':>7} {'%':>6}  output")
    for sec in range(16):
        lvl, seg = sec >> 2, sec & 3
        try:
            img, good, bad = render_section(rd, sec)
        except Exception as e:
            failures += 1
            label = f"L{lvl}s{seg}"
            print(f"{sec:>3} {label:>9} {'-':>7} {'-':>7} {'-':>6}  ERROR: {e}")
            continue
        pct = bad * 100.0 / (good + bad) if (good + bad) else 0
        if img is None:
            label = f"L{lvl}s{seg}"
            print(f"{sec:>3} {label:>9} {good:>7} {bad:>7} {pct:>5.1f}%  (no content)")
            continue
        if img.width > MAXW:
            img = img.resize((MAXW, max(1, img.height * MAXW // img.width)), Image.LANCZOS)
        path = os.path.join(OUT, f"sec{sec:02d}_L{lvl}s{seg}.png")
        img.save(path)
        label = f"L{lvl}s{seg}"
        print(f"{sec:>3} {label:>9} {good:>7} {bad:>7} {pct:>5.1f}%  {os.path.basename(path)}")

    # Exiting 0 with a section having failed publishes an incomplete catalogue in silence.
    if failures:
        print(f"\n{failures} sections failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
