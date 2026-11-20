-- Struktur- und Berechtigungsprüfung für Migration 0006; keine DML.
\set ON_ERROR_STOP on
DO $verify$
DECLARE t text;
BEGIN
  IF current_database() NOT IN ('retro_rag_v2_test', 'retro_rag_v2') THEN
    RAISE EXCEPTION 'verify_0006: falsche Datenbank';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM rag_v2.schema_migration WHERE version=6) THEN
    RAISE EXCEPTION 'verify_0006: Versionsmarker fehlt';
  END IF;
  FOREACH t IN ARRAY ARRAY[
    'entity_type','knowledge_topic','knowledge_topic_assignment',
    'entity_relation','entity_relation_evidence','knowledge_proposal'
  ] LOOP
    IF to_regclass('rag_v2.' || t) IS NULL THEN
      RAISE EXCEPTION 'verify_0006: Tabelle % fehlt', t;
    END IF;
    IF has_table_privilege('rag_v2_importer', 'rag_v2.'||t, 'UPDATE')
       OR has_table_privilege('rag_v2_importer', 'rag_v2.'||t, 'DELETE') THEN
      RAISE EXCEPTION 'verify_0006: Importer kann % ändern/löschen', t;
    END IF;
  END LOOP;
  IF to_regclass('rag_v2.accepted_entity_relation') IS NULL THEN
    RAISE EXCEPTION 'verify_0006: bestätigte Reader-View fehlt';
  END IF;
  IF has_table_privilege('rag_v2_reader', 'rag_v2.entity_relation', 'SELECT')
    OR has_table_privilege('rag_v2_reader', 'rag_v2.knowledge_proposal', 'SELECT')
    OR NOT has_table_privilege('rag_v2_reader', 'rag_v2.accepted_entity_relation', 'SELECT')
  THEN
    RAISE EXCEPTION 'verify_0006: Reader-Grenze verletzt';
  END IF;
  IF NOT has_table_privilege('rag_v2_importer', 'rag_v2.knowledge_proposal', 'INSERT')
    OR has_table_privilege('rag_v2_importer', 'rag_v2.entity_relation', 'INSERT')
    OR has_table_privilege('rag_v2_importer', 'rag_v2.knowledge_proposal', 'SELECT')
  THEN
    RAISE EXCEPTION 'verify_0006: Importer-Rechte fehlerhaft';
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid='rag_v2.reference_entity'::regclass AND conname='reference_entity_type_fk'
  ) THEN
    RAISE EXCEPTION 'verify_0006: Entitaetstyp-FK fehlt';
  END IF;
  IF (SELECT count(*) FROM rag_v2.entity_type) < 15 THEN
    RAISE EXCEPTION 'verify_0006: Entitaetstyp-Katalog unvollstaendig';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_trigger
    WHERE tgrelid='rag_v2.knowledge_proposal'::regclass
      AND tgname='knowledge_proposal_write_gate' AND NOT tgisinternal)
  THEN
    RAISE EXCEPTION 'verify_0006: Gate-Trigger fehlt';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_trigger
    WHERE tgrelid='rag_v2.entity_relation'::regclass
      AND tgname='relation_no_approval_before_policy' AND NOT tgisinternal)
  THEN
    RAISE EXCEPTION 'verify_0006: Fail-closed-Freigabesperre fehlt';
  END IF;
  RAISE NOTICE 'verify_0006: Struktur und zentrale Rechte PASS';
END;
$verify$;
