#!/usr/bin/env bash
# Exportiere ausschließlich das tatsächliche DDL der Retro-RAG-V2-Testdatenbank.
# Keine Daten, Credentials oder V1-Datenbanken werden exportiert.
set -Eeuo pipefail

cd "$(dirname "$0")/.."
container="codeanalyse-postgres"
database="retro_rag_v2_test"
target="db/schema/retro_rag_v2_test.sql"
mkdir -p db/schema

# DB- und Versionsprüfung im Container: Schutz vor versehentlichem V1-Export.
info="$(docker exec "$container" psql -X -A -t -v ON_ERROR_STOP=1 \
    -U codeanalyse -d "$database" -c \
    "SELECT current_database() || '|' || COALESCE((SELECT max(version)::text FROM rag_v2.schema_migration), 'missing')")"
if [[ "$info" != "retro_rag_v2_test|6" ]]; then
    echo "Abbruch: erwartet retro_rag_v2_test mit Migration 6, erhalten: $info" >&2
    exit 1
fi

gate="$(docker exec "$container" psql -XAt -v ON_ERROR_STOP=1 \
    -U codeanalyse -d "$database" -c \
    "SELECT writes_enabled FROM rag_v2.write_gate WHERE id=true")"
if [[ "$gate" != "f" ]]; then
    echo "Abbruch: V2-Write-Gate muss geschlossen sein, erhalten: $gate" >&2
    exit 1
fi

tmp="$(mktemp "$PWD/db/schema/.schema.XXXXXXXX.sql")"
trap 'rm -f "$tmp"' EXIT

# WICHTIG: -n rag_v2 exportiert NUR unser Anwendungsschema.
# --no-owner/--no-privileges vermeiden cluster- und umgebungsspezifische Grants.
docker exec "$container" pg_dump -U codeanalyse \
    -d "$database" --schema-only \
    --schema=rag_v2 \
    --no-owner --no-privileges --no-comments \
    --file=/dev/stdout > "$tmp"

if ! grep -q '^CREATE TABLE rag_v2\.schema_migration' "$tmp"; then
    echo "Abbruch: erwartete Schema-Migrations-Tabelle fehlt im Export" >&2
    exit 1
fi
if ! grep -q '^CREATE FUNCTION rag_v2.assert_import_write_gate()' "$tmp"; then
    echo "Abbruch: Gate-Funktion aus Migration 0004 fehlt im Schemaexport" >&2
    exit 1
fi
if ! grep -q '^CREATE UNIQUE INDEX document_source_identity_idx' "$tmp"; then
    echo "Abbruch: Identitätsindex aus Migration 0005 fehlt im Schemaexport" >&2
    exit 1
fi
if ! grep -q 'source_instance text' "$tmp"; then
    echo "Abbruch: source_instance aus Migration 0005 fehlt im Schemaexport" >&2
    exit 1
fi
if [[ "$(grep -c '^CREATE TABLE rag_v2\.' "$tmp")" -ne 43 ]]; then
    echo "Abbruch: erwartet genau 43 rag_v2-Tabellen" >&2
    exit 1
fi
# Gezielte 0006-Schutzpruefungen gegen den wirklich exportierten Datenbankstand.
for table in entity_type knowledge_topic knowledge_topic_assignment \
             entity_relation entity_relation_evidence knowledge_proposal; do
    if ! grep -Fq "CREATE TABLE rag_v2.$table (" "$tmp"; then
        echo "Abbruch: 0006-Tabelle $table fehlt im Schemaexport" >&2
        exit 1
    fi
done
# pg_dump schreibt View-Optionen (z.B. WITH (security_barrier='true'))
# zwischen den View-Namen und AS; diese Pruefung darf keinen exakten
# CREATE-VIEW-Einzeiler voraussetzen.
if ! grep -Eq '^CREATE VIEW rag_v2[.]accepted_entity_relation([[:space:]]|$)' "$tmp"; then
    echo "Abbruch: 0006-Sicherheits-View fehlt im Schemaexport" >&2
    exit 1
fi
# Die Sicherheitsoption wird unabhaengig vom pg_dump-Layout direkt
# aus PostgreSQL gelesen. Nur der erwartete boolesche Wert ist zulaessig.
barrier="$(docker exec "$container" psql -XAt -v ON_ERROR_STOP=1 \
    -U codeanalyse -d "$database" -c \
    "SELECT COALESCE((
      SELECT EXISTS(
        SELECT 1 FROM unnest(c.reloptions) AS opt
        WHERE opt IN ('security_barrier=true', 'security_barrier=on')
      )::text
      FROM pg_class c
      JOIN pg_namespace n ON n.oid=c.relnamespace
      WHERE n.nspname='rag_v2'
        AND c.relname='accepted_entity_relation'
        AND c.relkind='v'
    ), 'false')")"
if [[ "$barrier" != "true" ]]; then
    echo "Abbruch: accepted_entity_relation ohne security_barrier" >&2
    exit 1
fi
if ! grep -Fq 'CREATE FUNCTION rag_v2.guard_knowledge_proposal_import()' "$tmp"; then
    echo "Abbruch: 0006-Gate-Funktion fehlt im Schemaexport" >&2
    exit 1
fi

mv "$tmp" "$target"
trap - EXIT
echo "Schemaexport erzeugt: $target"
echo "Nur Struktur (DDL); kein Datenexport. Bitte vor Commit prüfen."
