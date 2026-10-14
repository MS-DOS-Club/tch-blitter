"""The hardware documentation generator: the blocks it writes into a page, and what they carry."""

import pathlib

import doc_blocks
import pytest
import yaml
from script_loader import load_script

gen = load_script("gen_hw_docs", "gen-hw-docs.py")


def reg(bits):
    return {
        "blitter": {
            "base": 0x700000,
            "registers": [{"word": 7, "bytes": [0x0E, 0x0F], "name": "flags", "bits": bits}],
        }
    }


def test_insert_respects_the_prose_around_it():
    """The generator writes ITS block and nothing else: hand prose lives in the same file."""
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        f = pathlib.Path(d) / "doc.md"
        f.write_text(
            "# Title\n\nprose before\n\n"
            f"{doc_blocks.opener('gen-hw-docs.py', 'x')}\n\nold\n"
            f"{doc_blocks.END}\n\nprose after\n",
            encoding="utf-8",
            newline="\n",
        )
        new = gen.insert_block(f, "x", "new\n")
        assert "prose before" in new and "prose after" in new
        assert "new" in new and "old" not in new


def test_a_missing_page_is_invalid_not_a_new_stub(tmp_path):
    """A renamed or deleted page must stop the generator, not get a page of bare blocks."""
    with pytest.raises(SystemExit) as stop:
        gen.insert_block(tmp_path / "gone.md", "x", "new\n")
    assert stop.value.code == 3
    assert not (tmp_path / "gone.md").exists()


def test_insert_does_not_nest_three_blocks_in_the_same_file(tmp_path):
    """Three blocks in one page: each is replaced by its own close, none takes the next one's."""
    end = doc_blocks.END
    doc = tmp_path / "placa.md"
    doc.write_text(
        "# title\n\n"
        + f"{doc_blocks.opener('gen-hw-docs.py', 'a')}\nold A\n{end}\n\nprose in between\n\n"
        + f"{doc_blocks.opener('gen-hw-docs.py', 'b')}\nold B\n{end}\n\nmore prose\n\n"
        + f"{doc_blocks.opener('gen-hw-docs.py', 'c')}\nold C\n{end}\n",
        encoding="utf-8",
        newline="\n",
    )
    for name, body in (("a", "AAA"), ("b", "BBB"), ("c", "CCC")):
        doc.write_text(gen.insert_block(doc, name, body), encoding="utf-8", newline="\n")

    text = doc.read_text(encoding="utf-8")
    assert text.count(doc_blocks.OPENER) == 3, f"blocks have been duplicated:\n{text}"
    assert text.count(end) == 3
    for body in ("AAA", "BBB", "CCC"):
        assert text.count(body) == 1, f"{body} appears more than once"
    assert "prose in between" in text and "more prose" in text, "it has eaten the prose"


def ports(bits, memory=None):
    return {
        "ports": [{"address": 0x7C0000, "name": "control_and_link", "bits": bits}],
        "memory": memory or [],
    }


def test_ports_and_memory_render_with_no_empty_table():
    """One heading and one bits table per port, one row per memory entry."""
    data = ports(
        [
            {
                "mask": 0xFF,
                "name": "link_data",
                "state": "confirmed",
                "evidence": "read at 0xa4858",
                "meaning": "the byte on the wire",
                "observed": {"wheelfir": "0xa5 at boot"},
            }
        ],
        memory=[
            {
                "range": [0x200000, 0x20FFFF],
                "name": "main_ram",
                "mirror": 0x10000,
                "state": "open",
                "description": "64 KB",
                "observed": {"kongball": "reached through 0x2100ae"},
            }
        ],
    )
    public = gen.public_ports_table(data)
    assert "### `0x7c0000` control_and_link" in public
    assert "| `0x00ff` | link_data | confirmed | the byte on the wire |" in public, public
    memory = gen.public_memory_table(data)
    assert "| `0x200000..0x20ffff` | main_ram | `0x010000` | **open** | 64 KB |" in memory, memory


# ---- the command's positions, owned by gfx.yaml


def _one_bit(bit):
    return {"blitter": {"registers": [{"word": 6, "bits": [bit]}]}}


_GFX = {
    "commands": {
        "blit": {
            "fields": {
                "source_tile": {"parts": [{"word": 6, "mask": 0xFC00}]},
                "source_x": {"parts": [{"word": 0, "mask": 0xFF00}, {"word": 6, "mask": 0x100}]},
            },
            "flags": {
                "page_twice": {"parts": [{"word": 6, "mask": 0x1}, {"word": 6, "mask": 0x2}]}
            },
        }
    }
}


def test_a_bit_naming_a_field_takes_its_mask_from_gfx_yaml():
    data = _one_bit({"field": "source_x", "name": "src_u_bit8"})
    assert gen.resolve_fields(data, _GFX) == []
    assert data["blitter"]["registers"][0]["bits"][0]["mask"] == 0x100, "the part on ITS word"


def test_the_reality_tennis_access_table_names_each_row_from_its_own_symbols():
    accesses = {
        "images": {
            "rltennis_maincpu": {
                "total": 10,
                "accesses": [
                    {"addr": 0x700000, "refs": 1},
                    {"addr": 0x700004, "refs": 2},
                    {"addr": 0x720000, "refs": 3},
                    {"addr": 0x7C0000, "refs": 4},
                ],
            }
        }
    }
    symbols = {
        "images": {
            # an E133 name at the same address must never reach the Reality Tennis table
            "wheelfir_maincpu": [{"addr": 0x7C0000, "name": "status_7c0000"}],
            "rltennis_maincpu,rltennisa_maincpu": [
                {"addr": 0x700000, "name": "rlt_blitter", "description": "B (0x700000-0x70000f)"},
                {"addr": 0x720001, "name": "rlt_idx", "description": "index"},
            ],
        }
    }
    out = gen.rltennis_accesses_table(accesses, symbols)
    assert "| `0x700000` | rlt_blitter | B (0x700000-0x70000f) | 1 |" in out
    assert "| `0x700004` | -- | inside rlt_blitter, word 2 | 2 |" in out
    assert "| `0x720000` | -- | the word whose low byte is rlt_idx | 3 |" in out
    assert "| `0x7c0000` | -- | outside the driver's map | 4 |" in out
    assert "10 absolute references to 4 distinct addresses." in out


def test_the_real_reality_tennis_access_table_counts_what_the_yaml_holds():
    root = pathlib.Path(__file__).resolve().parents[1]
    accesses = yaml.safe_load((root / "hardware" / "accesses.yaml").read_text(encoding="utf-8"))
    symbols = yaml.safe_load((root / "hardware" / "symbols.yaml").read_text(encoding="utf-8"))
    info = accesses["images"]["rltennis_maincpu"]
    out = gen.rltennis_accesses_table(accesses, symbols)
    rows = [line for line in out.splitlines() if line.startswith("| `0x")]
    assert len(rows) == len(info["accesses"])
    assert sum(int(r.rsplit("|", 2)[1]) for r in rows) == info["total"]
