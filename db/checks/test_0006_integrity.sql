-- PostgreSQL-Integritaetstests fuer 0006. Transaktion wird immer ROLLBACK.
-- Nur gegen retro_rag_v2_test als rag_v2_migrator ausfuehren.
\set ON_ERROR_STOP on
BEGIN;
DO $tests$
DECLARE
  p uuid := gen_random_uuid();
  a uuid := gen_random_uuid();
  b uuid := gen_random_uuid();
  e1 uuid := gen_random_uuid();
  e2 uuid := gen_random_uuid();
  s1 uuid := gen_random_uuid();
  s2 uuid := gen_random_uuid();
  rel uuid := gen_random_uuid();
BEGIN
  IF current_database() <> 'retro_rag_v2_test'
     OR current_user <> 'rag_v2_migrator' THEN
    RAISE EXCEPTION '0006 Tests nur auf Test-DB als Migrator';
  END IF;
  IF NOT EXISTS(SELECT 1 FROM rag_v2.schema_migration WHERE version=6) THEN
    RAISE EXCEPTION 'Migration 0006 fehlt';
  END IF;
  -- Themen: Mehrfachverschachtelung zulassen, Zyklen abweisen.
  INSERT INTO rag_v2.knowledge_topic(id, name)
  VALUES (a, 'migration-0006-test-a'), (b, 'migration-0006-test-b');
  UPDATE rag_v2.knowledge_topic SET parent_id=a WHERE id=b;
  BEGIN
    UPDATE rag_v2.knowledge_topic SET parent_id=b WHERE id=a;
    RAISE EXCEPTION 'Zyklustest: unerwartet zugelassen';
  EXCEPTION WHEN raise_exception THEN
    IF SQLERRM = 'Zyklustest: unerwartet zugelassen' THEN RAISE; END IF;
    IF SQLERRM NOT LIKE '%zyklische Themenhierarchie%' THEN RAISE; END IF;
  END;

  -- Neue Entitaetstypen und Beziehungen pruefen.
  INSERT INTO rag_v2.reference_entity(id, entity_type, entity_key, name)
  VALUES (e1,'concept',e1::text,'test-concept-a'),
         (e2,'concept',e2::text,'test-concept-b');
  INSERT INTO rag_v2.knowledge_subject(id, reference_entity_id)
  VALUES (s1,e1), (s2,e2);
  INSERT INTO rag_v2.entity_relation(id, source_subject_id, target_subject_id,
                                     relation_type)
  VALUES (rel,s1,s2,'related_to');
  BEGIN
    UPDATE rag_v2.entity_relation SET status='accepted' WHERE id=rel;
    RAISE EXCEPTION 'Freigabetest: unerwartet zugelassen';
  EXCEPTION WHEN raise_exception THEN
    IF SQLERRM = 'Freigabetest: unerwartet zugelassen' THEN RAISE; END IF;
    IF SQLERRM NOT LIKE '%Freigabepolicy%' THEN RAISE; END IF;
  END;

  -- Bei geschlossenem Gate duerfen auch gueltige Vorschlaege nicht entstehen.
  IF (SELECT writes_enabled FROM rag_v2.write_gate WHERE id=true) THEN
    RAISE EXCEPTION 'Vor Test Write-Gate schliessen';
  END IF;
  BEGIN
    INSERT INTO rag_v2.knowledge_proposal (
      id, proposal_kind, origin_kind, payload, provenance, agent_run_key
    ) VALUES (
      p,'fact','agent','{"statement":"test"}','{"model":"test"}','test-run'
    );
    RAISE EXCEPTION 'Gate-Test: unerwartet zugelassen';
  EXCEPTION WHEN SQLSTATE '42501' THEN
    -- assert_import_write_gate() wirft explizit 42501, nicht P0001.
    IF SQLERRM NOT LIKE '%Schreibsperre ist geschlossen%' THEN RAISE; END IF;
  END;
  IF EXISTS (SELECT 1 FROM rag_v2.knowledge_proposal WHERE id=p) THEN
    RAISE EXCEPTION 'Gate-Test: Vorschlag trotz Sperre gespeichert';
  END IF;

  -- Gate NUR in dieser zurueckzurollenden Transaktion oeffnen.
  -- Vorschlagsdatensaetze sind auch dann unveraenderlich.
  UPDATE rag_v2.write_gate SET writes_enabled=true WHERE id=true;
  INSERT INTO rag_v2.knowledge_proposal(
    id, proposal_kind, origin_kind, payload, provenance, agent_run_key
  ) VALUES (
    p, 'fact','agent','{"statement":"test"}','{"model":"test"}','test-run'
  );
  BEGIN
    UPDATE rag_v2.knowledge_proposal
    SET payload='{"statement":"changed"}' WHERE id=p;
    RAISE EXCEPTION 'Unveraenderlichkeit: UPDATE zugelassen';
  EXCEPTION WHEN raise_exception THEN
    IF SQLERRM = 'Unveraenderlichkeit: UPDATE zugelassen' THEN RAISE; END IF;
    IF SQLERRM NOT LIKE '%Vorschläge sind unveränderlich%' THEN RAISE; END IF;
  END;
  BEGIN
    DELETE FROM rag_v2.knowledge_proposal WHERE id=p;
    RAISE EXCEPTION 'Unveraenderlichkeit: DELETE zugelassen';
  EXCEPTION WHEN raise_exception THEN
    IF SQLERRM = 'Unveraenderlichkeit: DELETE zugelassen' THEN RAISE; END IF;
    IF SQLERRM NOT LIKE '%Vorschläge sind unveränderlich%' THEN RAISE; END IF;
  END;
  UPDATE rag_v2.write_gate SET writes_enabled=false WHERE id=true;
  RAISE NOTICE '0006 Integritaetstests PASS (noch ROLLBACK erforderlich)';
END;
$tests$;
ROLLBACK;
