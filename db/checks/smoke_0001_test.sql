-- Ausschließlich in retro_rag_v2_test ausführen.
-- Sämtliche Fixtures bleiben innerhalb einer zurückgerollten Transaktion.
\set ON_ERROR_STOP on
DO $guard$
BEGIN
    IF current_database() <> 'retro_rag_v2_test' THEN
        RAISE EXCEPTION 'Schutzabbruch: Smoke-Test ausschließlich in retro_rag_v2_test';
    END IF;
END;
$guard$;

BEGIN;
DO $smoke$
DECLARE
    v_type uuid;
    v_article uuid;
    v_unit uuid;
    v_system uuid;
    v_storage_location uuid;
    v_document uuid;
    v_version uuid;
    v_subject uuid;
    v_property uuid;
    v_fact uuid;
    v_evidence uuid;
    v_detected boolean := false;
BEGIN
    INSERT INTO rag_v2.component_type (code, name)
    VALUES ('smoke_cpu', 'CPU Test') RETURNING id INTO v_type;
    INSERT INTO rag_v2.article (component_type_id, manufacturer, model, model_key)
    VALUES (v_type, 'SmokeVendor', 'TestCPU', 'smokevendor:testcpu')
    RETURNING id INTO v_article;
    INSERT INTO rag_v2.unit (article_id, inventory_number)
    VALUES (v_article, 'SMOKE-000001') RETURNING id INTO v_unit;
    PERFORM rag_v2.validate_unit_location(v_unit);

    INSERT INTO rag_v2.storage_location (code)
    VALUES ('SMOKE-CABINET') RETURNING id INTO v_storage_location;
    UPDATE rag_v2.unit SET location_state = 'stored' WHERE id = v_unit;
    INSERT INTO rag_v2.storage_assignment (unit_id, storage_location_id)
    VALUES (v_unit, v_storage_location);
    PERFORM rag_v2.validate_unit_location(v_unit);

    INSERT INTO rag_v2.system (name)
    VALUES ('SMOKE-SYSTEM') RETURNING id INTO v_system;
    UPDATE rag_v2.storage_assignment
       SET valid_to = valid_from + interval '1 second'
     WHERE unit_id = v_unit AND valid_to IS NULL;
    UPDATE rag_v2.unit SET location_state = 'installed' WHERE id = v_unit;
    INSERT INTO rag_v2.installation (unit_id, system_id)
    VALUES (v_unit, v_system);
    PERFORM rag_v2.validate_unit_location(v_unit);

    -- Tabellenübergreifender Standortkonflikt muss abgewiesen werden.
    BEGIN
        UPDATE rag_v2.unit SET location_state = 'stored' WHERE id = v_unit;
        INSERT INTO rag_v2.storage_assignment (unit_id, storage_location_id)
        VALUES (v_unit, v_storage_location);
        PERFORM rag_v2.validate_unit_location(v_unit);
    EXCEPTION WHEN raise_exception THEN
        v_detected := true;
    END;
    IF NOT v_detected THEN
        RAISE EXCEPTION 'Standortkonflikt wurde nicht erkannt';
    END IF;

    INSERT INTO rag_v2.document (title)
    VALUES ('Smoke-Test Manual') RETURNING id INTO v_document;
    INSERT INTO rag_v2.document_source (document_id, source_system, source_key, source_uri)
    VALUES (v_document, 'smoke', 'unique-file-id', 'nextcloud://smoke/file');
    INSERT INTO rag_v2.document_version
        (document_id, version_no, content_hash, processing_state, state)
    VALUES (v_document, 1, repeat('a', 64), 'indexed', 'active')
    RETURNING id INTO v_version;
    INSERT INTO rag_v2.chunk
        (document_version_id, sequence_no, content, content_hash)
    VALUES (v_version, 0, 'AGP 2x 3,3 Volt', repeat('b', 64));

    INSERT INTO rag_v2.knowledge_subject (article_id)
    VALUES (v_article) RETURNING id INTO v_subject;
    INSERT INTO rag_v2.property (property_key, name, value_type, canonical_unit)
    VALUES ('smoke_voltage', 'Spannung', 'numeric', 'V')
    RETURNING id INTO v_property;

    -- Falscher Datentyp wird bei INSERT abgefangen.
    v_detected := false;
    BEGIN
        INSERT INTO rag_v2.fact (subject_id, property_id, value_text, unit_symbol)
        VALUES (v_subject, v_property, 'drei Volt', 'V');
    EXCEPTION WHEN raise_exception THEN
        v_detected := true;
    END;
    IF NOT v_detected THEN
        RAISE EXCEPTION 'Falscher Fakttyp wurde nicht erkannt';
    END IF;

    -- Ohne Quellenbeleg darf keine neue bestätigte Aussage freigegeben werden.
    v_detected := false;
    BEGIN
        INSERT INTO rag_v2.fact
            (subject_id, property_id, value_numeric, unit_symbol, status)
        VALUES (v_subject, v_property, 3.3, 'V', 'accepted')
        RETURNING id INTO v_fact;
        PERFORM rag_v2.validate_accepted_evidence('fact', v_fact);
    EXCEPTION WHEN raise_exception THEN
        v_detected := true;
    END;
    IF NOT v_detected THEN
        RAISE EXCEPTION 'Akzeptierter Fakt ohne Beleg wurde nicht erkannt';
    END IF;

    INSERT INTO rag_v2.fact
        (subject_id, property_id, value_numeric, unit_symbol, status)
    VALUES (v_subject, v_property, 3.3, 'V', 'accepted')
    RETURNING id INTO v_fact;
    INSERT INTO rag_v2.evidence
        (evidence_kind, document_version_id, page_number, excerpt)
    VALUES ('external', v_version, 1, 'AGP-Signalspannung 3,3 V')
    RETURNING id INTO v_evidence;
    INSERT INTO rag_v2.fact_evidence (fact_id, evidence_id)
    VALUES (v_fact, v_evidence);
    PERFORM rag_v2.validate_accepted_evidence('fact', v_fact);
END;
$smoke$;
SET CONSTRAINTS ALL IMMEDIATE;
ROLLBACK;
SELECT 'Smoke-Test abgeschlossen (Transaktion zurückgerollt)' AS result;
