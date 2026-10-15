# Debugging an arcade board in MAME

MAME is three things at once in this repository: the reference machine, the debugger and the test
oracle. The emulator is deterministic and observable, so the rule of thumb is to read and measure
before guessing. What follows is the MAME side of that: how to run it unattended, how to make the
debugger answer from a Lua script, and the traps that make an instrument report silence when the
machine did something. The paths under `src/` are MAME's, in the checkout `make setup` creates in
`upstream/`.

## Running MAME without a person at the keyboard

- **A `MACHINE_NOT_WORKING` set stops on its red warning until a key is pressed.** MAME skips the
  warning for a run bounded to 300 emulated seconds or fewer (`-seconds_to_run`), under `-debug`,
  or with no video output (`src/frontend/mame/ui/ui.cpp`, `display_startup_screens`). This
  repository's launcher, `scripts/lib/mame_run.sh`, keeps an unattended run at 300 or fewer.
- **`-video none` on macOS does not mean "no window".** It takes over the whole display instead.
  A small window, `-window -nomaximize -resolution 320x240`, is what an unattended capture uses.
- **`-nothrottle` changes the wall clock, not the frames.** Throttling only paces the host, and
  with the default `-snapsize auto` a snapshot is the emulated screen at its native size whatever
  the window. A user's `mame.ini` can change that default; the launcher passes `-inipath run` so
  none is read.
- **`-seconds_to_run` counts emulated seconds**, and it only advances while emulation does: a
  machine stopped in the debugger never reaches it.
- **When `-seconds_to_run` ends the run, MAME writes one more numbered snapshot** (one per screen
  under `-snapview native`; `src/emu/video.cpp`), up to a few frames after the bound on a still
  picture. A script that counts or pairs captures keeps the first N it asked for.
- **A frame notifier runs one ahead of `screen:frame_number()`.** It fires at the start of
  vblank, before the screen's counter moves, so a counter kept in the notifier from boot reads one
  more: its fifth call sees frame number 4. After a soft reset the autoboot script runs again
  while `frame_number()` keeps counting, so the two part ways. Both numberings are in use here:
  the family goldens (`goldens/<set>/scenes.conf`) count notifier calls, while `frame-series.sh`,
  `drive.lua` and Radical Enduro's scenery shot use `frame_number()`.
- **A clean NVRAM and cfg per run is what makes a run reproducible.** The attract is deterministic
  from a clean start; an EEPROM left by an earlier run changes it. So does a soft reset: RAM the
  game never initialises carries over, and a demo scene seen after resets is reached again only by
  replaying the same resets from a cold start, not by its frame number.
- **The SDL build (macOS, Linux) does nothing on SIGTERM**, and a clean exit is what writes `cfg/`
  and `nvram/` (`src/emu/machine.cpp`), so a run stopped with `kill -9` loses them. Under a
  debugger module that blocks while the machine is stopped (the gdbstub), the console's `quit`
  only schedules an exit the stopped machine never reaches: resume it first.

## The debugger from Lua: when a routine runs is measured, never inferred

An address that looks like the string printer may never execute, and one that looks like the
palette uploader may run once while the real one runs hundreds of times. A breakpoint answers the
question; the disassembly only suggests. Six things have to be right, and most of them, wrong,
produce the same symptom, silence, which reads as "that routine never runs":

1. **`-debug` on the command line.** Without it the cpu has no debugger at all (`cpu.debug` is
   `nil`). The debugger module only decides what a stop does: `-debugger none` evaluates every
   breakpoint and runs its action but releases each stop at once, with no window, which makes it
   the cheapest way to log from breakpoints in an unattended run.
2. **Under a module that parks (the gdbstub, the Qt window) the machine starts stopped.** The
   autoboot script sets its breakpoints and then sets
   `manager.machine.debugger.execution_state = "run"`.
3. **The action takes no braces.** `bpset(addr, cond, action)` takes the raw command list; the
   braces of the console's `bp 3456,1,{ printf ... ; g }` give `unknown command`, the `g` never
   runs and a parking machine sits at the first hit.
4. **`printf` writes to the debugger console**, not to stdout. To read it from outside, use
   `logerror` and `-log`, and read `error.log`.
5. **The control address is chosen by measuring.** An IRQ handler entry can be cold because the
   game installs its handlers through a RAM vector.
6. **Numbers in expressions are hexadecimal.** `frame>2700` asks about frame 0x2700, while the
   `%d` of the action prints decimal.

**A zero means something only beside a control**: a breakpoint on an address known to be hot, on
the same cpu as the routine under study, reported with the result. With the control at zero the
instrument is broken; with it firing, a zero on the routine is evidence. A condition needs its own
reading: if nothing fired anywhere under it, the zero is about the condition.

    cpu.debug:bpset(<hot address>, "1", 'logerror "CTRL f=%d\n",frame ; g')

**Breakpoints and watchpoints answer opposite questions.** A breakpoint answers "when does this
routine run", and needs its address. A watchpoint answers "who touches this datum", and is the way
to find a writer nobody has named yet: `cpu.debug:wpset(space, "w", addr, len, cond, action)`,
logging `PC`.

**A read tap says that an address was read, not that code ran there.** On these boards' 68000 a
read tap on the program space sees instruction fetches from ROM as well as data reads: a tap on
the vblank handler's first word fires once a frame. The debugger's watchpoints are installed as
taps too (`src/emu/debug/points.cpp`), so a read watchpoint on code fires on its fetch as well;
"this code ran" is still a breakpoint's answer. Taps need no debugger and are the cheap way to
watch I/O and RAM. Two details bite: a callback that returns a number replaces the value the cpu
reads, and a callback that raises an error is dropped silently while the tap keeps firing, so a
counter incremented before the risky part, with the body under `pcall`, tells a quiet machine from
a broken callback.

**The Lua `screen` has no `vpos`.** The beam line is derived from what it does have:
`floor((frame_period - time_until_pos(0, 0) + pixel_period / 2) / scan_period + 1e-9)`, wrapped
over the line count `frame_period / scan_period` rounded to an integer. The half pixel is because
`vpos()` rounds to the nearest pixel, and the `1e-9` makes a tie round up as `vpos()` does. Trust
it once it equals the debugger's `beamy` at a stop, which is MAME's own `vpos()`.

**A Lua read of a table the game rewrites every frame is whole only outside the game's write
pass.** During a race Wheels & Fire rewrites its road's per-line table in the upper part of the
frame, so a read from a frame notifier, which fires at vblank, gets one frame's table, while the
same read taken in the middle of the pass gets the lines already rewritten from one frame and the
rest from the frame before. Where the pass falls is found
first, with a write watchpoint logging `beamy`; a table whose pass reaches vblank is read at the
write or with the cpu stopped.

For a debugger outside MAME, `make debug` runs `radendurh` with the gdbstub; MAME's gdbstub
speaks the 68000 natively.

## Logging from a driver

The drivers here are written to go upstream, so they log the way MAME's C++ guide asks: `logerror`
for what a developer reads and `osd_printf_verbose` for what a user diagnoses, never a message at the
default verbosity. A trace worth keeping for good, such as which scale law a Wheels & Fire machine
runs, is one `logerror` line written once. `logerror` is only kept with `-log`, which writes
`error.log` in the working directory: `scripts/lib/mame_run.sh` passes it to a played session, and
any run that has to say what it ran reads it there.

## The cfg file

A comment containing two consecutive hyphens is invalid XML: MAME prints `Error parsing XML
configuration file` on stderr, loads the defaults and rewrites the file on exit. A `<port>` binds
only when its `tag`, `type` and `mask` match the driver's `PORT_BIT`, and its `defvalue` too when
the field's default under that mask is not zero; otherwise it is skipped without a word
(`src/emu/ioport.cpp`). The shape, with the values of Wheels & Fire's own `PORT_BIT` for button 1
(mask `0x0010`, active low, so its default under the mask is the mask itself):

```xml
<port tag=":P1" type="P1_BUTTON1" mask="16" defvalue="16">
    <newseq type="standard">KEYCODE_DOWN</newseq>
</port>
```

## Reading the machine without being misled

- **What is on screen is the live palette device** (`pen_color(i)`), not the buffer the game
  assembles before a fade: both hold plausible colours. When the game uploads its palette through
  the RAMDAC during vblank and the driver overrides it, the override goes at the falling edge of
  `screen_vblank`, after the upload; at `screen_update` or on the rising edge the upload undoes it.
- **Sync to the real event, not to a frame count.** A palette change belongs to the page flip it
  goes with: snapshot each plane's pens at the flip and apply them at vblank, and a change of the
  game's cadence cannot put the two out of step.
- **Verify a sign of life with something the failure cannot freeze.** A state variable in RAM keeps
  its last value when the 68000 hangs; the picture changing, or the state block still ticking, is
  the proof.
- **Decode from the address, not from a linear listing.** A flat disassembly of a ROM with code and
  data mixed drifts out of alignment at the first table; decoding a few instructions from the
  address is immune to that.
- **A value equal to its type's maximum is a cap, not a measurement.** The visible height of a
  board is measured with something anchored to an edge and where it comes to rest, not with the
  clip rectangle the game declares: Wheels & Fire's race portrait slides in pinned to the bottom
  and rests on row 251, while the declared clip ends at `0xff`.
- **Measure inside the box of the fault.** A detector averaging over the whole screen dilutes a fault
  that occupies part of it below any threshold; bound the region to where the fault is seen.
- **Open every capture.** A measurement answers the question it was asked; looking at the image asks
  all of them, including the one nobody thought of.
- **On a little-endian host a 68000 operand reads byte-swapped** when a ROM is patched live.

## When the picture is wrong

- **The ROM ran on the board, so the broken model is ours.** Before blaming the game's data, find
  the routine the game itself uses for that computation and validate the law it implements against
  a known answer: scale 100 must give the identity, 200 exactly double.
- **The emulator exposes latent bugs the board tolerated.** Silicon has margins and undocumented
  behaviour; MAME models the hardware as specified. When a port misbehaves on code that "worked on
  the board", a latent bug is the leading hypothesis, and its fix is commented as what it was.
- **Separate "not emitted" from "emitted and lost".** Log every blit with its source (page, u0,
  v0, size, ROM address), dump those graphics to PNG with the palette of their frame, and recognise
  the missing sprite by eye. If it is in the log, the fault is in composition, not in the blit.
- **Reproduce a frame offline before sweeping a parameter.** Dump the planes, the live palette and
  the per-line scroll of one frame from the driver, rebuild the frame in Python, prove it against
  the golden at zero pixels different, and only then sweep: a dozen emulator runs become a loop.

## Rebuilding a driver

One driver is rebuilt on its own, where the subtarget is `wheelfir` or `rltennis`:

```sh
cd upstream && make SUBTARGET=<subtarget> SOURCES=src/mame/tch/<driver>.cpp REGENIE=1 -j<cores>
```

`REGENIE=1` regenerates the subtarget's driver list, which a stale cache would build without the
machine. What the command does not say:

- The binary is shared: whatever was built last is what every run executes, and a failed build
  leaves the previous one in place. `scripts/lib/binary.sh` warns when a driver source is newer
  than its binary.
- macOS's `make` compares modification times to the second. A source swapped and rebuilt within
  the same second as the previous build can leave the old object linked, and `binary.sh` cannot
  see it either; delete the driver's `.o` before such a build. `scripts/export-patch.sh --check`
  proves which source is in `upstream/`; comparing binaries proves nothing, since two builds of one
  source are not byte-identical.
