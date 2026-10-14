#!/usr/bin/env python3
"""wheelfir-blit-law.py -- the stall-counter law of the zoom, re-derived blit by blit.

WHAT IT ANSWERS. The board author's model of the zoom says each axis is a pair of counters: a stall
field of n gives n/(n+1), a repeat field of n gives n/(n-1), a field of 0 or 32 is idle,
`clock_halve` halves, `clock_double` doubles, and the scale is the product. Nothing here goes
through the driver's percentage table: the scale comes from the fields alone. The question is
whether the destination each blit declares follows that law, and the answer is measured on what
the game really handed the blitter in a 1500-frame attract pass, not on what its tables say it
should hand it.

THE EVIDENCE it reads is `hardware/evidence/wheelfir-blit-law/` (its README says how it was
captured): the blitter's words 0..0xe at every write of the trigger, and the software clip
rectangle at the same instants. Every figure the record `wheelfir_the_law_holds_blit_by_blit` in
`hardware/registers.yaml` quotes from that capture is printed here, so the record can be checked
against a run instead of believed.

HOW IT SCORES, and why the controls are on the same set. Blits are grouped by source (page, u0,
v0, both walks); in every group showing at least three scales on an axis, the native span is the
median of steps x 100 / scale, and a prediction hits when it lands within one step plus 1%. A hit
rate means nothing alone, so two controls run on exactly the same measurements: the identity (the
span ignores the scale) and the scales shuffled among the measurements. A control scored over any
other set (every blit, most of them at 100%) would have another denominator and say nothing about
this one.

THE RESIDUE. The misses are clipped sprites, and the ones strictly inside the window are a cut the
game declares: with `--full`, the source rows each blit reads are walked through the driver's own
inverse of the ROM descriptor and set against the opaque rows of its graphic, which separates "the
law is wrong" from "the game asked for fewer rows". A planted truncation is the control that shows
the instrument can see one.

WHAT IT DOES NOT ESTABLISH. MAME is a model, and the game computes each destination in software
from the ROM tables, so this proves what the blitter receives and what the game declares per
blit, not that the FPGAs count that way.

`--full` adds the known answer (the model over the driver's `ZOOM_INDEX` against the real scale of
each ROM descriptor) and the source-row coverage; both need the MAME clone, `make disasm` and the
wheelfir romset, and a missing one is INVALID.

USAGE:
    uv run scripts/wheelfir-blit-law.py [--full]

EXIT: 0 every section ran; 2 usage; 3 INVALID (an input missing, a section that examined
nothing, or a control that came out no better than chance).
"""

from __future__ import annotations

import argparse
import lzma
import random
import re
import statistics
import struct
import sys
import zipfile
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "hardware" / "evidence" / "wheelfir-blit-law"
BLOCK = EVIDENCE / "block.rows.xz"
CLIPRECT = EVIDENCE / "cliprect.rows.xz"
FRAMES = (1331, 1339, 1389)
DRIVER = ROOT / "upstream" / "src" / "mame" / "tch" / "wheelfir.cpp"
MAINCPU = ROOT / "disasm" / "img" / "wheelfir_maincpu.bin"
ROMSET = ROOT / "run" / "mame_roms" / "wheelfir.zip"
# gfx1 as the driver loads it: eight 512 KB ROMs, two 512x512 8bpp pages each, in a 16 MB region
# erased to zero beyond them.
GFX_ROMS = (
    *("tch4.u52", "tch5.u53", "tch6.u54", "tch7.u55"),
    *("tch8.u56", "tch9.u57", "tch10.u58", "tch12.u59"),
)
GFX_REGION = 0x1000000

# The trigger write that fires a blit carries 0xffff; the one that arms it carries 0.
FIRE = 0xFFFF
# Pages from 0x1c up are the direct-write window, not graphics.
DIRECT_PAGE = 0x1C
# The clip window's edges, as the destination endpoints land on them (the bottom clip writes 256).
EDGES = {"u": (0, 335, 336), "v": (0, 255, 256)}
SHUFFLE_SEEDS = 20
MIN_SCALES = 3
# The row the clipped roadside objects end on, and the same row on the other page.
CUT_ROWS = (187, 188)
CUT_ROWS_OTHER_PAGE = tuple(r + 256 for r in CUT_ROWS)
PAGE_BOTTOMS = (255, 511)
# The car-selection screen's zoom, the other clipped sprite the misses name, in this pass.
CAR_SCREEN = range(659, 669)


def factor_stall(field: int) -> float:
    """A write-side stall field of n leaves n of every n+1 cycles writing."""
    n = field & 0x1F
    return 1.0 if field in (0, 0x20) else n / (n + 1)


def factor_repeat(field: int) -> float:
    """A read-side repeat field of n rereads one of every n-1 source pixels."""
    n = field & 0x1F
    if field in (0, 0x20):
        return 1.0
    return n / (n - 1) if n > 1 else float("inf")


def model_scale(index: int) -> float:
    """The scale, in percent, an index's fields give by the law alone (no table)."""
    stall, repeat = index & 0x3F, (index >> 6) & 0x3F
    s = 100.0 * factor_stall(stall) * factor_repeat(repeat)
    if index & 0x1000:
        s /= 2
    if index & 0x2000:
        s *= 2
    return s


def indices(w: list[int]) -> tuple[int, int]:
    """The zoom index of each axis, decoded from words 8..0xc exactly as the driver's do_blit."""
    stall_u = ((w[0xA] & 0x1F00) >> 8) | ((w[8] & 0x0100) >> 3)
    repeat_u = ((w[0xB] & 0x1F00) >> 8) | ((w[8] & 0x0400) >> 5)
    iu = stall_u | (repeat_u << 6) | ((w[9] & 1) << 12) | ((1 if w[8] & 0x1000 else 0) << 13)
    stall_v = (
        ((w[0xB] & 0xC000) >> 14)
        | ((w[0xC] & 0xC000) >> 12)
        | ((w[0xA] & 0x4000) >> 10)
        | ((w[8] & 0x0200) >> 4)
    )
    repeat_v = ((w[0xC] & 0x1F00) >> 8) | ((w[8] & 0x0800) >> 6)
    iv = stall_v | (repeat_v << 6) | ((1 if w[9] & 2 else 0) << 12)
    iv |= (1 if w[8] & 0x2000 else 0) << 13
    return iu, iv


@dataclass(frozen=True)
class Blit:
    """One fire of the trigger that reads its source, with what the law and the game say of it."""

    row: int
    frame: int
    pc: int
    iu: int
    iv: int
    x: tuple[int, int]
    y: tuple[int, int]
    steps_u: int
    steps_v: int
    page: int
    u0: int
    v0: int
    walk: tuple[int, int]
    rect: tuple[int, int, int, int]

    @property
    def source(self) -> tuple[int, int, int, int, int]:
        return (self.page, self.u0, self.v0, *self.walk)

    def scale(self, axis: str) -> float:
        return model_scale(self.iu if axis == "u" else self.iv)

    def steps(self, axis: str) -> int:
        return self.steps_u if axis == "u" else self.steps_v

    def ends(self, axis: str) -> tuple[int, int]:
        return self.x if axis == "u" else self.y

    def inside(self) -> bool:
        """Strictly inside the clip window on both axes, so no edge can have shortened it."""
        return all(1 <= v <= 334 for v in self.x) and all(1 <= v <= 254 for v in self.y)


def read_rows(path: Path) -> list[list[str]]:
    with lzma.open(path, "rt", encoding="utf-8") as f:
        return [line.split() for line in f if line.strip()]


def words(hexwords: str) -> list[int]:
    return [int(hexwords[i : i + 4], 16) for i in range(0, len(hexwords), 4)]


@dataclass
class Capture:
    rows: int
    fires: int
    excluded: Counter[str]
    kept: list[Blit]


class InvalidRunError(Exception):
    """An input missing or an instrument that examined nothing: the run answers 3, not a verdict."""


def load_capture(block: Path | None = None, cliprect: Path | None = None) -> Capture:
    """Every fire that reads its source and does not write index 0, with its clip rectangle."""
    block, cliprect = block or BLOCK, cliprect or CLIPRECT
    rects = {int(t[1]): tuple(words(t[6])) for t in read_rows(cliprect)}
    rows = read_rows(block)
    fires, excluded, kept = 0, Counter[str](), []
    for _, n, frame, pc, data, _mask, hexwords in rows:
        if int(data, 16) != FIRE:
            continue
        fires += 1
        w = words(hexwords)
        page = w[6] >> 10
        if not w[7] & 4:
            excluded["no source read"] += 1
            continue
        if w[7] & 8:
            excluded["writes index 0 (a colour fill)"] += 1
            continue
        if page >= DIRECT_PAGE:
            excluded["direct-write page"] += 1
            continue
        x0 = (w[0] & 0xFF) + (256 if w[7] & 0x40 else 0)
        x1 = (w[1] & 0xFF) + (256 if w[9] & 4 else 0)
        y0 = (w[2] & 0xFF) + (256 if w[7] & 0x80 else 0)
        y1 = (w[3] & 0xFF) + (256 if w[9] & 8 else 0)
        iu, iv = indices(w)
        r = rects[int(n)]
        kept.append(
            Blit(
                row=int(n),
                frame=int(frame),
                pc=int(pc, 16),
                iu=iu,
                iv=iv,
                x=(x0, x1),
                y=(y0, y1),
                steps_u=((x1 - x0) * (1 if w[7] & 1 else -1)) & 0x1FF,
                steps_v=((y1 - y0) * (1 if w[7] & 2 else -1)) & 0x1FF,
                page=page,
                u0=(w[0] >> 8) + (256 if w[6] & 0x100 else 0),
                v0=(w[2] >> 8) + (256 if w[6] & 0x200 else 0),
                walk=(w[8] & 0xC000, w[7] & 3),
                rect=(r[0], r[1], r[2], r[3]),
            )
        )
    return Capture(len(rows), fires, excluded, kept)


@dataclass(frozen=True)
class Measurement:
    axis: str
    group: tuple[int, ...]
    blit: Blit


def tested(blits: Iterable[Blit]) -> list[Measurement]:
    """Every axis measurement of a group showing at least MIN_SCALES scales on that axis."""
    groups: dict[tuple[int, ...], list[Blit]] = defaultdict(list)
    for b in blits:
        groups[b.source].append(b)
    out = []
    for axis in ("u", "v"):
        for key, g in groups.items():
            if len({round(b.scale(axis), 6) for b in g}) >= MIN_SCALES:
                out += [Measurement(axis, key, b) for b in g]
    return out


def score(ms: list[Measurement], scale_of: Callable[[int], float]) -> list[bool]:
    """Hit or miss per measurement, the native span estimated per group from `scale_of`."""
    per_group: dict[tuple[str, tuple[int, ...]], list[int]] = defaultdict(list)
    for i, m in enumerate(ms):
        per_group[(m.axis, m.group)].append(i)
    hit = [False] * len(ms)
    for idx in per_group.values():
        native = statistics.median(ms[i].blit.steps(ms[i].axis) * 100 / scale_of(i) for i in idx)
        for i in idx:
            predicted = native * scale_of(i) / 100
            hit[i] = abs(ms[i].blit.steps(ms[i].axis) - predicted) <= 1 + 0.01 * predicted
    return hit


def shuffled_scores(ms: list[Measurement]) -> list[int]:
    """Hits with the true scales permuted among the same measurements, per axis, one per seed."""
    out = []
    for seed in range(SHUFFLE_SEEDS):
        rnd, perm = random.Random(seed), dict[int, float]()
        for axis in ("u", "v"):
            ids = [i for i, m in enumerate(ms) if m.axis == axis]
            vals = [ms[i].blit.scale(axis) for i in ids]
            rnd.shuffle(vals)
            perm.update(zip(ids, vals, strict=True))
        out.append(sum(score(ms, perm.__getitem__)))
    return out


def on_edge(m: Measurement) -> bool:
    return any(e in EDGES[m.axis] for e in m.blit.ends(m.axis))


def first_ground_row(png: Path, x: int = 5, ground_y: int = 245) -> int:
    """The first row at column `x` holding the colour of the ground pixel below it."""
    from PIL import Image

    with Image.open(png) as im:
        rgb = im.convert("RGB")
        ground = rgb.getpixel((x, ground_y))
        return next(y for y in range(rgb.height) if rgb.getpixel((x, y)) == ground)


def law_report(cap: Capture) -> list[str]:
    """Everything the evidence alone answers."""
    blits = cap.kept
    scaled_blits = [b for b in blits if b.scale("u") != 100 or b.scale("v") != 100]
    undecodable = [b for b in blits if not all(25 <= b.scale(a) < 400 for a in "uv")]
    ms = tested(blits)
    if not ms:
        raise InvalidRunError(f"no group shows {MIN_SCALES} scales on an axis: nothing was scored")
    true_scale = [m.blit.scale(m.axis) for m in ms]
    model = score(ms, true_scale.__getitem__)
    identity = score(ms, lambda _: 100.0)
    shuffled = shuffled_scores(ms)
    scaled = [i for i, s in enumerate(true_scale) if s != 100]
    inside = [i for i in scaled if ms[i].blit.inside()]

    def hits(h: list[bool], sub: list[int]) -> int:
        return sum(h[i] for i in sub)

    every = list(range(len(ms)))
    # The criterion written before the run: each control at most half of what the model hits.
    if max(hits(identity, every), max(shuffled)) * 2 > hits(model, every):
        raise InvalidRunError(
            "a control hits more than half of what the model does: the law is not shown"
        )
    misses = [i for i in every if not model[i]]
    scaled_set = set(scaled)
    inside_misses = [i for i in inside if not model[i]]
    rects = Counter(b.rect for b in blits)
    edge_misses = [ms[i] for i in misses if on_edge(ms[i])]
    bottom = sorted(m.blit.frame for m in edge_misses if m.axis == "v" and m.blit.y[1] == 256)
    car = [m.blit for m in edge_misses if m.axis == "u" and m.blit.frame in CAR_SCREEN]
    at_336 = [b for b in car if b.x[1] == 336]
    lines = [
        f"capture: {cap.rows} rows, {cap.fires} fires, {len(blits)} kept "
        f"(excluded: {dict(cap.excluded)})",
        f"decode: {len(undecodable)} undecodable; {len(scaled_blits)} scaled blits, written by "
        f"{sorted(hex(p) for p in {b.pc for b in scaled_blits})}",
        f"tested: {len(ms)} axis measurements ({len(scaled)} scaled) in "
        f"{len({(m.axis, m.group) for m in ms})} groups",
        f"model:    {hits(model, every)} of {len(ms)}, scaled {hits(model, scaled)} of "
        f"{len(scaled)}, strictly inside {hits(model, inside)} of {len(inside)}",
        f"identity: {hits(identity, every)}, scaled {hits(identity, scaled)}, strictly inside "
        f"{hits(identity, inside)}; half the model minus the identity: "
        f"{hits(model, every) // 2 - hits(identity, every)}",
        f"shuffled: mean {statistics.mean(shuffled):.0f}, max {max(shuffled)} over "
        f"{SHUFFLE_SEEDS} seeds",
        f"misses: {len(misses)}, {sum(1 for i in misses if i in scaled_set)} of them scaled, "
        f"{len(edge_misses)} with an endpoint on a clip edge",
        f"  vertical misses ending on the bottom clip row 256, by frame: {bottom}",
        f"  car screen, horizontal misses: {len(car)}, {sum(b.x[1] == 0 for b in car)} ending "
        f"at x 0 and {len(at_336)} at x 336, whose spans are {sorted({b.steps_u for b in at_336})}"
        f" columns while their scale climbs {min((b.scale('u') for b in at_336), default=0):.0f}"
        f"..{max((b.scale('u') for b in at_336), default=0):.0f}",
        f"residue strictly inside: {len(inside_misses)} misses from "
        f"{len({ms[i].group for i in inside_misses})} sources, "
        f"{sum(1 for i in inside_misses if ms[i].axis == 'v')} vertical, "
        f"{sum(1 for i in inside_misses if ms[i].blit.y[1] in CUT_ROWS)} ending at y1 "
        f"{CUT_ROWS[0]} or {CUT_ROWS[1]}",
        f"clip rectangle (xmin, ymin, xmax, ymax) at the fire: {dict(rects)}",
    ]
    for f in FRAMES:
        lines.append(f"frame {f}: first ground row at x 5 is {first_ground_row(frame_png(f))}")
    return lines


def frame_png(frame: int) -> Path:
    return EVIDENCE / f"f{frame}.png"


# ---- --full: the driver's table, the ROM descriptors and the graphics


def zoom_index(driver: Path = DRIVER) -> list[int]:
    declaration = "static constexpr uint16_t ZOOM_INDEX[400] ="
    parts = driver.read_text(encoding="utf-8").split(declaration, 1)
    if len(parts) != 2:
        raise InvalidRunError(f"{driver.name} declares no ZOOM_INDEX[400]")
    body = parts[1]
    vals = [int(v, 16) for v in re.findall(r"0x[0-9a-fA-F]{4}", body.split("};", 1)[0])]
    if len(vals) != 400:
        raise InvalidRunError(f"ZOOM_INDEX holds {len(vals)} values, not 400")
    return vals


def descriptors(zi: list[int]) -> dict[int, list[int]]:
    """Each distinct index the table holds and its percentages; 0 is a hole below 25 but 100."""
    out: dict[int, list[int]] = {}
    for j, v in enumerate(zi):
        if v or j == 100:
            out.setdefault(v, []).append(j)
    return out


class Rom:
    """The main cpu image, read as the 68000 reads it."""

    def __init__(self, data: bytes) -> None:
        self.data = data

    def w(self, a: int) -> int:
        value: int = struct.unpack_from(">H", self.data, a & (len(self.data) - 2))[0]
        return value

    def s16(self, a: int) -> int:
        v = self.w(a)
        return v - 0x10000 if v & 0x8000 else v

    def scale_from(self, base: int, j: int, x: int) -> int:
        """The driver's scale_from: destination x through descriptor j of the table at base."""
        d = base + j * 16
        shift = self.w(d + 6)
        ta = (self.w(d + 8) << 16) | self.w(d + 10)
        tb = (self.w(d + 12) << 16) | self.w(d + 14)
        v = (2 * x + self.s16(ta + 2 * x)) & 0xFFFF
        v = (v - self.s16(tb + v)) & 0xFFFF
        return v >> shift

    def descriptor_tables(self) -> list[int]:
        """The two tables, found the driver's way: descriptor 100 is the identity, 200 doubles."""
        found = []
        for off in range(0, len(self.data) - 6400 + 1, 2):
            d = off + 1600
            a = (self.w(d + 8) << 16) | self.w(d + 10)
            b = (self.w(d + 12) << 16) | self.w(d + 14)
            if a != b or a == 0 or a >= len(self.data) or self.w(d + 6) > 8:
                continue
            if all(
                self.scale_from(off, 100, x) == x and self.scale_from(off, 200, x) == 2 * x
                for x in range(256)
            ):
                found.append(off)
                if len(found) == 2:
                    break
        if len(found) != 2:
            raise InvalidRunError(f"{len(found)} descriptor tables found, not 2")
        return found


def known_answer(zi: list[int], rom: Rom, bases: list[int]) -> list[str]:
    lines = [f"descriptor tables: {[hex(b) for b in bases]}"]
    for axis, base in enumerate(bases):
        errs = {
            v: max(abs(model_scale(v) - 100.0 * rom.scale_from(base, j, 255) / 255) for j in js)
            for v, js in descriptors(zi).items()
        }
        worst = max(errs, key=errs.__getitem__)
        over = sum(1 for e in errs.values() if e > 1)
        lines.append(
            f"known answer, axis {axis}: {len(errs)} descriptors, worst |model - real| "
            f"{errs[worst]:.3f} at {worst:#x}, over 1 point: {over}"
        )
    return lines


class Coverage:
    """Which source rows a blit reads under the driver's exact law, against its opaque rows."""

    def __init__(self, zi: list[int], rom: Rom, bases: list[int], gfx: bytes) -> None:
        self.table = {v: j for j, v in enumerate(zi)}  # the driver's m_zoom_table: last j wins
        self.rom, self.bases, self.gfx = rom, bases, gfx

    def percent(self, index: int) -> int:
        """The driver's get_scale: the first index at or above this one the table holds."""
        while index < (1 << 14):
            if index in self.table:
                return self.table[index]
            index += 1
        return 0

    def pixel(self, page: int, u: int, v: int) -> int:
        a = (page * 512 * 512 + (v & 0x1FF) * 512 + (u & 0x1FF)) & (GFX_REGION - 1)
        return self.gfx[a] if a < len(self.gfx) else 0

    def reads(self, axis: int, j: int, steps: int, inclusive: bool) -> list[int]:
        # the driver's loops are do-whiles: the first row is drawn whatever the step count
        last = max(steps if inclusive else steps - 1, 0)
        if j == 100:
            # the 1:1 blit samples one source row further in on the vertical axis
            return [s + (1 if axis == 1 else 0) for s in range(last + 1)]
        inverse, x = [], 0
        for d in range(last + 1):
            while x < 511 and self.rom.scale_from(self.bases[axis], j, x) < d:
                x += 1
            inverse.append(x)
        return inverse

    def rows_read(self, b: Blit, steps_v: int | None = None) -> tuple[list[int], list[int]]:
        ju, jv = self.percent(b.iu), self.percent(b.iv)
        inclusive = ju == 100 and jv == 100
        sv = b.steps_v if steps_v is None else steps_v
        return self.reads(0, ju, b.steps_u, inclusive), self.reads(1, jv, sv, inclusive)

    def opaque(self, b: Blit, us: list[int], vs: Iterable[int]) -> int:
        du = 1 if b.walk[0] & 0x4000 else -1
        dv = 1 if b.walk[0] & 0x8000 else -1
        return sum(
            1 for v in vs for u in set(us) if self.pixel(b.page, b.u0 + du * u, b.v0 + dv * v)
        )


def coverage_report(cov: Coverage, blits: list[Blit]) -> list[str]:
    blits = [b for b in blits if cov.percent(b.iu) and cov.percent(b.iv)]
    ms = tested(blits)
    model = score(ms, lambda i: ms[i].blit.scale(ms[i].axis))
    misses = {
        ms[i].blit.row
        for i in range(len(ms))
        if not model[i] and ms[i].blit.scale(ms[i].axis) != 100 and ms[i].blit.inside()
    }
    if not misses:
        raise InvalidRunError("no miss strictly inside the window to classify")
    groups: dict[tuple[int, ...], list[Blit]] = defaultdict(list)
    for b in blits:
        groups[b.source].append(b)
    sources = {b.source for b in blits if b.row in misses}

    def deepest(g: list[Blit]) -> int:
        return max((max(vs) for vs in (cov.rows_read(b)[1] for b in g) if vs), default=0)

    left_out: dict[str, Counter[int]] = {"miss": Counter(), "other": Counter()}
    ends: Counter[int] = Counter()
    planted = caught = 0
    for src in sources:
        g = groups[src]
        deep = deepest(g)
        for b in g:
            us, vs = cov.rows_read(b)
            n = deep - max(vs)
            left_out["miss" if b.row in misses else "other"][n] += 1
            if n >= 2 and cov.opaque(b, us, range(max(vs) + 1, deep + 1)):
                ends[b.y[1]] += 1
        others = [b for b in g if b.row not in misses and b.steps_v >= 6]
        if others:
            b = max(others, key=lambda q: q.steps_v)
            own = max(cov.rows_read(b)[1])
            us, vs = cov.rows_read(b, steps_v=b.steps_v * 2 // 3)
            planted += 1
            caught += cov.opaque(b, us, range(max(vs) + 1, own + 1)) > 0
    if not planted or caught < planted:
        raise InvalidRunError(
            f"the planted truncation was caught {caught} of {planted}: the instrument is blind"
        )
    miss_left = left_out["miss"]
    other = left_out["other"]
    at = {
        "the cut row": sum(ends[r] for r in CUT_ROWS),
        "the cut row on the other page": sum(ends[r] for r in CUT_ROWS_OTHER_PAGE),
        "a page bottom": sum(ends[r] for r in PAGE_BOTTOMS),
    }
    elsewhere = sum(ends.values()) - sum(at.values())
    return [
        f"coverage: {len(misses)} misses from {len(sources)} sources; rows left out per miss "
        f"{min(miss_left)}..{max(miss_left)}",
        f"  the other {sum(other.values())} blits of those sources: "
        f"{other[0] + other[1]} leave 0 or 1 rows out",
        f"  CONTROL planted truncation (a third cut off): caught {caught} of {planted}",
        "  truncated blits leaving opaque rows out end at: "
        + ", ".join(f"{where} {n}" for where, n in at.items())
        + f", elsewhere {elsewhere}, of {sum(ends.values())}",
    ]


def full_report(blits: list[Blit]) -> list[str]:
    missing = [p for p in (DRIVER, MAINCPU, ROMSET) if not p.exists()]
    if missing:
        names = ", ".join(str(p.relative_to(ROOT)) for p in missing)
        raise InvalidRunError(f"--full needs {names} (make setup, then make disasm)")
    zi = zoom_index()
    rom = Rom(MAINCPU.read_bytes())
    bases = rom.descriptor_tables()
    with zipfile.ZipFile(ROMSET) as z:
        absent = sorted(set(GFX_ROMS) - set(z.namelist()))
        if absent:
            raise InvalidRunError(f"{ROMSET.name} lacks {absent}")
        gfx = b"".join(z.read(n) for n in GFX_ROMS)
    keys = set(descriptors(zi))
    off_table = sum(1 for b in blits if b.iu not in keys or b.iv not in keys)
    lines = known_answer(zi, rom, bases)
    lines.append(
        f"decode: {off_table} kept blits carry an index outside the {len(keys)} descriptors"
    )
    return lines + coverage_report(Coverage(zi, rom, bases, gfx), blits)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--full", action="store_true", help="add the known answer and the coverage")
    args = ap.parse_args(argv)
    missing = [p for p in (BLOCK, CLIPRECT, *map(frame_png, FRAMES)) if not p.exists()]
    if missing:
        print(f"INVALID: the evidence is incomplete: {[str(p) for p in missing]}")
        return 3
    try:
        cap = load_capture()
    except (OSError, EOFError, lzma.LZMAError, ValueError, KeyError) as e:
        print(f"INVALID: the evidence does not read: {e!r}")
        return 3
    if not cap.kept:
        print("INVALID: the capture holds no blit that reads its source")
        return 3
    lines: list[str] = []
    try:
        lines += law_report(cap)
        if args.full:
            lines += full_report(cap.kept)
    except InvalidRunError as e:
        print("\n".join(lines + [f"INVALID: {e}"]))
        return 3
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
