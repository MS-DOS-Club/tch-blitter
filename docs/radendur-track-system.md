# The Radical Enduro track system

How Radical Enduro's engine stores and draws a track, read from the ROM and the 68000 code: the
data format, the two framebuffer planes and the paint order, and the palette. The track is an
**isometric sprite system** (Filmation / *Knight Lore* style): no raster warps the screen and no 2D
tilemap holds it; sprites stacked by depth make the 3/4 view. It is reproduced in
Python by `scripts/radendur_track_render.py`, with no emulator; the game itself, and the
captures that show the model at work, are on [the Radical Enduro page](games/radical-enduro.md).

## Data format of a track

The map is not a 2D array nor a bitmap: it is a **display list of sprites in
world cell coordinates**, per section, with triple indirection.

- Level at `0x20100e` (0-3), segment at `0x20101a` (0-3):
  `section = (level << 2) + segment` (0..15).
- Section table at `0xa2a62` (16 longs) -> section pointer. 12 byte header:
  `+0` LONG `count1` (number of 6 byte entries, starting at `ptr+0xC`).
- **Entry** (6 bytes): `+0` x (s16, cell) · `+2` y (s16, cell) · `+4` ref
  (u16) = `ctrl` (bits 14-15) `|` `id` (bits 0-13).
- `id` -> sprite table `0x29fc`: a sprite is `w` x `h` (`+0`, `+2`) followed by
  `w*h` **tilevals** (u16).
- `tileval` -> tile table `0xabf22` (16 bytes per tile): `+0` w1 · `+2` h1 ·
  `+4/+8` X offsets (normal / flip) · `+6` Y offset · `+0xC` LONG source. The real
  tile measures `(w1+1) x (h1+1)`, not a fixed 32x32. Source address in the graphics
  ROM: `page = b3>>2` (512x512 pages, 8bpp), `su0 = b2 + 256*(b3&1)`,
  `sv0 = b0 + 256*((b3>>1)&1)`. A 1:1 blit samples from row `sv0+1`, because the first source
  row of each tile is a one-pixel border; a scaled one does not. **Bit 15 of the tileval = flip-X**
  (uses the `+8` offset).

## The two planes and the paint order (hardware model)

The blitter (the two Actel FPGAs) **has no Z-buffer**: it only writes the pixel if
it is not transparent (pen 0). The order is set by the **68000 code** (drawer `FUN_000e0646`,
feeder of the high objects `displaylist_walker` at `0xe2dfe`; decompilable with `scripts/ghidra/DumpFuncs.java`).

1. **Two framebuffer planes.** The track/scenery goes to the **BG** plane; the bike
   and the dynamic objects go to the **FG** plane. `screen_update` composes **FG
   always over BG**: the bike always passes in front of the ground. Transparency
   = pen 0, with no colour blending.
2. **The drawer builds a GRID by cells.** It walks the visible entries of the
   section in **descending index** order and stamps **each tile** of the sprite into
   **its** cell `(x+c, y+r)`. The base ground (`ctrl=0`) overwrites slot0 of the cell;
   the flat markings (`ctrl=0x4000`) and the tall objects (`ctrl=0x8000`) are appended
   to the cell's list.
3. **The feeder walks the grid ROW by ROW** (cy asc, cx asc) and, per cell,
   emits its tiles in slot order. There are **two paths, chosen by the control bit**:
   the flat stuff (base + `0x4000`) is painted into the BG buffer; the tall ones
   (`0x8000`: palm trees, columns, signs, people) go into an **object list** that is
   drawn **on top** of everything flat.
4. Result: **3 passes** (base -> `0x4000` flats -> `0x8000` talls), all
   **per cell** (per tile) walking the grid row by row, and within each cell in
   descending index order.

The key is that **it is per cell, NOT per whole sprite**: each tile is drawn at the
depth of ITS cell. That is why a tall sign (with its face displaced upwards by its
Y offset) **is not cut** by the grass or the trunk of a nearer row: they fall on
different screen rows, where one depth for the whole sprite would cut the sign horizontally. The
order does **not depend on the type** of sprite (a bush can go in
front or behind): it is purely positional (cell) plus the emission order.

## The palettes

- The palette is set by the **BT478 RAMDAC**: **256 colours, 8 bits per channel**
  (0-255), **a single bank shared** by the whole screen (there is no per box or per
  plane palette). The values are uploaded as they are to the RGB888 port: they are
  8-bit direct, **not** 6-bit (no `<<2` applied).
- It is **assembled by ranges** from the `0xd6b12` table (the record layout and its copier are in
  [disasm/crashes-radendur.md](../disasm/crashes-radendur.md)); the "environment" of each
  level (which sets the vegetation, ground and other colours) is determined by the
  `env-id` of the section's props. Part of the ground range is additionally loaded at
  runtime.

## Reproduction in Python

`scripts/radendur_track_render.py` reconstructs any screen by reading the ROM: it emulates
the blitter's tile sampling (vectorised with numpy), the per cell order of the three
passes and the assembled palette. `scripts/radendur_tracks_all.py` renders the five
playable sections (0, 1, 2, 4 and 8) in full into `docs/img/radendur/tracks/`: the light versions
stay there, the full-resolution ones go to `tracks/full/`. All sixteen, the unfinished ones
included, are rendered by `scripts/radendur-sections-broken.py` into
[docs/img/radendur/sections/](img/radendur/sections/README.md).
