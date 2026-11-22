"""Schreibfreie WebDAV/DB-Planung über eine begrenzte Binär-Pipe.

Host: fetch (nur WebDAV über Host-Loopback, Ausgabe an stdout).
PostgreSQL-Netz-Namespace: plan (nur DB-SELECTs, Eingabe von stdin).
Keine Archivdatei, kein Apply, keine Gate-Änderung.
"""

import argparse
import hashlib
import json
import os
import struct
import sys
from urllib.parse import urlsplit

import psycopg

from retro_rag.importer.staging import plan_file
from retro_rag.importer.webdav import RemoteFile, WebDAV

MAX_BYTES = 1_000_000
MAX_HEADER = 16_384


def fetch_to_pipe(client: WebDAV, source_key: str, expected_sha256: str) -> None:
    """Übergibt genau ein SHA-geprüftes WebDAV-Original an den nächsten Prozess."""
    selected = [item for item in client.list_files() if item.source_key == source_key]
    if len(selected) != 1:
        raise ValueError("Nextcloud-fileid nicht eindeutig vorhanden")
    remote = selected[0]
    data = client.download(remote, max_bytes=MAX_BYTES)
    digest = hashlib.sha256(data).hexdigest()
    if digest != expected_sha256.lower():
        raise ValueError("SHA-256 weicht vom bestätigten Einzelabruf ab")
    metadata = {
        "source_key": remote.source_key,
        "instance_id": remote.instance_id,
        "uri": remote.uri,
        "name": remote.name,
        "etag": remote.etag,
        "byte_size": len(data),
        "content_type": remote.content_type,
        "sha256": digest,
    }
    header = json.dumps(metadata, ensure_ascii=False).encode("utf-8")
    if len(header) > MAX_HEADER:
        raise ValueError("Metadaten zu groß")
    output = sys.stdout.buffer
    output.write(struct.pack("!I", len(header)))
    output.write(header)
    output.write(data)
    output.flush()


def read_pipe(stream, expected_sha256: str) -> tuple[RemoteFile, bytes]:
    """Strikte Größen-, Hash- und Metadatenprüfung ohne Dateiablage."""
    prefix = stream.read(4)
    if len(prefix) != 4:
        raise ValueError("Fehlender Pipe-Header")
    header_size = struct.unpack("!I", prefix)[0]
    if not 1 <= header_size <= MAX_HEADER:
        raise ValueError("Ungültige Metadatenlänge")
    header = stream.read(header_size)
    if len(header) != header_size:
        raise ValueError("Unvollständige Metadaten")
    meta = json.loads(header)
    if not isinstance(meta, dict):
        raise TypeError("Metadaten müssen ein Objekt sein")
    required = ("source_key", "instance_id", "uri", "name", "byte_size", "sha256")
    if any(field not in meta for field in required):
        raise ValueError("Unvollständige WebDAV-Metadaten")
    size = meta["byte_size"]
    if type(size) is not int or not 1 <= size <= MAX_BYTES:
        raise ValueError("Ungültige Dateigröße")
    data = stream.read(size)
    if len(data) != size or stream.read(1):
        raise ValueError("Unvollständige oder überlange Pipe-Daten")
    digest = hashlib.sha256(data).hexdigest()
    if digest != expected_sha256.lower() or digest != meta["sha256"]:
        raise ValueError("SHA-256 der Pipe-Daten stimmt nicht überein")
    if (
        not isinstance(meta["source_key"], str)
        or not meta["source_key"].isdigit()
        or not isinstance(meta["instance_id"], str)
        or not meta["instance_id"].strip()
        or not isinstance(meta["name"], str)
        or not meta["name"].lower().endswith((".md", ".pdf"))
        or not isinstance(meta["uri"], str)
        or urlsplit(meta["uri"]).scheme not in ("http", "https")
    ):
        raise ValueError("Ungültige Quellidentität")
    remote = RemoteFile(
        source_key=meta["source_key"], instance_id=meta["instance_id"],
        uri=meta["uri"], name=meta["name"], etag=meta.get("etag"),
        byte_size=size, content_type=meta.get("content_type"),
    )
    return remote, data


def plan_from_pipe(conn: psycopg.Connection, stream, expected_sha256: str):
    """Öffnet ausschließlich eine read-only-Transaktion und plant eine Quelle."""
    remote, data = read_pipe(stream, expected_sha256)
    with conn.cursor() as cur:
        cur.execute("BEGIN READ ONLY")
        cur.execute("SELECT current_database(), session_user")
        if cur.fetchone() != ("retro_rag_v2_test", "rag_v2_importer_login"):
            raise RuntimeError("Nur dedizierter V2-Test-Importer erlaubt")
        cur.execute("SELECT writes_enabled FROM rag_v2.write_gate WHERE id=true")
        if cur.fetchone() != (False,):
            raise RuntimeError("Write-Gate nicht geschlossen: Vorschau abgebrochen")
        change = plan_file(conn, remote, data)
    conn.rollback()
    return change


def main() -> None:
    parser = argparse.ArgumentParser(description="Schreibfreie WebDAV-DB-Einzeldateiplanung")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("fetch", "plan"):
        command = sub.add_parser(name)
        command.add_argument("--expected-sha256", required=True)
        if name == "fetch":
            command.add_argument("--source-key", required=True)
    args = parser.parse_args()
    import re

    if not re.fullmatch(r"[0-9a-fA-F]{64}", args.expected_sha256):
        parser.error("SHA-256 muss 64 Hex-Zeichen enthalten")

    if args.command == "fetch":
        required = (
            "RETRO_V2_WEBDAV_URL", "RETRO_V2_WEBDAV_USER",
            "RETRO_V2_WEBDAV_APP_PASSWORD", "RETRO_V2_NEXTCLOUD_INSTANCE_ID",
        )
        if any(not os.getenv(name) for name in required):
            parser.error("WebDAV-Konfiguration fehlt")
        url = os.environ["RETRO_V2_WEBDAV_URL"]
        # Niemals Zugangsdaten über die Bridge transferieren.
        if urlsplit(url).scheme != "http" or urlsplit(url).hostname not in (
            "127.0.0.1", "localhost", "::1",
        ):
            parser.error("Bridge benötigt die geprüfte Host-Loopback-WebDAV-URL")
        client = WebDAV(
            url, os.environ["RETRO_V2_WEBDAV_USER"],
            os.environ["RETRO_V2_WEBDAV_APP_PASSWORD"],
            instance_id=os.environ["RETRO_V2_NEXTCLOUD_INSTANCE_ID"],
        )
        fetch_to_pipe(client, args.source_key, args.expected_sha256)
    else:
        dsn = os.environ.get("RETRO_V2_JOB_TEST_DSN")
        if not dsn:
            parser.error("RETRO_V2_JOB_TEST_DSN nicht gesetzt")
        with psycopg.connect(dsn, autocommit=True) as conn:
            change = plan_from_pipe(conn, sys.stdin.buffer, args.expected_sha256)
        print(
            f"READ ONLY planned_action={change.action} source_key={change.source_key} "
            f"sha256={change.content_hash}"
        )


if __name__ == "__main__":
    main()
