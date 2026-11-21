# Importvertrag und Metadaten – Phase 0, D

Stand: 09.11.2026. Diese Ergänzung konkretisiert den vorhandenen Transportvertrag
`src/retro_rag/importer/contract.py` (Version `0.1`), ersetzt ihn nicht.

## Zuständigkeiten

1. **Quellenadapter:** WebDAV `fileid` als stabile Quellenkennung; Pfad und
   SHA-256 als gesonderte Attribute. Ein Hash identifiziert Inhalt, nicht Dokumentidentität.
2. **Transportvertrag:** `contract_version`, `source`, `document`, `chunks`,
   `fact_proposals`, `warnings`, `indexing_allowed` gemäß `contract.py`.
3. **Metadatenvertrag:** `assess_metadata()` prüft Markdown-Frontmatter rein lesend;
   `title` und `document_type` sind Pflicht. Optional: `language`,
   `manufacturer`, `model`, `revision`, `source_url`,
   `published_at` und `tags`. Fachfelder bleiben im Metadaten-Dict erhalten,
   werden aber dadurch **nicht** als geprüfte Fakten anerkannt.
4. **Faktenfreigabe:** Niemals aufgrund von Frontmatter allein. Erfordert extern
   gepflegte Autoren-/Quellenberechtigung, validierte Fakten und Konfliktfreiheit.
   Die Prüffunktion berechnet lediglich die Eignung; das eigentliche Annehmen
   und Auditieren muss später durch die Review-/Freigabeschicht erfolgen.

## Beispiel Markdown

```yaml
---
title: ASUS CUBX Rev. 1.02
document_type: hardware_model
language: de
manufacturer: ASUS
model: CUBX
revision: "1.02"
tags:
  - mainboard
  - slot_1
---
```

Metadaten gelten als **untrusted input**. `trusted`, `verified`,
`trust_level`, `auto_approve` und `auto_approved` in der Quelldatei
erteilen niemals Berechtigungen und verhindern bei der Prüfung eine
Auto-Freigabeeignung. Weitere unbekannte technische Felder werden erhalten,
aber erst nach Feld-/Wertebereichsprüfung in strukturierte Fakten überführt.

## Entscheidungslogik

| Situation | Ergebnis |
|---|---|
| Pflichtfeld fehlt, falscher Typ, leerer Inhalt, doppelte Tags | Validierungsfehler; keine Faktenfreigabe |
| Metadaten gültig, externe Autorisierung fehlt | keine automatische Faktenfreigabe |
| Metadaten gültig, externe Autorisierung vorhanden, Fakten nicht geprüft | keine automatische Faktenfreigabe |
| Metadaten gültig, Autorisierung + Faktenprüfung + Konfliktfreiheit | grundsätzlich auto-freigabefähig; **keine automatische DB-Änderung** |
| Eigenes Vertrauens-Flag in YAML | Warnung; keine automatische Faktenfreigabe |
| Externes PDF | kein YAML-Vertrauen; Faktenreview erforderlich |

Ein erfolgreich **indexiertes Dokument** ist unabhängig von der
**Freigabe seiner Faktvorschläge**. Ungeprüfte Treffer müssen in Antworten
als ungeprüft erscheinen.

## Grenzen dieses Schritts

- Kein Datenbank-Schreibzugriff, keine Migration und keine Änderung des Write-Gates.
- Bestehender Importvertrag `0.1` bleibt erhalten; Schemaerweiterung verlangt später
  eine eigene Versionsnummer und Adaptermigration.
- Keine automatische Veröffentlichung von Fakten; Autorisierungsregister,
  Konfliktvalidator, Review-Oberfläche und Audit-Persistenz stehen noch aus.
- Frontmatter-Fehler unterbrechen derzeit den Markdown-Adapter; das Überführen
  solcher Fehler in persistente Review-Einträge folgt mit dem Job-Worker.

## Prüfen

```bash
python -m pytest -q tests/test_import_metadata.py
python -m ruff check src/retro_rag/importer/metadata.py tests/test_import_metadata.py
```
