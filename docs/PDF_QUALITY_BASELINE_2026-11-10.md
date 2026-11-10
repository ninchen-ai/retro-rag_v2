# PDF-Qualitätsbaseline – vollständiger Nextcloud-Durchlauf, 10.11.2026

## Verifikation und Geltungsbereich

Quelle: von Poseidon erzeugte lokale Berichte `retro-v2-pdf-quality-smoke.json` (2 PDFs, ohne Tabellenanalyse) und `retro-v2-pdf-quality.json` (29 PDFs, Tabellenanalyse aktiv). **Die vollständigen Berichte wurden nicht ins öffentliche Repository übertragen**; sie enthalten Dateinamen, private Quellkennungen und SHA-256-Hashes.

- Beide Berichte sind mit `completed=true` abgeschlossen.
- Vollanalyse: **29/29** Dokumente `status=ok`, **5.064/5.064** Seiten untersucht, **0 Seitenfehler**, **0 Tabellenerkennungsfehler**.
- Smoke-Test: **2/2** Dokumente erfolgreich. Für diese zwei PDFs stimmen alle Seitenmetriken und Aggregationen des Smoke-Tests mit dem Vollbericht überein, wenn die dort deaktivierte Tabellenanalyse ausgeklammert wird.
- Aus den JSON-Ergebnissen folgt **nicht**, dass die neu eingeführten Unit-Tests oder Ruff erneut auf Poseidon ausgeführt wurden. Diesen Nachweis gesondert führen.
- `status=ok` belegt die technische Ausführung der Analyse, **nicht** die sachliche Korrektheit aller Tabellen, Überschriften oder der Lesereihenfolge.

## Gesamtkennzahlen

| Indikator | Alle 29 Nextcloud-Quellen (einschließlich Duplikat) | Einmal je eindeutigem Datei-SHA-256 (28 PDFs) |
|---|---:|---:|
| PDF-Seiten | 5.064 | 4.953 |
| Seiten ohne extrahierten Text | 28 | 22 |
| Seiten mit unter 40 Zeichen (inkl. leere) | 32 | 26 |
| OCR-Kandidaten (heuristisch) | 5 | 4 |
| Seiten mit Mehrspaltenverdacht | 84 | 78 |
| Größere Schriftspannen als Überschriftshinweise | 12.295 | 12.175 |
| Tabellenerkennungen von PyMuPDF | 3.720 | 3.631 |

Die beiden Quellen namens `3C905CX.pdf` in unterschiedlichen Nextcloud-Verzeichnissen besitzen **identischen SHA-256-Inhaltshash**. Die Survey-/Qualitätsberichte zeigen damit zwei Quellorte desselben Binärdokuments. Für V2 Quellenidentitäten getrennt halten; Inhaltsduplikat kann intern zusammengeführt werden, ohne Verknüpfungen zu verlieren. Kein automatisches Schreiben oder Zusammenführen durchgeführt.

## Priorisierte OCR-/Leerseitenprüfung

| Dokument | Seite (PDF-Zählung ab 1) | Technischer Befund |
|---|---:|---|
| `cubx-103.pdf` | 111 | 0 Zeichen, 1 Bildobjekt, 94,26 % geschätzte Bildabdeckung; OCR-Kandidat |
| `3C905CX.pdf` | 1 | 0 Zeichen, ganzseitiges Bildobjekt, OCR-Kandidat; an beiden Quellen identisch |
| `directx-demystified-a-comprehensive-guide-to-game-development-essentials.pdf` | 2 | 0 Zeichen, ca. 58,72 % Bildabdeckung; OCR-Kandidat |
| `507700.pdf` | 24 | 0 Zeichen, 3 Bildobjekte, ca. 90,18 % Abdeckung; OCR-Kandidat |
| `cubx-103.pdf` | 112 | 0 Zeichen, keine Bildobjekte; mögliche Leerseite, nicht OCR-bestätigt |
| `intel chipsets 440 familiy.pdf` | 4 | 0 Zeichen, keine Bildobjekte; zunächst visuell prüfen |

Textarme Seiten allein sind **kein** Nachweis für OCR-Bedarf. Vektorbasierte Inhalte können trotz null Bildern und null Text existieren; auch die optische Seitenansicht muss geprüft werden. OCR nur nach manueller Verifikation/weiterer Qualitätsprüfung.

## Priorisierte Layout- und Tabellenprüfung

| Dokument und Testseite | Prüffokus |
|---|---|
| `usb_20.pdf` (z. B. S. 601–606) | 52 Mehrspaltenhinweise im gesamten Dokument, davon eine lange Folge im hinteren Bereich; korrekte Lesereihenfolge gegen visuelle Seite prüfen |
| `AMD K6-2 data sheet_Feb00.pdf` (S. 323–328) | Viele Mehrspaltenhinweise und äußerst textreiche Seiten (z. B. S. 326: 17.637 Zeichen) |
| `MGA-G200_199811.pdf` (S. 522, 524) | 19.686 bzw. 18.913 extrahierte Zeichen; verlustfreie Chunk-Rekonstruktion mit echten Inhalten testen |
| `ehci-specification-for-usb.pdf` (S. 43, 139) | 16 bzw. 15 Tabellenkandidaten auf einer Seite; Qualität, False Positives und Zellordnung prüfen |
| `USB_1.0_Specification.pdf` (S. 152, 156) | 10 bzw. 9 Tabellenkandidaten |
| `cubx-103.pdf` (S. 21) | Mainboard-Handbuch ohne Bookmarks mit 7 Tabellenkandidaten |
| `agp20.pdf` | 0 Bookmarks, 1.092 Hinweise auf größere Schriftspannen; Überschriftenhierarchie prüfen |
| `directx-demystified-a-comprehensive-guide-to-game-development-essentials.pdf` | 486 Seiten, 1 Bookmark, 0 Schriftgrößen-Überschriftshinweise und 0 Tabellen; möglicherweise anderes Schrift-/Layoutmuster |

Die Zähler `table_candidates` und `heading_size_candidates` sind **keine verifizierten Tabellen bzw. Kapitelüberschriften**. Wiederkehrende Beschriftungen, Kopfzeilen oder einzelne Zellen können Fehlklassifikationen erzeugen. Die `possible_multicolumn`-Heuristik beweist ebenfalls keine fehlerhafte Lesereihenfolge.

## Empfohlene nächste Abnahme

1. Kleinen **visuell verifizierten Goldstandard** aus den obigen Seiten erstellen: erwartete Textreihenfolge, echte Kapitelüberschriften, Tabellengrenzen/-zellen und die OCR-Frage.
2. Kennzahlen gegen diesen Goldstandard evaluieren: Präzision und Recall der Überschrift-/Tabellen-/Spaltenhinweise, OCR-Entscheidung pro Seite.
3. Erst bei belegten Defiziten gezielte OCR und Layoutnachverarbeitung an ergänzenden, kopierten Arbeitsartefakten durchführen; Provenienz und Seitenposition erhalten.
4. Mit Dokumentversion, Quellidentität und `document_source`-Zuordnung weiterarbeiten; **Write-Gate geschlossen lassen**.
5. Ressourcen-/Laufzeitmessungen (Dauer, CPU, RAM, PDF-Größe) beim nächsten Lauf miterfassen; die vorhandenen JSON-Berichte enthalten keine Laufzeiten.

**Status:** Vollständige schreibfreie Qualitätsanalyse bestanden; inhaltliche Layout-/OCR-Qualität noch nicht abgenommen.
