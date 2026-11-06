# `.scry/`: this repository's store

What this repository declares about how its boards run, so a session boots one without composing
the server's arguments by hand. The server reads it; nothing here is written by a tool.

    .scry/
      README.md             this page
      start/<name>.json     a run recipe: `start`'s arguments, in the `scry-start/1` format

## The recipes

| name | board | binary |
| --- | --- | --- |
| `radendur` | Radical Enduro (the early prototype, which hangs on its own faults) | `upstream/wheelfir` |
| `radendurh` | Radical Enduro, the clone whose maincpu ROM this repository fixes | `upstream/wheelfir` |
| `wheelfir` | Wheels & Fire | `upstream/wheelfir` |
| `pwball` | Power Ball | `upstream/wheelfir` |
| `kongball` | Kong Ball | `upstream/wheelfir` |
| `rltennis` | Reality Tennis | `upstream/rltennis` |
| `rltennisa` | Reality Tennis, the second layout | `upstream/rltennis` |

Each recipe is complete: it names its board, its binary, the romset directory, the directory MAME
reads its ini from, the symbol map of the main cpu and a bounded boot. No recipe inherits from
another; the few facts two boards share are written twice on purpose, because an include would be
a mechanism with no caller yet.

The binaries, the romsets and the 68000 images are not committed: `make setup` builds the two
binaries into `upstream/` and adds the fixed clone's romset, and `make disasm` writes the images
into `disasm/img/`, which six recipes name as their known-answer read. A recipe names them where
`make` leaves them, so boot a recipe after both, or give the call its own `binary`, `rompath` and
`reference_rom`.

`radendurh`'s maincpu ROM is the dump with the prototype's faults patched, which the repository
builds: the recipe's `reference_rom` is the flat image the build writes beside the zip,
`run/mame_roms/radendurh_maincpu.bin`, and its `reference_addr` is the first address the patch
changes, so the known-answer read tells the clone from the dump. Its symbols are the dump's, whose
addresses the patch keeps.

## How a path is written

Every recipe resolves against one base, the directory holding `.scry/`, so a relative path is
relative to this repository. What a tracked file must not carry, a host path, is written as a
placeholder:

- `${root}`: this repository.
- `${home}`: the user's home.
- `${state}`: the session's scratch directory.
- `${env:NAME}`: an environment variable, refused by name when it is unset.

## The caller wins

A recipe fills only what the call does not give, so `start(profile="rltennis", binary=...)` boots
the other build and takes the rest from the recipe. The reply's `profile` block names the file and
every key it supplied.

## What stays out

A recipe declares how a board starts: paths, arguments, how long a boot waits. What a board's
trace means (which stop serves a case, what a register proves, how a golden is judged) stays in
this repository's rules and its scripts, because only this repository holds the gate that keeps it
true.
