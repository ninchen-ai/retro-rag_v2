"""Nextcloud-Erkennung und explizit bestätigtes Einzeldatei-Staging."""

import argparse
import os
import re
from pathlib import Path

import psycopg

from retro_rag.importer.staging import plan_file, stage_file, digest
from retro_rag.importer.webdav import WebDAV


def main() -> None:
    parser = argparse.ArgumentParser(description="Retro-RAG-V2 WebDAV-Importstaging")
    parser.add_argument("--apply", action="store_true", help="Genau eine bestätigte Datei stagen")
    parser.add_argument("--source-key", help="Nextcloud-fileid der ausgewählten Datei")
    parser.add_argument(
        "--expected-sha256",
        help="SHA-256 aus einer zuvor geprüften Vorschau; für --apply verpflichtend",
    )
    parser.add_argument("--archive-root", type=Path, help="Archivverzeichnis für Rohdaten")
    parser.add_argument("--max-bytes", type=int, default=100_000_000)
    args = parser.parse_args()

    if args.max_bytes < 1:
        parser.error("--max-bytes muss positiv sein")
    if args.apply and (not args.source_key or not args.expected_sha256):
        parser.error("--apply erfordert --source-key und --expected-sha256")
    if args.apply and args.archive_root is None:
        parser.error("--apply erfordert --archive-root")
    if args.expected_sha256 and not re.fullmatch(r"[0-9a-fA-F]{64}", args.expected_sha256):
        parser.error("--expected-sha256 muss ein SHA-256-Hexwert sein")

    endpoint = os.environ.get("RETRO_V2_WEBDAV_URL")
    user = os.environ.get("RETRO_V2_WEBDAV_USER")
    password = os.environ.get("RETRO_V2_WEBDAV_APP_PASSWORD")
    instance_id = os.environ.get("RETRO_V2_NEXTCLOUD_INSTANCE_ID")
    dsn = os.environ.get("RETRO_V2_DATABASE_DSN")
    if not all((endpoint, user, password, dsn, instance_id)):
        parser.error("RETRO_V2_WEBDAV_URL/USER/APP_PASSWORD, NEXTCLOUD_INSTANCE_ID und DATABASE_DSN fehlen")

    client = WebDAV(endpoint, user, password, instance_id=instance_id)
    files = client.list_files()
    if not files:
        raise RuntimeError("Leere WebDAV-Dateiliste: keine Verarbeitung")
    if args.source_key:
        files = [file for file in files if file.source_key == args.source_key]
        if len(files) != 1:
            raise RuntimeError("Ausgewählte Nextcloud-fileid nicht eindeutig gefunden")
    elif args.apply:
        # Sicherheitsnetz gegen spätere CLI-Änderungen.
        raise RuntimeError("Apply ohne Datei-Auswahl verboten")

    print(f"Ausgewählte Dateien: {len(files)}")
    with psycopg.connect(dsn, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT current_database(), to_regclass('rag_v2.document_source')")
            dbname, source_table = cur.fetchone()
        if dbname != "retro_rag_v2_test" or source_table is None:
            raise RuntimeError("Es wird ausschließlich das vorhandene V2-Testschema verwendet")
        with conn.cursor() as cur:
            cur.execute("SELECT EXISTS (SELECT 1 FROM rag_v2.schema_migration WHERE version=5)")
            if not cur.fetchone()[0]:
                raise RuntimeError("Migration 0005 für Dokumentidentität fehlt")
        conn.rollback()

        for file in files:
            # Netzwerkfehler, ETag-Wechsel und verkürzte Antworten werden
            # vor dem ersten möglichen Datenbank-/Archivschreibzugriff erkannt.
            data = client.download(file, max_bytes=args.max_bytes)
            actual_hash = digest(data)
            if args.expected_sha256 and actual_hash != args.expected_sha256.lower():
                raise RuntimeError(
                    "SHA-256 weicht von der bestätigten Vorschau ab: kein Apply"
                )
            if args.apply:
                change = stage_file(conn, file, data, args.archive_root)
            else:
                change = plan_file(conn, file, data)
                conn.rollback()
            print(
                f"{change.action}: {file.name} [{file.source_key}] "
                f"sha256={change.content_hash}"
            )
    print("Keine Dokumentlöschungen, Versionenaktivierungen oder Freigaben durchgeführt.")


if __name__ == "__main__":
    main()
