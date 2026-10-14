#!/usr/bin/env python3
"""gen-hw-docs.py -- validates hardware/*.yaml and projects it onto the documentation.

`hardware/registers.yaml` is the data and the Markdown under `docs/boards/` its render. The schema
is validated first: a fact marked confirmed needs its evidence, a refutation the symptom that
refuted it (so the same reading is not refuted again), a measurement the machine it was taken on,
and `polarity` is its own field because a mechanism can be right with its sense inverted. Then the
marked blocks of the Markdown are written, and the prose around them is left alone. The block
markers are the key `verify-docs.py` reads as well.

Use:
    uv run scripts/gen-hw-docs.py           writes the blocks
    uv run scripts/gen-hw-docs.py --check   writes nothing: fails if anything is out of sync

`make check` runs --check, so the documentation and the data cannot drift apart unnoticed.
"""

import argparse
import pathlib
import re
import sys

import doc_blocks
import yaml
from image_keys import COMMON, rows_for
from memory_map import BLITTER_LAST, BLITTER_START
from symbols_model import (
    IMAGES,
    debugger_images,
    debugger_symbols_file,
    flatten,
    symbols_file,
    validate_symbols,
)

ROOT = pathlib.Path(__file__).resolve().parent.parent
# the hardware documentation lives inside its board's page
BOARD = ROOT / "docs" / "boards" / "wheels-and-fire-board.md"
RLTENNIS_BOARD = ROOT / "docs" / "boards" / "reality-tennis.md"
# The detail (evidence, per-machine measurements and refuted readings) is not rendered: it is far
# larger than what the hardware does, and it is read where it is written, in the YAML, so the
# board's page can be what is asked of it: what each register does.
SOURCE = ROOT / "hardware" / "registers.yaml"
# The blitter command's positions have one owner, `gfx.yaml`: a bit of `registers.yaml` that is a
# field of the command names it with `field:`, and its mask is derived from there.
GFX = ROOT / "hardware" / "gfx.yaml"
GFX_COMMAND = "blit"
SYMBOLS = ROOT / "hardware" / "symbols.yaml"
ACCESSES = ROOT / "hardware" / "accesses.yaml"
DISASSEMBLY = ROOT / "docs" / "disassembly.md"
ANALYSIS = ROOT / "disasm" / "analysis.txt"


# Every `observed` key starts with the set it was measured on (the games behave differently, and
# Reality Tennis is another board), then the topic after an underscore.
MACHINES = ("wheelfir", "pwball", "kongball", "radendurh", "radendur", "rltennis", "rltennisa")


def _split_key(key):
    """Splits `wheelfir_destination` into ('wheelfir', 'destination'), or None if it names none."""
    for m in MACHINES:
        if key == m:
            return m, ""
        if key.startswith(m + "_"):
            return m, key[len(m) + 1 :].replace("_", " ")
    return None


# the schema keys a YAML block scalar can swallow when indented one level too deep
SWALLOWABLE_KEYS = ("evidence", "observed", "refuted")


def load_registers():
    """`registers.yaml` with every bit that names a `field` given the mask `gfx.yaml` holds for
    it, and the problems met doing so (`resolve_fields`)."""
    data = yaml.safe_load(SOURCE.read_text(encoding="utf-8"))
    return data, resolve_fields(data, yaml.safe_load(GFX.read_text(encoding="utf-8")))


def resolve_fields(data, gfx):
    """Gives each blitter bit that names a `field` its mask: the one part of that field (or
    flag) of `gfx.yaml`'s command that sits on the bit's word. A bit with both a mask and a
    field, with neither, naming one that is both a field and a flag, or naming a field with no
    single part on its word is a problem, never a guess."""
    failures = []
    cmd = ((gfx or {}).get("commands") or {}).get(GFX_COMMAND) or {}
    fields, flags = cmd.get("fields") or {}, cmd.get("flags") or {}
    named = {**fields, **flags}
    both = set(fields) & set(flags)
    for reg in data.get("blitter", {}).get("registers", []):
        for bit in reg.get("bits", []) or []:
            where = f"register {reg['word']} bit {bit.get('name', '?')}"
            if "field" not in bit:
                if "mask" not in bit:
                    failures.append(f"{where}: neither a mask nor a field")
                continue
            if "mask" in bit:
                failures.append(f"{where}: both a mask and a field; gfx.yaml owns the position")
                continue
            if bit["field"] in both:
                failures.append(
                    f"{where}: {bit['field']!r} is both a field and a flag of gfx.yaml's "
                    f"command {GFX_COMMAND!r}, so it has two positions"
                )
                continue
            parts = [
                p
                for p in (named.get(bit["field"]) or {}).get("parts", [])
                if p.get("word") == reg["word"]
            ]
            if len(parts) != 1:
                failures.append(
                    f"{where}: field {bit['field']!r} has {len(parts)} part(s) on word "
                    f"{reg['word']} in gfx.yaml's command {GFX_COMMAND!r}, and a bit takes one"
                )
                continue
            bit["mask"] = parts[0]["mask"]
    return failures


def validate(data):
    """Returns the list of schema problems. Empty = everything is correct."""
    failures = []

    def check_item(item, where):
        state_ = item.get("state")
        if state_ == "confirmed" and not item.get("evidence"):
            failures.append(f"{where}: marked confirmed and carrying no evidence")
        if state_ not in (None, "confirmed", "open", "refuted"):
            failures.append(f"{where}: unknown state '{state_}'")
        refuted = item.get("refuted", [])
        if not isinstance(refuted, list):
            failures.append(f"{where}: 'refuted' is not a list of {{read, symptom}}")
            refuted = []
        for r in refuted:
            if not isinstance(r, dict):
                failures.append(
                    f"{where}: a refutation that is not a mapping of {{read, symptom}}: {r!r}"
                )
                continue
            if not r.get("symptom"):
                failures.append(f"{where}: refutation '{r.get('read')}' with no symptom")
            if not r.get("read"):
                failures.append(f"{where}: refutation with no reading")
        observed = item.get("observed") or {}
        if not isinstance(observed, dict):
            failures.append(f"{where}: 'observed' is not a mapping of machine to measurement")
            observed = {}
        for key in observed:
            if not isinstance(key, str) or _split_key(key) is None:
                failures.append(
                    f"{where}: what is observed in '{key}' does not say the machine; "
                    f"the key starts with one of {', '.join(MACHINES)}"
                )
        # A block scalar SWALLOWS whatever follows it with deeper indentation, in silence and with
        # no YAML error: a whole `observed:` can end up inside the text of `evidence`, so its
        # measurements and their machines stop existing as data. The fingerprint is unmistakable.
        swallowed = re.compile(rf"\b({'|'.join(SWALLOWABLE_KEYS)}): >-")
        for field, text in item.items():
            if isinstance(text, str) and swallowed.search(text):
                failures.append(
                    f"{where}: the text of '{field}' has swallowed schema keys; "
                    f"check the block indentation"
                )

    for reg in data.get("blitter", {}).get("registers", []):
        where_reg = f"register {reg['word']}"
        # the register itself too: a word used whole (the trigger, word 14) has no bits to carry it
        check_item(reg, where_reg)
        seen = set()
        for bit in reg.get("bits", []):
            m = bit.get("mask")
            if m is None:
                # resolve_fields has already said why it has none; its schema is still checked
                check_item(bit, f"{where_reg} bit ({bit.get('name', '?')})")
                continue
            if m in seen:
                failures.append(f"{where_reg}: mask {m:#06x} repeated")
            seen.add(m)
            check_item(bit, f"{where_reg} bit {m:#06x} ({bit.get('name', '?')})")

    for port in data.get("ports", []):
        if "address" in port:
            where_port = f"port {port['address']:#08x}"
        else:
            where_port = f"port {port.get('name', '?')}"
            failures.append(f"{where_port}: no address")
        check_item(port, where_port)
        seen = set()
        for bit in port.get("bits", []):
            m = bit.get("mask")
            if m is None:
                # a port bit has no `field` to take one from, so a missing mask is the problem
                failures.append(f"{where_port} bit ({bit.get('name', '?')}): no mask")
                check_item(bit, f"{where_port} bit ({bit.get('name', '?')})")
                continue
            if m in seen:
                failures.append(f"{where_port}: mask {m:#06x} repeated")
            seen.add(m)
            check_item(bit, f"{where_port} bit {m:#06x} ({bit.get('name', '?')})")

    for entry in data.get("memory", []):
        check_item(entry, f"memory {entry.get('name', '?')}")

    video = data.get("video", {})
    if "window" in video:
        check_item(video["window"], "video.window")
    return failures


def disasm_table(accesses, symbols):
    """The findings table of `docs/disassembly.md`, DERIVED rather than written by hand.

    Written by hand, all three columns go stale at once, and a public document then contradicts the
    canonical data of the same repository, which is the failure this project hunts.

    The three columns come from different places and not one of them is typed: the boot PC from
    BYTES 4..8 of the image itself (the 68000's reset vector), the function count from
    `disasm/analysis.txt` (written by the Ghidra pass) and the accesses from
    `hardware/accesses.yaml`.
    """
    functions = {}
    if ANALYSIS.exists():
        for line in ANALYSIS.read_text(encoding="utf-8").splitlines():
            m = re.match(r"#\s*(\S+)\.bin\s+functions:\s*(\d+)", line)  # `analysis.txt`'s own key
            if m:
                functions[m.group(1)] = int(m.group(2))

    rows = []
    for image in sorted((accesses or {}).get("images", {})):
        if not image.endswith("_maincpu"):
            continue  # the table is about the main programs
        bin_ = IMAGES / f"{image}.bin"
        if not bin_.exists():
            continue
        data = bin_.read_bytes()
        reset = int.from_bytes(data[4:8], "big")
        blitter = sum(
            e["refs"]
            for e in accesses["images"][image]["accesses"]
            if BLITTER_START <= e["addr"] <= BLITTER_LAST
        )
        own = sum(1 for k, _ in rows_for((symbols or {}).get("images", {}), image) if k != COMMON)
        rows.append((image, reset, functions.get(image), blitter, own))

    if not rows:
        print("INVALID: the disassembly table comes out without a single row")
        raise SystemExit(3)

    out = [
        "| Image | Boot PC | Functions | Blitter accesses (`0x700000`) | Symbols |",
        "|-------|--------:|----------:|------------------------------:|--------:|",
    ]
    for image, reset, n_functions, blitter, own in rows:
        fun = str(n_functions) if n_functions is not None else "--"
        out.append(
            f"| `{image.replace('_maincpu', '')}` | `{reset:#07x}` | {fun} | {blitter} | {own} |"
        )
    return "\n".join(out) + "\n"


# The labels of the rendered tables, one spelling per thing across every block of the page.
LABELS = {
    "word": "Word",
    "at_word": "at",
    "and_word": "and",
    "header": "| bit | name | state | what it does |",
    "sep": "|-----|------|-------|--------------|",
    "confirmed": "confirmed",
    "open": "**open**",
    "refuted": "refuted",
    "no_bits": "_No individual bits to document: the word is used whole, as the description"
    " above says._",
    "window": "The visible window is **{a}x{b}**.",
    "planes_header": "| plane | height | pages | description |",
    "planes_sep": "|-------|--------|-------|-------------|",
    "memory_header": "| range | name | mirror | state | what it is |",
    "memory_sep": "|-------|------|--------|-------|------------|",
}


def _bits_table(item, e):
    """The public table of an item's bits, or the sentence saying it is used whole."""
    if not item.get("bits"):
        return [e["no_bits"], ""]
    lines = [e["header"], e["sep"]]
    for bit in item["bits"]:
        label = e.get(bit.get("state", "?"), bit.get("state", "?"))
        lines.append(
            f"| `{bit['mask']:#06x}` | {bit.get('name', '')} | {label} | "
            f"{flatten(bit.get('meaning') or '')} |"
        )
    return lines + [""]


def public_registers_table(data):
    """The register map to PUBLISH: what each word and each bit does, and nothing else.

    What does NOT come in here, and it is most of the YAML's text: the evidence of how each thing
    was found out, the per-machine measurements and the refuted readings. That is the working
    notebook, not the board's documentation: whoever has the board in front of them wants to know
    what bit 3 does, not how many attempts it took to find out. That record stays in the YAML,
    where it is written and read.
    """
    e = LABELS
    lines = []
    for reg in sorted(data["blitter"]["registers"], key=lambda r: r["word"]):
        base = data["blitter"]["base"]
        dirs = f" {e['and_word']} ".join(f"`{base + b:#08x}`" for b in reg["bytes"])
        lines += [f"### {e['word']} {reg['word']} ({reg['name']}), {e['at_word']} {dirs}", ""]
        desc = reg.get("description") or ""
        if desc:
            lines += [flatten(desc), ""]
        lines += _bits_table(reg, e)
    return "\n".join(lines).rstrip() + "\n"


def _port_heading(port):
    return f"### `{port['address']:#08x}` {port['name']}"


def public_ports_table(data):
    """The other ports the main 68000 touches, to PUBLISH: what each one is and what its bits do."""
    lines = []
    for port in sorted(data["ports"], key=lambda p: p["address"]):
        lines += [_port_heading(port), ""]
        if port.get("description"):
            lines += [flatten(port["description"]), ""]
        lines += _bits_table(port, LABELS)
    return "\n".join(lines).rstrip() + "\n"


def _memory_rows(data, e):
    lines = [e["memory_header"], e["memory_sep"]]
    for entry in data["memory"]:
        lo, hi = entry["range"]
        mirror = f"`{entry['mirror']:#08x}`" if entry.get("mirror") else "--"
        state_ = entry.get("state", "?")
        lines.append(
            f"| `{lo:#08x}..{hi:#08x}` | {entry['name']} | {mirror} | {e.get(state_, state_)} | "
            f"{flatten(entry.get('description') or '')} |"
        )
    return lines


def public_memory_table(data):
    """The memory map's rows that carry a decision worth publishing."""
    return "\n".join(_memory_rows(data, LABELS)).rstrip() + "\n"


def public_video_block(data):
    """The visible window and the planes, without the notebook of how they were measured."""
    e = LABELS
    v = data["video"]
    w = v["window"]
    lines = [e["window"].format(a=w["width"], b=w["height"]), ""]
    desc = w.get("description") or ""
    if desc:
        lines += [flatten(desc), ""]
    lines += [e["planes_header"], e["planes_sep"]]
    for p in v.get("planes", []):
        lines.append(
            f"| {p['name']} | {p['height']} | {p.get('pages', 1)} | "
            f"{flatten(p.get('description') or '')} |"
        )
    return "\n".join(lines).rstrip() + "\n"


def accesses_table(accesses, symbols):
    """A comparison of what hardware each game touches, counted over the binary.

    What matters is not the absolute number but the COMPARISON: the same address across the four
    machines reveals who uses a mechanism and who does not. That is how it was seen that Power Ball
    does not reference the opaque-mode selector once.
    """
    machine_list = [
        m
        for m in ("radendur_maincpu", "wheelfir_maincpu", "pwball_maincpu", "kongball_maincpu")
        if m in accesses["images"]
    ]
    if not machine_list:
        return "No images scanned.\n"

    # each address's name, if the symbol source has it
    names = {}
    for entries in (symbols.get("images") or {}).values():
        for e in entries or []:
            names.setdefault(e["addr"], e["name"])

    all_addrs = sorted({a["addr"] for m in machine_list for a in accesses["images"][m]["accesses"]})
    head = [
        "Absolute references to each hardware address, counted over the program ROM.",
        "Anything reached through a pointer is not included.",
        "",
        "| address | name | " + " | ".join(m.split("_")[0] for m in machine_list) + " |",
    ]
    lines = head + ["|-----------|--------|" + "|".join(["------"] * len(machine_list)) + "|"]
    for addr in all_addrs:
        row = []
        for m in machine_list:
            n = next((a["refs"] for a in accesses["images"][m]["accesses"] if a["addr"] == addr), 0)
            row.append(str(n) if n else "-")
        # `--` and not blank when there is no symbol: an address with no name is a fact, and a gap
        # reads as a generator fault (the render validator refuses one).
        lines.append(f"| `{addr:#08x}` | {names.get(addr) or '--'} | " + " | ".join(row) + " |")
    lines.append("")
    for m in machine_list:
        info = accesses["images"][m]
        lines.append(
            f"- **{m.split('_')[0]}**: {info['total']} references to "
            f"{len(info['accesses'])} distinct addresses."
        )
    return "\n".join(lines).rstrip() + "\n"


def rltennis_accesses_table(accesses, symbols):
    """What hardware Reality Tennis touches, counted over its program ROM.

    One game on its board, so there is nothing to compare: each address carries its count and,
    where the driver's map names it, the symbol from Reality Tennis's own block of `symbols.yaml`.
    Never the E133 names, which share addresses with different hardware behind them.
    """
    image = "rltennis_maincpu"
    info = (accesses.get("images") or {}).get(image)
    if not info or not info.get("accesses"):
        return "No images scanned.\n"
    names = {}
    for key, e in rows_for(symbols.get("images") or {}, image):
        if key != COMMON:
            names.setdefault(e["addr"], (e["name"], e.get("description", "")))
    # The symbols were read from the driver's address map, so an address none of them reaches is
    # outside the map: inside a range a symbol declares, it is a word of that symbol; a word whose
    # low byte is a symbol is that symbol's word; anything else the map does not hold.
    ranges = []
    for name, what in names.values():
        m = re.search(r"\((0x[0-9a-fA-F]+)-(0x[0-9a-fA-F]+)\)", what)
        if m:
            ranges.append((int(m[1], 16), int(m[2], 16), name))

    def describe(addr):
        if addr in names:
            return names[addr]
        for lo, hi, name in ranges:
            if lo <= addr <= hi:
                return "--", f"inside {name}, word {(addr - lo) // 2}"
        if addr + 1 in names:
            return "--", f"the word whose low byte is {names[addr + 1][0]}"
        return "--", "outside the driver's map"

    lines = [
        "| address | symbol | what the driver's map says | references |",
        "|---------|--------|----------------------------|------------|",
    ]
    for a in sorted(info["accesses"], key=lambda a: a["addr"]):
        name, what = describe(a["addr"])
        lines.append(f"| `{a['addr']:#08x}` | {name} | {what} | {a['refs']} |")
    lines.append("")
    lines.append(
        f"{info['total']} absolute references to {len(info['accesses'])} distinct addresses."
    )
    return "\n".join(lines).rstrip() + "\n"


def insert_block(path, block_name, content):
    """The page at `path` with its `block_name` block holding `content`."""
    if not path.exists():
        print(f"INVALID: {path.name} does not exist; a generated block needs its page")
        raise SystemExit(3)
    start = doc_blocks.opener("gen-hw-docs.py", block_name)
    return doc_blocks.replace(path.read_text(encoding="utf-8"), start, f"\n{content}\n", path.name)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--check",
        action="store_true",
        help="does not write; fails if the documentation is out of sync",
    )
    args = ap.parse_args()

    data, field_failures = load_registers()
    # A source with no `images:` (missing, empty, or another shape) leaves published blocks
    # uncompared, or crashes the render that reads it, and the verdict would come out green all
    # the same. It is "I could not look", not "it is up to date".
    sources = {}
    for path, feeds in (
        (SYMBOLS, "every symbol block"),
        (ACCESSES, "the accesses and findings blocks"),
    ):
        loaded = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else None
        if (
            not isinstance(loaded, dict)
            or not isinstance(loaded.get("images"), dict)
            or not loaded["images"]
        ):
            print(
                f"INVALID: {path.name} is missing or holds no `images:`; {feeds} were not compared"
            )
            return 3
        sources[path] = loaded
    symbols, accesses = sources[SYMBOLS], sources[ACCESSES]

    failures = field_failures + validate(data) + validate_symbols(symbols)
    if failures:
        print("invalid schema:")
        for f in failures:
            print(f"  {f}")
        return 1

    # A LIST and not a dict keyed by path: the blocks go to the SAME file, the board's page, and a
    # dict indexed by path would keep only the last one, in silence.
    outputs = [
        (BOARD, "registers", public_registers_table(data)),
        (BOARD, "video", public_video_block(data)),
        (BOARD, "ports", public_ports_table(data)),
        (BOARD, "memory", public_memory_table(data)),
    ]
    outputs.append((BOARD, "accesses", accesses_table(accesses, symbols)))
    outputs.append((RLTENNIS_BOARD, "accesses", rltennis_accesses_table(accesses, symbols)))
    outputs.append((DISASSEMBLY, "findings", disasm_table(accesses, symbols)))

    # symbols.txt carries no blocks: the WHOLE file is generated
    complete = {ROOT / "disasm" / "symbols.txt": symbols_file(symbols)}
    extracted = sorted(p.stem for p in IMAGES.glob("*.bin"))
    for image in debugger_images(symbols, extracted):
        complete[ROOT / "disasm" / f"symbols-{image}.yaml"] = debugger_symbols_file(symbols, image)

    stale = []
    for path, content in complete.items():
        if args.check:
            if not path.exists() or path.read_text(encoding="utf-8") != content:
                stale.append(path.relative_to(ROOT))
        else:
            path.write_text(content, encoding="utf-8", newline="\n")
            print(f"  written {path.relative_to(ROOT)}")

    # In order and one after another: `insert_block` re-reads the file every time, so several blocks
    # in the same document accumulate rather than overwriting each other.
    for path, name, content in outputs:
        result = insert_block(path, name, content)
        if args.check:
            if not path.exists() or path.read_text(encoding="utf-8") != result:
                stale.append(f"{path.relative_to(ROOT)} [{name}]")
        else:
            path.write_text(result, encoding="utf-8", newline="\n")

    if args.check:
        if stale:
            print("documentation out of sync with hardware/registers.yaml:")
            for d in stale:
                print(f"  {d}")
            print("run: uv run scripts/gen-hw-docs.py")
            return 1
        print(f"documentation up to date ({len(outputs)} blocks, valid schema)")
    else:
        for path in dict.fromkeys(r for r, _, _ in outputs):
            print(f"  written {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
