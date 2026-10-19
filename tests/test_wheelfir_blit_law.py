"""The stall-counter law's script: decode and scoring on known answers, then the record's figures.

The record in `hardware/registers.yaml` quotes these figures; the evidence is tracked, so the
figures are asserted here and a change to the decode, the filters or the scoring that moves one
fails before the record and the script can disagree.
"""

from __future__ import annotations

import re

import pytest
from script_loader import load_script

law = load_script("wheelfir_blit_law", "wheelfir-blit-law.py")


@pytest.mark.parametrize(
    "index,scale",
    [
        (0x0000, 100.0),  # both fields idle
        (0x0020, 100.0),  # a stall field of 32 is idle too
        (0x0003, 75.0),  # stall 3: 3 of every 4 cycles write
        (0x0003 << 6, 150.0),  # repeat 3: 3/2
        (0x1000, 50.0),  # clock_halve
        (0x2000, 200.0),  # clock_double
        (0x0003 | (0x0003 << 6), 112.5),  # the product of both
    ],
)
def test_the_law_gives_the_scale_from_the_fields_alone(index: int, scale: float) -> None:
    assert law.model_scale(index) == pytest.approx(scale)


def test_the_decode_places_each_field_where_the_driver_reads_it() -> None:
    w = [0] * 15
    w[0xA] = 0x0300  # stall u = 3
    w[0xB] = 0x0500 | 0x4000  # repeat u = 5, stall v bit 0
    w[0xC] = 0x0200  # repeat v = 2
    w[9] = 0x0002  # clock_halve v
    w[8] = 0x1000  # clock_double u
    iu, iv = law.indices(w)
    assert iu == 3 | (5 << 6) | (1 << 13)
    assert iv == 1 | (2 << 6) | (1 << 12)


@pytest.mark.parametrize(
    "word,value,expected",
    [
        (8, 0x0100, (0x20, 0)),  # x stall field bit 5
        (8, 0x0400, (0x20 << 6, 0)),  # x repeat field bit 5
        (8, 0x0200, (0, 0x20)),  # y stall field bit 5
        (8, 0x0800, (0, 0x20 << 6)),  # y repeat field bit 5
        (0xB, 0x4000, (0, 0x01)),  # y stall field bits 0-1
        (0xB, 0x8000, (0, 0x02)),
        (0xC, 0x4000, (0, 0x04)),  # y stall field bits 2-3
        (0xC, 0x8000, (0, 0x08)),
        (0xA, 0x4000, (0, 0x10)),  # y stall field bit 4
    ],
)
def test_each_bit_of_the_register_map_lands_in_its_own_field(
    word: int, value: int, expected: tuple[int, int]
) -> None:
    w = [0] * 15
    w[word] = value
    assert law.indices(w) == expected


def _blit(row: int, iu: int, steps_u: int) -> object:
    return law.Blit(
        row=row,
        frame=row,
        pc=0,
        iu=iu,
        iv=0,
        x=(10, 10 + steps_u),
        y=(10, 20),
        steps_u=steps_u,
        steps_v=10,
        page=0,
        u0=0,
        v0=0,
        walk=(0, 0),
        rect=(0, 0, 336, 255),
    )


def test_a_group_that_follows_the_law_hits_and_the_identity_does_not() -> None:
    """A 40-column sprite drawn at 100%, 75% and 150% on u: the law predicts every span."""
    blits = [_blit(1, 0x0000, 40), _blit(2, 0x0003, 30), _blit(3, 0x0003 << 6, 60)]
    ms = [m for m in law.tested(blits) if m.axis == "u"]
    assert len(ms) == 3
    model = law.score(ms, lambda i: ms[i].blit.scale("u"))
    identity = law.score(ms, lambda _: 100.0)
    assert all(model) and sum(identity) == 1


def test_a_group_with_fewer_than_three_scales_is_not_tested() -> None:
    blits = [_blit(1, 0x0000, 40), _blit(2, 0x0003, 30)]
    assert law.tested(blits) == []


def test_the_record_figures_come_out_of_the_tracked_evidence() -> None:
    report = "\n".join(law.law_report(law.load_capture()))
    for figure in (
        "capture: 36261 rows, 18131 fires, 16020 kept",
        "decode: 0 undecodable; 1836 scaled blits, written by ['0xe52f0']",
        "tested: 4848 axis measurements (3654 scaled) in 86 groups",
        "model:    4569 of 4848, scaled 3377 of 3654, strictly inside 1609 of 1646",
        "identity: 2206, scaled 1016, strictly inside 474; half the model minus the identity: 78",
        "shuffled: mean 1082, max 1125 over 20 seeds",
        "spans are [180, 183] columns while their scale climbs 139..371",
        "residue strictly inside: 37 misses from 5 sources, 36 vertical, 33 ending at y1 187",
        "at the fire: {(0, 0, 336, 255): 16020}",
        "frame 1331: first ground row at x 5 is 242",
        "frame 1339: first ground row at x 5 is 242",
        "frame 1389: first ground row at x 5 is 242",
    ):
        assert figure in report, f"{figure!r} is not in the report:\n{report}"


def test_the_full_run_reproduces_the_known_answer_and_the_coverage() -> None:
    missing = [p for p in (law.MAINCPU, law.KONGBALL_MAINCPU, law.ROMSET) if not p.exists()]
    if missing:
        pytest.skip(f"--full needs {[str(p.relative_to(law.ROOT)) for p in missing]}")
    report = "\n".join(law.full_report(law.load_capture().kept))
    agree = re.search(r"capture against the tables: (\d+) of (\d+) scaled axis maps", report)
    assert agree and int(agree.group(2)) > 0 and agree.group(1) == agree.group(2), report
    for figure in (
        "known answer, axis 0: 192 descriptors, worst |model - real| 0.759",
        "known answer, axis 1: 192 descriptors, worst |model - real| 0.759",
        "over 1 point: 0",
        "decode: 0 kept blits carry an index outside the 192 descriptors",
        "coverage: 36 misses from 5 sources; rows left out per miss 1..9",
        "the other 577 blits of those sources: 522 leave 0 or 1 rows out",
        "CONTROL planted truncation (a third cut off): caught 5 of 5",
        "the cut row 34, the cut row on the other page 33, a page bottom 7, elsewhere 15, of 89",
    ):
        assert figure in report, f"{figure!r} is not in the report:\n{report}"


def test_the_rom_scale_tables_are_the_counters_and_a_moved_phase_is_not() -> None:
    missing = [p for p in (law.MAINCPU, law.KONGBALL_MAINCPU) if not p.exists()]
    if missing:
        pytest.skip(f"--full needs {[str(p.relative_to(law.ROOT)) for p in missing]}")
    for name, image in (("wheelfir", law.MAINCPU), ("kongball", law.KONGBALL_MAINCPU)):
        lines = law.tables_are_counters(name, law.Rom(image.read_bytes()))
        shared = re.search(r"shift: (\d+) of 400$", lines[0])
        tables = re.search(r"(\d+) reachable descriptors: A (\d+), B (\d+), shift (\d+)$", lines[1])
        control = re.search(r"repeat agrees on (\d+) of the \d+ .* stall on (\d+) of", lines[2])
        assert shared and tables and control, lines
        assert shared.group(1) == "400", lines
        n, *oks = (int(g) for g in tables.groups())
        assert oks == [n, n, n] and control.groups() == ("0", "0"), lines


def test_the_counters_at_75_percent_drop_one_source_column_in_four() -> None:
    """75% is stall 1 with repeat 3: of every four source columns, two land on one column."""
    index = 0x21 | (0x23 << 6)
    assert [law.counter_dest(index, x) for x in range(8)] == [0, 1, 2, 2, 3, 4, 5, 5]
    assert law.identity(0) and law.identity(0x20 | (0x20 << 6))
    assert not law.identity(0x1000) and not law.identity(0x2000)


def test_the_stepped_walk_is_the_first_source_to_reach_each_step_of_the_closed_form() -> None:
    """Every stall and repeat field with every clock bit: the walk inverts the tables' law."""
    for clocks in (0, 0x1000, 0x2000):
        for stall in range(32):
            for repeat in range(32):
                index = stall | (repeat << 6) | clocks
                inverse, x = [], 0
                for d in range(300):
                    while law.counter_dest(index, x) < d:
                        x += 1
                    inverse.append(x)
                assert law.source_walk(index, 299) == inverse, hex(index)
