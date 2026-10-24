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
- `wheelfir.cpp` is MAME's own and `rltennis.cpp` and the `radendurh` clone are proposed to it, so
  a change to either driver is written as MAME reviews it, from the first line. MAME's rules are
  `docs/source/contributing/cxx.rst` in `upstream/`; before a pull request is opened or amended,
  the `mame-review` skill (https://github.com/rb6502/mame-ai-tips/tree/master/mame-review)
  reviews it from `upstream/`, whose patches sit uncommitted on the pinned commit, so its paths
  mode reads them as the change: `src/mame/tch/rltennis.cpp` for Reality Tennis's pull request,
  `src/mame/tch/wheelfir.cpp` and `src/mame/mame.lst` for the clone's, never the Lua and gdbstub
  patches, which are not proposed with them. The drafts of the pull request
  texts go through its submission step too. `srcclean` is built from `src/tools/` before it, or
  that check comes back skipped, and a `DEBUG=1` build runs without an assertion firing.
- What a core developer tidied by hand in the merged `wheelfir.cpp`, after the skill had passed it,
  is written that way from the start: `using std::swap; swap(a, b);`; an endless loop left by
  `break` as `while (true) { }`, never `do { } while (true);`; `<bit>` over bit tricks
  (`std::has_single_bit(x)`, not `!(x & (x - 1))`); a `DEF_STR` in its exact meaning (the control
  type is `DEF_STR( Controls )`, not `Cabinet`, and an option with a standard string takes it);
  a blank line after the base config call (`board(config);`) before what it sets, two blank lines
  between top-level groups and between one game's ROM blocks and the next game's, one between a
  parent and its clone.
- No member is initialised in the class definition. A starting value goes in `machine_start`,
  except an input's initial state (a line a device callback latches), which goes in the
  constructor's initialiser list, where MAME's review asks for it; the state of the board's logic (a counter, a command latch, a write window) is cleared in
  `machine_reset`, and what behaves as memory (a scroll latch, a palette copy, a plane) keeps its
  `machine_start` value. The comment says what the driver clears, not what the board's reset does,
  unless that was measured.
- A control, a lever, a layout or a cabinet setting follows the genre's flagship driver in MAME,
  because that is the pattern a reviewer recognises and asks for: Out Run (`sega/segaorun.cpp`,
  `layout/outrun.lay`) for the gear lever.
- A comment carries the density of the file around it: one line where its neighbours have one, the
  why at the line it binds, no history. The story of a change goes in the commit message and the
  pull request description.
- A driver logs the way MAME's C++ guide asks (`docs/source/contributing/cxx.rst`, Logging):
  `logerror` for what a developer reads, `osd_printf_verbose`
  for what a user diagnoses, never `osd_printf_*` at the default verbosity. A milestone trace (a
  mode a machine enters, the first time a game does something) is kept for good, through
  `logerror`. `logerror` goes nowhere without `-log`: the launcher passes it to a played session, so
  the run's own `error.log` says what it ran, and a harness that has to state its mode reads it there.
- On radendur a healthy boot is told by an invariant, not a count: the exception handler `0x25a4`
  stays silent while the vblank handler `0x4a0` runs thousands of times.

## The render model is Python, MAME is the oracle

The track maps and their palettes are rebuilt in Python from the ROM
(`scripts/radendur_track_render.py`, `radendur_tracks_all.py`), and that is the clean render. MAME
is the oracle for the hardware (the real palette, the paint order) and for checking the two agree.

## Playing

MAME's default map: any key dismisses the red NOT_WORKING warning, `5` is a coin, `1` start. Wheels
& Fire keeps MAME's defaults (left `CTRL` the accelerator, a one-tap select in the menus, `LALT`
the brake, `SPACE` the turbo, the arrows the wheel); button 1 is the low/high gear lever, a toggle
declared as button 4 so it takes that button's defaults (`LSHIFT`, a pad's fourth button), a race
starts in low, and a layout draws the lever on screen. In Radical Enduro left `CTRL` accelerates
and the arrows move the bike. `radendurh` carries the crash fixes; `radendur`,
the dump, stops on its faults by design.

## The Wheels & Fire race is the reference

The race as its two goldens hold it is the validated reference, not a starting point to improve.
The displayed page is the bit the game declares, read on line 0 of the frame, and the clearing is
the game's own (a word-14 fill, and the bit-3 erase that walks its destination in columns); other
page readings were tried and each broke the race. The driver states the model in its header (the
blitter's two planes), at the line-0 sampling in `scanline_timer_callback` and on `m_page_at_line0`,
the page `screen_update` shows.

`goldens/wheelfir/05_race_hud.png` and `06_race_hud2.png` hold that state, two frames because one
cannot show a flicker, and they are not re-blessed to let a change pass: a change that turns them red
is wrong unless the owner decides the race changes, as when the three-row background bias went
because the service mode's convergence grid refuted it, and when the raster's writes were moved to
the line above (DISPLAY_LAG_LINES), which aligned the same grid and took the road off line 0 at
crests; the race now shows two rows of the game's ground fill above its horizon. A fix that only
moves the timeline changes the scene's frame number in `scenes.conf`, never the golden.
The siblings' goldens are not a validated reference: they are looked at and re-blessed when Wheels
& Fire improves (`goldens/README.md`).
