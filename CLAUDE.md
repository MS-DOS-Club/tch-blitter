# tch-blitter

Context for a coding assistant working on this repository, and for anyone who wants the map before
the territory. The public documentation starts at `README.md`; this file says how the tree is
organised and which reflexes keep it right. The rules under `.claude/rules/` load when a file they
govern is opened, and `mame-operations.md` in every session.

## What this repository is

The family of **TCH boards with a blitter**: Reality Tennis, Wheels & Fire, Power Ball, Kong Ball
and Radical Enduro. Five games, six romsets, one common video architecture, emulated in MAME. TCH's
other games (Little Robin, Speed Spin, Monsters World, Kick Goal, Action Hollywood) run on other
architectures and are out of scope.

Its origin, and still its deepest work, is the restoration of **Radical Enduro** (TCH / Sator
Videogames). In stock MAME the `radendur` set is `MACHINE_NOT_WORKING` inside `tch/wheelfir.cpp`,
and a comment there says that some courses reach gameplay but crash quickly; here it has a driver of
its own, `tch/radendur.cpp`, which emulates the dump as it is (`radendur`, which hangs on the
prototype's own faults), and a clone set, `radendurv2`, whose maincpu ROM has those faults fixed in
code: it boots, enters a game and finishes a race on the five playable tracks. The board's video
model was resolved by reading the 68000 (`docs/boards/wheels-and-fire-board.md`).

There is no source code of the games, only dumps, so nothing is assembled and the gate is the
observed boot state captured as goldens, not a byte-identical SHA. The one ROM built here is
radendurv2's, from the dump and a patch table (`make v2`).

This is a retro-preservation repository: the public documentation is written for enthusiasts of
vintage programming and arcade hardware, and says what is known, not how long it took to find out.

## Building and running

The romsets are not distributed (`README.md`, Getting started, says how to get and check them).
`make setup` clones MAME at the commit pinned in `scripts/lib/mame_src.sh` into `upstream/`
(gitignored), applies `patches/`, builds the three binaries and radendurv2's ROM; `make doctor` says
what a machine is missing; `make play` runs radendurv2; `make check` and `make check-all` run the
checks (`.claude/rules/checks.md`). `scripts/README.md` says what each tool is for.

Three drivers are this repository's own, and each patch is the only part of its driver that
travels, since `upstream/` is not committed:

| driver | games | SUBTARGET | binary | patch |
|--------|-------|-----------|--------|-------|
| `tch/wheelfir.cpp` | wheelfir, pwball, kongball | `wheelfir` | `upstream/wheelfir` | `0002-wheelfir-video-model.patch` |
| `tch/radendur.cpp` | radendur, radendurv2 | `radendu` | `upstream/radendu` | `0001-radendur-driver-fixes.patch` |
| `tch/rltennis.cpp` | rltennis, rltennisa | `rltennis` | `upstream/rltennis` | `0005-rltennis-blitter-scale.patch` |

Two more patches are not drivers. `0003-lua-thread-context-race.patch` fixes a race in MAME's Lua
console thread, and `0004-gdbstub-one-thread-per-cpu.patch` makes the gdbstub serve one GDB thread
per cpu, so a debugger reaches the sub cpu without moving the focus. `scripts/lib/patch_table.sh`
says which MAME files each patch owns.

## Hardware facts

The detail is `docs/boards/wheels-and-fire-board.md`, generated from `hardware/registers.yaml`.

- The Wheels & Fire board (TCH, Murcia; two layouts, `E1333` etched on the W&F board's solder
  side): two 68000 at 16 MHz, two Actel/TI TPC1020BFN FPGAs as a scaling blitter, a BT478 RAMDAC,
  an ADC0808 for the wheel, a 10-bit R2R DAC for sound and an ST93C46 EEPROM.
- IRQs: 3 is vblank; 1 is the blitter, a held level asserted while the blitter is idle; 5 is the
  line counter, which clocks the sound streamer on all four games (one word per line to the sub
  cpu) and in Wheels & Fire also writes the road's per-line scroll. Port `0x7c0000` is the EEPROM,
  the sound block flags and the link to a second cabinet.
- Reality Tennis is the blitter's reference, not the video model's: one 68000 at 8 MHz against the
  two at 16 MHz of the later board.
- MAME's gdbstub supports the 68000 natively, so no patch is needed to debug it.

## The track render model of Radical Enduro

- The road does not use raster to tilt the screen: it is a system of isometric sprites, in the
  Knight Lore / Filmation style, stacked and drawn by depth, and the 3/4 look comes from that
  stacking.
- The paint order, read from the disassembly: the drawer `FUN_000e0646` and the feeder
  `FUN_000e2dfe` paint by cell, grid row by grid row, in three passes (the base with ctrl 0, then
  the 0x4000 planes into the background, then the high 0x8000 ones on top as a list of objects),
  with descending index within a cell. Two framebuffer planes, the track below and the bike always
  on top. Full detail in `docs/radendur-track-system.md`.
- Reproduced in Python (`scripts/radendur_track_render.py`, numpy); the five playable
  tracks by `scripts/radendur_tracks_all.py`. Specific 68000 functions decompile with
  `scripts/ghidra/DumpFuncs.java`.
- Palette: BT478, 256 colours of 8 bits (no `<<2`), one shared bank, assembled by ranges from
  `0xd6b12` plus an environment overlay by environment id.

**The 1:1 seam.** Horizontal lines of garbage across a render are the blit seam: the first source
row of each tile is a one-pixel border in the graphics ROM, so a 1:1 blit samples one source row
further in, and a scaled one never does (the offset would move with the zoom). The fix lives in two
places and new blit code copies it: the `tile()` of `scripts/radendur_track_render.py` (`sv0+1`)
and each E133 driver's `v_bias` (`radendur.cpp`, `wheelfir.cpp`). Reality Tennis's board has no
seam, so `rltennis.cpp` carries none and must not get one. Widening the bias to every scale was
measured and refuted (`hardware/registers.yaml`, `wheelfir_the_fpga_skew_does_not_widen_the_seam_bias`).

## No fact is written by hand twice

Everything in this repository is in English, file names included. Years, authorships, MAME states, ROM sizes and image
measurements come from a data file and are projected into the README, `docs/` and `disasm/`:

| fact | source | generator | watched by |
|------|--------|-----------|------------|
| games: year, manufacturer, authorship, state | `hardware/games.yaml` | `gen-games.py` | `verify-games.py` |
| before/after pairs and their captions | `docs/img/before-after/manifest.yaml` | `gen-before-after.py` | `verify-images.py` |
| registers, bits, symbols | `hardware/*.yaml` | `gen-hw-docs.py` | its own `--check` |
| links, images, generated blocks | the documents themselves | -- | `verify-docs.py` |

Every fact carries its level: `verified` (read from a binary or MAME's code, re-checkable today),
`external` (a source, never promoted for sounding plausible) or `unknown` (said, not filled in).
Refuted facts are kept with their reason, so nobody proposes them again.

A published image shows what its caption says, because the caption is derived from measuring it
(`before-after.py`); and a generator that finds no data fails rather than writing an empty table.

`hardware/*.yaml` is the data and the Markdown under `docs/boards/` and `disasm/symbols.txt` its
render: a confirmed or refuted fact goes into the YAML first, with its evidence, then `make
hw-docs`. The schema and the order of work are `.claude/rules/hardware.md`. Evidence too large for
a record lives under `hardware/evidence/`, with the script that re-derives the record's figures.

## Working rules

- The hardware is fixed, not adaptive: a fix reflects the board's global behaviour and benefits the
  whole game, never a spot patch for one screen. Understand the mechanism (palette, blit, page
  swap) across the driver family before accepting a graphical fix.
- One game at a time while investigating, every set when a fix closes:
  `.claude/rules/mame-operations.md`.
- A graphical artefact is never blamed on the game's data: the ROM ran correctly on the board, so
  the broken model is ours.
- Every tracked file stays impersonal (no people, no assistant, no issue numbers) except the
  credits this repository ships; the exceptions and their exact wording are
  `.claude/rules/checks.md`, under Hygiene.

## Per game

| game | page | the reflex before touching it |
|------|------|-------------------------------|
| Radical Enduro | `docs/games/radical-enduro.md` | an isometric sprite track, not raster; five playable sections; the dump hangs, `radendurv2` plays (its fixes, its sound block and its full-scenery layer are the patch table `hardware/radendur-v2.yaml`) |
| Wheels & Fire | `docs/games/wheels-and-fire.md` | the road by raster; sky and road in the same plane; clips in software against 336x256 |
| Power Ball | `docs/games/power-ball.md` | the clean reference: it kills the aggressive video hypotheses |
| Kong Ball | `docs/games/kong-ball.md` | draws the HUD in the upper half, so it shows at once whether the page model is broken |
| Reality Tennis | `docs/games/reality-tennis.md` | the reference for the blitter, not for the video model |

## Where the detail is

| doing... | read first |
|----------|-----------|
| running MAME, repairing a driver, choosing the check for a change | `.claude/rules/mame-operations.md` |
| instrumenting a run: a Lua harness, a breakpoint, a capture, a palette read | `docs/mame-techniques.md` |
| writing a script or a test, or what is published | `.claude/rules/checks.md` |
| confirming or refuting a hardware fact | `.claude/rules/hardware.md` and `hardware/*.yaml` |
| proposing a theory about a known fault | the records in `hardware/registers.yaml`, which keep their refutations |

## Contributing

`CONTRIBUTING.md`: reproducible reports, one-topic pull requests, and assistance by an AI tool
disclosed with the model and its version.
