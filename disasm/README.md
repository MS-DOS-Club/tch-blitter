# Disassembly of the TCH 68000 code

Disassembly and analysis of the **68000 code** of the family's five games, nine images in
total. It is where the code is read before the driver is touched, instead of guessing.

## What lives here

What gets versioned is what cannot be regenerated without human work: `symbols.txt` (the names,
generated from `hardware/symbols.yaml` by `make hw-docs`, which are the analysis INPUT),
`analysis.txt` and `listings/` (its OUTPUT), `executed/` (the addresses MAME executed in each
image, an input the analysis is seeded with), this document
and the three diagnostics (`crashes-radendur.md`, `code-assessment.md`,
`gfx-assembly-findings.md`). The graphics dumps in `gfx/` are regenerable and not versioned.

Gitignored as derivable: the images (`img/*.bin`) and the Ghidra project (`ghidra/`). The analysis
is Ghidra's recursive one, which follows the code from the vectors instead of reading the image
linearly, so data is not decoded as instructions.

The scripts that build this pipeline (`disasm.sh`, `ghidra-setup.sh`, `ghidra-import.sh`,
`ghidra-export.sh`, and the `ghidra/*.java` they call) are described in `../scripts/README.md`,
which is the tool inventory. What is local to this directory:

| File | What it is |
|------|------------|
| `symbols.txt` | Hardware map (3 boards) + 68000 vectors + names already identified |
| `analysis.txt` | Export output: functions, blitter accesses, pseudo-C |
| `listings/*.lst` | Annotated listing per image, from the same export (see below) |
| `executed/*.txt` | ROM addresses MAME executed in an image, from its tracer (`scripts/trace-seeds.py`); the import disassembles them before the analysis |
| `img/*.bin` | Interleaved 68000 images (base 0x0) -- gitignored |

The whole chain on a fresh machine:

```sh
make ghidra-setup  # downloads Ghidra into tools/ (needs a JDK: brew install openjdk)
make disasm-all    # symbols.txt, images, Ghidra import, export, docs, in that order
```

`make disasm-all` stops at the first step that fails. An image is analysed again whenever its bytes, `symbols.txt`,
`SetupTCH.java`, the processor or the Ghidra release changed since its last import, and the export
refuses, with nothing written, a project whose labels are not exactly the ones
`hardware/symbols.yaml` declares. Besides the reset vector, the analysis is seeded from every
exception, interrupt and TRAP vector that points into ROM, and from every address MAME executed
in that image (`executed/`): an executed address is an instruction start, and seeding it first keeps
the analysis's heuristics from typing it as data. Ghidra's address-table heuristic runs with a
minimum of four consecutive addresses, the setting that makes the analysis agree with the machine.

Before the listings are moved into place, `scripts/verify-listings.py` checks each one against its
image with instruments that are not Ghidra: every line shows the image's bytes, the lines tile the
ROM, capstone (limited to the 68000) decodes the same instruction length at every instruction,
every ROM symbol is at its address, every register name is backed by a reference, and every
executed address still starts an instruction. A failure stops the export.

Open the GUI with `make ghidra-gui`.

## Reading a listing

`listings/<set>_<cpu>.lst` is one image read the way Ghidra's recursive analysis read it, one line
per instruction or datum, in address order:

```
wait_loop:
000f2132  40e7                  move SR,-(SP)
000f2134  46fc2700              move #0x2700,SR
000f2138  4a79002091ee          tst.w (DAT_002091ee).l
```

- The first column is the address, the second the bytes, the third the instruction in Ghidra's
  68000 syntax. A branch or a reference names its target when it has a name: ours from
  `symbols.txt`, Ghidra's own (`FUN_`, `LAB_`, `DAT_`) where nobody named it yet.
- Every ROM symbol of `hardware/symbols.yaml` sits at its address with its description as a `;`
  block above it; one that falls inside an instruction or a datum is named above that line, with
  its offset. RAM and hardware symbols appear as operand names; an immediate or a displacement off an
  address register is a number, unless `symbols.txt` named it. Routines start after a blank line.
- An access to a board register carries the name `hardware/registers.yaml` gives it, after a `;`
  (`; trigger`, `; control_and_link`). The names are the E1333 board's, so the Reality Tennis
  listings and the sound cpus' carry none.
- Data the analysis typed comes out as `dc.b`, `dc.w` or `dc.l`; the vector table is longs.
- A line ending `; not 68000 code: ...` is one Ghidra decoded (its language is a 68040's) and a
  68000-only disassembler does not: the analysis took data or an operand for an instruction there.
- Bytes the analysis never reached, neither as code nor as data, are one line saying which range
  and how long, not guessed at. They are mostly samples, graphics descriptors and tables reached
  through computed addresses.
- Code the game copies to RAM before running it (the sound cpus' mixer, Radical Enduro's level 5
  streamer) is listed as code at its ROM address, with `runs from <address>` in its `;` block.

The listings come out of `ghidra-export.sh` in the same run as `analysis.txt`, from the same
project.

**Per-image labels.** A line `@image <fragment>` opens a block that only applies to the images
whose name contains that fragment, and `@image *` returns to the common ones (hardware map,
vectors, register addresses). It is needed because at `0xe5300` each game has different code:
without the filter, one game's labels would land on another game's binary.

`symbols.txt` is the pipeline's INPUT and `analysis.txt` its OUTPUT: every name identified goes
into `hardware/symbols.yaml`, `make hw-docs` renders it into `symbols.txt`, and the next export
propagates it. That is why re-exporting after annotating
is not cosmetic: seeding a function name changes where Ghidra cuts the functions and improves
the decoding around it.

## The 9 code images

All the code is 68000, interleaved (even = big-endian high byte, odd = low), mapped at base
0x0. gfx and samples are data and are not disassembled as code.

| Image | Board | Role |
|-------|-------|------|
| `radendur_maincpu` | Radical Enduro | the main target |
| `radendur_subcpu` | Radical Enduro | sub (code + sound samples) |
| `wheelfir_maincpu` | Wheels & Fire | sibling on the same driver, and the one with the most symbols |
| `wheelfir_subcpu` | Wheels & Fire | sub |
| `pwball_maincpu` | Power Ball | sibling; symbols propagated from Wheels & Fire |
| `pwball_subcpu` | Power Ball | sub |
| `kongball_maincpu` | Kong Ball | sibling; symbols propagated from Wheels & Fire |
| `rltennis_maincpu` | Reality Tennis | REFERENCE (its blitter works) |
| `rltennisa_maincpu` | Reality Tennis, set 2 | the same program with a patch; analysed by Ghidra beside the others |

**The siblings' symbols were not seeded by hand**: they were carried over from Wheels & Fire by
flow correspondence and confirmed one by one by disassembling both windows. `hardware/symbols.yaml`
says which kind of evidence each one rests on, `correspondence` (same flow) or `identical` (the
bytes match over a large region, which is what holds up the data tables).

## Findings

### radendur's boot (main)

Reset PC = `0xf2034`. The boot is valid, readable 68000 code:

```
0xf2034  move.w  #0x2700, sr           ; supervisor, IRQs masked (level 7)
0xf2038  move.w  #0, (0x20351c).l      ; shadow of the control port 0x7c0000
0xf2040  jsr     (0x25dc).w            ; early init subroutine
0xf2044  move.w  #0xd800, (0x20351c).l
0xf204c  jsr     (0xf24de).l
...      lea/move.w into structures at 0x2091f0, 0x209280, ...
```

The reset vector points at valid RAM (SP = 0x201000) and valid ROM (PC), as the even/odd
interleave requires.

### Hardware parallelism (the lever)

The memory maps of `rltennis` and `wheelfir`/`radendur` are nearly identical, and the **blitter
sits at the same address `0x700000`** on both. That makes the blitter programming sequences of
the two boards directly comparable. See `symbols.txt`.

### Function map (Ghidra)

Auto-analysis with the entry seeded from the reset vector. The full readable dump (function
list, code that touches the blitter, pseudo-C of reset) is in `analysis.txt`; the per-image
function and blitter-access counts are the table in [../docs/disassembly.md](../docs/disassembly.md),
generated from it.

radendur's writes to 0x700000-0x70001f concentrate in `blit_program` (`0x2004`), which programs
one blit from a command block, and in the two level-1 handlers `irq_blitter` (`0x1f2a`) chains
to, `irq1_last_blit` (`0x1f42`) and `irq1_chain` (`0x1f94`), which write several registers a byte
at a time (`move.b` to `0x70000c`, `0x70000f`, `0x700003`, `0x700007`, `0x700013`).
`boot_init` (`0x25dc`) is the boot initialisation, called from reset: it clears RAM, arms the
interrupt trampolines and issues four clear blits, each followed by a delay; `mode_clear_blits`
(`0x2856`), called again from the main loop, issues the same four.

### Pseudo-C of radendur's boot (reset @ 0xf2034)

```c
void reset(void) {
  _DAT_0020351c = 0;
  boot_init();                    // RAM clear, IRQ trampolines, four clear blits
  _DAT_0020351c = 0xd800;
  FUN_000f24de();                 // init
  ...
  FUN_000f27de();
  ...
  FUN_000dfaba();
  _DAT_00201020 = 1;
  do {                            // main loop (a state machine)
    if (_DAT_00201020 != 0) { FUN_000dfaf4(); ... }
    ...
    // mode/screen dispatch through pointer tables at 0xf1fd4/f1fd8/f1fdc
    DAT_00203508 = *(int *)((int)&PTR_DAT_000f1fd4 + iVar1);
    ...
  } while (...);
}
```

It boots (init plus blitter), enters the main loop and dispatches modes through a pointer table.

### The track render system

The track's painting order is read from these functions and reproduced in
`../scripts/radendur_track_render.py`; `tests/test_render_golden.py` pins the geometry and
palette of the five playable sections.

- `FUN_000e0646` (**drawer**): builds a per-cell grid. It walks the section's entries in
  descending index and stamps each sprite tile into its cell; the base (ctrl=0) overwrites slot0,
  0x4000/0x8000 are added.
- `displaylist_walker` (`0xe2dfe`, the **high feeder**): walks the grid row by row and emits the 0x8000 tiles into an
  object list with screen coordinates (they get drawn on top of the flat stuff).
- `palette_range_copy` (`0xe2ed6`, the **palette memcpy**): copies a range of the `0xd6b12` table into the palette
  buffer according to an argument index.

The resulting model: two planes (BG track + FG bike), render PER CELL in 3 passes (base ->
0x4000 planes -> 0x8000 highs). Detail in
[the Radical Enduro track system](../docs/radendur-track-system.md).

### On-demand decompilation tools

`../scripts/ghidra/DumpFuncs.java` (described in `../scripts/README.md`) runs headlessly over the
already-analysed Ghidra project, without re-importing it:

```
# analyzeHeadless is NOT on the PATH: it lives in tools/, which is gitignored and
# installed by `make ghidra-setup`.
JAVA_HOME=$(. scripts/lib/jdk.sh && java_home_path) DECOMP_ADDRS=e0646,e2dfe \
  tools/ghidra/support/analyzeHeadless disasm/ghidra tch \
  -process radendur_maincpu.bin -noanalysis \
  -scriptPath scripts/ghidra -postScript DumpFuncs.java
```

`Xref.java` lists the references to an address (`XREF_ADDRS=...`).
