-- Retro-RAG V2: Rollenarchitektur, Eigentümerschaft und sichere Login-Vorbereitung.
-- Nur in retro_rag_v2_test bzw. retro_rag_v2 ausführen.
-- V1-Datenbanken, Nextcloud, bestehende Anmeldungen und pg_hba.conf bleiben unverändert.
-- Voraussetzung: 0001 und 0002 erfolgreich angewendet.
\set ON_ERROR_STOP on
BEGIN;

DO $guard$
DECLARE
    v_owner name;
BEGIN
    IF current_database() NOT IN ('retro_rag_v2_test', 'retro_rag_v2') THEN
        RAISE EXCEPTION 'Schutzabbruch: Datenbank % ist keine Retro-RAG-V2-Datenbank', current_database();
    END IF;
    IF current_setting('server_version_num')::integer NOT BETWEEN 160000 AND 169999 THEN
        RAISE EXCEPTION 'Schutzabbruch: PostgreSQL 16 erforderlich';
    END IF;
    IF to_regclass('rag_v2.schema_migration') IS NULL THEN
        RAISE EXCEPTION 'Schutzabbruch: Migration 0001 fehlt';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM rag_v2.schema_migration WHERE version = 1)
       OR NOT EXISTS (SELECT 1 FROM rag_v2.schema_migration WHERE version = 2)
       OR EXISTS (SELECT 1 FROM rag_v2.schema_migration WHERE version = 3) THEN
        RAISE EXCEPTION 'Schutzabbruch: benötigte Migrationen fehlen oder 0003 ist schon vorhanden';
    END IF;
    IF NOT (SELECT rolsuper FROM pg_roles WHERE rolname = current_user) THEN
        RAISE EXCEPTION '0003 benötigt einen administrativen Migrationszugang (Superuser)';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_roles
        WHERE rolname = 'rag_v2_migrator'
          AND NOT rolcanlogin AND NOT rolsuper AND NOT rolcreatedb AND NOT rolcreaterole
    ) THEN
        RAISE EXCEPTION 'Migrations-Eigentümergruppe fehlt oder ist zu privilegiert';
    END IF;
    SELECT pg_get_userbyid(n.nspowner) INTO v_owner
    FROM pg_namespace n WHERE n.nspname = 'rag_v2';
    IF v_owner <> current_user THEN
        RAISE EXCEPTION 'Schema gehört %, erwartet %', v_owner, current_user;
    END IF;
    IF EXISTS (
        SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'rag_v2' AND c.relkind IN ('r', 'p', 'S', 'v', 'm', 'f')
          AND pg_get_userbyid(c.relowner) <> current_user
    ) OR EXISTS (
        SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = 'rag_v2' AND pg_get_userbyid(p.proowner) <> current_user
    ) THEN
        RAISE EXCEPTION 'Unerwartete Besitzer im V2-Schema; keine automatische Übernahme';
    END IF;
END;
$guard$;

SELECT pg_advisory_xact_lock(824020, 2);

-- Die spätere App erhält eigene Login-Identitäten, die JETZT noch NOLOGIN sind.
-- Bereits vorhandene deaktivierte V2-Logins werden streng geprüft und wiederverwendet.
-- Ein aktiviertes Login braucht zusätzlich ein starkes Passwort und wirksame
-- HBA-Regeln, welche V1-Verbindungen für genau diese Konten verhindern.
DO $roles$
DECLARE
    v_role text;
BEGIN
    FOREACH v_role IN ARRAY ARRAY[
        'rag_v2_importer_login',
        'rag_v2_reviewer_login',
        'rag_v2_inventory_login',
        'rag_v2_reader_login',
        'rag_v2_lifecycle_login',
        'rag_v2_query_logger_login',
        'rag_v2_migrator_login'
    ] LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = v_role) THEN
            -- Bei späterer V2-Produktiv-DB sind dieselben Clusterrollen schon
            -- durch den erfolgreichen Testdatenbanklauf vorhanden.
            -- Bestehende Rollen nur nach strenger Prüfung wiederverwenden.
            IF NOT EXISTS (
                SELECT 1 FROM pg_roles
                WHERE rolname = v_role AND NOT rolcanlogin AND NOT rolsuper
                  AND NOT rolcreatedb AND NOT rolcreaterole AND NOT rolreplication
            ) THEN
                RAISE EXCEPTION 'Bestehende Rolle % ist nicht sicher deaktiviert', v_role;
            END IF;
        ELSE
            EXECUTE format(
                'CREATE ROLE %I NOLOGIN PASSWORD NULL INHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION',
                v_role
            );
        END IF;
    END LOOP;
END;
$roles$;

GRANT rag_v2_importer TO rag_v2_importer_login WITH INHERIT TRUE, SET FALSE;
GRANT rag_v2_reviewer TO rag_v2_reviewer_login WITH INHERIT TRUE, SET FALSE;
GRANT rag_v2_inventory TO rag_v2_inventory_login WITH INHERIT TRUE, SET FALSE;
GRANT rag_v2_reader TO rag_v2_reader_login WITH INHERIT TRUE, SET FALSE;
GRANT rag_v2_lifecycle TO rag_v2_lifecycle_login WITH INHERIT TRUE, SET FALSE;
GRANT rag_v2_query_logger TO rag_v2_query_logger_login WITH INHERIT TRUE, SET FALSE;
-- Die Migrationsidentität darf ihre Eigentümerrolle gezielt übernehmen.
GRANT rag_v2_migrator TO rag_v2_migrator_login WITH INHERIT TRUE, SET TRUE;

-- Schema- und Objekt-Eigentum: DDL später ohne Superuser möglich.
-- Objektgrants von 0002 bleiben beim Eigentümerwechsel erhalten.
DO $ownership$
DECLARE
    v_obj record;
BEGIN
    FOR v_obj IN
        SELECT c.relkind, c.relname
        FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'rag_v2'
          AND c.relkind IN ('r', 'p', 'S', 'v', 'm', 'f')
        ORDER BY c.relname
    LOOP
        IF v_obj.relkind = 'S' THEN
            EXECUTE format('ALTER SEQUENCE rag_v2.%I OWNER TO rag_v2_migrator', v_obj.relname);
        ELSIF v_obj.relkind = 'v' THEN
            EXECUTE format('ALTER VIEW rag_v2.%I OWNER TO rag_v2_migrator', v_obj.relname);
        ELSIF v_obj.relkind = 'm' THEN
            EXECUTE format('ALTER MATERIALIZED VIEW rag_v2.%I OWNER TO rag_v2_migrator', v_obj.relname);
        ELSIF v_obj.relkind = 'f' THEN
            EXECUTE format('ALTER FOREIGN TABLE rag_v2.%I OWNER TO rag_v2_migrator', v_obj.relname);
        ELSE
            EXECUTE format('ALTER TABLE rag_v2.%I OWNER TO rag_v2_migrator', v_obj.relname);
        END IF;
    END LOOP;
    FOR v_obj IN
        SELECT p.proname,
               pg_get_function_identity_arguments(p.oid) AS args,
               p.prokind
        FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = 'rag_v2'
    LOOP
        IF v_obj.prokind = 'p' THEN
            EXECUTE format('ALTER PROCEDURE rag_v2.%I(%s) OWNER TO rag_v2_migrator',
                v_obj.proname, v_obj.args);
        ELSE
            EXECUTE format('ALTER FUNCTION rag_v2.%I(%s) OWNER TO rag_v2_migrator',
                v_obj.proname, v_obj.args);
        END IF;
    END LOOP;
END;
$ownership$;
ALTER SCHEMA rag_v2 OWNER TO rag_v2_migrator;

-- Künftige Objekte müssen bewusst in nachfolgenden Migrationen freigegeben
-- werden; KEIN pauschales DEFAULT PRIVILEGES für alle zukünftigen Tabellen.
-- Migrationsanwendungen setzen bevorzugt SET ROLE rag_v2_migrator.
INSERT INTO rag_v2.schema_migration (version, description)
VALUES (3, 'V2-Loginidentitäten deaktiviert vorbereitet; Schema- und Objektbesitz konsolidiert');

COMMIT;
