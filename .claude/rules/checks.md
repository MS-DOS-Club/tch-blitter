---
paths:
  - "scripts/**"
  - "tests/**"
  - "Makefile"
  - "pyproject.toml"
  - "patches/**"
  - "upstream/src/mame/tch/**"
  - "CLAUDE.md"
  - "CONTRIBUTING.md"
  - "README.md"
  - ".claude/rules/**"
---

# Checks, scripts and the hygiene of what is published

## What to run

- `make check` before a pull request, once `make setup` has run: lint (ruff, mypy, shellcheck), the
  tests, the documentation against its data, the patches against `upstream/`. `make check-all` adds
  every golden and the save-state check, which boot MAME.
- GitHub Actions (`.github/workflows/check.yml`) runs `make lint` and `make test` on every push
  to `main` and every pull request: the part of `make check` that needs neither MAME nor the
  romsets. The documents and the patches are checked against `upstream/`, so they stay local.
- While investigating one game, its own gate only (`goldens-family.sh verify <set>`, or
  `make verify` for Radical Enduro); the whole family when the fix closes.
- A change to `hardware/*.yaml` or a document cannot move a golden: `make hw-docs` and
  `uv run scripts/verify-docs.py` are its checks.

## Scripts

- A script carries its language's extension, `#!/usr/bin/env bash` with `set -euo pipefail` for
  shell, and is clean under `shellcheck -x -P SCRIPTDIR`.
- Exit codes: 0 clean, 2 a usage error, anything else a failure; 3 where a check could not look (an
  input missing, nothing to examine). A check that examined nothing never answers 0.
- What a script can validate while it runs is validated there. No git hooks and no tests of tests:
  a test exercises a script's real behaviour.

## Language

Everything is English, file names included. When something changes, it is corrected where it was
already written, in every copy: a new note elsewhere does not supersede the old one, it contradicts
it.

## Hygiene

- Every tracked file is impersonal: no people, no AI, no board or issue numbers, no private notes.
  What the reader needs is the state, not where it was decided.
- `CLAUDE.md` and `.claude/rules/` are written for a coding assistant, so they name it and its files
  (`CLAUDE.local.md`), and `CONTRIBUTING.md` asks for AI assistance to be disclosed. They are
  impersonal in everything else.
- The exceptions, no wider than their words:
  1. The three drivers (`wheelfir.cpp`, `radendur.cpp`, `rltennis.cpp`, and so the patches): the
     `copyright-holders` line, because MAME attributes a driver to whoever wrote it, and the
     attribution block of each header, verbatim: `Original driver by Tomasz Slanina.`, then one
     sentence on what this repository did to that driver, ending `by Marcos Hernández, in
     collaboration, within MS-DOS Club's TCH preservation project
     (github.com/MS-DOS-Club/tch-blitter).`; `radendur.cpp`'s block closes with a pointer to
     `wheelfir.cpp` for the blitter notes.
  2. The line that closes `README.md` and each game page, verbatim: `Developed by Optimiza
     ([Marcos Hernández](https://www.linkedin.com/in/optimiza/)), in collaboration with [MS-DOS
     Club](https://msdos.club) and its [podcast](https://www.ivoox.com/podcast-ms-dos-club_sq_f11160693_1.html).`
  3. The credits and thanks of `README.md` and each `docs/games/*.md`, generated from
     `hardware/games.yaml`: the authors of the MAME drivers and the people who preserved and dumped
     the boards.
  4. The credits the sources carry: the teams that sign their ROMs, the board photographers
     recreativas.org credits, and the technical source MAME's Reality Tennis driver credits.
- `upstream/` and the romsets are never committed; `patches/` is the only part of a driver change
  that travels.
