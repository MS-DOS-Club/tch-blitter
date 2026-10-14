"""verify-docs.py's case check: a link must name every component with the case on disk."""

from __future__ import annotations

from script_loader import load_script

vd = load_script("verify_docs", "verify-docs.py")


def test_exact_spelling_passes(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "page.md").write_text("x", encoding="utf-8")
    assert vd.spelled_exactly(tmp_path, "docs/page.md")
    assert vd.spelled_exactly(tmp_path / "docs", "../docs/page.md")


def test_wrong_case_in_the_name_or_a_directory_fails(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "page.md").write_text("x", encoding="utf-8")
    assert not vd.spelled_exactly(tmp_path, "docs/Page.md")
    assert not vd.spelled_exactly(tmp_path, "Docs/page.md")


def test_documents_reaches_pages_below_the_root():
    """The page list is the whole tree, not what a wildcard matched at the root."""
    docs = vd.documents()
    assert vd.ROOT / "docs" / "mame-techniques.md" in docs
    assert vd.ROOT / "README.md" in docs
