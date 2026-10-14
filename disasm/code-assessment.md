# How finished radendur actually is

What the disassembled code says about Radical Enduro: a finished game or an unfinished skeleton.

## Verdict

**It is a finished game at the logic level, with a defective pass to hardware.** It is not a
skeleton and not a demo: the game code is complete and structured. What fails on the dump is
starting a race (display-list cursors overwritten with ROM bytes) and, on some sections, a race
already under way (a runaway object loop), not any absence of game code.

## Evidence of maturity (maincpu)

| Metric | Where it is | Reading |
|--------|-------------|---------|
| Functions reachable from reset | the table in [../docs/disassembly.md](../docs/disassembly.md) | a large, connected codebase |
| Function sizes | [analysis.txt](analysis.txt), each function with its size | many functions of serious logic, almost no stubs or thunks; complex routines alongside small ones |
| Code against data | [the annotated listing](listings/radendur_maincpu.lst) | the code is a small part of the 1 MB image; the rest is data, tables and tracks, normal in a data-heavy game |
| Calls and arithmetic | the same listing | modular code built on `jsr`/`bsr`, with real projection and scaling maths in its multiplies and divides |

Interpretation:

- **A real entity engine**: the largest function (0xebb84, `object_update`) works on structs
  (fields 0x62/0x8c/0xa4 of an object) with dynamic dispatch (`jsr (a2)`) by behaviour. That is
  rider, opponent and race-state logic, not a placeholder.
- **A complete graphics pipeline**: the clear blits (0x25dc at boot, 0x2856 again from the main
  loop), command dump to 0x700000 (0x2004), display-list render with a cursor (0xe2dfe), a blitter
  interrupt chain and a vblank handler (0x1f2a/0x400), and a per-line interrupt run from a RAM
  copy: the same engine as Wheels & Fire.
- **Sound is present**: the subcpu (reset 0x400) is a working sound driver with an init table, and
  radendur ships its sound ROMs (endu.u63/u65), unlike Kong Ball.
- **A complete attract**: logo, INSERT COINS, the screen cycle. All of it renders.

## What is broken

The mechanism is in **[crashes-radendur.md](crashes-radendur.md)**: a **ROM-driven buffer
overflow** (a memcpy at 0xe2f2c whose destination `0x203208 + 3*step` runs past the palette
buffer and stamps over the display-list cursor block at 0x203508), fed by the environment loop
reading one record past its array. It is the prototype's own overrun, not an unapplied fixup or relocation.

- It happens on pressing START: the race-entry path, not a general failure. The second crash,
  in a race, is a different mechanism with the same ending (crashes-radendur.md, crash 2).
- It is an integration defect of the prototype, not a content one, and it is the board's too: MAME's
  developers note that it *"crashes when selecting track on PCB"*.

## What that means for the restoration

It is repairable, and the `radendurh` ROM repairs it at the source (the environment loop that
reads one record past its array). What limits the game beyond that is its unfinished track data,
not race entry.
