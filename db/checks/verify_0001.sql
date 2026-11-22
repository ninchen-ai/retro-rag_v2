-- Rein lesende Prüfung nach 0001; psql -X -v ON_ERROR_STOP=1 -f ...
\set ON_ERROR_STOP on
DO $verify$
DECLARE
    required_tables text[] := ARRAY[
        'schema_migration', 'component_type', 'article', 'article_revision',
        'article_alias', 'unit', 'system', 'storage_location',
        'installation', 'storage_assignment', 'unit_condition_history',
        'document', 'document_source', 'document_version', 'chunk',
        'embedding_model', 'chunk_embedding', 'reference_entity',
        'knowledge_subject', 'property', 'property_component_type',
        'fact', 'evidence', 'fact_evidence', 'compatibility_rule',
        'compatibility_rule_evidence', 'trusted_source', 'processing_job',
        'processing_step', 'processing_artifact', 'review_batch',
        'review_item', 'review_decision', 'sync_run', 'document_error',
        'query_log', 'write_gate'
    ];
    t text;
BEGIN
    IF current_database() NOT IN ('retro_rag_v2', 'retro_rag_v2_test') THEN
        RAISE EXCEPTION 'Verifikation auf falscher Datenbank: %', current_database();
    END IF;
    FOREACH t IN ARRAY required_tables LOOP
        IF to_regclass(format('rag_v2.%I', t)) IS NULL THEN
            RAISE EXCEPTION 'Tabelle fehlt: rag_v2.%', t;
        END IF;
    END LOOP;
    IF NOT EXISTS (SELECT 1 FROM rag_v2.schema_migration WHERE version = 1) THEN
        RAISE EXCEPTION 'Migration 0001 nicht protokolliert';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM rag_v2.write_gate
                   WHERE id = true AND writes_enabled = false) THEN
        RAISE EXCEPTION 'Initiale Restore-/Schreibsperre ist nicht gesetzt';
    END IF;
    RAISE NOTICE '0001: % Tabellen vorhanden, Marker vorhanden, Schreibsperre aktiv',
        array_length(required_tables, 1);
END;
$verify$;

SELECT current_database() AS database_name,
       (SELECT extversion FROM pg_extension WHERE extname = 'vector') AS pgvector_version,
       (SELECT count(*) FROM information_schema.tables
          WHERE table_schema = 'rag_v2' AND table_type = 'BASE TABLE') AS v2_tables,
       (SELECT max(version) FROM rag_v2.schema_migration) AS migration_version,
       (SELECT writes_enabled FROM rag_v2.write_gate WHERE id = true) AS writes_enabled;
