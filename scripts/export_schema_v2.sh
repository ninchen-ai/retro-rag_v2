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
if [[ "$info" != "retro_rag_v2_test|5" ]]; then
    echo "Abbruch: erwartet retro_rag_v2_test mit Migration 5, erhalten: $info" >&2
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
if [[ "$(grep -c '^CREATE TABLE rag_v2\.' "$tmp")" -ne 37 ]]; then
    echo "Abbruch: erwartet genau 37 rag_v2-Tabellen" >&2
    exit 1
fi

mv "$tmp" "$target"
trap - EXIT
echo "Schemaexport erzeugt: $target"
echo "Nur Struktur (DDL); kein Datenexport. Bitte vor Commit prüfen."
