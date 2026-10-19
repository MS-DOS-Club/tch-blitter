# scripts/

What each tool is for. The `Makefile` wraps the ones used day to day (`make help` lists them);
Python runs with `uv run scripts/<name>.py`, and every MAME launch goes through `lib/mame_run.sh`.

## Build, run and check

| script | what it does |
|--------|--------------|
| `setup-mame.sh` | `make setup`: clones MAME at the pin into `upstream/`, applies `patches/`, builds `wheelfir` and `rltennis`, builds radendurh's ROM; `--doctor` (`make doctor`) says what this machine is missing |
| `radendur-session.sh` | `make play`, `fast`, `debug` (gdbstub) and `stop` for Radical Enduro |
| `build-and-run.sh` | `make ref SET=<set>`: builds a sibling's binary if needed and opens it |
| `radendurh.py` | `make radendurh`: builds radendurh's maincpu ROM from the verified dump and the patch table `hardware/radendurh.yaml`; `--check` says whether the zip is current |
| `export-patch.sh` | `make patch`: writes the driver changes in `upstream/` into `patches/`; `--check` says whether they still match |
| `verify-patches.sh` | the patches rebuild `upstream/`'s changes on a clean tree at the pin |
| `verify-romset.sh <set>` | a romset against its driver's `ROM_START` |
| `radendur-goldens.sh` | `make verify` / `make goldens`: Radical Enduro's goldens (boot, race start, desert race) |
| `goldens-family.sh` | `make verify-family` / `make bless-family`: the siblings' goldens, the frames in each `goldens/<set>/scenes.conf`, and the sound CRC where a set declares a `sound` line |
| `savestate-gate.sh` | `make savestate`: a state saved and loaded in a fresh process gives the same frames |
| `lib/mame_run.sh` | which binary runs each set, and the MAME command line every script launches (a quick unattended window, or a session to play) |
| `lib/sound_crc.lua` | the goldens' sound check: a CRC-32 of the words the sound CPU writes to its DACs |
| `lib/analog.lua` | holds an analog input at the value its port reads, for the goldens' `press` lines and `drive.lua` |
| `lib/mame_src.sh` | where the MAME checkout is, and the commit it is pinned to |
| `lib/patch_table.sh` | the patches and the MAME files each one owns |
| `lib/binary.sh` | prints the binary a run uses, and warns when its driver source is newer |
| `lib/jdk.sh` | `JAVA_HOME` for the Ghidra tools |

## The documentation, generated from the data

| script | what it does |
|--------|--------------|
| `gen-hw-docs.py` | `make hw-docs`: `hardware/*.yaml` into the board pages' tables and `disasm/symbols.txt`, validating the schema |
| `gen-games.py` | `hardware/games.yaml` into the README's game, credits and resources tables and each game page's facts |
| `gen-before-after.py` | `docs/img/before-after/manifest.yaml` into the README's before/after section |
| `gen-gif-manifest.py` | measures every published GIF into `docs/img/gifs/manifest.yaml` |
| `verify-docs.py` | links, images and generated blocks of every document, and every generator's `--check` |
| `verify-games.py` | every `verified` fact of `games.yaml` against its evidence (the driver's `GAME` macro, the ROM) |
| `verify-images.py` | every before/after pair still measures what its caption says |
| `doc_blocks.py`, `image_diff.py`, `symbols_model.py`, `image_keys.py`, `memory_map.py`, `port_names.py` | modules the generators, the checks and the Ghidra chain share |

## Captures and renders

| script | what it does |
|--------|--------------|
| `frame-series.sh <set> <from> <to> <dir>` | consecutive frames of one set |
| `gif.sh` | a stretch of frames into a GIF at real time, for the documentation |
| `remake-media.sh` | the recipe of the Wheels & Fire family's GIFs and before/after "after" images: remakes them from the current binary |
| `family-captures.py` | the documentation's stills of the seven sets (titles, attract and race frames, as its manifest lists them) |
| `before-after.py` | measures a before/after pair: how much changes and where |
| `make-readme-images.py` | the light images of Radical Enduro's page |
| `radendur_track_render.py` | Radical Enduro's isometric track renderer, from the ROM, no emulator |
| `radendur_tracks_all.py`, `radendur-track-details.py`, `radendur-sections-broken.py` | every track, the detail crops, and the sections the game never finished |
| `wheelfir-blit-law.py` | re-derives the zoom law record's figures from `hardware/evidence/wheelfir-blit-law/`; `--full` adds the ROM's descriptor tables |
| `signatures.py` | the teams' signatures in the ROMs |
| `drive.lua` | inserts a coin, starts and drives, on any set |
| `radendur/oracle.lua`, `radendur/nav-phase.lua`, `radendur/race-shot.lua` | the harnesses of Radical Enduro's goldens |

## The disassembly

| script | what it does |
|--------|--------------|
| `disasm.sh` | `make disasm`: the 68000 program images, `disasm/img/` |
| `ghidra-setup.sh`, `ghidra-import.sh`, `ghidra-export.sh` | download the pinned Ghidra, analyse the images, write `disasm/analysis.txt` and `disasm/listings/` (`make disasm-all` runs the chain) |
| `ghidra-labels.py` | the export's precondition: the project carries exactly `hardware/symbols.yaml`'s labels |
| `verify-listings.py` | each listing against its image with capstone; marks what Ghidra decoded and no 68000 runs |
| `listing_format.py` | the line formats of a listing and of an executed-address file |
| `trace-seeds.py` | the ROM addresses MAME executed, from a debugger trace, into `disasm/executed/` |
| `scan-hw-accesses.py` | which hardware each game touches, into `hardware/accesses.yaml` |
| `ghidra/*.java` | the scripts Ghidra runs headless: `SetupTCH` seeds the analysis, `MemoryMapTCH` declares the board's memory map, `ExportTCH`, `ListTCH` and `FactsTCH` write it out, `DumpFuncs` and `Xref` answer one question by hand |
