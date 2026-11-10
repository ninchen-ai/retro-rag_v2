# PDF-Testkorpus aus Nextcloud (Stufe 3)

## Ziel

Nicht nur bekannte Manuals, sondern **alle im konfigurierten Nextcloud-WebDAV-Baum sichtbaren PDFs** katalogisieren. Auswahl einer heterogenen Prüfmenge für Text-/Outline-Extraktion, spätere OCR- und Layouttests.

## Datenschutz und Sicherheit

- Kein DB-Zugriff, keine PDF-/Nextcloud-Änderung und keine Embeddings.
- Bestehende WebDAV-Ausschlüsse (z. B. Import, Vorlagen, Sofortupload) gelten weiter.
- WebDAV-Client erzwingt HTTPS bzw. HTTP nur auf Loopback und untersagt Redirects.
- Katalog wird nur **lokal** unter /tmp geschrieben und enthält interne Nextcloud-Pfade und IDs: **nicht committen**.
- Automatische Downloads erfordern bekannte Dateigröße und maximal 50 MiB.
- Bei Downloadfehlern wird pro Datei ein Fehler im Bericht protokolliert.
- Die PDF-Stichprobe untersucht maximal zwölf gleichmäßig verteilte Seiten je Dokument.
- Keine komplette OCR-/Tabellenanalyse; insbesondere Bildzählungen und Schriftgrößen sind nur Indikatoren.

## Start auf Poseidon

Im bestehenden V2-Checkout mit aktiviertem venv:

```bash
git fetch origin
git switch feat/pdf-extraction-stage3
git pull --ff-only
python -m pip install -e '.[dev,pdf]'

# Entsprechend der bereits verwendeten V2-WebDAV-Wurzel befüllen.
export RETRO_V2_NEXTCLOUD_URL='http://127.0.0.1:8080/remote.php/dav/files/nina/Retro-Computing/'
export RETRO_V2_NEXTCLOUD_USER='nina'
export RETRO_V2_NEXTCLOUD_INSTANCE_ID='<bereits-konfigurierte-stabile-instanzkennung>'

# Passwort wird sicher interaktiv abgefragt, falls nicht in
# RETRO_V2_NEXTCLOUD_APP_PASSWORD vorhanden.
python -m retro_rag.importer.pdf_survey --sample 30

# Gesamten geeigneten Bestand analysieren (kann lange dauern):
# python -m retro_rag.importer.pdf_survey --analyze-all

python -m pytest -q tests/test_pdf_extraction.py tests/test_pdf_survey.py
python -m ruff check src/retro_rag/importer/pdf_survey.py tests/test_pdf_survey.py
```

**Hinweis:** Die URL ist ein Beispiel für Poseidons Loopback-WebDAV. Benutzer, URL und stabile Instanzkennung an die tatsächlich konfigurierte Umgebung anpassen.

## Bericht

Standard: `/tmp/retro-v2-pdf-survey.json`. Enthält vollständiges PDF-Inventar (Pfad, Dateigröße, etag, Quelle, heuristische Kategorie), ausgewählte Kandidaten und für tatsächlich heruntergeladene PDFs: Seitenzahl, Bookmark-Anzahl, gleichmäßig verteilte Seitenstichprobe, Zeichenzahlen, Bildzahlen, mögliche größere Schriftspannen und Fehler.

Die Kategorien `standards`, `datasheets`, `manuals`, `other` werden **nur anhand von Pfadnamen** geschätzt. Die Auswahl mischt diese Kategorien und Größenklassen. Relevante Problemfälle (Scans, lange Dokumente, Tabellen, zweispaltiges Layout, nicht lesbare Dateien) nach Sichtung der Qualitätswerte gezielt ergänzen.

## Offene Weiterentwicklung

1. Echten PDF-Bestand katalogisieren und aggregierte Ergebnisse vergleichen.
2. Qualitätsstufen und Prioritäten aus realen Dokumenten ableiten.
3. Automatisierte OCR-/Layout-Testfälle mit Goldstandard (Seiten, Tabellen, Überschriften).
4. Durchsatz, Speicherbedarf und Fehlerbilder messen; erst danach produktive Integration.


## Ergebnis des ersten realen Laufs (10.11.2026)

Quelle: schreibfreier PDF-Survey auf Poseidon. Die vollständige JSON-Datei mit internen WebDAV-Pfaden bleibt außerhalb von Git.

- 29 von 29 sichtbaren PDFs erfolgreich geöffnet und stichprobenartig untersucht (Status ok).
- Insgesamt 5.064 PDF-Seiten; 322 Seiten in der Stichprobe.
- 10 PDFs ohne Bookmarks; zwei weitere mit nur einem Bookmark.
- Sechs Textarmut-Indikatoren (<40 Zeichen) in sechs Dokumenteinträgen. Das bestätigt noch keinen OCR-Bedarf: Cover und Leerseiten sind möglich.
- Drei PDFs übersteigen bisherige 500-Seiten-Grenze: MGA-G200_199811.pdf (574), usb_20.pdf (650), extensible-host-controler-interface-usb-xhci.pdf (645). Vorläufiges Adapterlimit jetzt 1.000 Seiten; 50-MiB-Dateilimit bleibt bestehen.
- Problemstellen: MGA-G200_199811.pdf S. 522 (19.686 Zeichen); RTL8169SC.PDF S. 9 (8.758 Zeichen); agp30.pdf S. 1 (202 Bildobjekte); xHCI-Spezifikation S. 177 (37 Bildobjekte). Bildanzahl ist kein Beleg für Scan.
- 3C905CX.pdf an zwei Nextcloud-Fundorten: gleiche Dateigröße und Stichprobenwerte, unterschiedliche fileids. Identische Binärinhalte sind erst nach SHA-256-Vergleich nachgewiesen.
- Ursprüngliche Kategorien sind heuristisch; die irrtümliche Erkennung von Datasheet-Namen als Standard durch Teilwort 'ata' wurde im Code korrigiert. Ursprüngliche JSON-Zahlen nicht rückwirkend verändern.

### Priorisierter Testkorpus

| Prüfschwerpunkt | Dokumente / Stichprobenseiten |
|---|---|
| Layout ohne Bookmarks | cubx-103.pdf, cusl2c-104.pdf, agp30.pdf, agp20.pdf, USB_1.0_Specification.pdf |
| Sehr viele Outlines | usb_20.pdf (624), xHCI-Spezifikation (621), AMD K6-2 data sheet_Feb00.pdf (276) |
| Verlustfreie Chunks | MGA-G200_199811.pdf S. 522, RTL8169SC.PDF S. 9 |
| Bild-/Diagrammindikatoren | agp30.pdf S. 1, xHCI S. 177, cusl2c-104.pdf S. 89 |
| Textarme/Leerseiten | cubx-103.pdf S. 112, intel chipsets 440 familiy.pdf S. 4, 3C905CX.pdf S. 1 |
| Quellidentität und Hash | beide 3C905CX.pdf-Fundorte |
| Kleine PDFs | hdd-001.pdf, DGE-528T_Datasheet.pdf, 128iPCI_QR_DE.pdf |

### Nächste Prüfungen

1. Ganze Dokumente seitenweise untersuchen, statt nur zwölf verteilte Seiten.
2. Referenzsätze für Überschriften, Tabellen, Textreihenfolge und Seitenbelege manuell verifizieren.
3. Textarme Seiten als Cover, Leerseite, Scan oder Extraktionsfehler klassifizieren; OCR nur gezielt anwenden.
4. Quellidentität ausschließlich nach Inhaltshashvergleich deduplizieren.
5. 1.000-Seiten-Limit und Kategorisierung auf Poseidon erneut testen; Ressourcenbedarf messen.

Diese Erweiterungen sind noch nicht auf Poseidon getestet. Write-Gate bleibt geschlossen.
