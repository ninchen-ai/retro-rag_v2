"""Nextcloud-Erkennung und geschütztes V2-Staging."""

import argparse
import os
from pathlib import Path

import psycopg

from retro_rag.importer.staging import plan_file, stage_file
from retro_rag.importer.webdav import WebDAV


def main() -> None:
    parser = argparse.ArgumentParser(description="Retro-RAG-V2 WebDAV-Importstaging")
    parser.add_argument("--apply", action="store_true", help="V2-Jobstaging schreiben")
    parser.add_argument("--archive-root", type=Path, help="Archivverzeichnis für Rohdaten")
    parser.add_argument("--max-bytes", type=int, default=100_000_000)
    args = parser.parse_args()
    if args.max_bytes < 1:
        parser.error("--max-bytes muss positiv sein")
    endpoint = os.environ.get("RETRO_V2_WEBDAV_URL")
    user = os.environ.get("RETRO_V2_WEBDAV_USER")
    password = os.environ.get("RETRO_V2_WEBDAV_APP_PASSWORD")
    instance_id = os.environ.get("RETRO_V2_NEXTCLOUD_INSTANCE_ID")
    dsn = os.environ.get("RETRO_V2_DATABASE_DSN")
    if not all((endpoint, user, password, dsn, instance_id)):
        parser.error("RETRO_V2_WEBDAV_URL/USER/APP_PASSWORD, NEXTCLOUD_INSTANCE_ID und DATABASE_DSN fehlen")
    if args.apply:
        from retro_rag.importer.archive_mount import (
            ARCHIVE_ROOT,
            verify_archive_mount,
        )
        if args.archive_root != ARCHIVE_ROOT:
            parser.error(
                f"--apply erfordert --archive-root {ARCHIVE_ROOT}"
            )
        verify_archive_mount(args.archive_root)
    if args.apply and "retro_rag_v2_test" not in dsn:
        parser.error("Vorerst nur retro_rag_v2_test für --apply freigegeben")

    client = WebDAV(endpoint, user, password, instance_id=instance_id)
    files = client.list_files()
    if not files:
        raise RuntimeError("Leere WebDAV-Dateiliste: keine Verarbeitung")
    print(f"Gefundene Dateien: {len(files)}")
    with psycopg.connect(dsn, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT current_database(), to_regclass('rag_v2.document_source')")
            dbname, gate_table = cur.fetchone()
        if dbname != "retro_rag_v2_test" or gate_table is None:
            raise RuntimeError("Es wird ausschließlich das vorhandene V2-Testschema verwendet")
        with conn.cursor() as cur:
            cur.execute("SELECT EXISTS (SELECT 1 FROM rag_v2.schema_migration WHERE version=5)")
            if not cur.fetchone()[0]:
                raise RuntimeError("Migration 0005 für Dokumentidentität fehlt")
        # Ein ROLLBACK beendet die lesende Planungstransaktion.
        conn.rollback()
        for file in files:
            data = client.download(file, max_bytes=args.max_bytes)
            if args.apply:
                change = stage_file(conn, file, data, args.archive_root)
            else:
                change = plan_file(conn, file, data)
                conn.rollback()
            print(f"{change.action}: {file.name} [{file.source_key}] {change.content_hash[:12]}")
    print("Keine Dokumentlöschungen oder Freigaben durchgeführt.")


if __name__ == "__main__":
    main()
