# Architekturentscheidungen – universelle Wissensplattform

**Stand:** 20.11.2026 · **Status:** fachlich freigegeben, technische Umsetzung offen.

Diese Entscheidungen ergänzen die vorhandenen, datierten Architekturentscheidungen in `README.md` und `conventions.md`; sie ersetzen diese nicht. Endgültige ADR-Nummern werden erst nach Abgleich der bisherigen Nummerierung vergeben.

## UWP-01 – Strukturierte Wissensplattform mit bedarfsabhängiger Modellierung
**Entscheidung:** Dokumente bleiben auch ohne strukturierte Extraktion nutzbar. Strukturierte Objekte und Beziehungen entstehen nur bei fachlichem Nutzen.
**Grund:** Universelle Nutzung ohne vollständige Ontologie und ohne Zwangsextraktion.
**Konsequenz:** Fachneutrale Kernobjekte, optionale Fachmodule, nachträgliche Modellierung.

## UWP-02 – Selektive, regelbasierte Extraktion
**Entscheidung:** Autorisierte Extraktionsprofile steuern die strukturierte Verarbeitung; normale Dokumentindexierung ist davon unabhängig.
**Grund:** Kontrollierbarer Rechen-, Review- und Qualitätsaufwand.
**Konsequenz:** Versionierte Profile, getrennte Jobs, Nachvollziehbarkeit von Regel und Modell; keine implizite Faktenfreigabe.

## UWP-03 – Regelabhängige Freigabe
**Entscheidung:** Ein unabhängiger Dienst darf nur bei autorisierter, versionierter Regel und erfolgreich abgeschlossenen vorgeschriebenen Prüfungen automatisch freigeben.
**Grund:** Technisch gültige oder selbstsicher formulierte LLM-Ergebnisse sind nicht automatisch richtig.
**Konsequenz:** Fail-closed, Konfliktprüfung, Quellenautorisierung, Audit, manuelles Review bei Unsicherheit. Freigaberegeln sind nicht aus importierten Inhalten steuerbar.

## UWP-04 – Getrennter Bereich für Agentenerkenntnisse
**Entscheidung:** Agenten dürfen Erkenntnisse dauerhaft als unbestätigte Vorschläge speichern; Bestätigung erfolgt ausschließlich unabhängig.
**Grund:** Wissenszuwachs ohne unkontrollierte Wissensveränderung.
**Konsequenz:** Vorschlags-API, Provenienz von Agentenläufen, getrennte Retrieval-Sicht, kein Agentenrecht auf Selbstfreigabe.

## Kompatibilität mit dem bestehenden System
- PostgreSQL 16/pgvector, Nextcloud als Dokumentquelle, Originalarchiv, Review und bestehende technische Rollen bleiben Ausgangspunkt.
- Die bestehenden Migrationen `0001`–`0005` werden nicht umgeschrieben.
- `rag_v2.write_gate` bleibt unverändert und geschlossen, bis eine gesonderte operative Freigabe vorliegt.
- Implementierung, Tabellenentwurf, neue Rollen und Migration `0006` sind **nicht** Teil dieser Dokumentationsentscheidung.
