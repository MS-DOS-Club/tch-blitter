# The capture behind the stall-counter law, blit by blit

What `hardware/registers.yaml` records as `wheelfir_the_law_holds_blit_by_blit` was measured on
this capture, and [`scripts/wheelfir-blit-law.py`](../../../scripts/wheelfir-blit-law.py)
re-derives every figure the record quotes from it. Nothing here needs the romset; the script's
`--full` does, with the MAME clone and `make disasm`, for the parts that read the graphics and the
ROM's descriptor tables.

It was taken in one MAME run of `wheelfir` with this repository's driver, the first 1500 frames of
the attract from boot with no input: at every write of the blitter's trigger (`0x70001e`) the
debugger recorded the blitter's block and, in the same pass, the game's clip rectangle, so the two
files below pair row by row.

| file | what it holds |
|------|---------------|
| `block.rows.xz` | the blitter's words 0..0xe at every write of the trigger |
| `cliprect.rows.xz` | the game's software clip rectangle (the four words at `0x20b4b8`: xmin, ymin, xmax, ymax) at the same writes |
| `f1331.png`, `f1339.png`, `f1389.png` | MAME snapshots of three race frames where the clipped roadside objects stand |

Each row is one write, seven fields separated by spaces:

    r <write> <frame> <pc> <value> <mask> <words>

`write` numbers the trigger writes from 1 and is the key that pairs the two files; `frame` is the
frame of the pass; `pc` the 68000 instruction that wrote the trigger; `value` the word written to the
trigger, in hex (`ffff` fires a blit, `0` arms the next one); `mask` the bytes of it written;
`words` the block read there, four hex digits per word.
