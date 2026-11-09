"""Prüft das festgelegte Originalarchiv vor Schreibzugriffen."""

import os
import stat
from pathlib import Path

ARCHIVE_ROOT = Path("/data/retro-rag/v2/originals")
MOUNTPOINT = Path("/data")
EXPECTED_UUID = "0ad31014-cd69-4b01-b177-b30bfd832481"


def verify_archive_mount(archive_root: Path) -> None:
    """Verweigert den Import bei falschem oder fehlendem Datenträger."""
    if archive_root != ARCHIVE_ROOT:
        raise RuntimeError(
            f"Nicht freigegebener Archivpfad: {archive_root}"
        )

    device = Path("/dev/disk/by-uuid") / EXPECTED_UUID

    if not MOUNTPOINT.is_mount():
        raise RuntimeError("/data ist kein aktiver Mountpoint")

    if not device.exists():
        raise RuntimeError("Erwartete Archiv-HDD nicht gefunden")

    if not stat.S_ISBLK(device.stat().st_mode):
        raise RuntimeError("Archivgerät ist kein Blockgerät")

    if MOUNTPOINT.stat().st_dev != device.stat().st_rdev:
        raise RuntimeError("Falscher Datenträger unter /data")

    if not archive_root.is_dir():
        raise RuntimeError("Archivverzeichnis fehlt")

    if archive_root.resolve() != ARCHIVE_ROOT:
        raise RuntimeError("Archivpfad enthält eine Umleitung")

    if archive_root.stat().st_dev != MOUNTPOINT.stat().st_dev:
        raise RuntimeError("Archiv liegt auf anderem Dateisystem")
