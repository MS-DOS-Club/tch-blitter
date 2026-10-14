# Boot goldens of the board's dump

`radendur` is the prototype's dump emulated with no intervention, so it stops on the prototype's own
faults. These captures pin how far it gets: the boot and attract are pixel for pixel the fixed
clone's (`../radendurh/`; the files differ only in the manufacturer and description MAME writes into each PNG's text), and
`04_race_start`, captured where the clone is already on the starting line, still shows the
selection screen. A change that moves any of them changes what the faithful emulation does, and is
looked at before `make goldens SET=radendur`.

The capture method, the self-check of the baseline and what to do on another machine are the
same as the clone's: [../radendurh/README.md](../radendurh/README.md).
