# Goldens: the family's visual gate

One directory per game. A FAIL is **never cosmetic**: it means the image changed, and what the
change is has to be looked at before anything is re-blessed.

| game | how |
|------|-----|
| `radendurv2` | `make verify`. It has to navigate: coin, menu, and reach the starting line |
| `radendur` | `make verify` too: the board's dump, emulated as it is, pinned short of the starting line |
| `wheelfir` | `make verify-family`. Fixed attract frames, no controls touched |
| `kongball` | the same |
| `pwball` | the same |
| `rltennis` | the same |
| `rltennisa` | the same. It is the SECOND dump of Reality Tennis, captured at the same frames as `rltennis`; what it draws there differs |

**How many scenes each one has is `goldens/<set>/scenes.conf`**; it is not counted here, because a
count nothing keeps true is a debt handed to whoever reads it next.

## Which binary they are blessed with

With **ours**, never with upstream's: `upstream/radendu` for the two Radical Enduro sets,
`upstream/wheelfir` for Wheels & Fire, Power Ball and Kong Ball, and `upstream/rltennis` for the two
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
- **`rltennis/00_title`**: the control of the sibling that already worked in MAME.

## And what a gate of instants does NOT see

A golden compares isolated instants, and two instants that agree **do not prove there is no flicker
between them**: a flicker can live exactly in the frames no golden looks at. `scripts/frame-series.sh`
captures consecutive frames for that, which is why Wheels & Fire's race has two goldens a hundred frames apart.

**A gate over mostly static witnesses can give GREEN over a state known to be bad**, so a gate is
validated in RED before it is believed in green.

## Determinism

Every run creates its NVRAM **clean**: an inherited EEPROM changes the attract and makes
comparisons fail that should not. And Radical Enduro's goldens are tied to the driver's real CPU clock,
with no multiplier ([radendurv2/README.md](radendurv2/README.md)).

## The siblings' goldens are not a validated reference

The two from the Wheels & Fire race (`05_race_hud` and `06_race_hud2`) are the FLOOR: they are
blessed over a state validated by looking at it, and if they go red the change is wrong.

Power Ball's, Kong Ball's and Reality Tennis's do NOT have that status: they are a record of the
current emulation, not a validated reference. Power Ball and Kong Ball
share a driver with Wheels & Fire, and Reality Tennis's own driver shares the blitter model: as
those drivers improve, their scenes CHANGE, and that change is expected and not a regression. They are re-blessed after looking at the comparison, never automatically.
