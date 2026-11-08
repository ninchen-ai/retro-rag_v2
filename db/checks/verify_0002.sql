-- Rein lesender Berechtigungscheck für Migration 0002.
\set ON_ERROR_STOP on
DO $verify$
DECLARE
    v_role text;
BEGIN
    IF current_database() NOT IN ('retro_rag_v2', 'retro_rag_v2_test') THEN
        RAISE EXCEPTION 'Schutzabbruch: falsche Datenbank %', current_database();
    END IF;
    IF NOT EXISTS (SELECT 1 FROM rag_v2.schema_migration WHERE version = 2) THEN
        RAISE EXCEPTION 'Migration 0002 ist nicht registriert';
    END IF;
    FOREACH v_role IN ARRAY ARRAY[
        'rag_v2_migrator', 'rag_v2_importer', 'rag_v2_reviewer',
        'rag_v2_inventory', 'rag_v2_reader',
        'rag_v2_lifecycle', 'rag_v2_query_logger'
    ]
    LOOP
        IF NOT EXISTS (
            SELECT 1 FROM pg_roles
            WHERE rolname = v_role AND NOT rolcanlogin
              AND NOT rolsuper AND NOT rolcreatedb AND NOT rolcreaterole
        ) THEN
            RAISE EXCEPTION 'Rolle % fehlt oder hat zu hohe Rechte', v_role;
        END IF;
    END LOOP;
    IF NOT has_table_privilege('rag_v2_reader', 'rag_v2.document', 'SELECT')
        OR has_table_privilege('rag_v2_reader', 'rag_v2.document', 'INSERT')
        OR has_table_privilege('rag_v2_reader', 'rag_v2.fact', 'UPDATE')
        OR has_table_privilege('rag_v2_reader', 'rag_v2.query_log', 'INSERT')
        OR has_table_privilege('rag_v2_importer', 'rag_v2.fact', 'INSERT')
        OR has_table_privilege('rag_v2_importer', 'rag_v2.trusted_source', 'UPDATE')
        OR has_table_privilege('rag_v2_importer', 'rag_v2.write_gate', 'UPDATE')
        OR has_table_privilege('rag_v2_inventory', 'rag_v2.document', 'UPDATE')
        OR has_table_privilege('rag_v2_reviewer', 'rag_v2.unit', 'UPDATE')
        OR NOT has_table_privilege('rag_v2_inventory', 'rag_v2.unit', 'UPDATE')
        OR NOT has_table_privilege('rag_v2_reviewer', 'rag_v2.review_decision', 'INSERT')
        OR has_table_privilege('rag_v2_reviewer', 'rag_v2.review_decision', 'UPDATE')
        OR NOT has_table_privilege('rag_v2_query_logger', 'rag_v2.query_log', 'INSERT')
        OR has_table_privilege('rag_v2_query_logger', 'rag_v2.query_log', 'SELECT')
        OR has_table_privilege('rag_v2_lifecycle', 'rag_v2.fact', 'DELETE')
        OR NOT has_table_privilege('rag_v2_lifecycle', 'rag_v2.chunk', 'DELETE')
    THEN
        RAISE EXCEPTION 'Mindestens eine erwartete Tabellenberechtigung stimmt nicht';
    END IF;
    RAISE NOTICE '0002: Sieben NOLOGIN-Rollen und zentrale Tabellenberechtigungen geprüft';
END;
$verify$;

SELECT rolname, rolcanlogin, rolsuper, rolcreatedb
FROM pg_roles
WHERE rolname LIKE 'rag_v2_%'
ORDER BY rolname;

-- WICHTIG: CONNECT auf V1 kann über PUBLIC erlaubt bleiben.
-- Die neue Rollen-ACL allein garantiert deshalb noch keine harte V1-Abschirmung!
SELECT datname,
       has_database_privilege('rag_v2_reader', datname, 'CONNECT') AS reader_can_connect
FROM pg_database
WHERE datname IN ('retro_rag', 'retro_rag_test', 'retro_rag_v2_test', 'retro_rag_v2')
ORDER BY datname;
