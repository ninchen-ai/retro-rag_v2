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

\`\`\`bash
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
\`\`\`

**Hinweis:** Die URL ist ein Beispiel für Poseidons Loopback-WebDAV. Benutzer, URL und stabile Instanzkennung an die tatsächlich konfigurierte Umgebung anpassen.

## Bericht

Standard: \`/tmp/retro-v2-pdf-survey.json\`. Enthält vollständiges PDF-Inventar (Pfad, Dateigröße, etag, Quelle, heuristische Kategorie), ausgewählte Kandidaten und für tatsächlich heruntergeladene PDFs: Seitenzahl, Bookmark-Anzahl, gleichmäßig verteilte Seitenstichprobe, Zeichenzahlen, Bildzahlen, mögliche größere Schriftspannen und Fehler.

Die Kategorien \`standards\`, \`datasheets\`, \`manuals\`, \`other\` werden **nur anhand von Pfadnamen** geschätzt. Die Auswahl mischt diese Kategorien und Größenklassen. Relevante Problemfälle (Scans, lange Dokumente, Tabellen, zweispaltiges Layout, nicht lesbare Dateien) nach Sichtung der Qualitätswerte gezielt ergänzen.

## Offene Weiterentwicklung

1. Echten PDF-Bestand katalogisieren und aggregierte Ergebnisse vergleichen.
2. Qualitätsstufen und Prioritäten aus realen Dokumenten ableiten.
3. Automatisierte OCR-/Layout-Testfälle mit Goldstandard (Seiten, Tabellen, Überschriften).
4. Durchsatz, Speicherbedarf und Fehlerbilder messen; erst danach produktive Integration.
