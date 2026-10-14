# shellcheck shell=bash
# patch_table.sh -- the patches this repository carries over the pinned MAME, and the files each
# one owns. Sourced. No file belongs to two patches: two patches editing one file apply in one
# order only, and nothing here would say which.
# shellcheck disable=SC2034  # read by the scripts that source this file
PATCHES="
0002-wheelfir-video-model.patch|src/mame/tch/wheelfir.cpp src/mame/mame.lst
0003-lua-thread-context-race.patch|src/frontend/mame/luaengine.cpp
0004-gdbstub-one-thread-per-cpu.patch|src/osd/modules/debugger/debuggdbstub.cpp
0005-rltennis-blitter-scale.patch|src/mame/tch/rltennis.cpp
"

patch_table_names() { printf '%s\n' "$PATCHES" | cut -d'|' -f1 | sed '/^$/d'; }
