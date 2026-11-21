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

## Validierung auf Poseidon (10.11.2026)

Nach den Korrekturen auf Commit `fbeb040` wurden die beiden PDF-Testmodule erneut auf Poseidon geprüft:

```text
python -m pytest -q tests/test_pdf_extraction.py tests/test_pdf_survey.py
............. [100%]
13 passed in 0.16s

python -m ruff check src/retro_rag/importer/pdf.py src/retro_rag/importer/pdf_survey.py tests/test_pdf_extraction.py tests/test_pdf_survey.py
All checks passed!
```

**Status:** Unit-Tests und Ruff erfolgreich; der Nextcloud-PDF-Survey wurde bereits an 29 Dateien (322 Stichprobenseiten) durchgeführt. Eine vollständige seitenweise Analyse aller 5.064 Seiten, OCR, Layout-Validierung und die Einbindung in die produktive Import-Pipeline wurden damit noch **nicht** abgenommen. V2-Write-Gate bleibt geschlossen.


## Vollständige Seitenqualitätsanalyse (neues Entwicklungsmodul)

`src/retro_rag/importer/pdf_quality.py` untersucht **jede Seite** der gefundenen
PDFs und schreibt ausschließlich einen lokalen JSON-Bericht. Kein Datenbankzugriff,
keine Nextcloud-Änderungen, keine Embeddings und kein OCR-Aufruf. Der bestehende
WebDAV-Client mit dessen ausgeschlossenen Verzeichnissen wird wiederverwendet.

**Durchführung auf Poseidon**, wenn die drei bereits verwendeten
`RETRO_V2_NEXTCLOUD_URL`, `RETRO_V2_NEXTCLOUD_USER` und
`RETRO_V2_NEXTCLOUD_INSTANCE_ID` gesetzt sind:

```bash
cd ~/projects/retro-rag_v2
git pull --ff-only
source .venv/bin/activate
python -m pytest -q tests/test_pdf_quality.py
python -m ruff check src/retro_rag/importer/pdf_quality.py tests/test_pdf_quality.py

# Vorab: zwei PDFs, ohne langsamere Tabellenanalyse.
python -m retro_rag.importer.pdf_quality --max-files 2 --no-tables \
  --report /tmp/retro-v2-pdf-quality-smoke.json

# Danach: alle gefundenen PDFs, inklusive geometrischer Tabellenanalyse.
python -m retro_rag.importer.pdf_quality \
  --report /tmp/retro-v2-pdf-quality.json
```

Fehlt `RETRO_V2_NEXTCLOUD_APP_PASSWORD`, wird das Nextcloud-App-Passwort
interaktiv abgefragt. Die JSON-Datei enthält Dateinamen, Quell-IDs, Hashwerte und
Seitenkennzahlen; **nicht ins öffentliche Repository einchecken**.

**Je Seite erfasste Indikatoren:** Zeichen- und Wortanzahl, Textblöcke,
Text leer / unter 40 Zeichen, Bildanzahl und angenäherte Bildflächenabdeckung,
OCR-Verdacht (wenig Text und Bildabdeckung mindestens 50 %),
häufigste Schriftgröße, auffällig größere Textspannen, mögliche Mehrspaltigkeit,
durch PyMuPDF erkannte Tabellen. Der Bericht enthält keine extrahierten
Textpassagen oder Bilder; das ursprüngliche PDF wird nicht verändert.

**Einschränkungen:** `ocr_candidate` ist nur ein Hinweis. Ein Scan mit kleiner
Bildfläche, eine Vektorzeichnung oder ein fehlerhaft extrahierter Text kann
unentdeckt bleiben. `heading_size_candidates` erkennt keine geprüften
Kapitelgrenzen. `possible_multicolumn` beweist keine falsche Lesereihenfolge.
`table_candidates` ist geometrische PyMuPDF-Erkennung; randlose Tabellen
können übersehen werden. Bildflächen können sich überschneiden, weshalb ihre
Summe auf 100 % gekappt wird und keine genaue Abdeckungsberechnung darstellt.

**Betriebssicherheit:** Maximal 50 MiB pro PDF und standardmäßig 1.000 Seiten,
maximale WebDAV-Verzeichnistiefe wird über den bestehenden Client beschränkt.
Nach jedem Dokument wird die JSON-Datei atomar aktualisiert; bei Abbruch
bleibt `completed=false` und es können die bereits untersuchten PDFs
nachgelesen werden. Ein erneuter Lauf beginnt aktuell von vorn; echtes
Resume/Cache ist noch nicht implementiert. Teilfehler und nicht auswertbare
PDFs werden sichtbar protokolliert. Bei Fehlerstatus liefert der CLI-Aufruf
Exitcode 1.

Das vollständige Analysemodul wurde isoliert lokal anhand synthetischer PDFs
mit acht Tests geprüft. **Tests auf Poseidon und der vollständige
Nextcloud-Lauf sind noch ausstehend**. Write-Gate geschlossen lassen.
