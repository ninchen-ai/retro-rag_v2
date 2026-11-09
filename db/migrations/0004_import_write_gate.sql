-- Retro-RAG V2: atomare Import-Schreibsperrenprüfung ohne UPDATE-Rechte am Gate.
-- Vorwärtsmigration nur für eine vorhandene V2-Datenbank.
\set ON_ERROR_STOP on
BEGIN;

DO $guard$
BEGIN
    IF current_database() NOT IN ('retro_rag_v2_test', 'retro_rag_v2') THEN
        RAISE EXCEPTION 'Schutzabbruch: keine V2-Datenbank: %', current_database();
    END IF;
    IF current_setting('server_version_num')::integer NOT BETWEEN 160000 AND 169999 THEN
        RAISE EXCEPTION 'Schutzabbruch: PostgreSQL 16 erforderlich';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM rag_v2.schema_migration WHERE version = 3)
       OR EXISTS (SELECT 1 FROM rag_v2.schema_migration WHERE version = 4) THEN
        RAISE EXCEPTION 'Migration 0003 fehlt oder 0004 ist bereits registriert';
    END IF;
    IF current_user <> 'rag_v2_migrator' THEN
        RAISE EXCEPTION '0004 muss mit SET ROLE rag_v2_migrator ausgeführt werden';
    END IF;
END;
$guard$;

SELECT pg_advisory_xact_lock(824020, 2);

-- SECURITY DEFINER besitzt die erforderlichen UPDATE/Lock-Rechte über
-- rag_v2_migrator, nicht über die Importer-Rolle.
-- Der Aufruf muss innerhalb derselben Transaktion wie die DML erfolgen.
CREATE FUNCTION rag_v2.assert_import_write_gate()
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, rag_v2
AS $func$
DECLARE
    v_enabled boolean;
BEGIN
    SELECT writes_enabled INTO v_enabled
    FROM rag_v2.write_gate
    WHERE id = true
    FOR SHARE;

    IF v_enabled IS DISTINCT FROM true THEN
        RAISE EXCEPTION 'V2-Schreibsperre ist geschlossen'
            USING ERRCODE = '42501';
    END IF;
END;
$func$;

-- Kein implizites EXECUTE für PUBLIC, keine Gate-DML für Importer.
REVOKE ALL ON FUNCTION rag_v2.assert_import_write_gate() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION rag_v2.assert_import_write_gate() TO rag_v2_importer;

INSERT INTO rag_v2.schema_migration (version, description)
VALUES (4, 'Transaktionale Write-Gate-Prüfung für Importer ohne Gate-UPDATE');

COMMIT;
