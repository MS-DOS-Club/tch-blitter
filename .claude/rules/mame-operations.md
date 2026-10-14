# Running MAME in this repository

No `paths:` on purpose: the emulator is driven from the shell without opening any particular file,
so this loads in every session.

## One game while investigating, every set when a fix closes

Five sets share `wheelfir.cpp` (wheelfir, pwball, kongball and Radical Enduro's two, through
`radendur_state`), and Reality Tennis's two share `rltennis.cpp`. Sharing a driver is not a reason to
work on several at once: while investigating, run, measure and fix only the game under work, and
judge by its symptom alone; read three games' symptoms at once and there are three explanations and
no measurement. When the fix closes, `make check-all` walks every set, and a sibling that breaks
then is information about the fix.

## Driver work

- The two drivers are this repository's: `upstream/src/mame/tch/wheelfir.cpp` and `rltennis.cpp`,
  carried by `patches/`. Before touching `wheelfir.cpp`, re-read
  `docs/boards/wheels-and-fire-board.md`, and keep `rltennis.cpp` open as the blitter's reference
  (not the video model's: it is a much smaller board).
- Rebuild only the driver touched: `cd upstream && make SUBTARGET=<subtarget>
  SOURCES="src/mame/tch/<driver>.cpp" REGENIE=1 -j<cores>`, where the subtarget is `wheelfir` or
  `rltennis`. Without `REGENIE=1` a stale driver list can build a
  binary without the machine, silently. Then `make patch`.
- The gate is the observed state, captured as goldens: a change that does not move the game forward,
  or breaks another set of the driver, is suspect.
- Instrument before supposing: the gdbstub (`make debug`, the 68000 is supported natively) and the
  driver's logging. A fault that no objective channel shows needs that channel first. How to
  instrument a run without being misled (the debugger from Lua and the six things a breakpoint
  needs, unattended runs, the cfg traps) is `docs/mame-techniques.md`: read it before the first
  harness.
- A driver logs the way MAME's C++ guide asks (`docs/source/contributing/cxx.rst`, Logging), because
  the drivers are proposed upstream: `logerror` for what a developer reads, `osd_printf_verbose`
  for what a user diagnoses, never `osd_printf_*` at the default verbosity. A milestone trace (which
  scale law a machine runs, the first time a game does something) is kept for good, through
  `logerror`. `logerror` goes nowhere without `-log`: the launcher passes it to a played session, so
  the run's own `error.log` says what it ran, and a harness that has to state its mode reads it there.
- On radendur a healthy boot is told by an invariant, not a count: the exception handler `0x25a4`
  stays silent while the vblank handler `0x4a0` runs thousands of times.

## The render model is Python, MAME is the oracle

The track maps and their palettes are rebuilt in Python from the ROM
(`scripts/radendur_track_render.py`, `radendur_tracks_all.py`), and that is the clean render. MAME
is the oracle for the hardware (the real palette, the paint order) and for checking the two agree.

## Playing

MAME's default map: any key dismisses the red NOT_WORKING warning, `5` is a coin, `1` start. In
Wheels & Fire `LSHIFT` is full throttle (pedal and button 1), `LCTRL` the pedal alone (what the
menus accept), `LALT` the brake, `SPACE` the turbo, the arrows the wheel; in Radical Enduro left
`CTRL` accelerates and the arrows move the bike. `radendurh` carries the crash fixes; `radendur`,
the dump, stops on its faults by design.

## The Wheels & Fire race is the reference

The race as the driver draws it now is the validated reference, not a starting point to improve.
The displayed page is the bit the game declares, read on line 0 of the frame, and the clearing is
the game's own (a word-14 fill, and the bit-3 erase that walks its destination in columns); other
page readings were tried and each broke the race. The driver states the model in its header (THE
PLANES), at the line-0 sampling in `scanline_timer_callback` and above `screen_update`'s compositing
loop.

`goldens/wheelfir/05_race_hud.png` and `06_race_hud2.png` hold that state, two frames because one
cannot show a flicker, and they are never re-blessed: a change that turns them red is wrong. A fix
that only moves the timeline changes the scene's frame number in `scenes.conf`, never the golden.
The siblings' goldens are not a validated reference: they are looked at and re-blessed when Wheels
& Fire improves (`goldens/README.md`).
