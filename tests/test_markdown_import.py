"""Regressionstests für die sichere Markdown-Vorstufe."""

import pytest

from retro_rag.importer.markdown import parse_frontmatter, read_markdown, split_sections


def test_frontmatter_requires_yaml() -> None:
    with pytest.raises(ValueError, match="Frontmatter fehlt"):
        parse_frontmatter("# Hallo")


def test_import_does_not_allow_indexing(tmp_path) -> None:
    source = tmp_path / "board.md"
    source.write_text(
        "---\ntitle: ASUS CUBX\ndocument_type: hardware_model\n---\n# Mainboard\n440BX\n",
        encoding="utf-8",
    )
    contract = read_markdown(source, "webdav-file-42")
    assert contract.source.source_id == "webdav-file-42"
    assert contract.document.title == "ASUS CUBX"
    assert contract.chunks[0].heading_path == ["Mainboard"]
    assert contract.fact_proposals == []
    assert contract.indexing_allowed is False


def test_oversized_section_is_split_without_loss() -> None:
    text = "abcdefghij" * 5
    chunks = split_sections(text, max_chars=13)
    assert "".join(chunk.text for chunk in chunks) == text
    assert all(len(chunk.text) <= 13 for chunk in chunks)
