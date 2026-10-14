# Track details (docs/img/radendur/detail/)

A zoom into the densest area (stands/START/signs) of each section, rendered from the ROM
with `scripts/radendur-track-details.py` (never from data captured at run time).

Structure: `section = (level<<2) + segment`, table at `0xA2A62`, 16 sections.
The menu paints EASY/MEDIUM/HARD (difficulty) plus a desert/jungle/mountain stretch
(= Level 0/1/2). Seg 3 = a duplicate of seg 2 that the menu never selects; forced in RAM,
it ends within seconds (`../starts/README.md`).

| Sec | Level | Seg | Theme | Difficulty | Role | State | Detail |
|----:|:-----:|:---:|-------|------------|------|-------|--------|
| 0 | 0 | 0 | desert | EASY | start | clean | `detail_L0_seg0_start_desert.png` |
| 1 | 0 | 1 | desert | EASY | stretch | clean | `detail_L0_seg1_stretch_desert.png` |
| 2 | 0 | 2 | desert | EASY | stretch | clean | `detail_L0_seg2_stretch_desert.png` |
| 3 | 0 | 3 | desert | EASY | dup-seg2 (unused) | clean | - |
| 4 | 1 | 0 | jungle | MEDIUM | start | clean | `detail_L1_seg0_start_jungle.png` |
| 5 | 1 | 1 | jungle | MEDIUM | stretch | interleaved | - |
| 6 | 1 | 2 | jungle | MEDIUM | stretch | interleaved | - |
| 7 | 1 | 3 | jungle | MEDIUM | dup-seg2 (unused) | interleaved | - |
| 8 | 2 | 0 | mountain | HARD | start | clean | `detail_L2_seg0_start_mountain.png` |
| 9 | 2 | 1 | mountain | HARD | stretch | interleaved | - |
| 10 | 2 | 2 | mountain | HARD | stretch | interleaved | - |
| 11 | 2 | 3 | mountain | HARD | dup-seg2 (unused) | interleaved | - |
| 12 | 3 | 0 | (no theme) | EXPERT | start | interleaved | - |
| 13 | 3 | 1 | (no theme) | EXPERT | stretch | undecorated | - |
| 14 | 3 | 2 | (no theme) | EXPERT | stretch | interleaved | - |
| 15 | 3 | 3 | (no theme) | EXPERT | dup-seg2 (unused) | interleaved | - |

State: **clean** = renders coherently; **undecorated** = the layout is continuous and
coherent and what is missing is ALL the scenery (that is section 13, and it is a
different development stage from "corrupt data": see `../sections/sec13_L3s1.png`);
**interleaved** = the prototype's incomplete format (a 2-good-2-garbage pattern; the
share of broken entries per section is in `../sections/README.md`).
Only Level 0 (desert) is complete (segs 0-2); Level 1 (jungle) and 2 (mountain) only
have their start; Level 3 is unfinished, although **EXPERT can be chosen in the menu**:
what does not exist is a finished track behind it.

The empirical sweep of the 16 sections (which draw, which hang, which are playable) is in `../starts/README.md`; the maps of all of them rendered from the ROM are in `../sections/README.md`.

## Regenerating

They are versioned, and regenerate from the ROM with `uv run scripts/radendur-track-details.py` (the other renders: `../sections/README.md`).
