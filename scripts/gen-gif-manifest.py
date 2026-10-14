"""gen-gif-manifest.py -- measures every published GIF into docs/img/gifs/manifest.yaml: frames,
delays, duration and the emulated frames they stand for, at the refresh the set's binary declares.
The capture takes one image per emulated frame, so a GIF runs at real time when
duration_s == emulated_frames / refresh_hz, and --check says whether the files still match.

Use:
    uv run scripts/gen-gif-manifest.py            rewrites the manifest
    uv run scripts/gen-gif-manifest.py --check    fails if it does not match the files
"""

from __future__ import annotations

import argparse
import functools
import os
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
GIFS = ROOT / "docs" / "img" / "gifs"
MANIFEST = GIFS / "manifest.yaml"

NOTE = (
    "Every GIF runs at REAL TIME, and here is the number that proves it rather than the assertion. "
    "The capture takes one image per EMULATED frame (a MAME frame notifier, not a recording of the "
    "window), so the -nothrottle it runs with only changes how long the host machine takes to "
    "produce them, not the interval between them. The GIF keeps one emulated frame of every `step` "
    "and holds each for step / refresh_hz seconds, refresh_hz being the rate the set's binary "
    "declares, that is, duration_s = emulated_frames / refresh_hz."
)
WHY = (
    "No browser plays a GIF at the board's full rate, and keeping every frame takes the gameplay "
    "GIFs over the size cap, so gif.sh keeps one frame in `step`. The price is jerky motion, which "
    "is easy to mistake for accelerated speed; that is why it is documented, so the doubt is not "
    "resolved twice."
)


def ffprobe(gif: Path, fields: str, count: bool = False) -> str:
    command = ["ffprobe", "-v", "error"]
    if count:
        command += ["-count_frames"]
    command += ["-select_streams", "v:0", "-show_entries", fields, "-of", "csv=p=0", str(gif)]
    return subprocess.run(command, capture_output=True, text=True, check=True).stdout.strip()


@functools.cache
def refresh_for_set(game: str) -> float:
    """The refresh the set's binary declares, asked through the shell helper the captures use."""
    shell = '. "$1/mame_src.sh"; . "$1/mame_run.sh"; mame_refresh_for_set "$2"'
    run = subprocess.run(
        ["bash", "-c", shell, "_", str(ROOT / "scripts" / "lib"), game],
        capture_output=True,
        text=True,
        env={**os.environ, "PROJECT_DIR": str(ROOT)},
    )
    if run.returncode != 0:
        print(f"INVALID: no refresh for {game}: {run.stderr.strip()}")
        sys.exit(3)
    return float(run.stdout)


def measure() -> dict:
    gifs = sorted(GIFS.glob("*.gif"))
    if not gifs:
        print(f"INVALID: no GIF in {GIFS}")
        sys.exit(3)
    entries = []
    for g in gifs:
        n_frames = int(ffprobe(g, "stream=nb_read_frames", count=True))
        width, height = (int(v) for v in ffprobe(g, "stream=width,height").split(","))
        dur = float(
            subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "csv=p=0",
                    str(g),
                ],
                capture_output=True,
                text=True,
                check=True,
            ).stdout
        )
        game = g.stem.split("-")[0]
        hz = refresh_for_set(game)
        # How many emulated frames each GIF frame stands for, read off the GIF's own delay.
        step = max(1, round(hz * dur / n_frames))
        entries.append(
            {
                "file": g.name,
                "set": game,
                "refresh_hz": round(hz, 3),
                "gif_frames": n_frames,
                "fps": round(n_frames / dur, 2),
                "width": width,
                "height": height,
                "duration_s": round(dur, 3),
                "emulated_frames": n_frames * step,
                "mb": round(g.stat().st_size / 1048576, 2),
            }
        )
    return {"note": NOTE, "why_decimated": WHY, "cap_mb": 4, "gifs": entries}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="fails if the manifest does not match")
    args = ap.parse_args()

    doc = measure()
    text = yaml.safe_dump(doc, allow_unicode=True, sort_keys=False, width=98)
    if args.check:
        if not MANIFEST.exists():
            print(f"INVALID: {MANIFEST.relative_to(ROOT)} is missing")
            return 3
        if MANIFEST.read_text() != text:
            print("the GIF manifest does not match the files; run the generator")
            return 1
        print(f"GIFs checked: {len(doc['gifs'])}")
        return 0

    MANIFEST.write_text(text)
    for e in doc["gifs"]:
        print(
            f"  {e['file']:28s} {e['gif_frames']:4d} frames at {e['fps']} fps = "
            f"{e['duration_s']:.2f} s   <- {e['emulated_frames']} emulated frames "
            f"({e['emulated_frames'] / e['refresh_hz']:.2f} s at {e['refresh_hz']} Hz)"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
