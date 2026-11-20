-- Retro-RAG V2: universeller Wissenskern, additive Strukturmigration 0006.
-- ENTWURF: vor einer Anwendung reviewen und auf Poseidon testen.
-- Ausführung nur in genehmigter V2-Datenbank, als rag_v2_migrator.
\set ON_ERROR_STOP on
BEGIN;
DO $guard$
BEGIN
  IF current_database() NOT IN ('retro_rag_v2_test', 'retro_rag_v2') THEN
    RAISE EXCEPTION '0006: keine freigegebene V2-Datenbank';
  END IF;
  IF current_setting('server_version_num')::integer NOT BETWEEN 160000 AND 169999 THEN
    RAISE EXCEPTION '0006: PostgreSQL 16 erforderlich';
  END IF;
  IF current_user <> 'rag_v2_migrator' THEN
    RAISE EXCEPTION '0006: SET ROLE rag_v2_migrator erforderlich';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM rag_v2.schema_migration WHERE version = 5)
     OR EXISTS (SELECT 1 FROM rag_v2.schema_migration WHERE version = 6) THEN
    RAISE EXCEPTION '0006: Migration 0005 fehlt oder 0006 bereits registriert';
  END IF;
  IF (SELECT count(*) FROM rag_v2.schema_migration WHERE version BETWEEN 1 AND 5) <> 5 THEN
    RAISE EXCEPTION '0006: unvollständige Migrationshistorie';
  END IF;
END
$guard$;

SELECT pg_advisory_xact_lock(824020, 2);

-- 1. Erweiterbarer Typkatalog, alte Codes unverändert übernehmen.
CREATE TABLE rag_v2.entity_type (
  code text PRIMARY KEY CHECK (code ~ '^[a-z][a-z0-9_]*$'),
  name text NOT NULL CHECK (btrim(name) <> ''),
  description text,
  enabled boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now()
);
INSERT INTO rag_v2.entity_type(code, name)
VALUES
  ('interface', 'Interface'), ('chipset', 'Chipset'),
  ('software', 'Software'), ('driver', 'Driver'),
  ('graphics_api', 'Graphics API'), ('standard', 'Standard'),
  ('other', 'Other'),
  ('person', 'Person'), ('place', 'Place'),
  ('organization', 'Organization'), ('event', 'Event'),
  ('concept', 'Concept'), ('technology', 'Technology'),
  ('product', 'Product'), ('publication', 'Publication');

-- Vorhandene Referenz-Entitäten werden nicht geändert; der neue FK validiert sie.
ALTER TABLE rag_v2.reference_entity
  DROP CONSTRAINT reference_entity_entity_type_check;
ALTER TABLE rag_v2.reference_entity
  ADD CONSTRAINT reference_entity_type_fk
  FOREIGN KEY (entity_type) REFERENCES rag_v2.entity_type(code)
  ON UPDATE RESTRICT ON DELETE RESTRICT;

-- 2. Themen sind KEINE knowledge_subjects. Beliebige Mehrfachzuordnung.
CREATE TABLE rag_v2.knowledge_topic (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  parent_id uuid REFERENCES rag_v2.knowledge_topic(id) ON DELETE RESTRICT,
  name text NOT NULL CHECK (btrim(name) <> ''),
  description text,
  created_at timestamptz NOT NULL DEFAULT now(),
  CHECK (parent_id IS DISTINCT FROM id),
  UNIQUE NULLS NOT DISTINCT (parent_id, name)
);

CREATE FUNCTION rag_v2.reject_topic_cycle()
RETURNS trigger LANGUAGE plpgsql SET search_path = pg_catalog, rag_v2 AS $fn$
BEGIN
  IF NEW.parent_id IS NULL THEN RETURN NEW; END IF;
  -- Parent-Änderungen serialisieren; parallele umgekehrte Umhängungen
  -- dürfen ohne gemeinsame Serialisierung keine Zyklen erzeugen.
  PERFORM pg_advisory_xact_lock(824020, 6);
  IF EXISTS (
    WITH RECURSIVE ancestry(id, parent_id) AS (
      SELECT t.id, t.parent_id
      FROM rag_v2.knowledge_topic t WHERE t.id = NEW.parent_id
      UNION
      SELECT t.id, t.parent_id
      FROM rag_v2.knowledge_topic t
      JOIN ancestry a ON t.id = a.parent_id
    )
    SELECT 1 FROM ancestry WHERE id = NEW.id
  ) THEN
    RAISE EXCEPTION '0006: zyklische Themenhierarchie';
  END IF;
  RETURN NEW;
END
$fn$;
CREATE TRIGGER topic_no_cycle
  BEFORE INSERT OR UPDATE OF parent_id ON rag_v2.knowledge_topic
  FOR EACH ROW EXECUTE FUNCTION rag_v2.reject_topic_cycle();

CREATE TABLE rag_v2.knowledge_topic_assignment (
  topic_id uuid NOT NULL REFERENCES rag_v2.knowledge_topic(id) ON DELETE RESTRICT,
  subject_id uuid NOT NULL REFERENCES rag_v2.knowledge_subject(id) ON DELETE RESTRICT,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (topic_id, subject_id)
);
CREATE INDEX knowledge_topic_assignment_subject_idx
  ON rag_v2.knowledge_topic_assignment(subject_id);

-- 3. Universelle Beziehungen neben fachlicher compatibility_rule.
CREATE TABLE rag_v2.entity_relation (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source_subject_id uuid NOT NULL REFERENCES rag_v2.knowledge_subject(id) ON DELETE RESTRICT,
  target_subject_id uuid NOT NULL REFERENCES rag_v2.knowledge_subject(id) ON DELETE RESTRICT,
  relation_type text NOT NULL CHECK (relation_type ~ '^[a-z][a-z0-9_]*$'),
  context jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(context) = 'object'),
  status text NOT NULL DEFAULT 'proposed'
    CHECK (status IN ('proposed','accepted','rejected','corrected','deferred')),
  valid_from timestamptz,
  valid_to timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  CHECK (valid_to IS NULL OR valid_from IS NULL OR valid_to > valid_from)
);
CREATE INDEX entity_relation_source_idx
  ON rag_v2.entity_relation(source_subject_id, relation_type, status);
CREATE INDEX entity_relation_target_idx
  ON rag_v2.entity_relation(target_subject_id, relation_type, status);

CREATE TABLE rag_v2.entity_relation_evidence (
  relation_id uuid NOT NULL REFERENCES rag_v2.entity_relation(id) ON DELETE RESTRICT,
  evidence_id uuid NOT NULL REFERENCES rag_v2.evidence(id) ON DELETE RESTRICT,
  PRIMARY KEY (relation_id, evidence_id)
);
CREATE INDEX entity_relation_evidence_evidence_idx
  ON rag_v2.entity_relation_evidence(evidence_id);

-- Reader bekommt ausschließlich bestätigte universelle Beziehungen.
CREATE VIEW rag_v2.accepted_entity_relation WITH (security_barrier = true) AS
  SELECT id, source_subject_id, target_subject_id, relation_type,
         context, valid_from, valid_to, created_at
  FROM rag_v2.entity_relation WHERE status = 'accepted';

CREATE FUNCTION rag_v2.validate_accepted_entity_relation(p_id uuid)
RETURNS void LANGUAGE plpgsql SET search_path = pg_catalog, rag_v2 AS $fn$
BEGIN
  IF EXISTS (
    SELECT 1 FROM rag_v2.entity_relation r WHERE r.id = p_id
    AND r.status = 'accepted'
    AND NOT EXISTS (
      SELECT 1 FROM rag_v2.entity_relation_evidence re
      WHERE re.relation_id = r.id
    )
  ) THEN
    RAISE EXCEPTION '0006: bestätigte Beziehung ohne Beleg %', p_id;
  END IF;
END
$fn$;

CREATE FUNCTION rag_v2.check_entity_relation_evidence()
RETURNS trigger LANGUAGE plpgsql SET search_path = pg_catalog, rag_v2 AS $fn$
BEGIN
  IF TG_TABLE_NAME = 'entity_relation' THEN
    PERFORM rag_v2.validate_accepted_entity_relation(NEW.id);
  ELSE
    PERFORM rag_v2.validate_accepted_entity_relation(
      CASE WHEN TG_OP = 'DELETE' THEN OLD.relation_id ELSE NEW.relation_id END
    );
    IF TG_OP = 'UPDATE' AND OLD.relation_id IS DISTINCT FROM NEW.relation_id THEN
      PERFORM rag_v2.validate_accepted_entity_relation(OLD.relation_id);
    END IF;
  END IF;
  RETURN NULL;
END
$fn$;

CREATE CONSTRAINT TRIGGER entity_relation_requires_evidence
  AFTER INSERT OR UPDATE ON rag_v2.entity_relation
  DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
  EXECUTE FUNCTION rag_v2.check_entity_relation_evidence();
CREATE CONSTRAINT TRIGGER entity_relation_evidence_integrity
  AFTER INSERT OR UPDATE OR DELETE ON rag_v2.entity_relation_evidence
  DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
  EXECUTE FUNCTION rag_v2.check_entity_relation_evidence();

CREATE FUNCTION rag_v2.prevent_accepted_entity_relation_rewrite()
RETURNS trigger LANGUAGE plpgsql SET search_path = pg_catalog, rag_v2 AS $fn$
BEGIN
  IF OLD.status = 'accepted' AND (
    NEW.source_subject_id IS DISTINCT FROM OLD.source_subject_id OR
    NEW.target_subject_id IS DISTINCT FROM OLD.target_subject_id OR
    NEW.relation_type IS DISTINCT FROM OLD.relation_type OR
    NEW.context IS DISTINCT FROM OLD.context OR
    NEW.valid_from IS DISTINCT FROM OLD.valid_from
  ) THEN
    RAISE EXCEPTION '0006: bestätigte Beziehung historisieren statt überschreiben';
  END IF;
  RETURN NEW;
END
$fn$;
CREATE TRIGGER entity_relation_no_accepted_rewrite
  BEFORE UPDATE ON rag_v2.entity_relation FOR EACH ROW
  EXECUTE FUNCTION rag_v2.prevent_accepted_entity_relation_rewrite();

-- 4. Vorschlagsbereich. Nur ein kontrollierter Workflow darf veröffentlichen.
-- status absichtlich NICHT vorhanden: proposal ist ein unveränderlicher
-- Eingangsdatensatz; Review-Status wird getrennt in review_item geführt.
CREATE TABLE rag_v2.knowledge_proposal (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  proposal_kind text NOT NULL CHECK (proposal_kind IN ('entity','fact','relation')),
  origin_kind text NOT NULL CHECK (origin_kind IN ('manual','extraction','agent')),
  payload jsonb NOT NULL CHECK (jsonb_typeof(payload) = 'object' AND payload <> '{}'::jsonb),
  provenance jsonb NOT NULL CHECK (jsonb_typeof(provenance) = 'object' AND provenance <> '{}'::jsonb),
  agent_run_key text,
  extraction_profile text,
  source_refs jsonb NOT NULL DEFAULT '[]'::jsonb
    CHECK (jsonb_typeof(source_refs) = 'array'),
  created_at timestamptz NOT NULL DEFAULT now(),
  CHECK (origin_kind <> 'agent' OR (agent_run_key IS NOT NULL AND btrim(agent_run_key) <> '')),
  CHECK (origin_kind <> 'extraction' OR
    (extraction_profile IS NOT NULL AND btrim(extraction_profile) <> ''))
);

CREATE INDEX knowledge_proposal_created_idx
  ON rag_v2.knowledge_proposal(created_at);

CREATE FUNCTION rag_v2.prevent_knowledge_proposal_rewrite()
RETURNS trigger LANGUAGE plpgsql SET search_path = pg_catalog, rag_v2 AS $fn$
BEGIN
  RAISE EXCEPTION '0006: Vorschläge sind unveränderlich';
END
$fn$;
CREATE TRIGGER knowledge_proposal_immutable
  BEFORE UPDATE OR DELETE ON rag_v2.knowledge_proposal
  FOR EACH ROW EXECUTE FUNCTION rag_v2.prevent_knowledge_proposal_rewrite();

-- Status- und Entscheidungsverlauf wird erst durch die Review-Anbindung
-- einer Folgemigration ergänzt; keine automatische Freigabe durch 0006.

-- Bei direkter INSERT-Erlaubnis die persistente Import-Sperre erzwingen.
CREATE FUNCTION rag_v2.guard_knowledge_proposal_import()
RETURNS trigger LANGUAGE plpgsql SET search_path = pg_catalog, rag_v2 AS $fn$
BEGIN
  PERFORM rag_v2.assert_import_write_gate();
  RETURN NEW;
END
$fn$;
CREATE TRIGGER knowledge_proposal_write_gate
  BEFORE INSERT ON rag_v2.knowledge_proposal
  FOR EACH ROW EXECUTE FUNCTION rag_v2.guard_knowledge_proposal_import();

-- 5. Rechte explizit setzen; PostgreSQL hat keine automatischen Grants für
-- später angelegte Tabellen, und der importer kann keine Fakten freigeben.
REVOKE ALL ON rag_v2.entity_type, rag_v2.knowledge_topic,
  rag_v2.knowledge_topic_assignment, rag_v2.entity_relation,
  rag_v2.entity_relation_evidence, rag_v2.knowledge_proposal FROM PUBLIC;
REVOKE ALL ON FUNCTION rag_v2.reject_topic_cycle(),
  rag_v2.validate_accepted_entity_relation(uuid),
  rag_v2.check_entity_relation_evidence(),
  rag_v2.prevent_accepted_entity_relation_rewrite(),
  rag_v2.prevent_knowledge_proposal_rewrite(),
  rag_v2.guard_knowledge_proposal_import() FROM PUBLIC;

GRANT SELECT ON rag_v2.entity_type, rag_v2.knowledge_topic,
  rag_v2.knowledge_topic_assignment, rag_v2.accepted_entity_relation
  TO rag_v2_reader;
GRANT SELECT ON rag_v2.entity_type, rag_v2.knowledge_topic,
  rag_v2.knowledge_topic_assignment, rag_v2.entity_relation,
  rag_v2.entity_relation_evidence, rag_v2.knowledge_proposal TO rag_v2_reviewer;
GRANT SELECT ON rag_v2.entity_type, rag_v2.knowledge_topic,
  rag_v2.knowledge_topic_assignment, rag_v2.entity_relation,
  rag_v2.entity_relation_evidence TO rag_v2_importer;
GRANT INSERT ON rag_v2.knowledge_proposal TO rag_v2_importer;
GRANT SELECT, INSERT, UPDATE ON rag_v2.knowledge_topic,
  rag_v2.knowledge_topic_assignment, rag_v2.entity_relation,
  rag_v2.entity_relation_evidence TO rag_v2_reviewer;
GRANT SELECT ON rag_v2.entity_type, rag_v2.knowledge_topic,
  rag_v2.knowledge_topic_assignment, rag_v2.entity_relation,
  rag_v2.entity_relation_evidence TO rag_v2_inventory;

INSERT INTO rag_v2.schema_migration(version, description)
VALUES (6, 'Universeller Wissenskern: Entitaetstypen, Themen, Beziehungen und Vorschlaege');
COMMIT;
