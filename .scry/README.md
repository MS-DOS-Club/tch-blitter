# `.scry/`

How this repository's arcade boards start under SCRY.

SCRY is a set of MCP servers that let an assistant run a program in an emulator and inspect it
live. This folder is what this repository keeps for it: how the program starts. Where it has
them, it also holds what its screens look like and a list of steps that drives it.

## Build first

The start profiles below need this built first.

    make setup && make disasm

## How to start

Call the `mame` server's `start` tool with a start profile's name: `start(profile="<name>")`. An argument in the same call wins over the profile's. A profile's paths resolve against the directory holding `.scry/`, and what would be this machine's path is a [placeholder](https://github.com/scry-mcp/scry-core/blob/main/docs/store-paths.md).

## Start profiles

A start profile is a saved set of `start` arguments, so a session boots a program without composing them by hand.

- `kongball` (`start/kongball.json`): Kong Ball.
- `pwball` (`start/pwball.json`): Power Ball.
- `radendur` (`start/radendur.json`): Radical Enduro, the early prototype.
- `radendurh` (`start/radendurh.json`): Radical Enduro, the clone whose ROM this repository fixes.
- `rltennis` (`start/rltennis.json`): Reality Tennis.
- `rltennisa` (`start/rltennisa.json`): Reality Tennis, the second layout.
- `wheelfir` (`start/wheelfir.json`): Wheels & Fire.

## Saved step lists

Each is a list of steps the `perform` tool replays.

- `perform/wheelfir-slave-waits-for-master.json`: replays 60 steps.

---

This page is rendered by the servers' `promote` from `about.json` and the files beside it; edit
those, never this page. To render it by hand, run `uv run python -m scry_core.scry_readme
<this repository>` from a scry-core checkout.
