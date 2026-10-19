# Goldens: the family's visual gate

One directory per game. A FAIL is **never cosmetic**: it means the image changed, and what the
change is has to be looked at before anything is re-blessed.

| game | how |
|------|-----|
| `radendurh` | `make verify`. It has to navigate: coin, menu, and reach the starting line |
| `radendur` | `make verify` too: the board's dump, emulated as it is, pinned short of the starting line |
| `wheelfir` | `make verify-family`. Fixed attract frames, no controls touched |
| `kongball` | the same |
| `pwball` | the same |
| `rltennis` | the same |
| `rltennisa` | the same. It is the SECOND dump of Reality Tennis, captured at the same frames as `rltennis`; what it draws there differs |

**How many scenes each one has is `goldens/<set>/scenes.conf`** for the family sets, and for the
two Radical Enduro sets the scene list in `scripts/radendur-goldens.sh` beside each set's
`checksums.sha256`; it is not counted here, because a
count nothing keeps true is a debt handed to whoever reads it next.

**Sound.** A family set whose sound CPU writes its DACs declares a `sound` line in its
`scenes.conf`, and `goldens/<set>/sound.crc` holds a CRC-32 of those writes from a cold boot and
from a second boot on the EEPROM the first one left, the way a board that has run before boots. The
writes are the game's integers, so the CRC is the same on every host; a sound CPU that dies stops
writing, and the count beside the CRC drops with it.

## Which binary they are blessed with

With **ours**, never with upstream's: `upstream/wheelfir` for Wheels & Fire, Power Ball, Kong Ball
and the two Radical Enduro sets, and `upstream/rltennis` for the two
Reality Tennis sets (`mame_binary_for_set` in `scripts/lib/mame_run.sh` is the table). Blessing
against the wrong binary protects nothing, so the script states which one it is using on every run.

## Why those scenes and not others

A scene is chosen for what it EXERCISES, and the reason is written in each
`goldens/<set>/scenes.conf`. The ones that are worth most:

- **`kongball/01_hud`**: with the scoreboard and the lives bar. That game draws them in the upper
  half of the sprite plane, so it is **the only thing in the family that detects a broken page
  model**: if the model fails, the whole HUD disappears.
- **`wheelfir/02_world_map`**: the horizon, where a wrong scroll model draws the road a second time.
- **`pwball/01_attract`**: the clean reference. If that moves, the change is suspect by definition.
- **`wheelfir/07_convergence`**: the service mode's grid, reached with the Test button (the `press`
  lines of its `scenes.conf`), the one screen whose answer is known in advance: every cell the same
  height, so an offset in the background's rows shows at once.
- **`rltennis/00_title`**: the control of the sibling that already worked in MAME.

## And what a gate of instants does NOT see

A golden compares isolated instants, and two instants that agree **do not prove there is no flicker
between them**: a flicker can live exactly in the frames no golden looks at. `scripts/frame-series.sh`
captures consecutive frames for that, which is why Wheels & Fire's race has two goldens a hundred frames apart.

**A gate over mostly static witnesses can give GREEN over a state known to be bad**, so a gate is
validated in RED before it is believed in green.

## Determinism

Every run starts from a **clean** NVRAM: an inherited EEPROM changes the attract and makes
comparisons fail that should not. Radical Enduro's passes then share theirs, because its scenes are
reached by navigating after the boot, and the family's sound check boots a second time on the
EEPROM the first run left, on purpose. A capture is the emulated screen alone (`-snapview native`
in `scripts/lib/mame_run.sh`), so Wheels & Fire's gear lever layout never reaches a golden. And
Radical Enduro's goldens are tied to the driver's real CPU clock,
with no multiplier ([radendurh/README.md](radendurh/README.md)).

## The siblings' goldens are not a validated reference

The two from the Wheels & Fire race (`05_race_hud` and `06_race_hud2`) are the FLOOR: they are
blessed over a state validated by looking at it, and if they go red the change is wrong.

Power Ball's, Kong Ball's and Reality Tennis's do NOT have that status: they are a record of the
current emulation, not a validated reference. Power Ball and Kong Ball
share a driver with Wheels & Fire, and Reality Tennis's own driver shares the blitter model: as
those drivers improve, their scenes CHANGE, and that change is expected and not a regression. They are re-blessed after looking at the comparison, never automatically.
