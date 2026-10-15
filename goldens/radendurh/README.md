# Boot goldens

The project's correctness gate. No ROM is assembled from source here, so there is no build SHA to
verify: the gate is the **observed boot state**. `make verify` runs `radendurh`, the clone whose
maincpu ROM has the prototype's faults fixed, its sound block placed as Power Ball and Kong Ball place
theirs and its scenery drawn further round the view, and then the dump `radendur` (`../radendur/`). It compares the
SHA-256 of fixed-frame captures against `checksums.sha256`: the boot through the oracle
(`scripts/radendur/oracle.lua`), the race start through `nav-phase.lua`, and stretches of the
desert's scenery through `scenery-shot.lua`.

A **FAIL is never cosmetic**: it is either a regression, or an advance of the boot that has to be
re-blessed on purpose with `make goldens` (`SET=radendur` for the dump's).

The comparison is against the SHAs in `checksums.sha256`; shifting the first capture
(`ORACLE_FRAMES=150,300,600,900 ./scripts/radendur-goldens.sh verify radendurh`) shows it fail.

## What these capture

With the fixed ROM the game boots and races, so these are real screens of the game. The board's
dump, emulated as it is, stops on its own faults; its baseline is `../radendur/`.

| golden | what it pins |
|--------|--------------|
| `00_sator_3s` | the end of the SATOR logo fade: the only screen where that logo's colour is seen. |
| `01_boot_5s`, `02_boot_10s` | intro |
| `03_boot_15s` | attract: the globe, the logos and the difficulty selector. It guards the logo colours. |
| `04_race_start` | **the desert starting line, bike stopped**. It is the gate of the colour IN A RACE: the first four cover intro and attract only. The section is verified in RAM before the picture (`nav-phase.lua`), so the start of another phase cannot slip in. |
| `05_desert_scenery` | **the stage tent in the desert, mid-race**, driven by `scripts/drive.lua`: the tent, palms and bushes the prototype's own engine leaves out and radendurh's scenery layer draws (not the board's behaviour). `scripts/radendur/scenery-shot.lua` writes the game's view origin with it, and the gate refuses a capture taken anywhere else. |
| `06_desert_descent` | **the desert while the view scrolls DOWN the track**, driven the same way: the bottom row the view adds keeps its trees, palm and fence, which radendurh's `scenery_strip_row` draws in the row it belongs to (the prototype's strip drawer leaves it bare). |

If a change to the palette model alters any of those screens, the golden fails on purpose and is re-blessed once
the change is checked to be the one that was sought.

## They are versioned: why, and what to do if they fail on another machine

They are versioned (small PNGs) so that a fresh clone has a baseline: a gate that does not travel
is not a gate, and re-blessing blind on whichever machine is at hand is how a regression goes
unnoticed.

The baselines are SHA-256 hashes of PNGs written by MAME at the pinned commit
(`scripts/lib/mame_src.sh`), on an arm64 host. A host of another architecture, or with another PNG
encoder, may write other bytes for the same picture. If `make verify` fails on a different machine,
the first question is which of the two things it is, and it is answered by LOOKING at the captures
in `tmp/goldens-verify-radendurh/labeled/` against these PNGs:

- **A visible difference** (different content): a regression or a real advance. It is diagnosed;
  only then `make goldens`.
- **Identical to the eye but a different SHA**: a host difference (PNG encoding or rounding), not
  the emulator's. In that case it is written down HERE and the gate moves to comparing pixels
  instead of SHAs, never to re-blessing on every machine: a baseline every Mac rewrites stops
  detecting anything.

## Tied to the CPU clock

The captures are blessed with the driver's real 16 MHz clock: the blitter IRQ is modelled as the
held level it is, timed by the game's own interrupt mask. Moving the clock moves the point the attract animation has reached at the same
seconds, so the gate fails with nothing broken: `03_boot_15s` changes visibly only because the
globe is at another angle of its spin. If the clock is ever changed, re-bless, and say
why in the commit.
