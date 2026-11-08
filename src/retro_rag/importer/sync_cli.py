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
    dsn = os.environ.get("RETRO_V2_DATABASE_DSN")
    if not all((endpoint, user, password, dsn)):
        parser.error("RETRO_V2_WEBDAV_URL/USER/APP_PASSWORD und DATABASE_DSN fehlen")
    if args.apply and args.archive_root is None:
        parser.error("--apply erfordert --archive-root")
    if args.apply and "retro_rag_v2_test" not in dsn:
        parser.error("Vorerst nur retro_rag_v2_test für --apply freigegeben")

    client = WebDAV(endpoint, user, password)
    files = client.list_files()
    if not files:
        raise RuntimeError("Leere WebDAV-Dateiliste: keine Verarbeitung")
    print(f"Gefundene Dateien: {len(files)}")
    with psycopg.connect(dsn, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT current_database(), to_regclass('rag_v2.write_gate')")
            dbname, gate_table = cur.fetchone()
        if dbname != "retro_rag_v2_test" or gate_table is None:
            raise RuntimeError("Es wird ausschließlich das vorhandene V2-Testschema verwendet")
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
