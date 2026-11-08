-- Lesende Abnahme der Migration 0004; keine Testdaten und keine Gate-Änderung.
\set ON_ERROR_STOP on
DO $verify$
DECLARE
    v_owner text;
    v_definer boolean;
BEGIN
    IF current_database() NOT IN ('retro_rag_v2_test', 'retro_rag_v2') THEN
        RAISE EXCEPTION 'Keine V2-Datenbank';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM rag_v2.schema_migration WHERE version = 4) THEN
        RAISE EXCEPTION 'Migration 0004 fehlt';
    END IF;
    SELECT pg_get_userbyid(p.proowner), p.prosecdef
      INTO v_owner, v_definer
    FROM pg_proc p
    WHERE p.oid = 'rag_v2.assert_import_write_gate()'::regprocedure;
    IF v_owner IS DISTINCT FROM 'rag_v2_migrator' OR v_definer IS DISTINCT FROM true THEN
        RAISE EXCEPTION 'Definer oder Eigentümer der Gate-Funktion falsch';
    END IF;
    IF NOT has_function_privilege('rag_v2_importer_login',
                                 'rag_v2.assert_import_write_gate()', 'EXECUTE')
       OR has_function_privilege('PUBLIC',
                                'rag_v2.assert_import_write_gate()', 'EXECUTE')
       OR has_table_privilege('rag_v2_importer_login','rag_v2.write_gate','UPDATE')
       OR has_table_privilege('rag_v2_importer_login','rag_v2.write_gate','DELETE')
       OR has_table_privilege('rag_v2_importer_login','rag_v2.write_gate','INSERT')
       OR NOT has_table_privilege('rag_v2_importer_login','rag_v2.write_gate','SELECT')
    THEN
        RAISE EXCEPTION 'Importer besitzt unerwartete Gate-Berechtigungen';
    END IF;
    RAISE NOTICE '0004: SECURITY DEFINER, EXECUTE, Gate-DML-Sperre geprüft';
END;
$verify$;
