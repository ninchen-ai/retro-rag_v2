-- Retro-RAG V2: rollenbasierte Zugriffsgrenzen (Phase 0).
-- Vorwärtsmigration, ausschließlich für die beiden V2-Datenbanken.
-- Rollen sind CLUSTERWEIT; alle Namen beginnen deshalb mit rag_v2_.
-- Bestehende V1-Rollen und -Datenbanken werden nicht verändert.
\set ON_ERROR_STOP on
BEGIN;

DO $guard$
BEGIN
    IF current_database() NOT IN ('retro_rag_v2', 'retro_rag_v2_test') THEN
        RAISE EXCEPTION 'Schutzabbruch: Datenbank % ist keine V2-Datenbank', current_database();
    END IF;
    IF current_setting('server_version_num')::integer NOT BETWEEN 160000 AND 169999 THEN
        RAISE EXCEPTION 'Schutzabbruch: PostgreSQL 16 erforderlich';
    END IF;
    IF to_regclass('rag_v2.schema_migration') IS NULL THEN
        RAISE EXCEPTION 'Schema rag_v2 und Migration 0001 fehlen';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM rag_v2.schema_migration WHERE version = 1)
       OR EXISTS (SELECT 1 FROM rag_v2.schema_migration WHERE version = 2) THEN
        RAISE EXCEPTION 'Migration 0001 fehlt oder 0002 wurde bereits ausgeführt';
    END IF;
    -- Diese Migration muss als Eigentümer der Tabellen laufen.
    IF EXISTS (
        SELECT 1 FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'rag_v2' AND c.relkind IN ('r', 'p')
          AND c.relowner <> (SELECT oid FROM pg_roles WHERE rolname = current_user)
    ) THEN
        RAISE EXCEPTION 'Migration nur als Eigentümer aller V2-Tabellen';
    END IF;
END;
$guard$;

SELECT pg_advisory_xact_lock(824020, 2);

-- NOLOGIN-Rollen sind zunächst reine Berechtigungsgruppen.
-- Spätere Login-Rollen erhalten gezielt Mitgliedschaften, niemals Superuser.
DO $roles$
DECLARE
    v_role text;
BEGIN
    FOREACH v_role IN ARRAY ARRAY[
        'rag_v2_migrator',
        'rag_v2_importer',
        'rag_v2_reviewer',
        'rag_v2_inventory',
        'rag_v2_reader',
        'rag_v2_lifecycle',
        'rag_v2_query_logger'
    ]
    LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = v_role) THEN
            RAISE EXCEPTION 'Rolle % existiert bereits: keine Übernahme unbekannter Clusterrollen', v_role;
        END IF;
        EXECUTE format(
            'CREATE ROLE %I NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION',
            v_role
        );
    END LOOP;
END;
$roles$;

-- Bestehende PUBLIC-Rechte nur auf neuem V2-Schema einschränken.
REVOKE ALL ON SCHEMA rag_v2 FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA rag_v2 FROM PUBLIC;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA rag_v2 FROM PUBLIC;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA rag_v2 FROM PUBLIC;

GRANT CONNECT ON DATABASE :DBNAME TO rag_v2_migrator, rag_v2_importer,
    rag_v2_reviewer, rag_v2_inventory, rag_v2_reader, rag_v2_lifecycle,
    rag_v2_query_logger;

GRANT USAGE ON SCHEMA rag_v2 TO rag_v2_migrator, rag_v2_importer,
    rag_v2_reviewer, rag_v2_inventory, rag_v2_reader, rag_v2_lifecycle,
    rag_v2_query_logger;

-- Migrationsrolle darf Schema verändern, jedoch keine Rollen verwalten.
-- Eigentümerschaft von 0001 bleibt zunächst beim initialen Ersteller.
-- Eine spätere Eigentümerübertragung muss separat getestet werden.
GRANT CREATE ON SCHEMA rag_v2 TO rag_v2_migrator;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA rag_v2
    TO rag_v2_migrator;

-- Lesen: keine direkten DML-Rechte; query_log schreibt eigene Minimalrolle.
GRANT SELECT ON ALL TABLES IN SCHEMA rag_v2 TO rag_v2_reader;
GRANT INSERT ON rag_v2.query_log TO rag_v2_query_logger;

-- Importiert nur Quellen, unbestätigte Vorschläge, Jobs und Suchdaten.
GRANT SELECT ON
    rag_v2.document, rag_v2.document_source, rag_v2.document_version,
    rag_v2.chunk, rag_v2.chunk_embedding, rag_v2.embedding_model,
    rag_v2.reference_entity, rag_v2.knowledge_subject,
    rag_v2.property, rag_v2.property_component_type,
    rag_v2.component_type, rag_v2.article, rag_v2.article_revision,
    rag_v2.article_alias, rag_v2.trusted_source, rag_v2.fact,
    rag_v2.evidence, rag_v2.fact_evidence,
    rag_v2.review_batch, rag_v2.review_item, rag_v2.review_decision,
    rag_v2.processing_job, rag_v2.processing_step, rag_v2.processing_artifact,
    rag_v2.write_gate
TO rag_v2_importer;
GRANT INSERT, UPDATE ON
    rag_v2.document, rag_v2.document_source, rag_v2.document_version,
    rag_v2.chunk, rag_v2.chunk_embedding,
    rag_v2.processing_job, rag_v2.processing_step, rag_v2.processing_artifact,
    rag_v2.review_batch, rag_v2.review_item, rag_v2.sync_run,
    rag_v2.document_error
TO rag_v2_importer;
GRANT SELECT, INSERT, UPDATE ON rag_v2.sync_run, rag_v2.document_error TO rag_v2_importer;

-- Freigabe: Belegprüfung und Review-Entscheidungen.
GRANT SELECT ON ALL TABLES IN SCHEMA rag_v2 TO rag_v2_reviewer;
GRANT INSERT, UPDATE ON
    rag_v2.fact, rag_v2.evidence, rag_v2.fact_evidence,
    rag_v2.compatibility_rule, rag_v2.compatibility_rule_evidence,
    rag_v2.review_batch, rag_v2.review_item, rag_v2.trusted_source
TO rag_v2_reviewer;
GRANT INSERT ON rag_v2.review_decision TO rag_v2_reviewer;

-- Bestand: Änderungen ausschließlich nach Prüfung in der API.
GRANT SELECT ON ALL TABLES IN SCHEMA rag_v2 TO rag_v2_inventory;
GRANT INSERT, UPDATE ON
    rag_v2.component_type, rag_v2.article, rag_v2.article_revision,
    rag_v2.article_alias, rag_v2.unit, rag_v2.system,
    rag_v2.storage_location, rag_v2.installation,
    rag_v2.storage_assignment, rag_v2.unit_condition_history
TO rag_v2_inventory;

-- Historische Dokumentkennungen und Belege werden beim Lifecycle nicht gelöscht.
GRANT SELECT ON ALL TABLES IN SCHEMA rag_v2 TO rag_v2_lifecycle;
GRANT UPDATE ON rag_v2.document, rag_v2.document_version, rag_v2.document_source
TO rag_v2_lifecycle;
GRANT DELETE ON rag_v2.chunk_embedding, rag_v2.chunk
TO rag_v2_lifecycle;

-- Alle Triggerfunktionen laufen weiterhin automatisch als INVOKER.
-- Nur ausdrücklich erforderliche direkte Helferfunktionen freigeben.
GRANT EXECUTE ON FUNCTION rag_v2.validate_unit_location(uuid)
TO rag_v2_inventory;
GRANT EXECUTE ON FUNCTION rag_v2.validate_accepted_evidence(text, uuid)
TO rag_v2_reviewer;

-- Kein operativer Role-Grant auf die Sicherheits-/Migrationsschalter.
-- SELECT darauf ist für Diagnose zulässig, Schreibrechte bleiben entzogen.
INSERT INTO rag_v2.schema_migration (version, description)
VALUES (2, 'V2-spezifische NOLOGIN-Rollen und minimale Tabellenrechte');

COMMIT;
