# Makefile -- tch-blitter: build this repository's MAME, play, and check the work.
# `make help` lists the targets. The romsets are not distributed: they go in run/mame_roms/ first.

.PHONY: help doctor setup setup-force play fast debug stop verify goldens verify-family bless-family \
        savestate radendurh ref disasm disasm-all ghidra-setup ghidra ghidra-export ghidra-gui patch hw-docs \
        test lint fmt check check-all clean distclean

.DEFAULT_GOAL := help

# <set>:<first frame> of each save-state check: a window where the planes the driver saves are drawn
SAVESTATE_FRAMES := wheelfir:1100 pwball:2580 kongball:880 radendur:900 radendurh:900 rltennis:900 rltennisa:900

help: ## Lists every target
	@grep -hE '^[a-zA-Z0-9_-]+:.*?##' $(MAKEFILE_LIST) | \
	  awk -F':.*##' '{printf "  \033[36m%-13s\033[0m %s\n", $$1, $$2}'

doctor: ## What this machine is missing (changes nothing)
	./scripts/setup-mame.sh --doctor

setup: ## Clones MAME at the pin, applies patches/, builds the two binaries and radendurh's ROM
	./scripts/setup-mame.sh

setup-force: ## As setup, rebuilding the binaries
	./scripts/setup-mame.sh --force

play: ## Plays radendurh (the fixed clone) at real speed
	./scripts/radendur-session.sh play

fast: ## radendurh unthrottled
	./scripts/radendur-session.sh fast

debug: ## radendurh with the gdbstub on :23946
	./scripts/radendur-session.sh debug

stop: ## Ends the instance play, fast or debug started
	./scripts/radendur-session.sh stop

verify: ## Radical Enduro's goldens: radendurh, then the dump
	@rc=0; ./scripts/radendur-goldens.sh verify radendurh || rc=1; \
	  ./scripts/radendur-goldens.sh verify radendur || rc=1; exit $$rc

goldens: ## Re-blesses one Radical Enduro set's goldens. SET=radendurh (default) | radendur
	./scripts/radendur-goldens.sh bless $(or $(SET),radendurh)

verify-family: ## The siblings' goldens (wheelfir, pwball, kongball, rltennis, rltennisa)
	./scripts/goldens-family.sh verify

bless-family: ## Re-blesses the siblings' goldens
	./scripts/goldens-family.sh bless

savestate: ## A save state loaded in a fresh process gives the same frames, every set
	@rc=0; for sf in $(SAVESTATE_FRAMES); do \
	  ./scripts/savestate-gate.sh "$${sf#*:}" 20 "$${sf%%:*}" || rc=1; done; exit $$rc

radendurh: ## Builds run/mame_roms/radendurh.zip from the dump and hardware/radendurh.yaml
	uv run scripts/radendurh.py

ref: ## Builds a set's driver if needed and opens it. SET=pwball|wheelfir|kongball|radendur|radendurh|rltennis|rltennisa
	./scripts/build-and-run.sh $(or $(SET),pwball)

disasm: ## The 68000 program images, disasm/img/
	./scripts/disasm.sh

disasm-all: ## The whole disassembly chain: symbols, images, Ghidra import and export, docs
	uv run scripts/gen-hw-docs.py
	./scripts/disasm.sh
	./scripts/ghidra-export.sh
	uv run scripts/gen-hw-docs.py

ghidra-setup: ## Downloads the pinned Ghidra into tools/ (needs a JDK)
	./scripts/ghidra-setup.sh

ghidra: ## Imports and analyses the images whose seed changed (FORCE=1 for all)
	./scripts/ghidra-import.sh

ghidra-export: ## Writes disasm/analysis.txt and disasm/listings/
	./scripts/ghidra-export.sh

ghidra-gui: ## Opens Ghidra on the disasm/ghidra project
	@JAVA_HOME=$$(. scripts/lib/jdk.sh && java_home_path) tools/ghidra/ghidraRun

patch: ## Writes the changes in upstream/ into patches/
	./scripts/export-patch.sh

hw-docs: ## Regenerates the documentation from hardware/*.yaml
	uv run scripts/gen-hw-docs.py

test: ## The Python tests
	uv run pytest

lint: ## ruff, mypy and shellcheck
	uv run ruff check scripts tests
	uv run ruff format --check scripts tests
	uv run mypy scripts tests
	shellcheck -x -P SCRIPTDIR $$(git ls-files '*.sh')

fmt: ## ruff format
	uv run ruff format scripts tests

check: lint test ## Before a pull request: lint, tests, the docs against their data, the patches against upstream/
	@ls disasm/img/*.bin >/dev/null 2>&1 || ./scripts/disasm.sh
	uv run scripts/verify-docs.py
	uv run scripts/verify-games.py
	uv run scripts/verify-images.py
	./scripts/export-patch.sh --check
	./scripts/verify-patches.sh

check-all: check verify verify-family savestate ## check, plus every golden and save state (boots MAME)

clean: ## Removes tmp/, where every run leaves its files
	rm -rf tmp

distclean: clean ## Also removes upstream/, the MAME clone
	@printf "Delete upstream/ (the MAME clone)? [y/N]: "
	@read c && case "$$c" in y|Y) rm -rf upstream && echo "upstream/ deleted" ;; *) echo "cancelled" ;; esac
