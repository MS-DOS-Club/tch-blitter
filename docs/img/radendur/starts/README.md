# The 16 sections, one by one

MAME captures of `radendurh` at the board's 16 MHz, navigating the game's own menu
(`scripts/radendur/nav-phase.lua` drove the menu to each one).

| result | sections | how many |
|--------|----------|----------|
| **finish the race on their own** | 0, 1, 2, 3, 4, 8, 13 | **7** |
| hang halfway | 5 | 1 |
| die before drawing | 6, 7, 9, 10, 11, 12, 14, 15 | 8 |

Five sections (0, 1, 2, 4, 8) run a full race and end on the game's own time limit. Sections 3 and
13 end within seconds: section 3 is a byte-identical duplicate of 2, and 13 has a hundred-odd
entries against the thousands of a real track, so **they end because there is nowhere left to go**,
not because they get completed.

## How each capture is labelled

- **The phase is read from RAM**, never counted in frames: `0x20100e`/`0x20101a` after every
  press, and `0x201014` after START.
- **A race is alive when the image changes** relative to the menu. `0x20100c` cannot tell: a hung
  68000 leaves it frozen at 4, saying "racing".
- **A race is finished when the game returns to the attract**, and there `0x20100c` does tell,
  because the CPU is alive and changing state.
- **A section that dies before drawing leaves on screen the last frame it painted**, which can be
  from before the cursor's last move. Those captures are named `_CRASH-last-frame`, and the phase is
  told by the RAM, not by the sign on screen.

## Names

- `..._start.png` -- the real starting line, bike stopped, with the race drawing.
- `..._finish.png` -- the moment of the hang, or of the end of the race.
- `..._CRASH-last-frame.png` -- **not a start and no identification of the phase**: the last thing
  left on screen when the game died before drawing.
- `_FORCED` -- segment 3, not reachable from the menu; forced in RAM.

## Results

| sec | level/seg | difficulty | from the menu | entries | garbage | draws | what happens while riding |
|----:|:---------:|---|:---:|---:|---:|:---:|---|
| 0 | L0s0 | EASY | yes | 3483 | 0.0% | **yes** | race finished on its own |
| 1 | L0s1 | EASY | yes | 6105 | 0.0% | **yes** | race finished on its own |
| 2 | L0s2 | EASY | yes | 6562 | 0.0% | **yes** | race finished on its own |
| 3 | L0s3 | EASY | no | 6562 | 0.0% | **yes** | race finished on its own, within seconds |
| 4 | L1s0 | MEDIUM | yes | 9743 | 0.0% | **yes** | race finished on its own |
| 5 | L1s1 | MEDIUM | yes | 8316 | 49.5% | yes, garbage | **grey hang** halfway |
| 6 | L1s2 | MEDIUM | yes | 7057 | 49.6% | no | crash right after START |
| 7 | L1s3 | MEDIUM | no | 7057 | 49.6% | no | crash right after START |
| 8 | L2s0 | HARD | yes | 6802 | 0.0% | **yes** | race finished on its own |
| 9 | L2s1 | HARD | yes | 283 | 36.4% | no | freezes on the menu after START |
| 10 | L2s2 | HARD | yes | 129 | 48.1% | no | crash after START |
| 11 | L2s3 | HARD | no | 129 | 48.1% | no | crash after START |
| 12 | L3s0 | EXPERT | yes | 488 | 45.7% | no | crash right after START |
| 13 | L3s1 | EXPERT | yes | 110 | 0.0% | **yes** | race finished on its own, within seconds |
| 14 | L3s2 | EXPERT | yes | 68 | 36.8% | no | crash right after START |
| 15 | L3s3 | EXPERT | no | 68 | 36.8% | no | crash right after START |

The crashes are the game's own fault handling: an address error ends in the handler at `0x25a4`
(the grey screen, looping at `0x25d4`), and a bus fault in the bare `rte` at `0x25a2`, which
faults again for ever. Section 9 is the one that dies without reaching it: its image and its
state freeze on the selection screen.

## Reading

- **8 of 16 sections draw a race**: 0, 1, 2, 3, 4, 5, 8 and 13. Of those, seven FINISH it and one
  (5) hangs halfway.
- **Only FIVE are real tracks**: 0, 1 and 2, which are the whole of Level 0, plus the start of
  Level 1 (section 4) and of Level 2 (section 8). The other two that finish do so in seconds because
  they have no course.
- **Every section that fails to draw has a large share of its entries at impossible coordinates.**
  The only one that draws with broken data is 5, and what it paints is garbage geometry before it
  hangs.
- **Only Level 0 has a complete track** (segments 0, 1, 2; the 3rd is a byte-identical duplicate of
  the 2nd and cannot be asked for anyway). Levels 1 and 2 only have their start finished. Level 3 has
  no track at all: its one healthy section (13) has a road and nothing more.
