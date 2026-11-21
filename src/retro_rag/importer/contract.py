"""Transportvertrag zwischen Importadaptern und späteren Persistenzstufen."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Source(StrictModel):
    source_id: str = Field(min_length=1)
    location: str = Field(min_length=1)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    kind: Literal["markdown", "pdf"]


class Document(StrictModel):
    title: str = Field(min_length=1)
    document_type: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class Chunk(StrictModel):
    ordinal: int = Field(ge=0)
    text: str = Field(min_length=1)
    chunk_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    heading_path: list[str] = Field(default_factory=list)
    page: int | None = Field(default=None, ge=1)


class EvidenceProposal(StrictModel):
    chunk_ordinal: int = Field(ge=0)
    quote: str = Field(min_length=1)
    page: int | None = Field(default=None, ge=1)


class FactProposal(StrictModel):
    subject: str = Field(min_length=1)
    property: str = Field(min_length=1)
    value: str | float | int
    unit: str | None = None
    evidence: EvidenceProposal
    confidence: float | None = Field(default=None, ge=0, le=1)


class ImportContract(StrictModel):
    contract_version: Literal["0.1"] = "0.1"
    source: Source
    document: Document
    chunks: list[Chunk]
    fact_proposals: list[FactProposal] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    indexing_allowed: bool = False
