"""Regressionstests für den Import-Metadatenvertrag (ohne Datenbank)."""

from retro_rag.importer.metadata import assess_metadata


def test_valid_metadata_does_not_grant_trust_by_itself():
    result = assess_metadata(
        {"title": "ASUS CUBX", "document_type": "hardware_model", "tags": ["AGP"]},
    )
    assert result.valid
    assert not result.fact_auto_approval_allowed
    assert result.normalized["title"] == "ASUS CUBX"


def test_fully_qualified_external_approval():
    data = {"title": "CUBX", "document_type": "hardware_model"}
    assert assess_metadata(
        data, externally_authorized=True, facts_validated=True, conflict_free=True
    ).fact_auto_approval_allowed
    assert not assess_metadata(
        data, externally_authorized=True, facts_validated=False, conflict_free=True
    ).fact_auto_approval_allowed
    assert not assess_metadata(
        data, externally_authorized=False, facts_validated=True, conflict_free=True
    ).fact_auto_approval_allowed


def test_empty_required_metadata_is_review_not_approval():
    result = assess_metadata({"title": "   ", "document_type": "hardware_model"})
    assert not result.valid
    assert not result.fact_auto_approval_allowed
    assert result.issues


def test_missing_document_type_is_rejected():
    result = assess_metadata({"title": "CUBX"})
    assert not result.valid
    assert "document_type" in result.issues[0]


def test_duplicate_tags_and_wrong_types_are_rejected():
    result = assess_metadata(
        {"title": "CUBX", "document_type": "hardware_model", "tags": ["AGP", "agp"]}
    )
    assert not result.valid
    assert not assess_metadata(
        {"title": 12, "document_type": "hardware_model"}
    ).valid


def test_self_declared_trust_cannot_authorize():
    result = assess_metadata(
        {"title": "CUBX", "document_type": "hardware_model", "trusted": True},
        externally_authorized=True,
        facts_validated=True,
        conflict_free=True,
    )
    assert result.valid
    assert not result.fact_auto_approval_allowed
    assert result.issues


def test_unknown_domain_specific_metadata_is_preserved():
    result = assess_metadata(
        {
            "title": "CUBX",
            "document_type": "hardware_model",
            "socket": "Slot 1",
            "ram_slots": 4,
        }
    )
    assert result.valid
    assert result.normalized["socket"] == "Slot 1"
    assert result.normalized["ram_slots"] == 4
