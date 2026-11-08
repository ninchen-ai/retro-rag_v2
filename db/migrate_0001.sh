#!/usr/bin/env bash
# Phase 0: expliziter, gegen V1 gesicherter Start von 0001.
set -euo pipefail

usage() {
    printf 'Verwendung: %s --database retro_rag_v2[_test] [--apply]\n' "$0" >&2
    exit 2
}

database=''
apply=false
while (($#)); do
    case "$1" in
        --database)
            (($# >= 2)) || usage
            database="$2"
            shift 2
            ;;
        --apply)
            apply=true
            shift
            ;;
        *) usage ;;
    esac
done

case "$database" in
    retro_rag_v2|retro_rag_v2_test) ;;
    *) printf 'Schutzabbruch: Datenbank %q ist nicht erlaubt.\n' "$database" >&2; exit 2 ;;
esac

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
file="$script_dir/migrations/0001_init.sql"
connected="$(psql -X -A -t -v ON_ERROR_STOP=1 -d "$database" \
    -c 'SELECT current_database()')"
if [[ "$connected" != "$database" ]]; then
    printf 'Schutzabbruch: verbunden mit %q statt %q.\n' "$connected" "$database" >&2
    exit 2
fi

if [[ "$apply" != true ]]; then
    printf 'DRY-RUN: Keine Änderung. Ziel: %s\nSQL-Datei: %s\n' "$database" "$file"
    printf 'Für die Ausführung --apply ergänzen (nach Backup und Test).\n'
    exit 0
fi

printf 'Führe Migration 0001 in %s aus.\n' "$database"
psql -X -v ON_ERROR_STOP=1 -d "$database" -f "$file"