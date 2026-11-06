"""`.scry/`: the seven run recipes this repository declares, each one complete, and the paths it
names written the way the server resolves them."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

STORE = Path(__file__).resolve().parents[1] / ".scry"
START = STORE / "start"
RECIPES = ("kongball", "pwball", "radendur", "radendurh", "rltennis", "rltennisa", "wheelfir")
#: `start`'s arguments a profile may name; the server refuses an unknown key at boot, and an
#: argument it does not take never belongs in a tracked recipe.
KEYS = frozenset(
    {
        "binary",
        "system",
        "rompath",
        "inipath",
        "reference_rom",
        "reference_addr",
        "reference_base",
        "symbols",
        "bases",
        "boot_seconds",
        "cfg",
        "display",
        "size",
        "background",
        "boot_lua",
        "env",
        "state_dir",
        "throttle_from_frame",
        "types",
        "presence",
        "shared",
        "stub_port",
        "view",
    }
)
#: What a path value starts with: the store's one base, so the file reads the same on any host.
BASE = "${root}/"


def _recipe(name: str) -> dict[str, Any]:
    doc: dict[str, Any] = json.loads((START / f"{name}.json").read_text(encoding="utf-8"))
    return doc


def test_the_store_holds_exactly_the_seven_recipes() -> None:
    assert sorted(p.stem for p in START.glob("*.json")) == list(RECIPES)


@pytest.mark.parametrize("name", RECIPES)
def test_each_recipe_is_a_complete_start_profile(name: str) -> None:
    doc = _recipe(name)
    assert doc.pop("format") == "scry-start/1"
    assert set(doc) <= KEYS
    assert doc["system"] == name
    for key in ("binary", "rompath", "inipath", "symbols", "reference_rom", "boot_seconds"):
        assert key in doc, f"{name} cannot boot alone: no {key}"
    for key, value in doc.items():
        if key in ("binary", "rompath", "inipath", "reference_rom", "symbols"):
            assert isinstance(value, str) and value.startswith(BASE), f"{name}.{key}={value!r}"


@pytest.mark.parametrize("name", RECIPES)
def test_the_known_answer_is_the_rom_the_recipe_runs(name: str) -> None:
    doc = _recipe(name)
    if name == "radendurh":
        assert doc["reference_rom"] == f"{BASE}run/mame_roms/radendurh_maincpu.bin", (
            "the clone's reference is the flat image its build writes, never the dump's"
        )
        assert doc["reference_addr"] != "0x0", "the vector table is what the patch never touches"
    else:
        assert doc["reference_rom"] == f"{BASE}disasm/img/{name}_maincpu.bin"
