"""The grammar of an image key in hardware/symbols.yaml, and the renders that follow it.

A key is a comma-separated list of fragments, and a fragment reaches every image whose name
contains it, as SetupTCH.java seeds Ghidra; `common` reaches every image.
"""

from __future__ import annotations

import symbols_model as sm
from image_keys import fragments, images_of, reaches, rows_for
from script_loader import load_script

gen = load_script("gen_hw_docs_keys", "gen-hw-docs.py")

IMAGES = ["radendur_maincpu", "wheelfir_maincpu", "wheelfir_subcpu"]
TABLE = {
    "common": [{"addr": 0, "name": "main_rom"}],
    "wheelfir": [{"addr": 0x400, "name": "w_both"}],
    "radendur_maincpu,wheelfir_maincpu": [{"addr": 0x700000, "name": "blit_data"}],
}


def test_a_fragment_reaches_every_image_that_contains_it() -> None:
    assert fragments(" radendur_maincpu, wheelfir_maincpu ,") == [
        "radendur_maincpu",
        "wheelfir_maincpu",
    ]
    assert reaches("wheelfir", "wheelfir_subcpu")
    assert reaches("common", "radendur_maincpu")
    assert not reaches("wheelfir_maincpu", "wheelfir_subcpu")
    assert images_of("wheelfir", IMAGES) == ["wheelfir_maincpu", "wheelfir_subcpu"]


def test_the_rows_of_an_image_follow_the_grammar() -> None:
    names = [r["name"] for _, r in rows_for(TABLE, "wheelfir_maincpu")]
    assert names == ["main_rom", "w_both", "blit_data"]


def test_the_debugger_file_pairs_as_ghidra_does() -> None:
    out = gen.debugger_symbols_file({"images": TABLE}, "wheelfir_maincpu")
    assert "name: w_both" in out
    assert "name: blit_data" in out


def test_a_fragment_key_gets_the_debugger_files_of_its_images() -> None:
    images = gen.debugger_images({"images": TABLE}, IMAGES)
    assert images == ["radendur_maincpu", "wheelfir_maincpu", "wheelfir_subcpu"]
    assert gen.debugger_images({"images": TABLE}, []) == [
        "radendur_maincpu",
        "wheelfir",
        "wheelfir_maincpu",
    ]


def test_the_ghidra_render_separates_by_image() -> None:
    out = sm.symbols_file(
        {
            "images": {
                "common": [{"addr": 0x4, "name": "vec_reset", "description": "boot"}],
                "wheelfir_maincpu": [{"addr": 0xE5300, "name": "wf_dispatch", "description": "x"}],
            }
        }
    )
    assert "@image *" in out and "@image wheelfir_maincpu" in out
    assert out.index("@image wheelfir_maincpu") < out.index("wf_dispatch")
