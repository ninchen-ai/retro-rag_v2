"""Prüft Archivdateien gegen PostgreSQL. Keine Löschoperationen."""

import os
from pathlib import Path
from urllib.parse import unquote, urlsplit

import psycopg

from retro_rag.importer.archive_mount import (
    ARCHIVE_ROOT,
    verify_archive_mount,
)
from retro_rag.importer.staging import digest


def main():
    verify_archive_mount(ARCHIVE_ROOT)

    dsn = os.environ["RETRO_V2_DATABASE_DSN"]

    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT current_database()")
            if cur.fetchone()[0] != "retro_rag_v2_test":
                raise RuntimeError("Nur V2-Testdatenbank zulässig")

            cur.execute(
                "SELECT archive_uri, content_hash "
                "FROM rag_v2.document_version"
            )
            records = cur.fetchall()

    referenced = {}
    problems = []

    for uri, expected_hash in records:
        parsed = urlsplit(uri)

        if parsed.scheme != "file" or parsed.netloc:
            problems.append(f"Ungültige Archiv-URI: {uri}")
            continue

        path = Path(unquote(parsed.path))

        if not path.is_relative_to(ARCHIVE_ROOT):
            problems.append(f"Archivpfad außerhalb des Archivs: {path}")
            continue

        referenced[path] = expected_hash

    for path, expected_hash in referenced.items():
        if not path.is_file() or path.is_symlink():
            problems.append(f"FEHLEND oder ungültig: {path}")
        elif digest(path.read_bytes()) != expected_hash:
            problems.append(f"HASH-FEHLER: {path}")

    orphaned = []

    for path in ARCHIVE_ROOT.rglob("*"):
        if not path.is_file():
            continue

        if path.is_symlink():
            problems.append(f"Symlink im Archiv: {path}")
        elif path.name.startswith(".archive-"):
            problems.append(f"TEMPORÄRE DATEI: {path}")
        elif path not in referenced:
            orphaned.append(path)

    print(f"Registrierte Archivdateien: {len(referenced)}")
    print(f"Verwaiste Dateien: {len(orphaned)}")
    print(f"Integritätsprobleme: {len(problems)}")

    for path in orphaned:
        print(f"VERWAIST: {path}")

    for problem in problems:
        print(problem)

    if orphaned or problems:
        raise SystemExit(1)

    print("PASS: Archiv und Datenbank konsistent")


if __name__ == "__main__":
    main()
