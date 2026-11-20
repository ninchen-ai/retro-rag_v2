-- 0006: Rollengrenzen innerhalb EINER externen Testtransaktion pruefen.
-- Keine eigenen BEGIN/COMMIT/ROLLBACK! In den transaktionalen
-- 0006-Testrunner NACH Migration und verify_0006 einbinden.
-- Verwenden von SET ROLE ist kein Ersatz fuer echte Login-/HBA-Tests.
\set ON_ERROR_STOP on

DO $setup$
DECLARE
  entity_a uuid := gen_random_uuid();
  entity_b uuid := gen_random_uuid();
  subject_a uuid := gen_random_uuid();
  subject_b uuid := gen_random_uuid();
BEGIN
  IF current_database() <> 'retro_rag_v2_test'
     OR current_user <> 'rag_v2_migrator' THEN
    RAISE EXCEPTION '0006 Rollentest nur auf V2-Test-DB als Migrator starten';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM rag_v2.schema_migration WHERE version = 6) THEN
    RAISE EXCEPTION '0006 Rollentest: Migration fehlt';
  END IF;
  IF (SELECT writes_enabled FROM rag_v2.write_gate WHERE id=true) IS DISTINCT FROM false THEN
    RAISE EXCEPTION '0006 Rollentest: geschlossenes Write-Gate erforderlich';
  END IF;
  INSERT INTO rag_v2.reference_entity(id, entity_type, entity_key, name)
  VALUES (entity_a,'concept',entity_a::text,'0006-test-entity-a'),
         (entity_b,'concept',entity_b::text,'0006-test-entity-b');
  INSERT INTO rag_v2.knowledge_subject(id, reference_entity_id)
  VALUES (subject_a,entity_a),(subject_b,entity_b);
  PERFORM set_config('rag_v2.test_0006_subject_a', subject_a::text, true);
  PERFORM set_config('rag_v2.test_0006_subject_b', subject_b::text, true);
END;
$setup$;

SET ROLE rag_v2_importer;
DO $importer$
DECLARE
  n bigint;
BEGIN
  IF current_user <> 'rag_v2_importer' THEN
    RAISE EXCEPTION 'Importer: aktuelle Rolle falsch';
  END IF;
  BEGIN
    INSERT INTO rag_v2.knowledge_proposal (
      proposal_kind, origin_kind, payload, provenance, agent_run_key
    ) VALUES ('fact','agent','{"statement":"rollentest"}',
              '{"model":"test"}','test-0006');
    RAISE EXCEPTION 'Importer: Write-Gate unerwartet umgangen';
  EXCEPTION WHEN SQLSTATE '42501' THEN
    IF SQLERRM NOT LIKE '%Schreibsperre ist geschlossen%' THEN RAISE; END IF;
  END;
  BEGIN
    SELECT count(*) INTO n FROM rag_v2.knowledge_proposal;
    RAISE EXCEPTION 'Importer: Proposal-SELECT unerwartet erlaubt';
  EXCEPTION WHEN SQLSTATE '42501' THEN NULL;
  END;
  BEGIN
    INSERT INTO rag_v2.entity_relation(
      source_subject_id, target_subject_id, relation_type
    ) VALUES (
      current_setting('rag_v2.test_0006_subject_a')::uuid,
      current_setting('rag_v2.test_0006_subject_b')::uuid, 'related_to'
    );
    RAISE EXCEPTION 'Importer: direkte Relation unerwartet erlaubt';
  EXCEPTION WHEN SQLSTATE '42501' THEN NULL;
  END;
  RAISE NOTICE '0006 role: importer PASS';
END;
$importer$;

SET ROLE rag_v2_reader;
DO $reader$
DECLARE
  n bigint;
BEGIN
  IF current_user <> 'rag_v2_reader' THEN
    RAISE EXCEPTION 'Reader: aktuelle Rolle falsch';
  END IF;
  SELECT count(*) INTO n FROM rag_v2.accepted_entity_relation;
  IF n <> 0 THEN RAISE EXCEPTION 'Reader: unerwartete freigegebene Beziehungen'; END IF;
  BEGIN
    SELECT count(*) INTO n FROM rag_v2.entity_relation;
    RAISE EXCEPTION 'Reader: direkte Relation unerwartet lesbar';
  EXCEPTION WHEN SQLSTATE '42501' THEN NULL;
  END;
  BEGIN
    SELECT count(*) INTO n FROM rag_v2.knowledge_proposal;
    RAISE EXCEPTION 'Reader: Proposal unerwartet lesbar';
  EXCEPTION WHEN SQLSTATE '42501' THEN NULL;
  END;
  RAISE NOTICE '0006 role: reader PASS';
END;
$reader$;

SET ROLE rag_v2_reviewer;
DO $reviewer$
DECLARE
  rel uuid := gen_random_uuid();
BEGIN
  IF current_user <> 'rag_v2_reviewer' THEN
    RAISE EXCEPTION 'Reviewer: aktuelle Rolle falsch';
  END IF;
  INSERT INTO rag_v2.entity_relation(
    id, source_subject_id, target_subject_id, relation_type
  ) VALUES (
    rel,
    current_setting('rag_v2.test_0006_subject_a')::uuid,
    current_setting('rag_v2.test_0006_subject_b')::uuid,
    'related_to'
  );
  PERFORM rag_v2.validate_accepted_entity_relation(rel);
  BEGIN
    UPDATE rag_v2.entity_relation SET status='accepted' WHERE id=rel;
    RAISE EXCEPTION 'Reviewer: Freigabe unerwartet erlaubt';
  EXCEPTION WHEN raise_exception THEN
    IF SQLERRM = 'Reviewer: Freigabe unerwartet erlaubt' THEN RAISE; END IF;
    IF SQLERRM NOT LIKE '%Freigabepolicy%' THEN RAISE; END IF;
  END;
  RAISE NOTICE '0006 role: reviewer PASS';
END;
$reviewer$;

SET ROLE rag_v2_migrator;
DO $final$
BEGIN
  IF current_user <> 'rag_v2_migrator' THEN
    RAISE EXCEPTION '0006 Rollentest: Migrator-Rolle nicht wiederhergestellt';
  END IF;
  RAISE NOTICE '0006 Rollengrenzen PASS (noch ROLLBACK erforderlich)';
END;
$final$;
