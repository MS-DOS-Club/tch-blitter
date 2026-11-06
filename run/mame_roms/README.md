# run/mame_roms/

The six MAME romsets go here as `.zip` files: `rltennis`, `rltennisa`, `wheelfir`, `pwball`,
`kongball` and `radendur`. They are not distributed with this repository; how to get them and
check them is in the [README](../../README.md#getting-started). `make setup` adds
`radendurh.zip`, built here from the `radendur` dump; the same file is on the
[Internet Archive](https://archive.org/details/radendurh). Beside it the build writes
`radendurh_maincpu.bin`, the same ROM flattened as `rom_check` compares it, which the
repository's `.scry/start/radendurh.json` names.
