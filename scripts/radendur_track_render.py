#!/usr/bin/env python3
"""radendur_track_render.py -- reconstructs radendur's track screens/maps in Python from the ROM,
emulating the blitter and the ISOMETRIC render model (Filmation, Knight Lore style): sprites
stacked by depth, not a raster deformation of the screen.

Data model (reverse engineered from the driver):
  level 0x20100e (0-3), segment 0x20101a (0-3) -> section = (level<<2)+seg  [0..15]
  section table 0xa2a62[sec] -> section pointer
    header 12B: +0 LONG count1 (6B entries); +4 LONG count2 (44B props)
    entry 6B: +0 x:s16(cell) +2 y:s16(cell) +4 ref:u16 = ctrl(14-15)|id(0-13)
      id=ref&0x3fff -> sprite table 0x29fc: +0 w +2 h +4 w*h tilevals
        tv&0x7fff -> tile table 0xabf22 (16B): +0 w1 +2 h1 +4 xoff +6 yoff +8 xoff2
                     +0xc srcLONG=[b0 b1 b2 b3]
          blit size = (w1+1)x(h1+1); page=(b3>>2)*0x40000; su0=b2+256*(b3&1);
          sv0=b0+256*(b3&2); tileval bit15 = FLIP-X (uses xoff2 at +8)
    props 44B (at ptr+0xC+count1*6): +0x1c env-id -> palette arg 0x13+id

Render (the hardware's REAL model, read from the disassembly):
  - It is PER CELL (per tile), NOT per atomic sprite. The drawer FUN_000e0646 stamps each tile of
    the sprite into its grid cell; the feeder walks the grid ROW by ROW and emits per cell. 3
    passes by the control bit: (1) base ground ctrl=0; (2) planes 0x4000 into the BG; (3) tall
    ones 0x8000 ON TOP (they go to the object list). Within each cell, DESCENDING index (the
    drawer walks the entries from high index to low).
  - Per cell each tile goes to ITS cell's depth: a tall billboard (large yoff) is NOT cut by the
    grass of a nearer row (they land on different screen rows). Per-feet/anchor models (whole
    sprite) cut the billboard; this one does not.
  - PALETTE: BT478 = 1 shared bank of 256 8-bit colours (NOT per box). It is assembled by ranges
    from 0xd6b12; the level's environment is set by the props' env-ids.

Use: uv run scripts/radendur_track_render.py            (one section per level -> tmp/map-repro/)
     uv run scripts/radendur_track_render.py <section>       (a specific section)
     uv run scripts/radendur_track_render.py <section> --crop x0 y0 x1 y1   (crop in cells)
"""

import argparse
import os
import zipfile

import numpy as np
from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SECTION_TABLE = 0xA2A62
SPRITE_TABLE = 0x29FC
TILE_TABLE = 0xABF22
PAL_ASM = 0xD6B12
CELL = 32
# radendur's gfx1 layout: (rom, offset). Each 512x512 8bpp page = 0x40000.
GFX_LAYOUT = [
    ("endu.u52", 0x000000),
    ("endu.u53", 0x080000),
    ("endu.u54", 0x100000),
    ("endu.u55", 0x180000),
    ("endu.u56", 0x200000),
    ("endu.u57", 0x280000),
    ("endu.u58", 0x300000),
    ("endu.u59", 0x380000),
    ("endu.u200", 0x400000),
    ("endu.u201", 0x480000),
    ("endu.u202", 0x500000),
    ("endu.u203", 0x580000),
    ("endu.u204", 0x600000),
    ("endu.u205", 0x680000),
]


def load_maincpu(z):
    """Main 68000 ROM, interleaved u21(even)/u19(odd)."""
    even, odd = z.read("endu.u21"), z.read("endu.u19")
    out = bytearray(len(even) + len(odd))
    out[0::2] = even
    out[1::2] = odd
    return bytes(out)


def load_gfx(z):
    blob = bytearray(0x700000)
    for name, off in GFX_LAYOUT:
        d = z.read(name)
        blob[off : off + len(d)] = d
    return bytes(blob)


class Renderer:
    def __init__(self, rom, gfx):
        self.rom = rom
        self.gfx = gfx
        # gfx as 28 pages of 512x512 (8bpp) for vectorised sampling with numpy
        self.gfxpages = np.frombuffer(gfx, dtype=np.uint8).reshape(-1, 512, 512)
        self.cache = {}

    def u16(self, k):
        return (self.rom[k] << 8) | self.rom[k + 1]

    def s16(self, k):
        v = self.u16(k)
        return v - 0x10000 if v >= 0x8000 else v

    def u32(self, k):
        return (self.u16(k) << 16) | self.u16(k + 2)

    def tile(self, tv):
        """(nt, xoff, yoff) of the tileval, cached. nt = a uint8 (h, w) array with flip-x ALREADY
        applied; 0 = transparent. None if the descriptor is invalid."""
        if tv in self.cache:
            return self.cache[tv]
        ti = tv & 0x7FFF
        flipx = bool(tv & 0x8000)
        e = TILE_TABLE + ti * 16
        if e + 16 > len(self.rom):
            self.cache[tv] = None
            return None
        w1, h1 = self.u16(e), self.u16(e + 2)
        # bit15 (flip-x) uses the destination offset at +8; the normal one uses +4
        xoff = self.s16(e + 8) if flipx else self.s16(e + 4)
        yoff = self.s16(e + 6)
        b0, b2, b3 = self.rom[e + 0xC], self.rom[e + 0xE], self.rom[e + 0xF]
        page = b3 >> 2
        su0 = b2 + (256 if b3 & 1 else 0)
        sv0 = b0 + (256 if b3 & 2 else 0)
        w, h = w1 + 1, h1 + 1
        if not (1 <= w <= 512 and 1 <= h <= 512) or page >= len(self.gfxpages):
            self.cache[tv] = None
            return None
        # vectorised sampling with a 512 wrap. seam fix (v_bias=1, as in the MAME driver): the
        # first source row of every 1:1 tile is a 1 px edge of rubbish; sample from sv0+1.
        rows = (sv0 + 1 + np.arange(h)) & 0x1FF
        cols = (su0 + np.arange(w)) & 0x1FF
        nt = self.gfxpages[page][np.ix_(rows, cols)]
        if flipx:
            nt = nt[:, ::-1]
        nt = np.ascontiguousarray(nt)
        self.cache[tv] = (nt, xoff, yoff)
        return self.cache[tv]

    def parse(self, section):
        ptr = self.u32(SECTION_TABLE + section * 4)
        count1 = self.u32(ptr) & 0xFFFF
        cur = ptr + 0xC
        ents = []
        for i in range(count1):
            a = cur + i * 6
            if a + 6 > len(self.rom):
                break
            x, y, ref = self.s16(a), self.s16(a + 2), self.u16(a + 4)
            if -16 <= x <= 4096 and -16 <= y <= 4096:
                ents.append((x, y, ref, i))
        return ents, ptr, count1

    def section_palette(self, section):
        """Assembles the section's 8-bit RAMDAC palette (256 col): base ranges from 0xd6b12, and
        the environment via the props' env-ids (offset 0x1c -> arg 0x13+id)."""
        pal = [0] * 768

        def apply(arg):
            e = PAL_ASM + arg * 4
            start, count = self.rom[e + 2], self.rom[e + 3]
            off = self.u16(e + 4)
            src = PAL_ASM + off
            # start + count can run past the 256 colours (the race palette's rubbish descriptor:
            # start=180, count=98); the board writes on into whatever RAM follows, here only what
            # fits is copied
            for i in range(min(count, 256 - start)):
                for k in range(3):
                    pal[(start + i) * 3 + k] = self.rom[src + i * 3 + k]

        for a in (1, 2, 0x0A):  # defaults: base 1-216, tail 225-255, middle 217-224
            apply(a)
        # env from the section's props (in ascending id order, like the loader)
        ptr = self.u32(SECTION_TABLE + section * 4)
        count1 = self.u32(ptr) & 0xFFFF
        count2 = self.u32(ptr + 4) & 0xFFFF
        props = ptr + 0xC + count1 * 6
        envs = set()
        for i in range(count2):
            v = self.u16(props + i * 44 + 0x1C)
            if 0 <= v <= 0x63:
                envs.add(v)
        for v in sorted(envs):
            apply(0x13 + v)
        return pal

    def render(self, section, crop=None):
        ents, ptr, count = self.parse(section)
        if not ents:
            return None
        xs = [e[0] for e in ents]
        ys = [e[1] for e in ents]
        cx0, cy0, cx1, cy1 = crop if crop else (min(xs), min(ys), max(xs), max(ys))
        wc, hc = cx1 - cx0 + 1, cy1 - cy0 + 1
        cw, ch = wc * CELL, hc * CELL
        canvas = np.zeros((ch, cw), dtype=np.uint8)
        # DRAWING ORDER = THE HARDWARE'S REAL MODEL, read from the disassembly (drawer
        # FUN_000e0646 + flat feeder FUN_000e2d44 + tall feeder FUN_000e2dfe). It is NOT an
        # invented sort nor a per-feet one: it is PER CELL (per tile), grid row by row, in THREE
        # passes.
        #
        # 1) The drawer stamps EACH tileval of a sprite into ITS grid cell (x+c, y+r), walking the
        #    section's entries in DESCENDING INDEX order (e0646's loop starts at the max index and
        #    decrements A0). base (ctrl=0) overwrites the cell's slot0; 0x4000 and 0x8000 are
        #    APPENDED to the cell's list.
        # 2) The feeder walks the grid ROW by ROW (cy asc), column by column (cx asc), and per cell
        #    emits its tiles in slot order (= stamping order = DESCENDING index).
        # 3) TWO paths by the control bit: the FLAT ones (base + 0x4000) go to the BG buffer; the
        #    TALL ones (0x8000: palms/columns/billboards/people) go to a SEPARATE LIST (0x203510)
        #    drawn as OBJECTS ON TOP of everything flat.
        #
        # So each tile is drawn at its cell's depth, not the whole sprite's: a tall billboard (a
        # face with a large yoff) is not cut by the grass of a nearer row.
        base, flat, tall = {}, {}, {}  # cell -> [(idx, tv, gx, gy)]
        for x, y, ref, i in ents:
            ctrl = ref & 0xC000
            idn = ref & 0x3FFF
            sp = self.u32(SPRITE_TABLE + idn * 4)
            if sp + 4 > len(self.rom):
                continue
            w, h = self.u16(sp), self.u16(sp + 2)
            if not (0 < w <= 64 and 0 < h <= 64):
                continue
            layer = base if ctrl == 0x0000 else (flat if ctrl == 0x4000 else tall)
            for r in range(h):
                for c in range(w):
                    to = sp + 4 + (r * w + c) * 2
                    if to + 2 > len(self.rom):
                        continue
                    tv = self.u16(to)
                    if tv == 0:
                        continue
                    cell = ((x + c) << 16) | ((y + r) & 0xFFFF)
                    layer.setdefault(cell, []).append((i, tv, x + c, y + r))

        def blit(tv, gx, gy):
            t = self.tile(tv)
            if t is None:
                return
            nt, xoff, yoff = t  # nt already carries the flip-x applied
            th, tw = nt.shape
            dx = (gx - cx0) * CELL + xoff
            dy = (gy - cy0) * CELL + yoff
            sx0, sy0 = max(0, -dx), max(0, -dy)
            sx1, sy1 = min(tw, cw - dx), min(th, ch - dy)
            if sx1 <= sx0 or sy1 <= sy0:
                return
            sub = nt[sy0:sy1, sx0:sx1]
            region = canvas[dy + sy0 : dy + sy1, dx + sx0 : dx + sx1]
            mask = sub != 0
            region[mask] = sub[mask]

        def emit(layer):
            # grid row by row (cy asc, cx asc); within the cell, DESCENDING index (the drawer's
            # stamping order: high index first -> to the back of the cell).
            for cell in sorted(layer, key=lambda k: (k & 0xFFFF, k >> 16)):
                for _idx, tv, gx, gy in sorted(layer[cell], key=lambda t: -t[0]):
                    blit(tv, gx, gy)

        emit(base)  # 1) flat ground at the back
        emit(flat)  # 2) flat markings/fences (0x4000) over the ground, in the BG
        emit(tall)  # 3) tall objects (0x8000) ON TOP, like the hardware's object list
        im = Image.fromarray(canvas, "P")
        im.putpalette(self.section_palette(section))
        return im.convert("RGB"), cx0, cy0, ptr, count, len(ents)


def add_grid(im, ox_cells, oy_cells, step=8):
    """A 32px cell grid with ABSOLUTE world-cell labels (column yellow, row cyan)."""
    im = im.copy()
    dr = ImageDraw.Draw(im)
    w, h = im.size
    for cx in range(w // CELL + 1):
        bold = (ox_cells + cx) % step == 0
        dr.line([(cx * CELL, 0), (cx * CELL, h)], fill=(255, 60, 60) if bold else (70, 70, 70))
    for cy in range(h // CELL + 1):
        bold = (oy_cells + cy) % step == 0
        dr.line([(0, cy * CELL), (w, cy * CELL)], fill=(255, 60, 60) if bold else (70, 70, 70))
    for cx in range(w // CELL):
        if (ox_cells + cx) % step == 0:
            dr.text((cx * CELL + 1, 1), str(ox_cells + cx), fill=(255, 255, 0))
    for cy in range(h // CELL):
        if (oy_cells + cy) % step == 0:
            dr.text((1, cy * CELL + 1), str(oy_cells + cy), fill=(0, 255, 255))
    return im


def main():
    # argparse rather than a hand walk of sys.argv: a word it does not know is rc=2, not dropped.
    ap = argparse.ArgumentParser(description="Render Radical Enduro track sections from the ROM.")
    ap.add_argument("section", nargs="?", type=lambda v: int(v, 0), help="default: 0 4 8 13")
    ap.add_argument("--crop", nargs=4, type=lambda v: int(v, 0), metavar=("X0", "Y0", "X1", "Y1"))
    args = ap.parse_args()
    crop = tuple(args.crop) if args.crop else None
    z = zipfile.ZipFile(os.path.join(ROOT, "run/mame_roms/radendur.zip"))
    rd = Renderer(load_maincpu(z), load_gfx(z))
    out_dir = os.path.join(ROOT, "tmp/map-repro")
    os.makedirs(out_dir, exist_ok=True)
    sections = [args.section] if args.section is not None else [0, 4, 8, 13]
    for s in sections:
        res = rd.render(s, crop=crop)
        if res is None:
            print(f"section {s}: no entries")
            continue
        img, cx0, cy0, ptr, count, drawn = res
        img = add_grid(img, cx0, cy0)
        path = os.path.join(out_dir, f"section_{s}_L{s >> 2}.png")
        img.save(path)
        print(
            f"section {s} (L{s >> 2}): ptr=0x{ptr:06x} entries={count} drawn={drawn} "
            f"origin cell ({cx0},{cy0}) {img.size} -> {path}"
        )


if __name__ == "__main__":
    main()
