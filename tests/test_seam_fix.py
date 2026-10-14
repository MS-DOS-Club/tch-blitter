"""The seam fix: the first source row of every 1:1 tile is a one-pixel border in the graphics ROM,
so a tile is sampled from `sv0 + 1`, and the bias goes on the row only, never on the column.
"""

import numpy as np
from radendur_track_render import TILE_TABLE

# a sample from the head of the table, enough to cover tiles whose two first rows differ
TILES = 64


def descriptor_of(rd, ti):
    """(page, su0, sv0, w, h) of tile `ti`, read the same way tile() reads them."""
    e = TILE_TABLE + ti * 16
    w1, h1 = rd.u16(e), rd.u16(e + 2)
    b0, b2, b3 = rd.rom[e + 0xC], rd.rom[e + 0xE], rd.rom[e + 0xF]
    return b3 >> 2, b2 + (256 if b3 & 1 else 0), b0 + (256 if b3 & 2 else 0), w1 + 1, h1 + 1


def tiles(rd):
    for ti in range(TILES):
        page, su0, sv0, w, h = descriptor_of(rd, ti)
        if page >= len(rd.gfxpages) or not (1 <= w <= 512 and 1 <= h <= 512):
            continue
        got = rd.tile(ti)
        if got is not None:
            yield ti, rd.gfxpages[page], su0, sv0, w, h, got[0]


def test_the_tile_is_sampled_one_row_further_in(rd):
    for ti, page, su0, sv0, w, _h, nt in tiles(rd):
        cols = (su0 + np.arange(w)) & 0x1FF
        assert np.array_equal(nt[0], page[(sv0 + 1) & 0x1FF, cols]), f"tile {ti}: row is not sv0+1"


def test_the_fix_is_vertical_only(rd):
    for ti, page, su0, sv0, _w, h, nt in tiles(rd):
        rows = (sv0 + 1 + np.arange(h)) & 0x1FF
        assert np.array_equal(nt[:, 0], page[rows, su0 & 0x1FF]), f"tile {ti}: column is not su0"
