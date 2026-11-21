-- Retro-RAG V2: erste, ausschließlich vorwärts gerichtete Schema-Migration.
-- WICHTIG: Ausschließlich auf NEUEN Datenbanken retro_rag_v2 oder retro_rag_v2_test ausführen.
-- Keine Verbindung zu retro_rag (V1) und retro_rag_test herstellen.
-- Die DDL ist absichtlich vollständig schemaqualifiziert.
\set ON_ERROR_STOP on
BEGIN;

-- Dieser Block MUSS vor sämtlichen Änderungen stehen. Auch bei falschem -d
-- beendet RAISE EXCEPTION die gesamte Transaktion ohne DDL-Änderungen.
DO $migration_guard$
BEGIN
    IF current_database() NOT IN ('retro_rag_v2', 'retro_rag_v2_test') THEN
        RAISE EXCEPTION 'Schutzabbruch: nicht freigegebene Datenbank %', current_database();
    END IF;

    IF current_setting('server_version_num')::integer NOT BETWEEN 160000 AND 169999 THEN
        RAISE EXCEPTION 'Schutzabbruch: PostgreSQL 16 ist erforderlich';
    END IF;

    IF EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = 'rag_v2') THEN
        RAISE EXCEPTION 'Schutzabbruch: Schema rag_v2 existiert bereits; keine Wiederholung von 0001';
    END IF;
END;
$migration_guard$;

-- Das Advisory Lock verhindert parallele Initialisierung innerhalb derselben DB.
SELECT pg_advisory_xact_lock(824020, 2);

-- Voraussetzung: Erweiterungsdateien von pgvector sind auf PostgreSQL 16 installiert.
-- CREATE EXTENSION ist nur in der freigegebenen V2-Datenbank erlaubt.
CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public;
DO $extension_guard$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_extension e
        JOIN pg_namespace n ON n.oid = e.extnamespace
        WHERE e.extname = 'vector' AND n.nspname = 'public'
    ) THEN
        RAISE EXCEPTION 'pgvector muss im Schema public installiert sein';
    END IF;
END;
$extension_guard$;
CREATE SCHEMA rag_v2;
REVOKE ALL ON SCHEMA rag_v2 FROM PUBLIC;

-- Migrationsprotokoll: weitere Migrationen werden einmalig aufsteigend ausgeführt.
CREATE TABLE rag_v2.schema_migration (
    version         integer PRIMARY KEY CHECK (version > 0),
    description     text NOT NULL,
    applied_at      timestamptz NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- A. Kataloge, Hardwaremodelle und Bestandsdaten
-- ---------------------------------------------------------------------------
CREATE TABLE rag_v2.component_type (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    code            text NOT NULL UNIQUE CHECK (code ~ '^[a-z][a-z0-9_]*$'),
    name            text NOT NULL CHECK (btrim(name) <> ''),
    created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE rag_v2.article (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    component_type_id uuid NOT NULL REFERENCES rag_v2.component_type(id),
    manufacturer    text NOT NULL CHECK (btrim(manufacturer) <> ''),
    model           text NOT NULL CHECK (btrim(model) <> ''),
    model_key       text NOT NULL CHECK (btrim(model_key) <> ''),
    notes           text,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX article_model_key_idx ON rag_v2.article (model_key);

CREATE TABLE rag_v2.article_revision (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    article_id      uuid NOT NULL REFERENCES rag_v2.article(id) ON DELETE RESTRICT,
    revision        text NOT NULL CHECK (btrim(revision) <> ''),
    notes           text,
    created_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (article_id, revision),
    UNIQUE (id, article_id)
);

CREATE TABLE rag_v2.article_alias (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    article_id      uuid NOT NULL REFERENCES rag_v2.article(id) ON DELETE RESTRICT,
    alias           text NOT NULL CHECK (btrim(alias) <> ''),
    created_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (article_id, alias)
);

CREATE TABLE rag_v2.unit (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    article_id      uuid NOT NULL REFERENCES rag_v2.article(id) ON DELETE RESTRICT,
    article_revision_id uuid,
    inventory_number text NOT NULL UNIQUE CHECK (btrim(inventory_number) <> ''),
    serial_number   text,
    completeness    text CHECK (completeness IN ('complete', 'incomplete')),
    functional_state text NOT NULL DEFAULT 'untested'
                    CHECK (functional_state IN ('working', 'needs_repair', 'defective', 'untested')),
    location_state  text NOT NULL DEFAULT 'unknown'
                    CHECK (location_state IN ('unknown', 'installed', 'stored')),
    notes           text,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (article_revision_id, article_id)
        REFERENCES rag_v2.article_revision(id, article_id) ON DELETE RESTRICT
);
CREATE INDEX unit_article_idx ON rag_v2.unit (article_id);
CREATE INDEX unit_serial_idx ON rag_v2.unit (serial_number) WHERE serial_number IS NOT NULL;

-- Physische Systeminstanz, in der einzelne Exemplare verbaut sein können.
CREATE TABLE rag_v2.system (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name            text NOT NULL UNIQUE CHECK (btrim(name) <> ''),
    notes           text,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE rag_v2.storage_location (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    code            text NOT NULL UNIQUE CHECK (btrim(code) <> ''),
    description     text,
    parent_id       uuid REFERENCES rag_v2.storage_location(id) ON DELETE RESTRICT,
    created_at      timestamptz NOT NULL DEFAULT now(),
    CHECK (parent_id IS DISTINCT FROM id)
);

CREATE TABLE rag_v2.installation (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    unit_id         uuid NOT NULL REFERENCES rag_v2.unit(id) ON DELETE RESTRICT,
    system_id       uuid NOT NULL REFERENCES rag_v2.system(id) ON DELETE RESTRICT,
    slot_name       text,
    valid_from      timestamptz NOT NULL DEFAULT now(),
    valid_to        timestamptz,
    notes           text,
    created_at      timestamptz NOT NULL DEFAULT now(),
    CHECK (valid_to IS NULL OR valid_to > valid_from)
);
CREATE UNIQUE INDEX installation_one_active_per_unit_idx
    ON rag_v2.installation (unit_id) WHERE valid_to IS NULL;

CREATE TABLE rag_v2.storage_assignment (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    unit_id         uuid NOT NULL REFERENCES rag_v2.unit(id) ON DELETE RESTRICT,
    storage_location_id uuid NOT NULL REFERENCES rag_v2.storage_location(id) ON DELETE RESTRICT,
    valid_from      timestamptz NOT NULL DEFAULT now(),
    valid_to        timestamptz,
    notes           text,
    created_at      timestamptz NOT NULL DEFAULT now(),
    CHECK (valid_to IS NULL OR valid_to > valid_from)
);
CREATE UNIQUE INDEX storage_one_active_per_unit_idx
    ON rag_v2.storage_assignment (unit_id) WHERE valid_to IS NULL;

-- Vergangene Verbauungen/Lagerungen sind Ereignisse, keine überschreibbaren
-- aktuellen Felder. Nur ein erstmaliges Schließen via valid_to ist erlaubt.
CREATE FUNCTION rag_v2.prevent_assignment_rewrite()
RETURNS trigger LANGUAGE plpgsql SET search_path = pg_catalog, rag_v2 AS $func$
BEGIN
    IF NEW.unit_id IS DISTINCT FROM OLD.unit_id OR
       NEW.valid_from IS DISTINCT FROM OLD.valid_from THEN
        RAISE EXCEPTION 'Historische Zuordnung nicht überschreiben; alte schließen, neue anlegen';
    END IF;
    IF TG_TABLE_NAME = 'installation' THEN
        IF NEW.system_id IS DISTINCT FROM OLD.system_id THEN
            RAISE EXCEPTION 'Systemwechsel erfordert eine neue historische Zuordnung';
        END IF;
    ELSE
        IF NEW.storage_location_id IS DISTINCT FROM OLD.storage_location_id THEN
            RAISE EXCEPTION 'Lagerortwechsel erfordert eine neue historische Zuordnung';
        END IF;
    END IF;
    IF OLD.valid_to IS NOT NULL AND NEW.valid_to IS DISTINCT FROM OLD.valid_to THEN
        RAISE EXCEPTION 'Bereits geschlossene Zuordnung ist unveränderlich';
    END IF;
    RETURN NEW;
END;
$func$;

CREATE TRIGGER installation_no_rewrite
    BEFORE UPDATE ON rag_v2.installation
    FOR EACH ROW EXECUTE FUNCTION rag_v2.prevent_assignment_rewrite();
CREATE TRIGGER storage_assignment_no_rewrite
    BEFORE UPDATE ON rag_v2.storage_assignment
    FOR EACH ROW EXECUTE FUNCTION rag_v2.prevent_assignment_rewrite();

-- Standortprüfung wird am Transaktionsende ausgeführt. So kann der Wechsel
-- installiert -> gelagert atomar erfolgen. Sperre auf dem Eltern-Datensatz
-- serialisiert konkurrierende Bewegungen ein und desselben Exemplars.
CREATE FUNCTION rag_v2.validate_unit_location(p_unit_id uuid)
RETURNS void LANGUAGE plpgsql SET search_path = pg_catalog, rag_v2 AS $func$
DECLARE
    v_state text;
    v_installations integer;
    v_storage integer;
BEGIN
    SELECT location_state INTO v_state
    FROM rag_v2.unit WHERE id = p_unit_id FOR UPDATE;
    IF NOT FOUND THEN
        RETURN; -- FK bzw. Löschung wird separat behandelt.
    END IF;

    SELECT count(*) INTO v_installations FROM rag_v2.installation
      WHERE unit_id = p_unit_id AND valid_to IS NULL;
    SELECT count(*) INTO v_storage FROM rag_v2.storage_assignment
      WHERE unit_id = p_unit_id AND valid_to IS NULL;

    IF v_installations + v_storage > 1 OR
       (v_state = 'unknown' AND v_installations + v_storage <> 0) OR
       (v_state = 'installed' AND (v_installations <> 1 OR v_storage <> 0)) OR
       (v_state = 'stored' AND (v_storage <> 1 OR v_installations <> 0)) THEN
        RAISE EXCEPTION
            'Ungültige Standortzuordnung: unit %, Status %, Installationen %, Lagerungen %',
            p_unit_id, v_state, v_installations, v_storage;
    END IF;
END;
$func$;

CREATE FUNCTION rag_v2.check_unit_location_trigger()
RETURNS trigger LANGUAGE plpgsql SET search_path = pg_catalog, rag_v2 AS $func$
BEGIN
    IF TG_TABLE_NAME = 'unit' THEN
        PERFORM rag_v2.validate_unit_location(NEW.id);
    ELSIF TG_OP = 'DELETE' THEN
        PERFORM rag_v2.validate_unit_location(OLD.unit_id);
    ELSIF TG_OP = 'UPDATE' THEN
        PERFORM rag_v2.validate_unit_location(NEW.unit_id);
        IF OLD.unit_id IS DISTINCT FROM NEW.unit_id THEN
            PERFORM rag_v2.validate_unit_location(OLD.unit_id);
        END IF;
    ELSE
        PERFORM rag_v2.validate_unit_location(NEW.unit_id);
    END IF;
    RETURN NULL;
END;
$func$;

CREATE CONSTRAINT TRIGGER unit_location_integrity
    AFTER INSERT OR UPDATE ON rag_v2.unit
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
    EXECUTE FUNCTION rag_v2.check_unit_location_trigger();
CREATE CONSTRAINT TRIGGER installation_location_integrity
    AFTER INSERT OR UPDATE OR DELETE ON rag_v2.installation
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
    EXECUTE FUNCTION rag_v2.check_unit_location_trigger();
CREATE CONSTRAINT TRIGGER storage_location_integrity
    AFTER INSERT OR UPDATE OR DELETE ON rag_v2.storage_assignment
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
    EXECUTE FUNCTION rag_v2.check_unit_location_trigger();

-- Zustandsänderungen nachvollziehbar machen, auch wenn ein Client sie vergisst.
CREATE TABLE rag_v2.unit_condition_history (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    unit_id         uuid NOT NULL REFERENCES rag_v2.unit(id) ON DELETE RESTRICT,
    changed_at      timestamptz NOT NULL DEFAULT now(),
    changed_by      text NOT NULL DEFAULT session_user,
    old_completeness text,
    new_completeness text,
    old_functional_state text,
    new_functional_state text
);

CREATE FUNCTION rag_v2.audit_unit_condition()
RETURNS trigger LANGUAGE plpgsql SET search_path = pg_catalog, rag_v2 AS $func$
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO rag_v2.unit_condition_history (
            unit_id, old_completeness, new_completeness,
            old_functional_state, new_functional_state
        ) VALUES (NEW.id, NULL, NEW.completeness, NULL, NEW.functional_state);
    ELSIF OLD.completeness IS DISTINCT FROM NEW.completeness OR
          OLD.functional_state IS DISTINCT FROM NEW.functional_state THEN
        INSERT INTO rag_v2.unit_condition_history (
            unit_id, old_completeness, new_completeness,
            old_functional_state, new_functional_state
        ) VALUES (
            NEW.id, OLD.completeness, NEW.completeness,
            OLD.functional_state, NEW.functional_state
        );
    END IF;
    RETURN NEW;
END;
$func$;

CREATE TRIGGER unit_condition_audit
    AFTER INSERT OR UPDATE OF completeness, functional_state ON rag_v2.unit
    FOR EACH ROW EXECUTE FUNCTION rag_v2.audit_unit_condition();

-- ---------------------------------------------------------------------------
-- B. Dokumentidentität, Quellen, Versionen, Suche
-- ---------------------------------------------------------------------------
CREATE TABLE rag_v2.document (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    title           text NOT NULL CHECK (btrim(title) <> ''),
    document_type   text,
    availability    text NOT NULL DEFAULT 'available'
                    CHECK (availability IN ('available', 'deactivated', 'removed')),
    deactivated_at  timestamptz,
    removed_at      timestamptz,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE rag_v2.document_source (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id     uuid NOT NULL REFERENCES rag_v2.document(id) ON DELETE RESTRICT,
    source_system   text NOT NULL CHECK (btrim(source_system) <> ''),
    source_key      text NOT NULL CHECK (btrim(source_key) <> ''),
    source_uri      text NOT NULL CHECK (btrim(source_uri) <> ''),
    last_seen_content_hash text CHECK (last_seen_content_hash IS NULL OR
                                      last_seen_content_hash ~ '^[0-9a-f]{64}$'),
    is_available    boolean NOT NULL DEFAULT true,
    first_seen_at   timestamptz NOT NULL DEFAULT now(),
    last_seen_at    timestamptz NOT NULL DEFAULT now(),
    UNIQUE (source_system, source_key)
);
CREATE INDEX document_source_document_idx ON rag_v2.document_source (document_id);

CREATE TABLE rag_v2.document_version (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id     uuid NOT NULL REFERENCES rag_v2.document(id) ON DELETE RESTRICT,
    version_no      integer NOT NULL CHECK (version_no > 0),
    content_hash    text NOT NULL CHECK (content_hash ~ '^[0-9a-f]{64}$'),
    processing_state text NOT NULL DEFAULT 'discovered'
                    CHECK (processing_state IN ('discovered', 'processing', 'indexed', 'failed')),
    state           text CHECK (state IN ('active', 'superseded', 'archived')),
    source_filename text,
    archive_uri     text, -- Ablageort der unveränderten Original-/Versionskopie.
    mime_type       text,
    byte_size       bigint CHECK (byte_size IS NULL OR byte_size >= 0),
    indexed_at      timestamptz,
    superseded_at   timestamptz,
    archive_after   timestamptz,
    created_at      timestamptz NOT NULL DEFAULT now(),
    CHECK (state IS NULL OR processing_state = 'indexed'),
    UNIQUE (document_id, version_no)
);
CREATE UNIQUE INDEX document_one_current_version_idx
    ON rag_v2.document_version (document_id) WHERE state = 'active';
CREATE INDEX document_version_hash_idx ON rag_v2.document_version (content_hash);
CREATE INDEX document_version_document_idx ON rag_v2.document_version (document_id, state);

CREATE TABLE rag_v2.chunk (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    document_version_id uuid NOT NULL REFERENCES rag_v2.document_version(id) ON DELETE CASCADE,
    sequence_no     integer NOT NULL CHECK (sequence_no >= 0),
    content         text NOT NULL CHECK (btrim(content) <> ''),
    content_hash    text NOT NULL CHECK (content_hash ~ '^[0-9a-f]{64}$'),
    page_from       integer CHECK (page_from IS NULL OR page_from > 0),
    page_to         integer CHECK (page_to IS NULL OR page_to > 0),
    section_path    text[] NOT NULL DEFAULT ARRAY[]::text[],
    source_locator  jsonb NOT NULL DEFAULT '{}'::jsonb,
    search_vector   tsvector GENERATED ALWAYS AS
                    (to_tsvector('simple'::regconfig, content)) STORED,
    created_at      timestamptz NOT NULL DEFAULT now(),
    CHECK (page_from IS NULL OR page_to IS NULL OR page_to >= page_from),
    UNIQUE (document_version_id, sequence_no)
);
CREATE INDEX chunk_fulltext_idx ON rag_v2.chunk USING gin (search_vector);
CREATE INDEX chunk_version_hash_idx ON rag_v2.chunk (document_version_id, content_hash);

CREATE TABLE rag_v2.embedding_model (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    model_name      text NOT NULL UNIQUE CHECK (btrim(model_name) <> ''),
    dimensions      integer NOT NULL CHECK (dimensions > 0 AND dimensions <= 16000),
    metric          text NOT NULL DEFAULT 'cosine' CHECK (metric IN ('cosine', 'l2', 'ip')),
    created_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (id, dimensions)
);

-- Dimensionsoffener pgvector-Typ: 768 und 1024 können nebeneinander existieren.
-- ANN-Indizes erst später pro ausgewähltem Modell/Dimension anlegen.
CREATE TABLE rag_v2.chunk_embedding (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    chunk_id        uuid NOT NULL REFERENCES rag_v2.chunk(id) ON DELETE CASCADE,
    embedding_model_id uuid NOT NULL,
    dimensions      integer NOT NULL,
    embedding       public.vector NOT NULL,
    created_at      timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (embedding_model_id, dimensions)
        REFERENCES rag_v2.embedding_model(id, dimensions) ON DELETE RESTRICT,
    CHECK (public.vector_dims(embedding) = dimensions),
    UNIQUE (chunk_id, embedding_model_id)
);
CREATE INDEX chunk_embedding_model_idx ON rag_v2.chunk_embedding (embedding_model_id);

-- ---------------------------------------------------------------------------
-- C. Wissensobjekte, Fakten, Belege und Kompatibilität
-- ---------------------------------------------------------------------------
CREATE TABLE rag_v2.reference_entity (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type     text NOT NULL CHECK (entity_type IN
                    ('interface', 'chipset', 'software', 'driver', 'graphics_api', 'standard', 'other')),
    entity_key      text NOT NULL CHECK (btrim(entity_key) <> ''),
    name            text NOT NULL CHECK (btrim(name) <> ''),
    description     text,
    created_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (entity_type, entity_key)
);

-- Ein gemeinsamer, mit echten FKs abgesicherter Identifikator für Faktenobjekte.
CREATE TABLE rag_v2.knowledge_subject (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    article_id      uuid REFERENCES rag_v2.article(id) ON DELETE RESTRICT,
    article_revision_id uuid REFERENCES rag_v2.article_revision(id) ON DELETE RESTRICT,
    document_id     uuid REFERENCES rag_v2.document(id) ON DELETE RESTRICT,
    reference_entity_id uuid REFERENCES rag_v2.reference_entity(id) ON DELETE RESTRICT,
    created_at      timestamptz NOT NULL DEFAULT now(),
    CHECK (num_nonnulls(article_id, article_revision_id, document_id, reference_entity_id) = 1)
);
CREATE UNIQUE INDEX knowledge_subject_article_unique
    ON rag_v2.knowledge_subject (article_id) WHERE article_id IS NOT NULL;
CREATE UNIQUE INDEX knowledge_subject_revision_unique
    ON rag_v2.knowledge_subject (article_revision_id) WHERE article_revision_id IS NOT NULL;
CREATE UNIQUE INDEX knowledge_subject_document_unique
    ON rag_v2.knowledge_subject (document_id) WHERE document_id IS NOT NULL;
CREATE UNIQUE INDEX knowledge_subject_reference_unique
    ON rag_v2.knowledge_subject (reference_entity_id) WHERE reference_entity_id IS NOT NULL;

CREATE TABLE rag_v2.property (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    property_key    text NOT NULL UNIQUE CHECK (property_key ~ '^[a-z][a-z0-9_]*$'),
    name            text NOT NULL CHECK (btrim(name) <> ''),
    value_type      text NOT NULL CHECK (value_type IN ('numeric', 'text')),
    canonical_unit  text,
    created_at      timestamptz NOT NULL DEFAULT now(),
    CHECK (value_type = 'numeric' OR canonical_unit IS NULL)
);

CREATE TABLE rag_v2.property_component_type (
    property_id     uuid NOT NULL REFERENCES rag_v2.property(id) ON DELETE RESTRICT,
    component_type_id uuid NOT NULL REFERENCES rag_v2.component_type(id) ON DELETE RESTRICT,
    PRIMARY KEY (property_id, component_type_id)
);

CREATE TABLE rag_v2.fact (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    subject_id      uuid NOT NULL REFERENCES rag_v2.knowledge_subject(id) ON DELETE RESTRICT,
    property_id     uuid NOT NULL REFERENCES rag_v2.property(id) ON DELETE RESTRICT,
    value_numeric   numeric,
    value_text      text,
    unit_symbol     text,
    status          text NOT NULL DEFAULT 'proposed'
                    CHECK (status IN ('proposed', 'accepted', 'rejected', 'corrected', 'deferred')),
    confidence      numeric(4,3) CHECK (confidence >= 0 AND confidence <= 1),
    valid_from      timestamptz NOT NULL DEFAULT now(),
    valid_to        timestamptz,
    created_at      timestamptz NOT NULL DEFAULT now(),
    CHECK (num_nonnulls(value_numeric, value_text) = 1),
    CHECK (value_text IS NULL OR btrim(value_text) <> ''),
    CHECK (valid_to IS NULL OR valid_to > valid_from)
);
CREATE INDEX fact_subject_property_idx ON rag_v2.fact (subject_id, property_id, status);

-- Bestätigte Fakten werden bei Korrektur historisch abgeschlossen und als
-- neue Datensätze angelegt; ihr damaliger Wert darf nicht überschrieben werden.
CREATE FUNCTION rag_v2.prevent_accepted_fact_rewrite()
RETURNS trigger LANGUAGE plpgsql SET search_path = pg_catalog, rag_v2 AS $func$
BEGIN
    IF OLD.status = 'accepted' AND (
        NEW.subject_id IS DISTINCT FROM OLD.subject_id OR
        NEW.property_id IS DISTINCT FROM OLD.property_id OR
        NEW.value_numeric IS DISTINCT FROM OLD.value_numeric OR
        NEW.value_text IS DISTINCT FROM OLD.value_text OR
        NEW.unit_symbol IS DISTINCT FROM OLD.unit_symbol
    ) THEN
        RAISE EXCEPTION 'Bestätigten Fakt nicht überschreiben; historisieren und neuen Fakt anlegen';
    END IF;
    RETURN NEW;
END;
$func$;
CREATE TRIGGER fact_no_accepted_rewrite
    BEFORE UPDATE ON rag_v2.fact
    FOR EACH ROW EXECUTE FUNCTION rag_v2.prevent_accepted_fact_rewrite();

-- Faktenwerte müssen dem Vokabular entsprechen. Bei einer Hardware-Quelle
-- gelten auch die erlaubten Komponentenarten (sofern für den Key definiert).
CREATE FUNCTION rag_v2.validate_fact_value_trigger()
RETURNS trigger LANGUAGE plpgsql SET search_path = pg_catalog, rag_v2 AS $func$
DECLARE
    v_type text;
    v_unit text;
    v_component_type_id uuid;
BEGIN
    SELECT value_type, canonical_unit INTO v_type, v_unit
    FROM rag_v2.property WHERE id = NEW.property_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Unbekannte Eigenschaft %', NEW.property_id;
    END IF;
    IF (v_type = 'numeric' AND NEW.value_numeric IS NULL) OR
       (v_type = 'text' AND NEW.value_text IS NULL) THEN
        RAISE EXCEPTION 'Falscher Wertetyp für Eigenschaft %', NEW.property_id;
    END IF;
    IF NEW.unit_symbol IS DISTINCT FROM v_unit THEN
        RAISE EXCEPTION 'Erwartete kanonische Einheit %, erhalten %', v_unit, NEW.unit_symbol;
    END IF;
    IF v_type = 'text' AND NEW.unit_symbol IS NOT NULL THEN
        RAISE EXCEPTION 'Texteigenschaft darf keine Einheit haben';
    END IF;

    SELECT a.component_type_id INTO v_component_type_id
    FROM rag_v2.knowledge_subject ks
    JOIN rag_v2.article a ON a.id = ks.article_id
    WHERE ks.id = NEW.subject_id;
    IF NOT FOUND THEN
        SELECT a.component_type_id INTO v_component_type_id
        FROM rag_v2.knowledge_subject ks
        JOIN rag_v2.article_revision ar ON ar.id = ks.article_revision_id
        JOIN rag_v2.article a ON a.id = ar.article_id
        WHERE ks.id = NEW.subject_id;
    END IF;

    IF v_component_type_id IS NOT NULL AND
       EXISTS (SELECT 1 FROM rag_v2.property_component_type
              WHERE property_id = NEW.property_id) AND
       NOT EXISTS (SELECT 1 FROM rag_v2.property_component_type
                   WHERE property_id = NEW.property_id
                     AND component_type_id = v_component_type_id) THEN
        RAISE EXCEPTION 'Eigenschaft % nicht für Komponentenart % freigegeben',
            NEW.property_id, v_component_type_id;
    END IF;
    RETURN NEW;
END;
$func$;

CREATE TRIGGER fact_property_validation
    BEFORE INSERT OR UPDATE OF property_id, subject_id, value_numeric, value_text, unit_symbol
    ON rag_v2.fact FOR EACH ROW
    EXECUTE FUNCTION rag_v2.validate_fact_value_trigger();

CREATE TABLE rag_v2.evidence (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    evidence_kind   text NOT NULL CHECK (evidence_kind IN ('external', 'self_tested')),
    document_version_id uuid REFERENCES rag_v2.document_version(id) ON DELETE RESTRICT,
    page_number     integer CHECK (page_number IS NULL OR page_number > 0),
    source_locator  text,
    excerpt         text,
    test_date       date,
    test_setup      text,
    availability    text NOT NULL DEFAULT 'available'
                    CHECK (availability IN ('available', 'source_unavailable')),
    created_at      timestamptz NOT NULL DEFAULT now(),
    CHECK ((evidence_kind = 'external' AND document_version_id IS NOT NULL
            AND excerpt IS NOT NULL AND btrim(excerpt) <> '')
        OR (evidence_kind = 'self_tested' AND test_date IS NOT NULL
            AND test_setup IS NOT NULL AND btrim(test_setup) <> ''))
);
CREATE INDEX evidence_version_idx ON rag_v2.evidence (document_version_id);

CREATE TABLE rag_v2.fact_evidence (
    fact_id         uuid NOT NULL REFERENCES rag_v2.fact(id) ON DELETE CASCADE,
    evidence_id     uuid NOT NULL REFERENCES rag_v2.evidence(id) ON DELETE RESTRICT,
    PRIMARY KEY (fact_id, evidence_id)
);

CREATE TABLE rag_v2.compatibility_rule (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    left_subject_id uuid NOT NULL REFERENCES rag_v2.knowledge_subject(id) ON DELETE RESTRICT,
    right_subject_id uuid NOT NULL REFERENCES rag_v2.knowledge_subject(id) ON DELETE RESTRICT,
    relation        text NOT NULL CHECK (relation IN
                    ('compatible', 'incompatible', 'requires', 'conditional')),
    -- Die konkrete DSL wird erst in einer Folgemigration festgelegt.
    conditions      jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(conditions) = 'object'),
    notes           text,
    status          text NOT NULL DEFAULT 'unsupported'
                    CHECK (status IN ('unsupported', 'proposed', 'accepted',
                                     'rejected', 'corrected', 'deferred')),
    valid_from      timestamptz NOT NULL DEFAULT now(),
    valid_to        timestamptz,
    created_at      timestamptz NOT NULL DEFAULT now(),
    CHECK (valid_to IS NULL OR valid_to > valid_from)
);
CREATE INDEX compatibility_subjects_idx
    ON rag_v2.compatibility_rule (left_subject_id, right_subject_id, status);

CREATE TABLE rag_v2.compatibility_rule_evidence (
    compatibility_rule_id uuid NOT NULL
        REFERENCES rag_v2.compatibility_rule(id) ON DELETE CASCADE,
    evidence_id     uuid NOT NULL REFERENCES rag_v2.evidence(id) ON DELETE RESTRICT,
    PRIMARY KEY (compatibility_rule_id, evidence_id)
);

-- Ein freigegebener Fakt/eine freigegebene Regel braucht mindestens einen Beleg.
-- Deferred: Fakt/Regel und Beleg können innerhalb EINER Transaktion entstehen.
CREATE FUNCTION rag_v2.validate_accepted_evidence(
    p_object_type text, p_object_id uuid
) RETURNS void LANGUAGE plpgsql SET search_path = pg_catalog, rag_v2 AS $func$
DECLARE v_missing boolean;
BEGIN
    IF p_object_type = 'fact' THEN
        SELECT EXISTS (
            SELECT 1 FROM rag_v2.fact f WHERE f.id = p_object_id
            AND f.status = 'accepted'
            AND NOT EXISTS (SELECT 1 FROM rag_v2.fact_evidence fe WHERE fe.fact_id = f.id)
        ) INTO v_missing;
    ELSE
        SELECT EXISTS (
            SELECT 1 FROM rag_v2.compatibility_rule cr WHERE cr.id = p_object_id
            AND cr.status = 'accepted'
            AND NOT EXISTS (
                SELECT 1 FROM rag_v2.compatibility_rule_evidence cre
                WHERE cre.compatibility_rule_id = cr.id)
        ) INTO v_missing;
    END IF;
    IF v_missing THEN
        RAISE EXCEPTION 'Freigabe ohne Quellenbeleg: % / %', p_object_type, p_object_id;
    END IF;
END;
$func$;

CREATE FUNCTION rag_v2.check_accepted_evidence_trigger()
RETURNS trigger LANGUAGE plpgsql SET search_path = pg_catalog, rag_v2 AS $func$
BEGIN
    IF TG_TABLE_NAME = 'fact' THEN
        PERFORM rag_v2.validate_accepted_evidence('fact', NEW.id);
    ELSIF TG_TABLE_NAME = 'compatibility_rule' THEN
        PERFORM rag_v2.validate_accepted_evidence('rule', NEW.id);
    ELSIF TG_TABLE_NAME = 'fact_evidence' THEN
        PERFORM rag_v2.validate_accepted_evidence('fact',
            CASE WHEN TG_OP = 'DELETE' THEN OLD.fact_id ELSE NEW.fact_id END);
        IF TG_OP = 'UPDATE' AND OLD.fact_id IS DISTINCT FROM NEW.fact_id THEN
            PERFORM rag_v2.validate_accepted_evidence('fact', OLD.fact_id);
        END IF;
    ELSE
        PERFORM rag_v2.validate_accepted_evidence('rule',
            CASE WHEN TG_OP = 'DELETE' THEN OLD.compatibility_rule_id
                 ELSE NEW.compatibility_rule_id END);
        IF TG_OP = 'UPDATE' AND OLD.compatibility_rule_id IS DISTINCT FROM NEW.compatibility_rule_id THEN
            PERFORM rag_v2.validate_accepted_evidence('rule', OLD.compatibility_rule_id);
        END IF;
    END IF;
    RETURN NULL;
END;
$func$;

CREATE CONSTRAINT TRIGGER fact_evidence_required
    AFTER INSERT OR UPDATE ON rag_v2.fact
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
    EXECUTE FUNCTION rag_v2.check_accepted_evidence_trigger();
CREATE CONSTRAINT TRIGGER rule_evidence_required
    AFTER INSERT OR UPDATE ON rag_v2.compatibility_rule
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
    EXECUTE FUNCTION rag_v2.check_accepted_evidence_trigger();
CREATE CONSTRAINT TRIGGER fact_evidence_integrity
    AFTER INSERT OR UPDATE OR DELETE ON rag_v2.fact_evidence
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
    EXECUTE FUNCTION rag_v2.check_accepted_evidence_trigger();
CREATE CONSTRAINT TRIGGER rule_evidence_integrity
    AFTER INSERT OR UPDATE OR DELETE ON rag_v2.compatibility_rule_evidence
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
    EXECUTE FUNCTION rag_v2.check_accepted_evidence_trigger();

-- ---------------------------------------------------------------------------
-- D. Dokumentimport, Resume, Review und Qualitätsprotokolle
-- ---------------------------------------------------------------------------
CREATE TABLE rag_v2.trusted_source (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_system   text NOT NULL,
    source_key      text NOT NULL,
    enabled         boolean NOT NULL DEFAULT false,
    authorized_by   text NOT NULL CHECK (btrim(authorized_by) <> ''),
    authorized_at   timestamptz NOT NULL DEFAULT now(),
    notes           text,
    UNIQUE (source_system, source_key)
);

CREATE TABLE rag_v2.processing_job (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    document_version_id uuid REFERENCES rag_v2.document_version(id) ON DELETE RESTRICT,
    job_type        text NOT NULL CHECK (btrim(job_type) <> ''),
    status          text NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled')),
    attempts        integer NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    max_attempts    integer NOT NULL DEFAULT 3 CHECK (max_attempts > 0),
    lease_owner     text,
    lease_until     timestamptz,
    last_error      text,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now(),
    completed_at    timestamptz,
    CHECK (attempts <= max_attempts)
);
CREATE INDEX processing_job_queue_idx ON rag_v2.processing_job (status, lease_until, created_at);

CREATE TABLE rag_v2.processing_step (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    processing_job_id uuid NOT NULL REFERENCES rag_v2.processing_job(id) ON DELETE RESTRICT,
    step_name       text NOT NULL CHECK (btrim(step_name) <> ''),
    status          text NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'running', 'completed', 'failed', 'skipped')),
    input_hash      text CHECK (input_hash IS NULL OR input_hash ~ '^[0-9a-f]{64}$'),
    attempts        integer NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    max_attempts    integer NOT NULL DEFAULT 3 CHECK (max_attempts > 0),
    lease_owner     text,
    lease_until     timestamptz,
    last_error      text,
    created_at      timestamptz NOT NULL DEFAULT now(),
    completed_at    timestamptz,
    UNIQUE (processing_job_id, step_name),
    CHECK (attempts <= max_attempts)
);

CREATE TABLE rag_v2.processing_artifact (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    processing_step_id uuid NOT NULL REFERENCES rag_v2.processing_step(id) ON DELETE RESTRICT,
    artifact_kind   text NOT NULL CHECK (btrim(artifact_kind) <> ''),
    artifact_uri    text NOT NULL CHECK (btrim(artifact_uri) <> ''),
    content_hash    text CHECK (content_hash IS NULL OR content_hash ~ '^[0-9a-f]{64}$'),
    created_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (processing_step_id, artifact_kind, artifact_uri)
);

CREATE TABLE rag_v2.review_batch (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    document_version_id uuid REFERENCES rag_v2.document_version(id) ON DELETE RESTRICT,
    title           text,
    status          text NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'closed')),
    created_at      timestamptz NOT NULL DEFAULT now(),
    closed_at       timestamptz
);

CREATE TABLE rag_v2.review_item (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    review_batch_id uuid NOT NULL REFERENCES rag_v2.review_batch(id) ON DELETE RESTRICT,
    item_kind       text NOT NULL CHECK (item_kind IN
                    ('fact', 'compatibility', 'document_identity', 'inventory')),
    -- Ein Proposal ist ein überprüfter Vorschlag, kein direktes DB-Update.
    proposal        jsonb NOT NULL CHECK (jsonb_typeof(proposal) = 'object'),
    status          text NOT NULL DEFAULT 'proposed'
                    CHECK (status IN ('proposed', 'accepted', 'rejected', 'corrected', 'deferred')),
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE rag_v2.review_decision (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    review_item_id  uuid NOT NULL REFERENCES rag_v2.review_item(id) ON DELETE RESTRICT,
    decision        text NOT NULL CHECK (decision IN ('accepted', 'rejected', 'corrected', 'deferred')),
    decided_by      text NOT NULL CHECK (btrim(decided_by) <> ''),
    reason          text,
    old_value       jsonb,
    new_value       jsonb,
    decided_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX review_decision_item_idx ON rag_v2.review_decision (review_item_id, decided_at);

-- Nachvollziehbare Review-Entscheidungen werden niemals überschrieben.
CREATE FUNCTION rag_v2.prevent_review_decision_rewrite()
RETURNS trigger LANGUAGE plpgsql SET search_path = pg_catalog, rag_v2 AS $func$
BEGIN
    RAISE EXCEPTION 'Review-Entscheidungen sind unveränderlich';
    RETURN NULL; -- unerreichbar, aber Trigger-Rückgabe explizit
END;
$func$;
CREATE TRIGGER review_decision_immutable
    BEFORE UPDATE OR DELETE ON rag_v2.review_decision
    FOR EACH ROW EXECUTE FUNCTION rag_v2.prevent_review_decision_rewrite();

CREATE TABLE rag_v2.sync_run (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    started_at      timestamptz NOT NULL DEFAULT now(),
    finished_at     timestamptz,
    apply_mode      boolean NOT NULL DEFAULT false,
    status          text NOT NULL DEFAULT 'running'
                    CHECK (status IN ('running', 'completed', 'failed', 'blocked')),
    discovered      integer NOT NULL DEFAULT 0 CHECK (discovered >= 0),
    changed         integer NOT NULL DEFAULT 0 CHECK (changed >= 0),
    archived        integer NOT NULL DEFAULT 0 CHECK (archived >= 0),
    deactivated     integer NOT NULL DEFAULT 0 CHECK (deactivated >= 0),
    removed         integer NOT NULL DEFAULT 0 CHECK (removed >= 0),
    errors          integer NOT NULL DEFAULT 0 CHECK (errors >= 0),
    details         jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE rag_v2.document_error (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id     uuid REFERENCES rag_v2.document(id) ON DELETE RESTRICT,
    document_version_id uuid REFERENCES rag_v2.document_version(id) ON DELETE RESTRICT,
    step_name       text NOT NULL,
    error_message   text NOT NULL,
    retry_count     integer NOT NULL DEFAULT 0 CHECK (retry_count >= 0),
    created_at      timestamptz NOT NULL DEFAULT now()
);

-- Kein harter FK zu Chunks: deren Suchdaten werden regulär gelöscht,
-- historische Antworten und Quellenkennungen müssen jedoch erhalten bleiben.
CREATE TABLE rag_v2.query_log (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    question        text NOT NULL,
    answer          text,
    used_sources    jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(used_sources) = 'array'),
    evaluation      jsonb,
    created_at      timestamptz NOT NULL DEFAULT now()
);

-- Persistente Schreibsperre nach Restore. Default ist gesperrt;
-- die spätere Betriebs-/Autorisierungslogik muss eine Freigabe vorsehen.
CREATE TABLE rag_v2.write_gate (
    id              boolean PRIMARY KEY DEFAULT true CHECK (id),
    writes_enabled  boolean NOT NULL DEFAULT false,
    reason          text NOT NULL DEFAULT 'Initialisierung: Schreibfreigabe ausstehend',
    changed_by      text,
    changed_at      timestamptz NOT NULL DEFAULT now()
);
INSERT INTO rag_v2.write_gate (id, writes_enabled) VALUES (true, false);

INSERT INTO rag_v2.schema_migration (version, description)
VALUES (1, 'Initiales, von Retro-RAG V1 isoliertes Datenmodell');

COMMIT;