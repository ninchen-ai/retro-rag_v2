--
-- PostgreSQL database dump
--

\restrict pdVmmSQerRX1UeNtWahktfan5v9MU15zViJEPMG4pPZqe1dZmzA2MQ63DKL9xzN

-- Dumped from database version 16.15 (Debian 16.15-1.pgdg12+2)
-- Dumped by pg_dump version 16.15 (Debian 16.15-1.pgdg12+2)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: rag_v2; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA rag_v2;


--
-- Name: assert_import_write_gate(); Type: FUNCTION; Schema: rag_v2; Owner: -
--

CREATE FUNCTION rag_v2.assert_import_write_gate() RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'pg_catalog', 'rag_v2'
    AS $$
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
$$;


--
-- Name: audit_unit_condition(); Type: FUNCTION; Schema: rag_v2; Owner: -
--

CREATE FUNCTION rag_v2.audit_unit_condition() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path TO 'pg_catalog', 'rag_v2'
    AS $$
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
$$;


--
-- Name: check_accepted_evidence_trigger(); Type: FUNCTION; Schema: rag_v2; Owner: -
--

CREATE FUNCTION rag_v2.check_accepted_evidence_trigger() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path TO 'pg_catalog', 'rag_v2'
    AS $$
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
$$;


--
-- Name: check_unit_location_trigger(); Type: FUNCTION; Schema: rag_v2; Owner: -
--

CREATE FUNCTION rag_v2.check_unit_location_trigger() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path TO 'pg_catalog', 'rag_v2'
    AS $$
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
$$;


--
-- Name: prevent_accepted_fact_rewrite(); Type: FUNCTION; Schema: rag_v2; Owner: -
--

CREATE FUNCTION rag_v2.prevent_accepted_fact_rewrite() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path TO 'pg_catalog', 'rag_v2'
    AS $$
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
$$;


--
-- Name: prevent_assignment_rewrite(); Type: FUNCTION; Schema: rag_v2; Owner: -
--

CREATE FUNCTION rag_v2.prevent_assignment_rewrite() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path TO 'pg_catalog', 'rag_v2'
    AS $$
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
$$;


--
-- Name: prevent_review_decision_rewrite(); Type: FUNCTION; Schema: rag_v2; Owner: -
--

CREATE FUNCTION rag_v2.prevent_review_decision_rewrite() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path TO 'pg_catalog', 'rag_v2'
    AS $$
BEGIN
    RAISE EXCEPTION 'Review-Entscheidungen sind unveränderlich';
    RETURN NULL; -- unerreichbar, aber Trigger-Rückgabe explizit
END;
$$;


--
-- Name: validate_accepted_evidence(text, uuid); Type: FUNCTION; Schema: rag_v2; Owner: -
--

CREATE FUNCTION rag_v2.validate_accepted_evidence(p_object_type text, p_object_id uuid) RETURNS void
    LANGUAGE plpgsql
    SET search_path TO 'pg_catalog', 'rag_v2'
    AS $$
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
$$;


--
-- Name: validate_fact_value_trigger(); Type: FUNCTION; Schema: rag_v2; Owner: -
--

CREATE FUNCTION rag_v2.validate_fact_value_trigger() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path TO 'pg_catalog', 'rag_v2'
    AS $$
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
$$;


--
-- Name: validate_unit_location(uuid); Type: FUNCTION; Schema: rag_v2; Owner: -
--

CREATE FUNCTION rag_v2.validate_unit_location(p_unit_id uuid) RETURNS void
    LANGUAGE plpgsql
    SET search_path TO 'pg_catalog', 'rag_v2'
    AS $$
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
$$;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: article; Type: TABLE; Schema: rag_v2; Owner: -
--

CREATE TABLE rag_v2.article (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    component_type_id uuid NOT NULL,
    manufacturer text NOT NULL,
    model text NOT NULL,
    model_key text NOT NULL,
    notes text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT article_manufacturer_check CHECK ((btrim(manufacturer) <> ''::text)),
    CONSTRAINT article_model_check CHECK ((btrim(model) <> ''::text)),
    CONSTRAINT article_model_key_check CHECK ((btrim(model_key) <> ''::text))
);


--
-- Name: article_alias; Type: TABLE; Schema: rag_v2; Owner: -
--

CREATE TABLE rag_v2.article_alias (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    article_id uuid NOT NULL,
    alias text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT article_alias_alias_check CHECK ((btrim(alias) <> ''::text))
);


--
-- Name: article_revision; Type: TABLE; Schema: rag_v2; Owner: -
--

CREATE TABLE rag_v2.article_revision (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    article_id uuid NOT NULL,
    revision text NOT NULL,
    notes text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT article_revision_revision_check CHECK ((btrim(revision) <> ''::text))
);


--
-- Name: chunk; Type: TABLE; Schema: rag_v2; Owner: -
--

CREATE TABLE rag_v2.chunk (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    document_version_id uuid NOT NULL,
    sequence_no integer NOT NULL,
    content text NOT NULL,
    content_hash text NOT NULL,
    page_from integer,
    page_to integer,
    section_path text[] DEFAULT ARRAY[]::text[] NOT NULL,
    source_locator jsonb DEFAULT '{}'::jsonb NOT NULL,
    search_vector tsvector GENERATED ALWAYS AS (to_tsvector('simple'::regconfig, content)) STORED,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT chunk_check CHECK (((page_from IS NULL) OR (page_to IS NULL) OR (page_to >= page_from))),
    CONSTRAINT chunk_content_check CHECK ((btrim(content) <> ''::text)),
    CONSTRAINT chunk_content_hash_check CHECK ((content_hash ~ '^[0-9a-f]{64}$'::text)),
    CONSTRAINT chunk_page_from_check CHECK (((page_from IS NULL) OR (page_from > 0))),
    CONSTRAINT chunk_page_to_check CHECK (((page_to IS NULL) OR (page_to > 0))),
    CONSTRAINT chunk_sequence_no_check CHECK ((sequence_no >= 0))
);


--
-- Name: chunk_embedding; Type: TABLE; Schema: rag_v2; Owner: -
--

CREATE TABLE rag_v2.chunk_embedding (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    chunk_id uuid NOT NULL,
    embedding_model_id uuid NOT NULL,
    dimensions integer NOT NULL,
    embedding public.vector NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT chunk_embedding_check CHECK ((public.vector_dims(embedding) = dimensions))
);


--
-- Name: compatibility_rule; Type: TABLE; Schema: rag_v2; Owner: -
--

CREATE TABLE rag_v2.compatibility_rule (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    left_subject_id uuid NOT NULL,
    right_subject_id uuid NOT NULL,
    relation text NOT NULL,
    conditions jsonb DEFAULT '{}'::jsonb NOT NULL,
    notes text,
    status text DEFAULT 'unsupported'::text NOT NULL,
    valid_from timestamp with time zone DEFAULT now() NOT NULL,
    valid_to timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT compatibility_rule_check CHECK (((valid_to IS NULL) OR (valid_to > valid_from))),
    CONSTRAINT compatibility_rule_conditions_check CHECK ((jsonb_typeof(conditions) = 'object'::text)),
    CONSTRAINT compatibility_rule_relation_check CHECK ((relation = ANY (ARRAY['compatible'::text, 'incompatible'::text, 'requires'::text, 'conditional'::text]))),
    CONSTRAINT compatibility_rule_status_check CHECK ((status = ANY (ARRAY['unsupported'::text, 'proposed'::text, 'accepted'::text, 'rejected'::text, 'corrected'::text, 'deferred'::text])))
);


--
-- Name: compatibility_rule_evidence; Type: TABLE; Schema: rag_v2; Owner: -
--

CREATE TABLE rag_v2.compatibility_rule_evidence (
    compatibility_rule_id uuid NOT NULL,
    evidence_id uuid NOT NULL
);


--
-- Name: component_type; Type: TABLE; Schema: rag_v2; Owner: -
--

CREATE TABLE rag_v2.component_type (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    code text NOT NULL,
    name text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT component_type_code_check CHECK ((code ~ '^[a-z][a-z0-9_]*$'::text)),
    CONSTRAINT component_type_name_check CHECK ((btrim(name) <> ''::text))
);


--
-- Name: document; Type: TABLE; Schema: rag_v2; Owner: -
--

CREATE TABLE rag_v2.document (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    title text NOT NULL,
    document_type text,
    availability text DEFAULT 'available'::text NOT NULL,
    deactivated_at timestamp with time zone,
    removed_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT document_availability_check CHECK ((availability = ANY (ARRAY['available'::text, 'deactivated'::text, 'removed'::text]))),
    CONSTRAINT document_title_check CHECK ((btrim(title) <> ''::text))
);


--
-- Name: document_error; Type: TABLE; Schema: rag_v2; Owner: -
--

CREATE TABLE rag_v2.document_error (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    document_id uuid,
    document_version_id uuid,
    step_name text NOT NULL,
    error_message text NOT NULL,
    retry_count integer DEFAULT 0 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT document_error_retry_count_check CHECK ((retry_count >= 0))
);


--
-- Name: document_source; Type: TABLE; Schema: rag_v2; Owner: -
--

CREATE TABLE rag_v2.document_source (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    document_id uuid NOT NULL,
    source_system text NOT NULL,
    source_key text NOT NULL,
    source_uri text NOT NULL,
    last_seen_content_hash text,
    is_available boolean DEFAULT true NOT NULL,
    first_seen_at timestamp with time zone DEFAULT now() NOT NULL,
    last_seen_at timestamp with time zone DEFAULT now() NOT NULL,
    source_instance text,
    CONSTRAINT document_source_instance_valid CHECK (((source_system <> 'nextcloud'::text) OR ((source_instance IS NOT NULL) AND (btrim(source_instance) <> ''::text)))),
    CONSTRAINT document_source_last_seen_content_hash_check CHECK (((last_seen_content_hash IS NULL) OR (last_seen_content_hash ~ '^[0-9a-f]{64}$'::text))),
    CONSTRAINT document_source_source_key_check CHECK ((btrim(source_key) <> ''::text)),
    CONSTRAINT document_source_source_system_check CHECK ((btrim(source_system) <> ''::text)),
    CONSTRAINT document_source_source_uri_check CHECK ((btrim(source_uri) <> ''::text))
);


--
-- Name: document_version; Type: TABLE; Schema: rag_v2; Owner: -
--

CREATE TABLE rag_v2.document_version (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    document_id uuid NOT NULL,
    version_no integer NOT NULL,
    content_hash text NOT NULL,
    processing_state text DEFAULT 'discovered'::text NOT NULL,
    state text,
    source_filename text,
    archive_uri text,
    mime_type text,
    byte_size bigint,
    indexed_at timestamp with time zone,
    superseded_at timestamp with time zone,
    archive_after timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT document_version_byte_size_check CHECK (((byte_size IS NULL) OR (byte_size >= 0))),
    CONSTRAINT document_version_check CHECK (((state IS NULL) OR (processing_state = 'indexed'::text))),
    CONSTRAINT document_version_content_hash_check CHECK ((content_hash ~ '^[0-9a-f]{64}$'::text)),
    CONSTRAINT document_version_processing_state_check CHECK ((processing_state = ANY (ARRAY['discovered'::text, 'processing'::text, 'indexed'::text, 'failed'::text]))),
    CONSTRAINT document_version_state_check CHECK ((state = ANY (ARRAY['active'::text, 'superseded'::text, 'archived'::text]))),
    CONSTRAINT document_version_version_no_check CHECK ((version_no > 0))
);


--
-- Name: embedding_model; Type: TABLE; Schema: rag_v2; Owner: -
--

CREATE TABLE rag_v2.embedding_model (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    model_name text NOT NULL,
    dimensions integer NOT NULL,
    metric text DEFAULT 'cosine'::text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT embedding_model_dimensions_check CHECK (((dimensions > 0) AND (dimensions <= 16000))),
    CONSTRAINT embedding_model_metric_check CHECK ((metric = ANY (ARRAY['cosine'::text, 'l2'::text, 'ip'::text]))),
    CONSTRAINT embedding_model_model_name_check CHECK ((btrim(model_name) <> ''::text))
);


--
-- Name: evidence; Type: TABLE; Schema: rag_v2; Owner: -
--

CREATE TABLE rag_v2.evidence (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    evidence_kind text NOT NULL,
    document_version_id uuid,
    page_number integer,
    source_locator text,
    excerpt text,
    test_date date,
    test_setup text,
    availability text DEFAULT 'available'::text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT evidence_availability_check CHECK ((availability = ANY (ARRAY['available'::text, 'source_unavailable'::text]))),
    CONSTRAINT evidence_check CHECK ((((evidence_kind = 'external'::text) AND (document_version_id IS NOT NULL) AND (excerpt IS NOT NULL) AND (btrim(excerpt) <> ''::text)) OR ((evidence_kind = 'self_tested'::text) AND (test_date IS NOT NULL) AND (test_setup IS NOT NULL) AND (btrim(test_setup) <> ''::text)))),
    CONSTRAINT evidence_evidence_kind_check CHECK ((evidence_kind = ANY (ARRAY['external'::text, 'self_tested'::text]))),
    CONSTRAINT evidence_page_number_check CHECK (((page_number IS NULL) OR (page_number > 0)))
);


--
-- Name: fact; Type: TABLE; Schema: rag_v2; Owner: -
--

CREATE TABLE rag_v2.fact (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    subject_id uuid NOT NULL,
    property_id uuid NOT NULL,
    value_numeric numeric,
    value_text text,
    unit_symbol text,
    status text DEFAULT 'proposed'::text NOT NULL,
    confidence numeric(4,3),
    valid_from timestamp with time zone DEFAULT now() NOT NULL,
    valid_to timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT fact_check CHECK ((num_nonnulls(value_numeric, value_text) = 1)),
    CONSTRAINT fact_check1 CHECK (((valid_to IS NULL) OR (valid_to > valid_from))),
    CONSTRAINT fact_confidence_check CHECK (((confidence >= (0)::numeric) AND (confidence <= (1)::numeric))),
    CONSTRAINT fact_status_check CHECK ((status = ANY (ARRAY['proposed'::text, 'accepted'::text, 'rejected'::text, 'corrected'::text, 'deferred'::text]))),
    CONSTRAINT fact_value_text_check CHECK (((value_text IS NULL) OR (btrim(value_text) <> ''::text)))
);


--
-- Name: fact_evidence; Type: TABLE; Schema: rag_v2; Owner: -
--

CREATE TABLE rag_v2.fact_evidence (
    fact_id uuid NOT NULL,
    evidence_id uuid NOT NULL
);


--
-- Name: installation; Type: TABLE; Schema: rag_v2; Owner: -
--

CREATE TABLE rag_v2.installation (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    unit_id uuid NOT NULL,
    system_id uuid NOT NULL,
    slot_name text,
    valid_from timestamp with time zone DEFAULT now() NOT NULL,
    valid_to timestamp with time zone,
    notes text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT installation_check CHECK (((valid_to IS NULL) OR (valid_to > valid_from)))
);


--
-- Name: knowledge_subject; Type: TABLE; Schema: rag_v2; Owner: -
--

CREATE TABLE rag_v2.knowledge_subject (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    article_id uuid,
    article_revision_id uuid,
    document_id uuid,
    reference_entity_id uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT knowledge_subject_check CHECK ((num_nonnulls(article_id, article_revision_id, document_id, reference_entity_id) = 1))
);


--
-- Name: processing_artifact; Type: TABLE; Schema: rag_v2; Owner: -
--

CREATE TABLE rag_v2.processing_artifact (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    processing_step_id uuid NOT NULL,
    artifact_kind text NOT NULL,
    artifact_uri text NOT NULL,
    content_hash text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT processing_artifact_artifact_kind_check CHECK ((btrim(artifact_kind) <> ''::text)),
    CONSTRAINT processing_artifact_artifact_uri_check CHECK ((btrim(artifact_uri) <> ''::text)),
    CONSTRAINT processing_artifact_content_hash_check CHECK (((content_hash IS NULL) OR (content_hash ~ '^[0-9a-f]{64}$'::text)))
);


--
-- Name: processing_job; Type: TABLE; Schema: rag_v2; Owner: -
--

CREATE TABLE rag_v2.processing_job (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    document_version_id uuid,
    job_type text NOT NULL,
    status text DEFAULT 'pending'::text NOT NULL,
    attempts integer DEFAULT 0 NOT NULL,
    max_attempts integer DEFAULT 3 NOT NULL,
    lease_owner text,
    lease_until timestamp with time zone,
    last_error text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    completed_at timestamp with time zone,
    CONSTRAINT processing_job_attempts_check CHECK ((attempts >= 0)),
    CONSTRAINT processing_job_check CHECK ((attempts <= max_attempts)),
    CONSTRAINT processing_job_job_type_check CHECK ((btrim(job_type) <> ''::text)),
    CONSTRAINT processing_job_max_attempts_check CHECK ((max_attempts > 0)),
    CONSTRAINT processing_job_status_check CHECK ((status = ANY (ARRAY['pending'::text, 'running'::text, 'completed'::text, 'failed'::text, 'cancelled'::text])))
);


--
-- Name: processing_step; Type: TABLE; Schema: rag_v2; Owner: -
--

CREATE TABLE rag_v2.processing_step (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    processing_job_id uuid NOT NULL,
    step_name text NOT NULL,
    status text DEFAULT 'pending'::text NOT NULL,
    input_hash text,
    attempts integer DEFAULT 0 NOT NULL,
    max_attempts integer DEFAULT 3 NOT NULL,
    lease_owner text,
    lease_until timestamp with time zone,
    last_error text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    completed_at timestamp with time zone,
    CONSTRAINT processing_step_attempts_check CHECK ((attempts >= 0)),
    CONSTRAINT processing_step_check CHECK ((attempts <= max_attempts)),
    CONSTRAINT processing_step_input_hash_check CHECK (((input_hash IS NULL) OR (input_hash ~ '^[0-9a-f]{64}$'::text))),
    CONSTRAINT processing_step_max_attempts_check CHECK ((max_attempts > 0)),
    CONSTRAINT processing_step_status_check CHECK ((status = ANY (ARRAY['pending'::text, 'running'::text, 'completed'::text, 'failed'::text, 'skipped'::text]))),
    CONSTRAINT processing_step_step_name_check CHECK ((btrim(step_name) <> ''::text))
);


--
-- Name: property; Type: TABLE; Schema: rag_v2; Owner: -
--

CREATE TABLE rag_v2.property (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    property_key text NOT NULL,
    name text NOT NULL,
    value_type text NOT NULL,
    canonical_unit text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT property_check CHECK (((value_type = 'numeric'::text) OR (canonical_unit IS NULL))),
    CONSTRAINT property_name_check CHECK ((btrim(name) <> ''::text)),
    CONSTRAINT property_property_key_check CHECK ((property_key ~ '^[a-z][a-z0-9_]*$'::text)),
    CONSTRAINT property_value_type_check CHECK ((value_type = ANY (ARRAY['numeric'::text, 'text'::text])))
);


--
-- Name: property_component_type; Type: TABLE; Schema: rag_v2; Owner: -
--

CREATE TABLE rag_v2.property_component_type (
    property_id uuid NOT NULL,
    component_type_id uuid NOT NULL
);


--
-- Name: query_log; Type: TABLE; Schema: rag_v2; Owner: -
--

CREATE TABLE rag_v2.query_log (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    question text NOT NULL,
    answer text,
    used_sources jsonb DEFAULT '[]'::jsonb NOT NULL,
    evaluation jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT query_log_used_sources_check CHECK ((jsonb_typeof(used_sources) = 'array'::text))
);


--
-- Name: reference_entity; Type: TABLE; Schema: rag_v2; Owner: -
--

CREATE TABLE rag_v2.reference_entity (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    entity_type text NOT NULL,
    entity_key text NOT NULL,
    name text NOT NULL,
    description text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT reference_entity_entity_key_check CHECK ((btrim(entity_key) <> ''::text)),
    CONSTRAINT reference_entity_entity_type_check CHECK ((entity_type = ANY (ARRAY['interface'::text, 'chipset'::text, 'software'::text, 'driver'::text, 'graphics_api'::text, 'standard'::text, 'other'::text]))),
    CONSTRAINT reference_entity_name_check CHECK ((btrim(name) <> ''::text))
);


--
-- Name: review_batch; Type: TABLE; Schema: rag_v2; Owner: -
--

CREATE TABLE rag_v2.review_batch (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    document_version_id uuid,
    title text,
    status text DEFAULT 'open'::text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    closed_at timestamp with time zone,
    CONSTRAINT review_batch_status_check CHECK ((status = ANY (ARRAY['open'::text, 'closed'::text])))
);


--
-- Name: review_decision; Type: TABLE; Schema: rag_v2; Owner: -
--

CREATE TABLE rag_v2.review_decision (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    review_item_id uuid NOT NULL,
    decision text NOT NULL,
    decided_by text NOT NULL,
    reason text,
    old_value jsonb,
    new_value jsonb,
    decided_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT review_decision_decided_by_check CHECK ((btrim(decided_by) <> ''::text)),
    CONSTRAINT review_decision_decision_check CHECK ((decision = ANY (ARRAY['accepted'::text, 'rejected'::text, 'corrected'::text, 'deferred'::text])))
);


--
-- Name: review_item; Type: TABLE; Schema: rag_v2; Owner: -
--

CREATE TABLE rag_v2.review_item (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    review_batch_id uuid NOT NULL,
    item_kind text NOT NULL,
    proposal jsonb NOT NULL,
    status text DEFAULT 'proposed'::text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT review_item_item_kind_check CHECK ((item_kind = ANY (ARRAY['fact'::text, 'compatibility'::text, 'document_identity'::text, 'inventory'::text]))),
    CONSTRAINT review_item_proposal_check CHECK ((jsonb_typeof(proposal) = 'object'::text)),
    CONSTRAINT review_item_status_check CHECK ((status = ANY (ARRAY['proposed'::text, 'accepted'::text, 'rejected'::text, 'corrected'::text, 'deferred'::text])))
);


--
-- Name: schema_migration; Type: TABLE; Schema: rag_v2; Owner: -
--

CREATE TABLE rag_v2.schema_migration (
    version integer NOT NULL,
    description text NOT NULL,
    applied_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT schema_migration_version_check CHECK ((version > 0))
);


--
-- Name: storage_assignment; Type: TABLE; Schema: rag_v2; Owner: -
--

CREATE TABLE rag_v2.storage_assignment (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    unit_id uuid NOT NULL,
    storage_location_id uuid NOT NULL,
    valid_from timestamp with time zone DEFAULT now() NOT NULL,
    valid_to timestamp with time zone,
    notes text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT storage_assignment_check CHECK (((valid_to IS NULL) OR (valid_to > valid_from)))
);


--
-- Name: storage_location; Type: TABLE; Schema: rag_v2; Owner: -
--

CREATE TABLE rag_v2.storage_location (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    code text NOT NULL,
    description text,
    parent_id uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT storage_location_check CHECK ((parent_id IS DISTINCT FROM id)),
    CONSTRAINT storage_location_code_check CHECK ((btrim(code) <> ''::text))
);


--
-- Name: sync_run; Type: TABLE; Schema: rag_v2; Owner: -
--

CREATE TABLE rag_v2.sync_run (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    started_at timestamp with time zone DEFAULT now() NOT NULL,
    finished_at timestamp with time zone,
    apply_mode boolean DEFAULT false NOT NULL,
    status text DEFAULT 'running'::text NOT NULL,
    discovered integer DEFAULT 0 NOT NULL,
    changed integer DEFAULT 0 NOT NULL,
    archived integer DEFAULT 0 NOT NULL,
    deactivated integer DEFAULT 0 NOT NULL,
    removed integer DEFAULT 0 NOT NULL,
    errors integer DEFAULT 0 NOT NULL,
    details jsonb DEFAULT '{}'::jsonb NOT NULL,
    CONSTRAINT sync_run_archived_check CHECK ((archived >= 0)),
    CONSTRAINT sync_run_changed_check CHECK ((changed >= 0)),
    CONSTRAINT sync_run_deactivated_check CHECK ((deactivated >= 0)),
    CONSTRAINT sync_run_discovered_check CHECK ((discovered >= 0)),
    CONSTRAINT sync_run_errors_check CHECK ((errors >= 0)),
    CONSTRAINT sync_run_removed_check CHECK ((removed >= 0)),
    CONSTRAINT sync_run_status_check CHECK ((status = ANY (ARRAY['running'::text, 'completed'::text, 'failed'::text, 'blocked'::text])))
);


--
-- Name: system; Type: TABLE; Schema: rag_v2; Owner: -
--

CREATE TABLE rag_v2.system (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    name text NOT NULL,
    notes text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT system_name_check CHECK ((btrim(name) <> ''::text))
);


--
-- Name: trusted_source; Type: TABLE; Schema: rag_v2; Owner: -
--

CREATE TABLE rag_v2.trusted_source (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    source_system text NOT NULL,
    source_key text NOT NULL,
    enabled boolean DEFAULT false NOT NULL,
    authorized_by text NOT NULL,
    authorized_at timestamp with time zone DEFAULT now() NOT NULL,
    notes text,
    CONSTRAINT trusted_source_authorized_by_check CHECK ((btrim(authorized_by) <> ''::text))
);


--
-- Name: unit; Type: TABLE; Schema: rag_v2; Owner: -
--

CREATE TABLE rag_v2.unit (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    article_id uuid NOT NULL,
    article_revision_id uuid,
    inventory_number text NOT NULL,
    serial_number text,
    completeness text,
    functional_state text DEFAULT 'untested'::text NOT NULL,
    location_state text DEFAULT 'unknown'::text NOT NULL,
    notes text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT unit_completeness_check CHECK ((completeness = ANY (ARRAY['complete'::text, 'incomplete'::text]))),
    CONSTRAINT unit_functional_state_check CHECK ((functional_state = ANY (ARRAY['working'::text, 'needs_repair'::text, 'defective'::text, 'untested'::text]))),
    CONSTRAINT unit_inventory_number_check CHECK ((btrim(inventory_number) <> ''::text)),
    CONSTRAINT unit_location_state_check CHECK ((location_state = ANY (ARRAY['unknown'::text, 'installed'::text, 'stored'::text])))
);


--
-- Name: unit_condition_history; Type: TABLE; Schema: rag_v2; Owner: -
--

CREATE TABLE rag_v2.unit_condition_history (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    unit_id uuid NOT NULL,
    changed_at timestamp with time zone DEFAULT now() NOT NULL,
    changed_by text DEFAULT SESSION_USER NOT NULL,
    old_completeness text,
    new_completeness text,
    old_functional_state text,
    new_functional_state text
);


--
-- Name: write_gate; Type: TABLE; Schema: rag_v2; Owner: -
--

CREATE TABLE rag_v2.write_gate (
    id boolean DEFAULT true NOT NULL,
    writes_enabled boolean DEFAULT false NOT NULL,
    reason text DEFAULT 'Initialisierung: Schreibfreigabe ausstehend'::text NOT NULL,
    changed_by text,
    changed_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT write_gate_id_check CHECK (id)
);


--
-- Name: article_alias article_alias_article_id_alias_key; Type: CONSTRAINT; Schema: rag_v2; Owner: -
--

ALTER TABLE ONLY rag_v2.article_alias
    ADD CONSTRAINT article_alias_article_id_alias_key UNIQUE (article_id, alias);


--
-- Name: article_alias article_alias_pkey; Type: CONSTRAINT; Schema: rag_v2; Owner: -
--

ALTER TABLE ONLY rag_v2.article_alias
    ADD CONSTRAINT article_alias_pkey PRIMARY KEY (id);


--
-- Name: article article_pkey; Type: CONSTRAINT; Schema: rag_v2; Owner: -
--

ALTER TABLE ONLY rag_v2.article
    ADD CONSTRAINT article_pkey PRIMARY KEY (id);


--
-- Name: article_revision article_revision_article_id_revision_key; Type: CONSTRAINT; Schema: rag_v2; Owner: -
--

ALTER TABLE ONLY rag_v2.article_revision
    ADD CONSTRAINT article_revision_article_id_revision_key UNIQUE (article_id, revision);


--
-- Name: article_revision article_revision_id_article_id_key; Type: CONSTRAINT; Schema: rag_v2; Owner: -
--

ALTER TABLE ONLY rag_v2.article_revision
    ADD CONSTRAINT article_revision_id_article_id_key UNIQUE (id, article_id);


--
-- Name: article_revision article_revision_pkey; Type: CONSTRAINT; Schema: rag_v2; Owner: -
--

ALTER TABLE ONLY rag_v2.article_revision
    ADD CONSTRAINT article_revision_pkey PRIMARY KEY (id);


--
-- Name: chunk chunk_document_version_id_sequence_no_key; Type: CONSTRAINT; Schema: rag_v2; Owner: -
--

ALTER TABLE ONLY rag_v2.chunk
    ADD CONSTRAINT chunk_document_version_id_sequence_no_key UNIQUE (document_version_id, sequence_no);


--
-- Name: chunk_embedding chunk_embedding_chunk_id_embedding_model_id_key; Type: CONSTRAINT; Schema: rag_v2; Owner: -
--

ALTER TABLE ONLY rag_v2.chunk_embedding
    ADD CONSTRAINT chunk_embedding_chunk_id_embedding_model_id_key UNIQUE (chunk_id, embedding_model_id);


--
-- Name: chunk_embedding chunk_embedding_pkey; Type: CONSTRAINT; Schema: rag_v2; Owner: -
--

ALTER TABLE ONLY rag_v2.chunk_embedding
    ADD CONSTRAINT chunk_embedding_pkey PRIMARY KEY (id);


--
-- Name: chunk chunk_pkey; Type: CONSTRAINT; Schema: rag_v2; Owner: -
--

ALTER TABLE ONLY rag_v2.chunk
    ADD CONSTRAINT chunk_pkey PRIMARY KEY (id);


--
-- Name: compatibility_rule_evidence compatibility_rule_evidence_pkey; Type: CONSTRAINT; Schema: rag_v2; Owner: -
--

ALTER TABLE ONLY rag_v2.compatibility_rule_evidence
    ADD CONSTRAINT compatibility_rule_evidence_pkey PRIMARY KEY (compatibility_rule_id, evidence_id);


--
-- Name: compatibility_rule compatibility_rule_pkey; Type: CONSTRAINT; Schema: rag_v2; Owner: -
--

ALTER TABLE ONLY rag_v2.compatibility_rule
    ADD CONSTRAINT compatibility_rule_pkey PRIMARY KEY (id);


--
-- Name: component_type component_type_code_key; Type: CONSTRAINT; Schema: rag_v2; Owner: -
--

ALTER TABLE ONLY rag_v2.component_type
    ADD CONSTRAINT component_type_code_key UNIQUE (code);


--
-- Name: component_type component_type_pkey; Type: CONSTRAINT; Schema: rag_v2; Owner: -
--

ALTER TABLE ONLY rag_v2.component_type
    ADD CONSTRAINT component_type_pkey PRIMARY KEY (id);


--
-- Name: document_error document_error_pkey; Type: CONSTRAINT; Schema: rag_v2; Owner: -
--

ALTER TABLE ONLY rag_v2.document_error
    ADD CONSTRAINT document_error_pkey PRIMARY KEY (id);


--
-- Name: document document_pkey; Type: CONSTRAINT; Schema: rag_v2; Owner: -
--

ALTER TABLE ONLY rag_v2.document
    ADD CONSTRAINT document_pkey PRIMARY KEY (id);


--
-- Name: document_source document_source_pkey; Type: CONSTRAINT; Schema: rag_v2; Owner: -
--

ALTER TABLE ONLY rag_v2.document_source
    ADD CONSTRAINT document_source_pkey PRIMARY KEY (id);


--
-- Name: document_version document_version_document_id_version_no_key; Type: CONSTRAINT; Schema: rag_v2; Owner: -
--

ALTER TABLE ONLY rag_v2.document_version
    ADD CONSTRAINT document_version_document_id_version_no_key UNIQUE (document_id, version_no);


--
-- Name: document_version document_version_pkey; Type: CONSTRAINT; Schema: rag_v2; Owner: -
--

ALTER TABLE ONLY rag_v2.document_version
    ADD CONSTRAINT document_version_pkey PRIMARY KEY (id);


--
-- Name: embedding_model embedding_model_id_dimensions_key; Type: CONSTRAINT; Schema: rag_v2; Owner: -
--

ALTER TABLE ONLY rag_v2.embedding_model
    ADD CONSTRAINT embedding_model_id_dimensions_key UNIQUE (id, dimensions);


--
-- Name: embedding_model embedding_model_model_name_key; Type: CONSTRAINT; Schema: rag_v2; Owner: -
--

ALTER TABLE ONLY rag_v2.embedding_model
    ADD CONSTRAINT embedding_model_model_name_key UNIQUE (model_name);


--
-- Name: embedding_model embedding_model_pkey; Type: CONSTRAINT; Schema: rag_v2; Owner: -
--

ALTER TABLE ONLY rag_v2.embedding_model
    ADD CONSTRAINT embedding_model_pkey PRIMARY KEY (id);


--
-- Name: evidence evidence_pkey; Type: CONSTRAINT; Schema: rag_v2; Owner: -
--

ALTER TABLE ONLY rag_v2.evidence
    ADD CONSTRAINT evidence_pkey PRIMARY KEY (id);


--
-- Name: fact_evidence fact_evidence_pkey; Type: CONSTRAINT; Schema: rag_v2; Owner: -
--

ALTER TABLE ONLY rag_v2.fact_evidence
    ADD CONSTRAINT fact_evidence_pkey PRIMARY KEY (fact_id, evidence_id);


--
-- Name: fact fact_pkey; Type: CONSTRAINT; Schema: rag_v2; Owner: -
--

ALTER TABLE ONLY rag_v2.fact
    ADD CONSTRAINT fact_pkey PRIMARY KEY (id);


--
-- Name: installation installation_pkey; Type: CONSTRAINT; Schema: rag_v2; Owner: -
--

ALTER TABLE ONLY rag_v2.installation
    ADD CONSTRAINT installation_pkey PRIMARY KEY (id);


--
-- Name: knowledge_subject knowledge_subject_pkey; Type: CONSTRAINT; Schema: rag_v2; Owner: -
--

ALTER TABLE ONLY rag_v2.knowledge_subject
    ADD CONSTRAINT knowledge_subject_pkey PRIMARY KEY (id);


--
-- Name: processing_artifact processing_artifact_pkey; Type: CONSTRAINT; Schema: rag_v2; Owner: -
--

ALTER TABLE ONLY rag_v2.processing_artifact
    ADD CONSTRAINT processing_artifact_pkey PRIMARY KEY (id);


--
-- Name: processing_artifact processing_artifact_processing_step_id_artifact_kind_artifa_key; Type: CONSTRAINT; Schema: rag_v2; Owner: -
--

ALTER TABLE ONLY rag_v2.processing_artifact
    ADD CONSTRAINT processing_artifact_processing_step_id_artifact_kind_artifa_key UNIQUE (processing_step_id, artifact_kind, artifact_uri);


--
-- Name: processing_job processing_job_pkey; Type: CONSTRAINT; Schema: rag_v2; Owner: -
--

ALTER TABLE ONLY rag_v2.processing_job
    ADD CONSTRAINT processing_job_pkey PRIMARY KEY (id);


--
-- Name: processing_step processing_step_pkey; Type: CONSTRAINT; Schema: rag_v2; Owner: -
--

ALTER TABLE ONLY rag_v2.processing_step
    ADD CONSTRAINT processing_step_pkey PRIMARY KEY (id);


--
-- Name: processing_step processing_step_processing_job_id_step_name_key; Type: CONSTRAINT; Schema: rag_v2; Owner: -
--

ALTER TABLE ONLY rag_v2.processing_step
    ADD CONSTRAINT processing_step_processing_job_id_step_name_key UNIQUE (processing_job_id, step_name);


--
-- Name: property_component_type property_component_type_pkey; Type: CONSTRAINT; Schema: rag_v2; Owner: -
--

ALTER TABLE ONLY rag_v2.property_component_type
    ADD CONSTRAINT property_component_type_pkey PRIMARY KEY (property_id, component_type_id);


--
-- Name: property property_pkey; Type: CONSTRAINT; Schema: rag_v2; Owner: -
--

ALTER TABLE ONLY rag_v2.property
    ADD CONSTRAINT property_pkey PRIMARY KEY (id);


--
-- Name: property property_property_key_key; Type: CONSTRAINT; Schema: rag_v2; Owner: -
--

ALTER TABLE ONLY rag_v2.property
    ADD CONSTRAINT property_property_key_key UNIQUE (property_key);


--
-- Name: query_log query_log_pkey; Type: CONSTRAINT; Schema: rag_v2; Owner: -
--

ALTER TABLE ONLY rag_v2.query_log
    ADD CONSTRAINT query_log_pkey PRIMARY KEY (id);


--
-- Name: reference_entity reference_entity_entity_type_entity_key_key; Type: CONSTRAINT; Schema: rag_v2; Owner: -
--

ALTER TABLE ONLY rag_v2.reference_entity
    ADD CONSTRAINT reference_entity_entity_type_entity_key_key UNIQUE (entity_type, entity_key);


--
-- Name: reference_entity reference_entity_pkey; Type: CONSTRAINT; Schema: rag_v2; Owner: -
--

ALTER TABLE ONLY rag_v2.reference_entity
    ADD CONSTRAINT reference_entity_pkey PRIMARY KEY (id);


--
-- Name: review_batch review_batch_pkey; Type: CONSTRAINT; Schema: rag_v2; Owner: -
--

ALTER TABLE ONLY rag_v2.review_batch
    ADD CONSTRAINT review_batch_pkey PRIMARY KEY (id);


--
-- Name: review_decision review_decision_pkey; Type: CONSTRAINT; Schema: rag_v2; Owner: -
--

ALTER TABLE ONLY rag_v2.review_decision
    ADD CONSTRAINT review_decision_pkey PRIMARY KEY (id);


--
-- Name: review_item review_item_pkey; Type: CONSTRAINT; Schema: rag_v2; Owner: -
--

ALTER TABLE ONLY rag_v2.review_item
    ADD CONSTRAINT review_item_pkey PRIMARY KEY (id);


--
-- Name: schema_migration schema_migration_pkey; Type: CONSTRAINT; Schema: rag_v2; Owner: -
--

ALTER TABLE ONLY rag_v2.schema_migration
    ADD CONSTRAINT schema_migration_pkey PRIMARY KEY (version);


--
-- Name: storage_assignment storage_assignment_pkey; Type: CONSTRAINT; Schema: rag_v2; Owner: -
--

ALTER TABLE ONLY rag_v2.storage_assignment
    ADD CONSTRAINT storage_assignment_pkey PRIMARY KEY (id);


--
-- Name: storage_location storage_location_code_key; Type: CONSTRAINT; Schema: rag_v2; Owner: -
--

ALTER TABLE ONLY rag_v2.storage_location
    ADD CONSTRAINT storage_location_code_key UNIQUE (code);


--
-- Name: storage_location storage_location_pkey; Type: CONSTRAINT; Schema: rag_v2; Owner: -
--

ALTER TABLE ONLY rag_v2.storage_location
    ADD CONSTRAINT storage_location_pkey PRIMARY KEY (id);


--
-- Name: sync_run sync_run_pkey; Type: CONSTRAINT; Schema: rag_v2; Owner: -
--

ALTER TABLE ONLY rag_v2.sync_run
    ADD CONSTRAINT sync_run_pkey PRIMARY KEY (id);


--
-- Name: system system_name_key; Type: CONSTRAINT; Schema: rag_v2; Owner: -
--

ALTER TABLE ONLY rag_v2.system
    ADD CONSTRAINT system_name_key UNIQUE (name);


--
-- Name: system system_pkey; Type: CONSTRAINT; Schema: rag_v2; Owner: -
--

ALTER TABLE ONLY rag_v2.system
    ADD CONSTRAINT system_pkey PRIMARY KEY (id);


--
-- Name: trusted_source trusted_source_pkey; Type: CONSTRAINT; Schema: rag_v2; Owner: -
--

ALTER TABLE ONLY rag_v2.trusted_source
    ADD CONSTRAINT trusted_source_pkey PRIMARY KEY (id);


--
-- Name: trusted_source trusted_source_source_system_source_key_key; Type: CONSTRAINT; Schema: rag_v2; Owner: -
--

ALTER TABLE ONLY rag_v2.trusted_source
    ADD CONSTRAINT trusted_source_source_system_source_key_key UNIQUE (source_system, source_key);


--
-- Name: unit_condition_history unit_condition_history_pkey; Type: CONSTRAINT; Schema: rag_v2; Owner: -
--

ALTER TABLE ONLY rag_v2.unit_condition_history
    ADD CONSTRAINT unit_condition_history_pkey PRIMARY KEY (id);


--
-- Name: unit unit_inventory_number_key; Type: CONSTRAINT; Schema: rag_v2; Owner: -
--

ALTER TABLE ONLY rag_v2.unit
    ADD CONSTRAINT unit_inventory_number_key UNIQUE (inventory_number);


--
-- Name: unit unit_pkey; Type: CONSTRAINT; Schema: rag_v2; Owner: -
--

ALTER TABLE ONLY rag_v2.unit
    ADD CONSTRAINT unit_pkey PRIMARY KEY (id);


--
-- Name: write_gate write_gate_pkey; Type: CONSTRAINT; Schema: rag_v2; Owner: -
--

ALTER TABLE ONLY rag_v2.write_gate
    ADD CONSTRAINT write_gate_pkey PRIMARY KEY (id);


--
-- Name: article_model_key_idx; Type: INDEX; Schema: rag_v2; Owner: -
--

CREATE INDEX article_model_key_idx ON rag_v2.article USING btree (model_key);


--
-- Name: chunk_embedding_model_idx; Type: INDEX; Schema: rag_v2; Owner: -
--

CREATE INDEX chunk_embedding_model_idx ON rag_v2.chunk_embedding USING btree (embedding_model_id);


--
-- Name: chunk_fulltext_idx; Type: INDEX; Schema: rag_v2; Owner: -
--

CREATE INDEX chunk_fulltext_idx ON rag_v2.chunk USING gin (search_vector);


--
-- Name: chunk_version_hash_idx; Type: INDEX; Schema: rag_v2; Owner: -
--

CREATE INDEX chunk_version_hash_idx ON rag_v2.chunk USING btree (document_version_id, content_hash);


--
-- Name: compatibility_subjects_idx; Type: INDEX; Schema: rag_v2; Owner: -
--

CREATE INDEX compatibility_subjects_idx ON rag_v2.compatibility_rule USING btree (left_subject_id, right_subject_id, status);


--
-- Name: document_one_current_version_idx; Type: INDEX; Schema: rag_v2; Owner: -
--

CREATE UNIQUE INDEX document_one_current_version_idx ON rag_v2.document_version USING btree (document_id) WHERE (state = 'active'::text);


--
-- Name: document_source_document_idx; Type: INDEX; Schema: rag_v2; Owner: -
--

CREATE INDEX document_source_document_idx ON rag_v2.document_source USING btree (document_id);


--
-- Name: document_source_identity_idx; Type: INDEX; Schema: rag_v2; Owner: -
--

CREATE UNIQUE INDEX document_source_identity_idx ON rag_v2.document_source USING btree (source_system, COALESCE(source_instance, ''::text), source_key);


--
-- Name: document_version_document_idx; Type: INDEX; Schema: rag_v2; Owner: -
--

CREATE INDEX document_version_document_idx ON rag_v2.document_version USING btree (document_id, state);


--
-- Name: document_version_hash_idx; Type: INDEX; Schema: rag_v2; Owner: -
--

CREATE INDEX document_version_hash_idx ON rag_v2.document_version USING btree (content_hash);


--
-- Name: evidence_version_idx; Type: INDEX; Schema: rag_v2; Owner: -
--

CREATE INDEX evidence_version_idx ON rag_v2.evidence USING btree (document_version_id);


--
-- Name: fact_subject_property_idx; Type: INDEX; Schema: rag_v2; Owner: -
--

CREATE INDEX fact_subject_property_idx ON rag_v2.fact USING btree (subject_id, property_id, status);


--
-- Name: installation_one_active_per_unit_idx; Type: INDEX; Schema: rag_v2; Owner: -
--

CREATE UNIQUE INDEX installation_one_active_per_unit_idx ON rag_v2.installation USING btree (unit_id) WHERE (valid_to IS NULL);


--
-- Name: knowledge_subject_article_unique; Type: INDEX; Schema: rag_v2; Owner: -
--

CREATE UNIQUE INDEX knowledge_subject_article_unique ON rag_v2.knowledge_subject USING btree (article_id) WHERE (article_id IS NOT NULL);


--
-- Name: knowledge_subject_document_unique; Type: INDEX; Schema: rag_v2; Owner: -
--

CREATE UNIQUE INDEX knowledge_subject_document_unique ON rag_v2.knowledge_subject USING btree (document_id) WHERE (document_id IS NOT NULL);


--
-- Name: knowledge_subject_reference_unique; Type: INDEX; Schema: rag_v2; Owner: -
--

CREATE UNIQUE INDEX knowledge_subject_reference_unique ON rag_v2.knowledge_subject USING btree (reference_entity_id) WHERE (reference_entity_id IS NOT NULL);


--
-- Name: knowledge_subject_revision_unique; Type: INDEX; Schema: rag_v2; Owner: -
--

CREATE UNIQUE INDEX knowledge_subject_revision_unique ON rag_v2.knowledge_subject USING btree (article_revision_id) WHERE (article_revision_id IS NOT NULL);


--
-- Name: processing_job_queue_idx; Type: INDEX; Schema: rag_v2; Owner: -
--

CREATE INDEX processing_job_queue_idx ON rag_v2.processing_job USING btree (status, lease_until, created_at);


--
-- Name: review_decision_item_idx; Type: INDEX; Schema: rag_v2; Owner: -
--

CREATE INDEX review_decision_item_idx ON rag_v2.review_decision USING btree (review_item_id, decided_at);


--
-- Name: storage_one_active_per_unit_idx; Type: INDEX; Schema: rag_v2; Owner: -
--

CREATE UNIQUE INDEX storage_one_active_per_unit_idx ON rag_v2.storage_assignment USING btree (unit_id) WHERE (valid_to IS NULL);


--
-- Name: unit_article_idx; Type: INDEX; Schema: rag_v2; Owner: -
--

CREATE INDEX unit_article_idx ON rag_v2.unit USING btree (article_id);


--
-- Name: unit_serial_idx; Type: INDEX; Schema: rag_v2; Owner: -
--

CREATE INDEX unit_serial_idx ON rag_v2.unit USING btree (serial_number) WHERE (serial_number IS NOT NULL);


--
-- Name: fact_evidence fact_evidence_integrity; Type: TRIGGER; Schema: rag_v2; Owner: -
--

CREATE CONSTRAINT TRIGGER fact_evidence_integrity AFTER INSERT OR DELETE OR UPDATE ON rag_v2.fact_evidence DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION rag_v2.check_accepted_evidence_trigger();


--
-- Name: fact fact_evidence_required; Type: TRIGGER; Schema: rag_v2; Owner: -
--

CREATE CONSTRAINT TRIGGER fact_evidence_required AFTER INSERT OR UPDATE ON rag_v2.fact DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION rag_v2.check_accepted_evidence_trigger();


--
-- Name: fact fact_no_accepted_rewrite; Type: TRIGGER; Schema: rag_v2; Owner: -
--

CREATE TRIGGER fact_no_accepted_rewrite BEFORE UPDATE ON rag_v2.fact FOR EACH ROW EXECUTE FUNCTION rag_v2.prevent_accepted_fact_rewrite();


--
-- Name: fact fact_property_validation; Type: TRIGGER; Schema: rag_v2; Owner: -
--

CREATE TRIGGER fact_property_validation BEFORE INSERT OR UPDATE OF property_id, subject_id, value_numeric, value_text, unit_symbol ON rag_v2.fact FOR EACH ROW EXECUTE FUNCTION rag_v2.validate_fact_value_trigger();


--
-- Name: installation installation_location_integrity; Type: TRIGGER; Schema: rag_v2; Owner: -
--

CREATE CONSTRAINT TRIGGER installation_location_integrity AFTER INSERT OR DELETE OR UPDATE ON rag_v2.installation DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION rag_v2.check_unit_location_trigger();


--
-- Name: installation installation_no_rewrite; Type: TRIGGER; Schema: rag_v2; Owner: -
--

CREATE TRIGGER installation_no_rewrite BEFORE UPDATE ON rag_v2.installation FOR EACH ROW EXECUTE FUNCTION rag_v2.prevent_assignment_rewrite();


--
-- Name: review_decision review_decision_immutable; Type: TRIGGER; Schema: rag_v2; Owner: -
--

CREATE TRIGGER review_decision_immutable BEFORE DELETE OR UPDATE ON rag_v2.review_decision FOR EACH ROW EXECUTE FUNCTION rag_v2.prevent_review_decision_rewrite();


--
-- Name: compatibility_rule_evidence rule_evidence_integrity; Type: TRIGGER; Schema: rag_v2; Owner: -
--

CREATE CONSTRAINT TRIGGER rule_evidence_integrity AFTER INSERT OR DELETE OR UPDATE ON rag_v2.compatibility_rule_evidence DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION rag_v2.check_accepted_evidence_trigger();


--
-- Name: compatibility_rule rule_evidence_required; Type: TRIGGER; Schema: rag_v2; Owner: -
--

CREATE CONSTRAINT TRIGGER rule_evidence_required AFTER INSERT OR UPDATE ON rag_v2.compatibility_rule DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION rag_v2.check_accepted_evidence_trigger();


--
-- Name: storage_assignment storage_assignment_no_rewrite; Type: TRIGGER; Schema: rag_v2; Owner: -
--

CREATE TRIGGER storage_assignment_no_rewrite BEFORE UPDATE ON rag_v2.storage_assignment FOR EACH ROW EXECUTE FUNCTION rag_v2.prevent_assignment_rewrite();


--
-- Name: storage_assignment storage_location_integrity; Type: TRIGGER; Schema: rag_v2; Owner: -
--

CREATE CONSTRAINT TRIGGER storage_location_integrity AFTER INSERT OR DELETE OR UPDATE ON rag_v2.storage_assignment DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION rag_v2.check_unit_location_trigger();


--
-- Name: unit unit_condition_audit; Type: TRIGGER; Schema: rag_v2; Owner: -
--

CREATE TRIGGER unit_condition_audit AFTER INSERT OR UPDATE OF completeness, functional_state ON rag_v2.unit FOR EACH ROW EXECUTE FUNCTION rag_v2.audit_unit_condition();


--
-- Name: unit unit_location_integrity; Type: TRIGGER; Schema: rag_v2; Owner: -
--

CREATE CONSTRAINT TRIGGER unit_location_integrity AFTER INSERT OR UPDATE ON rag_v2.unit DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION rag_v2.check_unit_location_trigger();


--
-- Name: article_alias article_alias_article_id_fkey; Type: FK CONSTRAINT; Schema: rag_v2; Owner: -
--

ALTER TABLE ONLY rag_v2.article_alias
    ADD CONSTRAINT article_alias_article_id_fkey FOREIGN KEY (article_id) REFERENCES rag_v2.article(id) ON DELETE RESTRICT;


--
-- Name: article article_component_type_id_fkey; Type: FK CONSTRAINT; Schema: rag_v2; Owner: -
--

ALTER TABLE ONLY rag_v2.article
    ADD CONSTRAINT article_component_type_id_fkey FOREIGN KEY (component_type_id) REFERENCES rag_v2.component_type(id);


--
-- Name: article_revision article_revision_article_id_fkey; Type: FK CONSTRAINT; Schema: rag_v2; Owner: -
--

ALTER TABLE ONLY rag_v2.article_revision
    ADD CONSTRAINT article_revision_article_id_fkey FOREIGN KEY (article_id) REFERENCES rag_v2.article(id) ON DELETE RESTRICT;


--
-- Name: chunk chunk_document_version_id_fkey; Type: FK CONSTRAINT; Schema: rag_v2; Owner: -
--

ALTER TABLE ONLY rag_v2.chunk
    ADD CONSTRAINT chunk_document_version_id_fkey FOREIGN KEY (document_version_id) REFERENCES rag_v2.document_version(id) ON DELETE CASCADE;


--
-- Name: chunk_embedding chunk_embedding_chunk_id_fkey; Type: FK CONSTRAINT; Schema: rag_v2; Owner: -
--

ALTER TABLE ONLY rag_v2.chunk_embedding
    ADD CONSTRAINT chunk_embedding_chunk_id_fkey FOREIGN KEY (chunk_id) REFERENCES rag_v2.chunk(id) ON DELETE CASCADE;


--
-- Name: chunk_embedding chunk_embedding_embedding_model_id_dimensions_fkey; Type: FK CONSTRAINT; Schema: rag_v2; Owner: -
--

ALTER TABLE ONLY rag_v2.chunk_embedding
    ADD CONSTRAINT chunk_embedding_embedding_model_id_dimensions_fkey FOREIGN KEY (embedding_model_id, dimensions) REFERENCES rag_v2.embedding_model(id, dimensions) ON DELETE RESTRICT;


--
-- Name: compatibility_rule_evidence compatibility_rule_evidence_compatibility_rule_id_fkey; Type: FK CONSTRAINT; Schema: rag_v2; Owner: -
--

ALTER TABLE ONLY rag_v2.compatibility_rule_evidence
    ADD CONSTRAINT compatibility_rule_evidence_compatibility_rule_id_fkey FOREIGN KEY (compatibility_rule_id) REFERENCES rag_v2.compatibility_rule(id) ON DELETE CASCADE;


--
-- Name: compatibility_rule_evidence compatibility_rule_evidence_evidence_id_fkey; Type: FK CONSTRAINT; Schema: rag_v2; Owner: -
--

ALTER TABLE ONLY rag_v2.compatibility_rule_evidence
    ADD CONSTRAINT compatibility_rule_evidence_evidence_id_fkey FOREIGN KEY (evidence_id) REFERENCES rag_v2.evidence(id) ON DELETE RESTRICT;


--
-- Name: compatibility_rule compatibility_rule_left_subject_id_fkey; Type: FK CONSTRAINT; Schema: rag_v2; Owner: -
--

ALTER TABLE ONLY rag_v2.compatibility_rule
    ADD CONSTRAINT compatibility_rule_left_subject_id_fkey FOREIGN KEY (left_subject_id) REFERENCES rag_v2.knowledge_subject(id) ON DELETE RESTRICT;


--
-- Name: compatibility_rule compatibility_rule_right_subject_id_fkey; Type: FK CONSTRAINT; Schema: rag_v2; Owner: -
--

ALTER TABLE ONLY rag_v2.compatibility_rule
    ADD CONSTRAINT compatibility_rule_right_subject_id_fkey FOREIGN KEY (right_subject_id) REFERENCES rag_v2.knowledge_subject(id) ON DELETE RESTRICT;


--
-- Name: document_error document_error_document_id_fkey; Type: FK CONSTRAINT; Schema: rag_v2; Owner: -
--

ALTER TABLE ONLY rag_v2.document_error
    ADD CONSTRAINT document_error_document_id_fkey FOREIGN KEY (document_id) REFERENCES rag_v2.document(id) ON DELETE RESTRICT;


--
-- Name: document_error document_error_document_version_id_fkey; Type: FK CONSTRAINT; Schema: rag_v2; Owner: -
--

ALTER TABLE ONLY rag_v2.document_error
    ADD CONSTRAINT document_error_document_version_id_fkey FOREIGN KEY (document_version_id) REFERENCES rag_v2.document_version(id) ON DELETE RESTRICT;


--
-- Name: document_source document_source_document_id_fkey; Type: FK CONSTRAINT; Schema: rag_v2; Owner: -
--

ALTER TABLE ONLY rag_v2.document_source
    ADD CONSTRAINT document_source_document_id_fkey FOREIGN KEY (document_id) REFERENCES rag_v2.document(id) ON DELETE RESTRICT;


--
-- Name: document_version document_version_document_id_fkey; Type: FK CONSTRAINT; Schema: rag_v2; Owner: -
--

ALTER TABLE ONLY rag_v2.document_version
    ADD CONSTRAINT document_version_document_id_fkey FOREIGN KEY (document_id) REFERENCES rag_v2.document(id) ON DELETE RESTRICT;


--
-- Name: evidence evidence_document_version_id_fkey; Type: FK CONSTRAINT; Schema: rag_v2; Owner: -
--

ALTER TABLE ONLY rag_v2.evidence
    ADD CONSTRAINT evidence_document_version_id_fkey FOREIGN KEY (document_version_id) REFERENCES rag_v2.document_version(id) ON DELETE RESTRICT;


--
-- Name: fact_evidence fact_evidence_evidence_id_fkey; Type: FK CONSTRAINT; Schema: rag_v2; Owner: -
--

ALTER TABLE ONLY rag_v2.fact_evidence
    ADD CONSTRAINT fact_evidence_evidence_id_fkey FOREIGN KEY (evidence_id) REFERENCES rag_v2.evidence(id) ON DELETE RESTRICT;


--
-- Name: fact_evidence fact_evidence_fact_id_fkey; Type: FK CONSTRAINT; Schema: rag_v2; Owner: -
--

ALTER TABLE ONLY rag_v2.fact_evidence
    ADD CONSTRAINT fact_evidence_fact_id_fkey FOREIGN KEY (fact_id) REFERENCES rag_v2.fact(id) ON DELETE CASCADE;


--
-- Name: fact fact_property_id_fkey; Type: FK CONSTRAINT; Schema: rag_v2; Owner: -
--

ALTER TABLE ONLY rag_v2.fact
    ADD CONSTRAINT fact_property_id_fkey FOREIGN KEY (property_id) REFERENCES rag_v2.property(id) ON DELETE RESTRICT;


--
-- Name: fact fact_subject_id_fkey; Type: FK CONSTRAINT; Schema: rag_v2; Owner: -
--

ALTER TABLE ONLY rag_v2.fact
    ADD CONSTRAINT fact_subject_id_fkey FOREIGN KEY (subject_id) REFERENCES rag_v2.knowledge_subject(id) ON DELETE RESTRICT;


--
-- Name: installation installation_system_id_fkey; Type: FK CONSTRAINT; Schema: rag_v2; Owner: -
--

ALTER TABLE ONLY rag_v2.installation
    ADD CONSTRAINT installation_system_id_fkey FOREIGN KEY (system_id) REFERENCES rag_v2.system(id) ON DELETE RESTRICT;


--
-- Name: installation installation_unit_id_fkey; Type: FK CONSTRAINT; Schema: rag_v2; Owner: -
--

ALTER TABLE ONLY rag_v2.installation
    ADD CONSTRAINT installation_unit_id_fkey FOREIGN KEY (unit_id) REFERENCES rag_v2.unit(id) ON DELETE RESTRICT;


--
-- Name: knowledge_subject knowledge_subject_article_id_fkey; Type: FK CONSTRAINT; Schema: rag_v2; Owner: -
--

ALTER TABLE ONLY rag_v2.knowledge_subject
    ADD CONSTRAINT knowledge_subject_article_id_fkey FOREIGN KEY (article_id) REFERENCES rag_v2.article(id) ON DELETE RESTRICT;


--
-- Name: knowledge_subject knowledge_subject_article_revision_id_fkey; Type: FK CONSTRAINT; Schema: rag_v2; Owner: -
--

ALTER TABLE ONLY rag_v2.knowledge_subject
    ADD CONSTRAINT knowledge_subject_article_revision_id_fkey FOREIGN KEY (article_revision_id) REFERENCES rag_v2.article_revision(id) ON DELETE RESTRICT;


--
-- Name: knowledge_subject knowledge_subject_document_id_fkey; Type: FK CONSTRAINT; Schema: rag_v2; Owner: -
--

ALTER TABLE ONLY rag_v2.knowledge_subject
    ADD CONSTRAINT knowledge_subject_document_id_fkey FOREIGN KEY (document_id) REFERENCES rag_v2.document(id) ON DELETE RESTRICT;


--
-- Name: knowledge_subject knowledge_subject_reference_entity_id_fkey; Type: FK CONSTRAINT; Schema: rag_v2; Owner: -
--

ALTER TABLE ONLY rag_v2.knowledge_subject
    ADD CONSTRAINT knowledge_subject_reference_entity_id_fkey FOREIGN KEY (reference_entity_id) REFERENCES rag_v2.reference_entity(id) ON DELETE RESTRICT;


--
-- Name: processing_artifact processing_artifact_processing_step_id_fkey; Type: FK CONSTRAINT; Schema: rag_v2; Owner: -
--

ALTER TABLE ONLY rag_v2.processing_artifact
    ADD CONSTRAINT processing_artifact_processing_step_id_fkey FOREIGN KEY (processing_step_id) REFERENCES rag_v2.processing_step(id) ON DELETE RESTRICT;


--
-- Name: processing_job processing_job_document_version_id_fkey; Type: FK CONSTRAINT; Schema: rag_v2; Owner: -
--

ALTER TABLE ONLY rag_v2.processing_job
    ADD CONSTRAINT processing_job_document_version_id_fkey FOREIGN KEY (document_version_id) REFERENCES rag_v2.document_version(id) ON DELETE RESTRICT;


--
-- Name: processing_step processing_step_processing_job_id_fkey; Type: FK CONSTRAINT; Schema: rag_v2; Owner: -
--

ALTER TABLE ONLY rag_v2.processing_step
    ADD CONSTRAINT processing_step_processing_job_id_fkey FOREIGN KEY (processing_job_id) REFERENCES rag_v2.processing_job(id) ON DELETE RESTRICT;


--
-- Name: property_component_type property_component_type_component_type_id_fkey; Type: FK CONSTRAINT; Schema: rag_v2; Owner: -
--

ALTER TABLE ONLY rag_v2.property_component_type
    ADD CONSTRAINT property_component_type_component_type_id_fkey FOREIGN KEY (component_type_id) REFERENCES rag_v2.component_type(id) ON DELETE RESTRICT;


--
-- Name: property_component_type property_component_type_property_id_fkey; Type: FK CONSTRAINT; Schema: rag_v2; Owner: -
--

ALTER TABLE ONLY rag_v2.property_component_type
    ADD CONSTRAINT property_component_type_property_id_fkey FOREIGN KEY (property_id) REFERENCES rag_v2.property(id) ON DELETE RESTRICT;


--
-- Name: review_batch review_batch_document_version_id_fkey; Type: FK CONSTRAINT; Schema: rag_v2; Owner: -
--

ALTER TABLE ONLY rag_v2.review_batch
    ADD CONSTRAINT review_batch_document_version_id_fkey FOREIGN KEY (document_version_id) REFERENCES rag_v2.document_version(id) ON DELETE RESTRICT;


--
-- Name: review_decision review_decision_review_item_id_fkey; Type: FK CONSTRAINT; Schema: rag_v2; Owner: -
--

ALTER TABLE ONLY rag_v2.review_decision
    ADD CONSTRAINT review_decision_review_item_id_fkey FOREIGN KEY (review_item_id) REFERENCES rag_v2.review_item(id) ON DELETE RESTRICT;


--
-- Name: review_item review_item_review_batch_id_fkey; Type: FK CONSTRAINT; Schema: rag_v2; Owner: -
--

ALTER TABLE ONLY rag_v2.review_item
    ADD CONSTRAINT review_item_review_batch_id_fkey FOREIGN KEY (review_batch_id) REFERENCES rag_v2.review_batch(id) ON DELETE RESTRICT;


--
-- Name: storage_assignment storage_assignment_storage_location_id_fkey; Type: FK CONSTRAINT; Schema: rag_v2; Owner: -
--

ALTER TABLE ONLY rag_v2.storage_assignment
    ADD CONSTRAINT storage_assignment_storage_location_id_fkey FOREIGN KEY (storage_location_id) REFERENCES rag_v2.storage_location(id) ON DELETE RESTRICT;


--
-- Name: storage_assignment storage_assignment_unit_id_fkey; Type: FK CONSTRAINT; Schema: rag_v2; Owner: -
--

ALTER TABLE ONLY rag_v2.storage_assignment
    ADD CONSTRAINT storage_assignment_unit_id_fkey FOREIGN KEY (unit_id) REFERENCES rag_v2.unit(id) ON DELETE RESTRICT;


--
-- Name: storage_location storage_location_parent_id_fkey; Type: FK CONSTRAINT; Schema: rag_v2; Owner: -
--

ALTER TABLE ONLY rag_v2.storage_location
    ADD CONSTRAINT storage_location_parent_id_fkey FOREIGN KEY (parent_id) REFERENCES rag_v2.storage_location(id) ON DELETE RESTRICT;


--
-- Name: unit unit_article_id_fkey; Type: FK CONSTRAINT; Schema: rag_v2; Owner: -
--

ALTER TABLE ONLY rag_v2.unit
    ADD CONSTRAINT unit_article_id_fkey FOREIGN KEY (article_id) REFERENCES rag_v2.article(id) ON DELETE RESTRICT;


--
-- Name: unit unit_article_revision_id_article_id_fkey; Type: FK CONSTRAINT; Schema: rag_v2; Owner: -
--

ALTER TABLE ONLY rag_v2.unit
    ADD CONSTRAINT unit_article_revision_id_article_id_fkey FOREIGN KEY (article_revision_id, article_id) REFERENCES rag_v2.article_revision(id, article_id) ON DELETE RESTRICT;


--
-- Name: unit_condition_history unit_condition_history_unit_id_fkey; Type: FK CONSTRAINT; Schema: rag_v2; Owner: -
--

ALTER TABLE ONLY rag_v2.unit_condition_history
    ADD CONSTRAINT unit_condition_history_unit_id_fkey FOREIGN KEY (unit_id) REFERENCES rag_v2.unit(id) ON DELETE RESTRICT;


--
-- PostgreSQL database dump complete
--

\unrestrict pdVmmSQerRX1UeNtWahktfan5v9MU15zViJEPMG4pPZqe1dZmzA2MQ63DKL9xzN

