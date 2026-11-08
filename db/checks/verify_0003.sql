-- Nur lesende Prüfung nach Migration 0003, keine Testdatensätze.
\set ON_ERROR_STOP on
DO $verify$
DECLARE
    v_role text;
    v_count integer;
BEGIN
    IF current_database() NOT IN ('retro_rag_v2', 'retro_rag_v2_test') THEN
        RAISE EXCEPTION 'Schutzabbruch: falsche Datenbank %', current_database();
    END IF;
    IF NOT EXISTS (SELECT 1 FROM rag_v2.schema_migration WHERE version = 3) THEN
        RAISE EXCEPTION 'Migration 0003 fehlt';
    END IF;
    IF (SELECT pg_get_userbyid(nspowner) FROM pg_namespace WHERE nspname = 'rag_v2')
       <> 'rag_v2_migrator' THEN
        RAISE EXCEPTION 'Schema-Eigentümer stimmt nicht';
    END IF;
    SELECT count(*) INTO v_count
    FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'rag_v2' AND c.relkind IN ('r','p','S','v','m','f')
      AND pg_get_userbyid(c.relowner) <> 'rag_v2_migrator';
    IF v_count <> 0 THEN
        RAISE EXCEPTION '% V2-Relationen haben falschen Eigentümer', v_count;
    END IF;
    SELECT count(*) INTO v_count
    FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
    WHERE n.nspname = 'rag_v2'
      AND pg_get_userbyid(p.proowner) <> 'rag_v2_migrator';
    IF v_count <> 0 THEN
        RAISE EXCEPTION '% V2-Funktionen haben falschen Eigentümer', v_count;
    END IF;
    FOREACH v_role IN ARRAY ARRAY[
        'importer', 'reviewer', 'inventory', 'reader',
        'lifecycle', 'query_logger', 'migrator'
    ] LOOP
        IF NOT EXISTS (
            SELECT 1 FROM pg_roles p
            WHERE p.rolname = 'rag_v2_' || v_role || '_login'
              AND NOT p.rolcanlogin AND NOT p.rolsuper
              AND NOT p.rolcreatedb AND NOT p.rolcreaterole
              AND NOT p.rolreplication
        ) THEN
            RAISE EXCEPTION 'Rolle rag_v2_%_login fehlt oder ist schon aktiviert', v_role;
        END IF;
        IF NOT EXISTS (
            SELECT 1
            FROM pg_auth_members m
            JOIN pg_roles g ON g.oid = m.roleid
            JOIN pg_roles p ON p.oid = m.member
            WHERE g.rolname = 'rag_v2_' || v_role
              AND p.rolname = 'rag_v2_' || v_role || '_login'
              AND m.inherit_option
              AND m.set_option = (v_role = 'migrator')
              AND NOT m.admin_option
        ) THEN
            RAISE EXCEPTION 'Rollenzuordnung für % fehlt oder ist zu weitgehend', v_role;
        END IF;
    END LOOP;

    IF has_table_privilege('rag_v2_reader_login','rag_v2.fact','INSERT')
       OR has_table_privilege('rag_v2_reader_login','rag_v2.fact','UPDATE')
       OR has_table_privilege('rag_v2_importer_login','rag_v2.fact','INSERT')
       OR has_table_privilege('rag_v2_inventory_login','rag_v2.document','UPDATE')
       OR has_table_privilege('rag_v2_reviewer_login','rag_v2.unit','UPDATE')
       OR has_table_privilege('rag_v2_reader_login','rag_v2.write_gate','UPDATE')
       OR NOT has_table_privilege('rag_v2_reader_login','rag_v2.fact','SELECT')
       OR NOT has_table_privilege('rag_v2_reviewer_login','rag_v2.review_decision','INSERT')
    THEN
        RAISE EXCEPTION 'Unzulässige oder fehlende effektive Rechte bei V2-Loginrollen';
    END IF;

    IF (SELECT writes_enabled FROM rag_v2.write_gate WHERE id = true) IS DISTINCT FROM false THEN
        RAISE EXCEPTION 'Schreibsperre unerwartet deaktiviert';
    END IF;

    RAISE NOTICE '0003: Eigentümer, sieben deaktivierte Logins, Mitgliedschaften und Rechte geprüft';
END;
$verify$;

SELECT current_database() AS database_name,
       (SELECT max(version) FROM rag_v2.schema_migration) AS schema_version,
       (SELECT pg_get_userbyid(nspowner) FROM pg_namespace WHERE nspname='rag_v2') AS schema_owner,
       (SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
         WHERE n.nspname='rag_v2' AND c.relkind='r') AS tables;

SELECT rolname, rolcanlogin, rolsuper, rolcreatedb, rolcreaterole
FROM pg_roles WHERE rolname LIKE 'rag_v2_%_login' ORDER BY rolname;

-- Nur zur Diagnose: PUBLIC CONNECT auf V1 ist weiterhin möglich.
-- Vor Login-Aktivierung muss HBA gezielt pro V2-Login angepasst sein.
SELECT datname, has_database_privilege('rag_v2_reader_login', datname, 'CONNECT') AS can_connect
FROM pg_database
WHERE datname IN ('retro_rag', 'retro_rag_test', 'retro_rag_v2_test', 'retro_rag_v2')
ORDER BY datname;
