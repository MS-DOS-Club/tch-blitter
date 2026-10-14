# Full track maps (docs/img/radendur/tracks/)

The five playable sections, each rendered whole from the ROM with `scripts/radendur_tracks_all.py`,
emulating the blitter and the isometric model. The full-resolution version goes to `full/`; the one
rescaled to at most 1400 px wide stays here, and `scripts/make-readme-images.py` scales it down
again into the `../readme/map-*.png` the game page shows.

The five rescaled images in this folder are versioned; `full/` is not, and regenerates from the
`radendur` romset in `run/mame_roms/` with `uv run scripts/radendur_tracks_all.py` (the other
renders: [../sections/README.md](../sections/README.md)).
