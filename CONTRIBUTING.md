# Contributing

This repository follows [MAME's own practice for contributions](https://docs.mamedev.org/contributing/index.html),
because its drivers are meant to go upstream and a change that would not pass there is a change
made twice. What follows is that practice, narrowed to this tree.

## Reporting a fault

An issue is for a fault somebody else can reproduce. "It doesn't work" is not enough to act on, so
a report carries:

- **What happens and what should happen instead.** For a graphical fault, a capture of each.
- **What it ran on:** the commit of this repository, the MAME commit it was built against (pinned
  in `scripts/lib/mame_src.sh`, so the same unless you changed it), and any build option you
  changed. For a video fault, the GPU and the video output; for an input fault, the controller.
- **The set** (`wheelfir`, `pwball`, `kongball`, `radendur`, `radendurh`, `rltennis`, `rltennisa`)
  and whether its romset passes `-verifyroms` (README, Getting started).
- **The steps to reach it**, written for somebody who knows MAME but not necessarily the game: the
  frame or the moment, the inputs. A save state or an input recording helps more than a paragraph.
- **A reference for the right behaviour**, ideally a recording of the original board. A fault seen
  only in MAME is a fault in the model until the board says otherwise.

Questions and support are not issues.

## Proposing a change

- **One topic per pull request.** A driver fix, a hardware fact, a tool: each on its own, so each
  can be judged, reverted or taken upstream alone.
- **Build it and run it.** `make setup` builds the two binaries. A driver change is also built
  once with `DEBUG=1`, as MAME asks, so its assertions compile and do not trigger:
  `cd upstream && make SUBTARGET=wheelfir SOURCES=src/mame/tch/wheelfir.cpp REGENIE=1 DEBUG=1 -j8` builds
  `upstream/wheelfird`, which runs the set as `upstream/wheelfird -rompath run/mame_roms wheelfir`.
  Watch the change working on the set it is about.
- **Run the checks.** Once `make setup` has run, `make check` runs the linters, the tests, the documentation against its data
  and the patches against `upstream/`; `make check-all` adds every golden and the save-state check.
  A golden that turns red is information about the change: say in the description which ones moved
  and why.
- **A driver change travels as its patch.** `upstream/` is not committed; `make patch` exports the
  driver into `patches/`, and `scripts/export-patch.sh --check` refuses a driver that diverges from
  its patch.
- **A hardware fact goes into `hardware/*.yaml` first**, with its evidence, and `make hw-docs`
  projects it into the documentation; the generated blocks are never edited by hand.
- **Describe it.** A one-line title and a description that says what the change does and why;
  never an empty description. Commit messages follow
  [Conventional Commits](https://www.conventionalcommits.org/) (`fix(wheelfir): ...`).
- **Disclose AI assistance.** A pull request made with the help of an AI tool says so in its
  description, naming the model and its version. It is not a reason to reject a change; it tells the
  reviewer where to look harder. Whoever opens the pull request is responsible for understanding and
  explaining every line of it.

## Licence

The drivers derive from MAME and keep its licence (BSD-3-Clause), and the tools and documentation
here are under the same terms; a contribution is made under them.
