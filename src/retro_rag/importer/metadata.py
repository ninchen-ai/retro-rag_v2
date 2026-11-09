"""Versionierte Metadatenprüfung vor Staging, Indexierung und Faktenreview.

Quellautorisierung wird bewusst nicht aus YAML abgeleitet.
"""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator


class DocumentMetadata(BaseModel):
    """Metadaten eigener Markdown-Quellen; zusätzliche Fachfelder bleiben erhalten."""

    model_config = ConfigDict(extra="allow", strict=True)

    title: str = Field(min_length=1)
    document_type: str = Field(min_length=1)
    language: str | None = None
    manufacturer: str | None = None
    model: str | None = None
    revision: str | None = None
    source_url: str | None = None
    published_at: date | None = None
    tags: list[str] = Field(default_factory=list)

    @field_validator(
        "title", "document_type", "language", "manufacturer", "model",
        "revision", "source_url",
    )
    @classmethod
    def nonblank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("Leere Zeichenketten sind nicht erlaubt")
        return value

    @field_validator("tags")
    @classmethod
    def valid_tags(cls, value: list[str]) -> list[str]:
        if any(not isinstance(tag, str) or not tag.strip() for tag in value):
            raise ValueError("Tags müssen nichtleere Zeichenketten sein")
        if len(set(tag.casefold() for tag in value)) != len(value):
            raise ValueError("Tags dürfen nicht doppelt vorkommen")
        return value


@dataclass(frozen=True)
class MetadataAssessment:
    valid: bool
    issues: tuple[str, ...]
    normalized: dict[str, Any]
    fact_auto_approval_allowed: bool


def assess_metadata(
    raw: dict[str, Any],
    *,
    externally_authorized: bool = False,
    facts_validated: bool = False,
    conflict_free: bool = False,
) -> MetadataAssessment:
    """Prüft Daten ohne Schreibzugriff und ohne Vertrauen aus YAML zu übernehmen.

    Keine dieser Prüfungen setzt Dokumente automatisch auf indexed oder gibt Fakten frei.
    Eine externe Autorisierung ist nur eine der notwendigen Freigabebedingungen.
    """
    try:
        model = DocumentMetadata.model_validate(raw)
    except ValidationError as exc:
        issues = tuple(
            f"{'.'.join(map(str, error['loc']))}: {error['msg']}"
            for error in exc.errors()
        )
        return MetadataAssessment(False, issues, {}, False)

    normalized = model.model_dump(mode="json", exclude_none=True)
    warnings: list[str] = []
    # YAML-Angaben über die eigene Vertrauenswürdigkeit sind keine Berechtigung.
    if any(
        key in raw for key in
        ("trusted", "verified", "auto_approve", "auto_approved", "trust_level")
    ):
        warnings.append("Vertrauensangaben aus YAML sind nicht autoritativ")

    approved = (
        externally_authorized
        and facts_validated
        and conflict_free
        and not warnings
    )
    return MetadataAssessment(True, tuple(warnings), normalized, approved)
