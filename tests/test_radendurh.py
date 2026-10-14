"""scripts/radendurh.py: it refuses another dump, each hand-encoded routine decodes to its source
operand for operand, and the built image holds every jsr, routine and fix where the table puts them.
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path
from typing import Any

import pytest
from capstone import (  # type: ignore[import-untyped]
    CS_ARCH_M68K,
    CS_MODE_BIG_ENDIAN,
    CS_MODE_M68K_000,
    Cs,
)
from script_loader import load_script

rh = load_script("radendurh_mod", "radendurh.py")

MD = Cs(CS_ARCH_M68K, CS_MODE_BIG_ENDIAN | CS_MODE_M68K_000)
# The tests that need the dump skip where conftest.py's do: a clone without the romsets.
needs_rom = pytest.mark.skipif(
    not (rh.ROMS / "radendur.zip").exists(),
    reason="no run/mame_roms/radendur.zip: the romsets are not distributed (README)",
)
# An instruction that reads the condition codes another one left (Bcc, Scc, DBcc, the X users).
CC_READERS = re.compile(
    r"^(b(?!ra|sr|tst|set|clr|chg)[a-z]{2}\.|s(?!ub|wap|top)[a-z]{2}\.b|db|addx|subx|negx|rox)"
)


def table() -> dict[str, Any]:
    t: dict[str, Any] = rh.load_table(rh.TABLE)
    return t


def image(roms: dict[str, bytes], t: dict[str, Any]) -> bytes:
    r = t["clone"]["roms"]
    img = bytearray(len(roms[r["even"]]) * 2)
    img[0::2] = roms[r["even"]]
    img[1::2] = roms[r["odd"]]
    return bytes(img)


def hooks_laid_out(t: dict[str, Any]) -> list[tuple[dict[str, Any], int, dict[str, int]]]:
    """(layer, its block's base, its labels), laid out by the generator's own function."""
    out = []
    base = t["hook_base"]
    for layer in t["layers"]:
        labels, block = rh.layout(layer, base)
        out.append((layer, base, labels))
        base += len(block)
    return out


def _source_text(line: str) -> str:
    return re.sub(r"^\.?\w+:\s*", "", line)


def _normalise(op: str) -> str:
    """One spelling for an operand list: capstone's `$201730.l` is the source's `($201730).l`."""
    op = op.replace(" ", "").lower()
    op = re.sub(r"\(\$([0-9a-f]+)\)\.l", r"$\1.l", op)
    return re.sub(r"#\$?([0-9a-f]+)", lambda m: f"#{int(m.group(1), 16):x}", op)


# --- the routines, from the table alone ----------------------------------------------------------


def test_every_routine_decodes_to_its_source() -> None:
    """Mnemonic and operands of every instruction; branch targets are the next test's."""
    checked = 0
    for layer, _, labels in hooks_laid_out(table()):
        for h in layer.get("hooks", []):
            code = rh.words(h["words"])
            ins = list(MD.disasm(code, labels[h["label"]]))
            assert sum(i.size for i in ins) == len(code), h["label"]
            assert len(ins) == len(h["source"]), h["label"]
            for line, i in zip(h["source"], ins, strict=True):
                mnem, _, ops = _source_text(line).partition(" ")
                assert i.mnemonic == re.sub(r"\.s$", ".b", mnem), f"{h['label']}: {line}"
                if mnem.startswith("db"):
                    # the counter register; the target is the branch test's
                    assert i.op_str.split(",")[0] == ops.split(",")[0].strip(), (
                        f"{h['label']}: {line}"
                    )
                elif not mnem.startswith("b"):
                    # the source writes immediates in decimal unless they carry a `$`
                    want = re.sub(r"#(\d+)\b", lambda m: f"#${int(m.group(1)):x}", ops.strip())
                    assert _normalise(i.op_str) == _normalise(want), f"{h['label']}: {line}"
                checked += 1
    assert checked > 0, "no instruction was examined"


def test_branches_land_on_their_labels() -> None:
    """Every branch capstone decodes lands on the label its source line names."""
    checked = decoded = 0
    for layer, _, labels in hooks_laid_out(table()):
        for h in layer.get("hooks", []):
            ins = list(MD.disasm(rh.words(h["words"]), labels[h["label"]]))
            local = {
                m.group(1): i.address
                for line, i in zip(h["source"], ins, strict=True)
                if (m := re.match(r"^(\.\w+):", line))
            }
            for line, i in zip(h["source"], ins, strict=True):
                if not re.match(r"^(b(?!tst|set|clr|chg)|db)", i.mnemonic):
                    continue
                decoded += 1
                name = _source_text(line).split()[-1].split(",")[-1]
                want = local.get(name, labels.get(name))
                assert want is not None, f"{h['label']}: {line} names no label"
                assert int(i.op_str.split("$")[-1], 16) == want, f"{h['label']}: {line}"
                checked += 1
    assert decoded > 0 and checked == decoded


def test_every_routine_ends_or_falls_into_the_next() -> None:
    for layer in table()["layers"]:
        hooks = layer.get("hooks", [])
        for k, h in enumerate(hooks):
            last = list(MD.disasm(rh.words(h["words"]), 0))[-1].mnemonic
            if "falls_into" in h:
                assert k + 1 < len(hooks) and hooks[k + 1]["label"] == h["falls_into"], h["label"]
            else:
                assert last in ("rts", "bra.b", "bra.w", "jmp"), f"{h['label']} ends in {last}"


# --- what the generator refuses ------------------------------------------------------------------


@needs_rom
def test_another_dump_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    good = rh.ROMS / "radendur.zip"
    for rom in ("endu.u21", "endu.u19"):
        bad = tmp_path / rom / "radendur.zip"
        bad.parent.mkdir()
        with zipfile.ZipFile(good) as zin, zipfile.ZipFile(bad, "w") as zout:
            for n in zin.namelist():
                data = bytearray(zin.read(n))
                if n == rom:
                    data[0x1000] ^= 0xFF
                zout.writestr(n, bytes(data))
        monkeypatch.setattr(rh, "ROMS", bad.parent)
        with pytest.raises(rh.InvalidError, match=f"{re.escape(rom)} sha1"):
            rh.build(table(), None)


# --- the built image ---------------------------------------------------------------------------


@needs_rom
def test_the_image_holds_what_the_table_says() -> None:
    t = table()
    img = image(rh.build(t, None)[0], t)
    checked = 0
    for layer, base, labels in hooks_laid_out(t):
        _, block = rh.layout(layer, base)
        assert img[base : base + len(block)] == block, layer["name"]
        for w in layer.get("words", []):
            new = rh.words(w["new"])
            assert img[w["addr"] : w["addr"] + len(new)] == new, w["why"]
            checked += 1
        for s in layer.get("sites", []):
            for at in s["at"]:
                ins = list(MD.disasm(img[at : at + len(rh.words(s["old"]))], at))
                target = int(ins[0].op_str.lstrip("$").split(".")[0], 16)
                assert ins[0].mnemonic == "jsr" and target == labels[s["hook"]], f"{at:06x}"
                assert all(i.mnemonic == "nop" for i in ins[1:]), f"{s['hook']} at {at:06x}"
                checked += 1
    assert checked > 0


@needs_rom
def test_condition_codes_are_read_only_after_a_site_that_sets_them() -> None:
    """A routine leaves its own flags, not the replaced instruction's: only a site marked
    sets_flags may be followed by an instruction that reads them."""
    t = table()
    dump = bytes(rh.load_image(t))
    checked = 0
    for layer in t["layers"]:
        for s in layer.get("sites", []):
            for at in s["at"]:
                after = at + len(rh.words(s["old"]))
                nxt = next(MD.disasm(dump[after : after + 10], after))
                reads = bool(CC_READERS.match(nxt.mnemonic))
                assert reads == bool(s.get("sets_flags")), f"{at:06x} then {nxt.mnemonic}"
                checked += 1
    assert checked > 0


def _target(ins: Any) -> int:
    return int(ins.op_str.lstrip("$").split(".")[0], 16)


def test_a_stand_in_reaches_the_drawer_its_sites_called() -> None:
    """A hook that replaces a call, ending in jmp or making a single jsr and returning, reaches the
    address every site it replaces called; a call site whose hook is neither fails."""
    checked = 0
    for layer in table()["layers"]:
        ends = {}
        for h in layer.get("hooks", []):
            ins = list(MD.disasm(rh.words(h["words"]), 0))
            calls = [i for i in ins if i.mnemonic == "jsr"]
            if ins[-1].mnemonic == "jmp":
                ends[h["label"]] = _target(ins[-1])
            elif ins[-1].mnemonic == "rts" and len(calls) == 1:
                ends[h["label"]] = _target(calls[0])
        for site in layer.get("sites", []):
            if site["old"][0] == rh.JSR_ABS_L:
                assert site["hook"] in ends, f"{site['hook']} replaces a call and reaches no drawer"
            if site["hook"] in ends:
                called = (site["old"][1] << 16) | site["old"][2]
                assert site["old"][0] == rh.JSR_ABS_L and called == ends[site["hook"]], site
                checked += 1
    assert checked > 0, "no stub was examined"


@needs_rom
def test_a_stage_differs_from_the_full_build_only_where_later_layers_write() -> None:
    t = table()
    first = image(rh.build(t, t["layers"][0]["name"])[0], t)
    full = image(rh.build(t, None)[0], t)
    later: set[int] = set()
    for layer, base, _ in hooks_laid_out(t)[1:]:
        later.update(range(base, base + len(rh.layout(layer, base)[1])))
        for site in layer.get("sites", []):
            for at in site["at"]:
                later.update(range(at, at + 2 * len(site["old"])))
        for word in layer.get("words", []):
            later.update(range(word["addr"], word["addr"] + 2 * len(word["new"])))
    changed = {i for i in range(len(full)) if first[i] != full[i]}
    assert changed and changed <= later


@needs_rom
def test_the_build_is_reproducible() -> None:
    a, _ = rh.build(table(), None)
    b, _ = rh.build(table(), None)
    assert a and rh.zipped(a) == rh.zipped(b)
