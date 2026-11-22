-- Lesende Prüfung von Migration 0005.
\set ON_ERROR_STOP on
DO $verify$
BEGIN
 IF current_database() NOT IN ('retro_rag_v2_test','retro_rag_v2')
    OR NOT EXISTS (SELECT 1 FROM rag_v2.schema_migration WHERE version=5) THEN
  RAISE EXCEPTION '0005 nicht korrekt registriert';
 END IF;
 IF NOT EXISTS (
  SELECT 1 FROM pg_indexes WHERE schemaname='rag_v2'
   AND tablename='document_source' AND indexname='document_source_identity_idx'
 ) THEN RAISE EXCEPTION 'Instanzidentitätsindex fehlt'; END IF;
 IF NOT EXISTS (
  SELECT 1 FROM pg_constraint WHERE conname='document_source_instance_valid'
 ) THEN RAISE EXCEPTION 'Nextcloud-Instanzpflicht fehlt'; END IF;
 IF NOT has_table_privilege('rag_v2_importer_login','rag_v2.document_source','INSERT')
    OR has_table_privilege('rag_v2_importer_login','rag_v2.write_gate','UPDATE') THEN
  RAISE EXCEPTION 'Importer-Berechtigungen unerwartet';
 END IF;
 RAISE NOTICE '0005: Instanzkennung, Identitätsindex, Berechtigungen geprüft';
END;
$verify$;
