"""Markdown-Vorstufe: Original unverändert lesen, YAML prüfen, Abschnitte bilden."""

import hashlib
import re
from pathlib import Path

import yaml

from retro_rag.importer.contract import Chunk, Document, ImportContract, Source

_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse_frontmatter(content: str) -> tuple[dict, str]:
    """YAML-Frontmatter muss am Dokumentanfang stehen."""
    normalized = content.removeprefix("\ufeff")
    lines = normalized.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        raise ValueError("YAML-Frontmatter fehlt")
    end = next((i for i, line in enumerate(lines[1:], 1) if line.strip() == "---"), None)
    if end is None:
        raise ValueError("YAML-Frontmatter ist nicht abgeschlossen")
    data = yaml.safe_load("".join(lines[1:end]))
    if not isinstance(data, dict):
        raise ValueError("YAML-Frontmatter muss ein Mapping sein")
    return data, "".join(lines[end + 1 :])


def split_sections(body: str, max_chars: int = 4000) -> list[Chunk]:
    """Abschnittsorientiertes Chunking mit hartem Größenlimit (vorläufiger Wert)."""
    if max_chars < 1:
        raise ValueError("max_chars muss positiv sein")
    path: list[str] = []
    sections: list[tuple[list[str], str]] = []
    lines: list[str] = []

    def flush() -> None:
        text = "".join(lines).strip()
        if text:
            sections.append((path.copy(), text))
        lines.clear()

    for line in body.splitlines(keepends=True):
        match = _HEADING.match(line)
        if match:
            flush()
            depth = len(match.group(1))
            path = path[: depth - 1] + [match.group(2).strip()]
        lines.append(line)
    flush()

    result: list[Chunk] = []
    for headings, text in sections:
        # Chunk-Grenzen sind reproduzierbar; keine stillschweigende Abschneidung.
        for start in range(0, len(text), max_chars):
            part = text[start : start + max_chars]
            result.append(
                Chunk(
                    ordinal=len(result),
                    text=part,
                    chunk_hash=sha256(part.encode("utf-8")),
                    heading_path=headings,
                )
            )
    return result


def read_markdown(path: Path, source_id: str, max_chars: int = 4000) -> ImportContract:
    """Nur lesen; keine DB-Schreibzugriffe und keine Freigabe von Fakten."""
    raw = path.read_bytes()
    content = raw.decode("utf-8-sig")
    metadata, body = parse_frontmatter(content)
    title = metadata.get("title")
    document_type = metadata.get("document_type")
    if not isinstance(title, str) or not title.strip():
        raise ValueError("YAML-Feld 'title' fehlt oder ist leer")
    if not isinstance(document_type, str) or not document_type.strip():
        raise ValueError("YAML-Feld 'document_type' fehlt oder ist leer")
    return ImportContract(
        source=Source(
            source_id=source_id,
            location=str(path),
            content_hash=sha256(raw),
            kind="markdown",
        ),
        document=Document(title=title, document_type=document_type, metadata=metadata),
        chunks=split_sections(body, max_chars=max_chars),
        warnings=["Quellenautorisierung, Schema- und Konfliktprüfung sind noch nicht implementiert."],
        indexing_allowed=False,
    )
