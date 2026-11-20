-- Negative Integritätstests für 0006, alle Änderungen zurückrollen.
-- Als rag_v2_migrator gegen retro_rag_v2_test ausführen.
\set ON_ERROR_STOP on
BEGIN;
DO $tests$
DECLARE
  p uuid := gen_random_uuid();
  a uuid := gen_random_uuid();
  b uuid := gen_random_uuid();
BEGIN
  IF current_database() <> 'retro_rag_v2_test'
     OR current_user <> 'rag_v2_migrator' THEN
    RAISE EXCEPTION '0006 Tests nur auf Test-DB als Migrator';
  END IF;
  IF NOT EXISTS(SELECT 1 FROM rag_v2.schema_migration WHERE version=6) THEN
    RAISE EXCEPTION 'Migration 0006 fehlt';
  END IF;

  INSERT INTO rag_v2.knowledge_topic(id, name) VALUES (a, 'migration-0006-test-a'), (b, 'migration-0006-test-b');
  UPDATE rag_v2.knowledge_topic SET parent_id=a WHERE id=b;
  BEGIN
    UPDATE rag_v2.knowledge_topic SET parent_id=b WHERE id=a;
    RAISE EXCEPTION 'Zyklustest: unerwartet zugelassen';
  EXCEPTION WHEN raise_exception THEN
    IF SQLERRM = 'Zyklustest: unerwartet zugelassen' THEN RAISE; END IF;
    IF SQLERRM NOT LIKE '%zyklische Themenhierarchie%' THEN RAISE; END IF;
  END;

  -- Bei geschlossenem Gate darf selbst ein gültiger Proposal-INSERT
  -- durch die Import-Gate-Prüfung nicht wirksam werden.
  IF (SELECT writes_enabled FROM rag_v2.write_gate WHERE id=true) THEN
    RAISE EXCEPTION 'Vor Test Write-Gate schließen';
  END IF;
  BEGIN
    INSERT INTO rag_v2.knowledge_proposal (
      id, proposal_kind, origin_kind, payload, provenance,
      agent_run_key
    ) VALUES (
      p, 'fact','agent','{"statement":"test"}','{"model":"test"}','test-run'
    );
    RAISE EXCEPTION 'Gate-Test: unerwartet zugelassen';
  EXCEPTION WHEN raise_exception THEN
    IF SQLERRM = 'Gate-Test: unerwartet zugelassen' THEN RAISE; END IF;
    IF SQLERRM NOT LIKE '%Schreibsperre ist geschlossen%' THEN RAISE; END IF;
  END;
  IF EXISTS (SELECT 1 FROM rag_v2.knowledge_proposal WHERE id=p) THEN
    RAISE EXCEPTION 'Gate-Test: persistierter Vorschlag trotz Sperre';
  END IF;
  RAISE NOTICE '0006 negative Integritaetstests PASS (mit ROLLBACK)';
END
$tests$;
ROLLBACK;
