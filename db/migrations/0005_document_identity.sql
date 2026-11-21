-- Retro-RAG V2: Nextcloud-Instanzidentität und quellbezogene Eindeutigkeit.
\set ON_ERROR_STOP on
BEGIN;
DO $guard$
BEGIN
 IF current_database() NOT IN ('retro_rag_v2_test','retro_rag_v2') THEN
  RAISE EXCEPTION 'Keine V2-Datenbank';
 END IF;
 IF current_setting('server_version_num')::integer NOT BETWEEN 160000 AND 169999 THEN
  RAISE EXCEPTION 'PostgreSQL 16 erforderlich';
 END IF;
 IF current_user <> 'rag_v2_migrator' THEN
  RAISE EXCEPTION 'SET ROLE rag_v2_migrator erforderlich';
 END IF;
 IF NOT EXISTS (SELECT 1 FROM rag_v2.schema_migration WHERE version=4)
    OR EXISTS (SELECT 1 FROM rag_v2.schema_migration WHERE version=5) THEN
  RAISE EXCEPTION 'Migration 0004 fehlt oder 0005 ist bereits angewendet';
 END IF;
 -- Bestehende Nextcloud-IDs dürfen nicht blind einer Instanz zugeordnet werden.
 IF EXISTS (SELECT 1 FROM rag_v2.document_source WHERE source_system='nextcloud') THEN
  RAISE EXCEPTION 'Bestandsquellen vorhanden: Instanzzuordnung manuell migrieren, kein automatisches Backfill';
 END IF;
END;
$guard$;
SELECT pg_advisory_xact_lock(824020, 2);
ALTER TABLE rag_v2.document_source
 ADD COLUMN source_instance text;
ALTER TABLE rag_v2.document_source
 ADD CONSTRAINT document_source_instance_valid CHECK (
  source_system <> 'nextcloud' OR
  (source_instance IS NOT NULL AND btrim(source_instance) <> '')
 );
ALTER TABLE rag_v2.document_source
 DROP CONSTRAINT document_source_source_system_source_key_key;
-- Nicht-Nextcloud-Quellen behalten die bisherige Eindeutigkeit bei NULL.
CREATE UNIQUE INDEX document_source_identity_idx
 ON rag_v2.document_source (source_system, COALESCE(source_instance, ''), source_key);
INSERT INTO rag_v2.schema_migration (version,description)
 VALUES (5,'Nextcloud-Instanzidentität und sichere Dokument-Dublettenprüfung');
COMMIT;
