"""Read-only WebDAV discovery with explicit identity and safe URL handling."""

from dataclasses import dataclass
from urllib.parse import quote, unquote, urljoin, urlsplit
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from xml.etree import ElementTree as ET
import base64


DAV = "{DAV:}"


@dataclass(frozen=True)
class RemoteFile:
    source_key: str
    uri: str
    name: str
    etag: str | None
    byte_size: int | None
    content_type: str | None


class WebDAV:
    """Kein Schreibzugriff auf die Nextcloud; Basic Auth nur über HTTPS oder Loopback."""

    def __init__(self, url: str, username: str, app_password: str, timeout: int = 30):
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https") or not parts.netloc:
            raise ValueError("Ungültige WebDAV-URL")
        if parts.scheme == "http" and parts.hostname not in ("localhost", "127.0.0.1", "::1"):
            raise ValueError("WebDAV über HTTP ist nur auf Loopback erlaubt")
        if parts.username or parts.password or parts.query or parts.fragment:
            raise ValueError("Keine Zugangsdaten, Query oder Fragmente in der URL verwenden")
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
            if current in seen:
                continue
            seen.add(current)
            if len(seen) > max_directories:
                raise RuntimeError("WebDAV-Verzeichnislimit überschritten")
            xml = self._request(current, "PROPFIND",
                                b'<?xml version="1.0"?><d:propfind xmlns:d="DAV:"><d:allprop/></d:propfind>')
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
                prop = None
                for status in response.findall(DAV + "propstat"):
                    if (status.findtext(DAV + "status") or "").split(" ")[1:2] == ["200"]:
                        prop = status.find(DAV + "prop")
                        break
                if prop is None:
                    raise RuntimeError("WebDAV-Eigenschaften fehlen oder sind nicht lesbar")
                rtype = prop.find(DAV + "resourcetype")
                if rtype is not None and rtype.find(DAV + "collection") is not None:
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
                    source_key=str(key), uri=uri, name=name,
                    etag=prop.findtext(DAV + "getetag"),
                    byte_size=int(raw_size) if raw_size else None,
                    content_type=prop.findtext(DAV + "getcontenttype"),
                ))
        keys = [f.source_key for f in results]
        if len(keys) != len(set(keys)):
            raise RuntimeError("Doppelte Nextcloud-fileid in Dateiliste")
        return sorted(results, key=lambda f: f.source_key)

    def download(self, file: RemoteFile, max_bytes: int = 100_000_000) -> bytes:
        if file.byte_size is not None and file.byte_size > max_bytes:
            raise ValueError(f"Datei überschreitet Größenlimit: {file.name}")
        data = self._request(file.uri, "GET")
        if len(data) > max_bytes:
            raise ValueError(f"Datei überschreitet Größenlimit: {file.name}")
        return data


def _no_redirect_opener():
    from urllib.request import build_opener, HTTPRedirectHandler

    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            raise HTTPError(req.full_url, code, "WebDAV-Redirect verboten", headers, fp)
    return build_opener(NoRedirect())
