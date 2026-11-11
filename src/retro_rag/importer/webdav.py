"""Read-only WebDAV discovery with explicit identity and safe URL handling."""

import base64
from dataclasses import dataclass
from urllib.error import HTTPError
from urllib.parse import unquote, urljoin, urlsplit
from urllib.request import Request
from xml.etree import ElementTree as ET


DAV = "{DAV:}"

# Verzeichnisse mit Eingangsdateien, Vorlagen oder automatischen Uploads.
EXCLUDED_DIRECTORIES = frozenset({"import", "retro-rag-hardware-vorlagen-v1", "sofortupload"})


def is_excluded_directory(uri: str, root_uri: str) -> bool:
    """Prüft ganze Pfadsegmente unterhalb der WebDAV-Wurzel, ohne Präfixverwechslungen."""
    path = unquote(urlsplit(uri).path)
    root_path = unquote(urlsplit(root_uri).path).rstrip("/") + "/"
    if not path.startswith(root_path):
        raise ValueError("WebDAV-Pfad liegt außerhalb des Startverzeichnisses")
    relative = path[len(root_path):]
    # Dateien werden nicht anhand des Dateinamens ausgefiltert.
    segments = relative.strip("/").split("/") if relative.strip("/") else []
    directories = segments if path.endswith("/") else segments[:-1]
    return any(segment.casefold() in EXCLUDED_DIRECTORIES for segment in directories)



@dataclass(frozen=True)
class RemoteFile:
    source_key: str
    uri: str
    name: str
    etag: str | None
    byte_size: int | None
    content_type: str | None
    instance_id: str = ""


class WebDAV:
    """Kein Schreibzugriff auf die Nextcloud; Basic Auth nur über HTTPS oder Loopback."""

    def __init__(self, url: str, username: str, app_password: str, timeout: int = 30, *, instance_id: str = ""):
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https") or not parts.netloc:
            raise ValueError("Ungültige WebDAV-URL")
        if parts.scheme == "http" and parts.hostname not in ("localhost", "127.0.0.1", "::1"):
            raise ValueError("WebDAV über HTTP ist nur auf Loopback erlaubt")
        if parts.username or parts.password or parts.query or parts.fragment:
            raise ValueError("Keine Zugangsdaten, Query oder Fragmente in der URL verwenden")
        if not instance_id or not instance_id.strip() or any(c.isspace() for c in instance_id):
            raise ValueError("Stabile Nextcloud-Instanzkennung (--instance-id / RETRO_V2_NEXTCLOUD_INSTANCE_ID) erforderlich")
        self.instance_id = instance_id
        self.root = url.rstrip("/") + "/"
        self.timeout = timeout
        token = base64.b64encode(f"{username}:{app_password}".encode()).decode()
        self.auth = "Basic " + token
        self.origin = (parts.scheme, parts.netloc)

    def _request(self, url: str, method: str, data: bytes | None = None) -> bytes:
        parts = urlsplit(url)
        if (parts.scheme, parts.netloc) != self.origin:
            raise ValueError("WebDAV-URL außerhalb der konfigurierten Origin")
        req = Request(url, data=data, method=method, headers={"Authorization": self.auth})
        if method == "PROPFIND":
            req.add_header("Depth", "1")
            req.add_header("Content-Type", "application/xml; charset=utf-8")
        # urllib folgt Weiterleitungen auch beim GET. Redirects werden bewusst untersagt.
        opener = _no_redirect_opener()
        with opener.open(req, timeout=self.timeout) as response:
            return response.read()

    def list_files(self, max_directories: int = 1000) -> list[RemoteFile]:
        """Depth-1 rekursiv; feste Obergrenze gegen unkontrollierte Traversierung."""
        pending = [self.root]
        seen = set()
        results: list[RemoteFile] = []
        while pending:
            current = pending.pop()
            if current in seen or is_excluded_directory(current, self.root):
                continue
            seen.add(current)
            if len(seen) > max_directories:
                raise RuntimeError("WebDAV-Verzeichnislimit überschritten")
            xml = self._request(current, "PROPFIND",
                                (
                                    b'<?xml version="1.0" encoding="utf-8"?>'
                                    b'<d:propfind xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns">'
                                    b'<d:prop><d:resourcetype/><d:displayname/>'
                                    b'<d:getetag/><d:getcontentlength/><d:getcontenttype/>'
                                    b'<oc:fileid/></d:prop></d:propfind>'
                                ))
            root = ET.fromstring(xml)
            if root.tag != DAV + "multistatus":
                raise RuntimeError("Ungültige WebDAV-Multistatus-Antwort")
            for response in root.findall(DAV + "response"):
                href = response.findtext(DAV + "href")
                if not href:
                    continue
                uri = urljoin(current, href)
                parts = urlsplit(uri)
                if (parts.scheme, parts.netloc) != self.origin:
                    raise ValueError("WebDAV-Quellpfad wechselt Origin")
                if not unquote(parts.path).startswith(unquote(urlsplit(self.root).path)):
                    raise ValueError("WebDAV-Quellpfad außerhalb des Startverzeichnisses")
                if uri.rstrip("/") == current.rstrip("/"):
                    continue
                if is_excluded_directory(uri, self.root):
                    continue
                prop = None
                for status in response.findall(DAV + "propstat"):
                    if (status.findtext(DAV + "status") or "").split(" ")[1:2] == ["200"]:
                        prop = status.find(DAV + "prop")
                        break
                if prop is None:
                    raise RuntimeError("WebDAV-Eigenschaften fehlen oder sind nicht lesbar")
                rtype = prop.find(DAV + "resourcetype")
                if rtype is not None and rtype.find(DAV + "collection") is not None:
                    if is_excluded_directory(uri.rstrip("/") + "/", self.root):
                        continue
                    pending.append(uri.rstrip("/") + "/")
                    continue
                name = unquote(parts.path.rstrip("/").split("/")[-1])
                if not name.lower().endswith((".md", ".pdf")):
                    continue
                key = prop.findtext("{http://owncloud.org/ns}fileid")
                # Ohne stabile Nextcloud-fileid ist Rename/Move nicht eindeutig erkennbar.
                if not key:
                    raise RuntimeError(f"Nextcloud-fileid fehlt für {uri}")
                raw_size = prop.findtext(DAV + "getcontentlength")
                results.append(RemoteFile(
                    source_key=str(key), uri=uri, name=name, instance_id=self.instance_id,
                    etag=prop.findtext(DAV + "getetag"),
                    byte_size=int(raw_size) if raw_size else None,
                    content_type=prop.findtext(DAV + "getcontenttype"),
                ))
        keys = [f.source_key for f in results]
        if len(keys) != len(set(keys)):
            raise RuntimeError("Doppelte Nextcloud-fileid in Dateiliste")
        return sorted(results, key=lambda f: f.source_key)

    def download(self, file: RemoteFile, max_bytes: int = 100_000_000) -> bytes:
        """Begrenzter, konditionaler GET; bei Netz-/ETag-Fehlern kein Ergebnis."""
        if max_bytes < 1:
            raise ValueError("max_bytes muss positiv sein")
        if file.instance_id != self.instance_id:
            raise ValueError("Nextcloud-Instanzkennung stimmt nicht überein")
        if is_excluded_directory(file.uri, self.root):
            raise ValueError("Ausgeschlossene WebDAV-Quelle")
        parts = urlsplit(file.uri)
        if (parts.scheme, parts.netloc) != self.origin:
            raise ValueError("WebDAV-URL außerhalb der konfigurierten Origin")
        if not unquote(parts.path).startswith(unquote(urlsplit(self.root).path)):
            raise ValueError("WebDAV-URL außerhalb des Startverzeichnisses")
        if file.byte_size is not None and file.byte_size > max_bytes:
            raise ValueError(f"Datei überschreitet Größenlimit: {file.name}")

        headers = {"Authorization": self.auth}
        if file.etag:
            headers["If-Match"] = file.etag
        request = Request(file.uri, method="GET", headers=headers)
        with _no_redirect_opener().open(request, timeout=self.timeout) as response:
            response_etag = response.headers.get("ETag")
            if file.etag and response_etag and response_etag != file.etag:
                raise RuntimeError("WebDAV-ETag hat sich während des Abrufs geändert")
            reported = response.headers.get("Content-Length")
            if reported is not None and int(reported) > max_bytes:
                raise ValueError(f"Datei überschreitet Größenlimit: {file.name}")
            chunks = []
            total = 0
            while True:
                block = response.read(min(64 * 1024, max_bytes - total + 1))
                if not block:
                    break
                total += len(block)
                if total > max_bytes:
                    raise ValueError(f"Datei überschreitet Größenlimit: {file.name}")
                chunks.append(block)
            if reported is not None and total != int(reported):
                raise RuntimeError("Unvollständiger WebDAV-Download")
            if file.byte_size is not None and total != file.byte_size:
                raise RuntimeError("WebDAV-Dateigröße hat sich seit der Liste geändert")
            return b"".join(chunks)


def _no_redirect_opener():
    from urllib.request import HTTPRedirectHandler, build_opener

    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            raise HTTPError(req.full_url, code, "WebDAV-Redirect verboten", headers, fp)
    return build_opener(NoRedirect())
