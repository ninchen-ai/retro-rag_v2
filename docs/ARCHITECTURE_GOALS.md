# Architekturziele – universelle Wissensplattform

**Status:** fachlich freigegeben am 20.11.2026 · **Fassung:** 3.0 · **Geltung:** Zielarchitektur, nicht Implementierungsnachweis.

## Leitbild
Lokale persönliche Wissensplattform für beliebige Fachgebiete. Dokumentenwissen und bedarfsabhängig strukturierte Wissensobjekte koexistieren. Extraktion und Freigabe erfolgen regelgesteuert; Agenten speichern neue Erkenntnisse ausschließlich als getrennte unbestätigte Vorschläge.

## Architekturziele
### AZ-01 – Universelle und KI-unabhängige Wissenshaltung
Wissen verschiedener Fachgebiete und Quellenformate wird dauerhaft verwaltet. Das grundlegende Datenmodell ist fachneutral; LLMs, Embeddings, RAG-Verfahren und Agenten sind austauschbare Nutzungskomponenten.

### AZ-02 – Bedarfsabhängige und selektive Wissensstrukturierung
Dokumente können ohne strukturierte Faktenextraktion aufgenommen und durchsucht werden. Strukturierung erfolgt auf Anforderung oder durch autorisierte, konfigurierbare Extraktionsprofile. Technische Indexierung, Extraktion und fachliche Freigabe sind unabhängige Vorgänge; nachträgliche Strukturierung ist möglich.

### AZ-03 – Flexible Organisation von Wissensbeständen
Optionale thematische Sammlungen organisieren Dokumente und Wissensobjekte. Mehrfachzuordnungen und fachübergreifende Abfragen sind möglich, ohne separate Datenbanken pro Sammlung.

### AZ-04 – Unveränderliche Originale und vollständige Provenienz
Originaldokumente bleiben unverändert. Abgeleitete Daten verweisen auf Quelle, Dokumentversion und Fundstelle. Automatische Extraktionen dokumentieren Verfahren, Regelversion und Modell; Agentenerkenntnisse dokumentieren Agent, Ausführung und Eingangsquellen.

### AZ-05 – Erhaltung alternativer und widersprüchlicher Erkenntnisse
Abweichende Aussagen, Lösungen und Implementierungen bleiben nebeneinander bestehen. Widersprüche werden nicht stillschweigend überschrieben oder zusammengeführt; zeitliche und kontextuelle Gültigkeit wird dokumentiert.

### AZ-06 – Kontextabhängige Bewertung von Wissen
Alternativen werden anhand expliziter Kriterien verglichen. Voraussetzungen, Belege, Tests, Ergebnisse und Unsicherheiten bleiben nachvollziehbar. Eine Präferenz ist nur im angegebenen Kontext gültig.

### AZ-07 – Hybrides und qualitätsbewusstes Retrieval
SQL, Volltext und Vektorsuche sind kombinierbar; fachspezifische Suchverfahren ergänzbar. Treffer enthalten Herkunft, Version und Prüfstatus. Unbestätigte Agentenvorschläge werden nicht als bestätigte Tatsachen präsentiert; eine getrennte Vorschlagssuche ist möglich.

### AZ-08 – Fachübergreifende Wissensobjekte und Beziehungen
Eigenständige typisierte Wissensobjekte und Beziehungen werden nach Bedarf modelliert. Ein vollständiger Knowledge Graph oder eine zusätzliche Graphdatenbank ist keine Voraussetzung. Bestehende Fachmodelle, insbesondere das Hardwareinventar, bleiben erhalten.

### AZ-09 – Kontrollierte KI-Agenten und getrennte Vorschlagshaltung
Agenten dürfen über definierte Schnittstellen recherchieren, analysieren und versionierte unbestätigte Vorschläge dauerhaft speichern. Vorschläge sind logisch vom bestätigten Wissen getrennt. Agenten dürfen weder eigene Vorschläge freigeben noch Freigaberegeln ändern oder bestätigtes Wissen direkt überschreiben.

### AZ-10 – Regelabhängige Freigabe und reproduzierbare Validierung
Vorschläge durchlaufen geeignete Prüfungen. Automatische Freigabe setzt eine ausdrücklich autorisierte, versionierte Regel und alle vorgeschriebenen erfolgreichen Prüfungen voraus. Unvollständige, widersprüchliche oder nicht überprüfbare Ergebnisse bleiben im Review. Entscheidungen sind auditierbar; LLM-Confidence allein ist kein Freigabenachweis.

### AZ-11 – Modularer Aufbau und lokaler Einzelbenutzerbetrieb
Die Plattform ist für eine Person ausgelegt. Universelle Kernfunktionen und Fachmodule sind getrennt. Keine umfangreiche Mandantenverwaltung; technische Rollen, isolierte Dienste und kontrollierte Schreibrechte bleiben bestehen.

### AZ-12 – Datenintegrität, Wiederherstellbarkeit und evolutionäre Weiterentwicklung
Daten, Quellenbeziehungen, Freigaben und historische Entscheidungen bleiben erhalten. Migrationen sind versioniert und getestet; Backups, Dry-Run, kontrollierte Schreibfreigaben und Wiederherstellbarkeit sind verbindlich. Retro-RAG V2 wird inkrementell erweitert.

## Vier fachlich freigegebene Entscheidungen
1. Strukturierte Wissensplattform mit bedarfsabhängiger Modellierung.
2. Selektive und regelbasierte Wissensextraktion.
3. Regelabhängige Freigabe extrahierter Wissensobjekte.
4. Agentenerkenntnisse werden automatisch als unbestätigte Vorschläge in einem logisch getrennten Bereich gespeichert.

## Verbindliche Schutzgrenzen
- Importierte Dokumente und Agentenausgaben dürfen Freigaberegeln nicht selbst autorisieren.
- Der erzeugende Agent darf seine Vorschläge nicht selbst bestätigen.
- Unbekannte Regeln, fehlende Belege, Konflikte und Prüfungsfehler führen zu Review statt automatischer Freigabe.
- Originale, bisherige Dokumentidentitäten, vorhandene Reviewhistorie und das Write-Gate bleiben geschützt.
- Die Zielarchitektur autorisiert **keine** produktiven Schreibzugriffe oder Schemaänderungen.

## Offene Detailentscheidungen
Universelles Wissensobjektmodell und Verhältnis zu `knowledge_subject`, `reference_entity`, `fact` und `evidence`; konkretes Extraktionsprofilformat; Freigabepolicy und Auditpersistenz; Agentenautonomie und Ressourcenlimits; Aufbewahrung unbestätigter Vorschläge; Migrations- und Abnahmekonzept. Keine dieser Fragen wird durch dieses Dokument als bereits implementiert dargestellt.

## Implementierungsnachtrag – 20.11.2026

Die fachliche Freigabe der zwölf Ziele bleibt unverändert. Das universelle Wissensobjektmodell 3.1 wurde anschließend fachlich freigegeben und als **erste additive Datenmodellstufe** in Migration `0006` umgesetzt. In `retro_rag_v2_test` sind sechs neue Tabellen und die geschützte Sicht `accepted_entity_relation` mit insgesamt 43 Tabellen dauerhaft installiert. SQL-/Rollen-/Parallelitätstests und der Restore des Pre-0006-Backups im bestehenden Cluster wurden erfolgreich nachgewiesen ([Abnahmeprotokoll](UNIVERSAL_KNOWLEDGE_SCHEMA_0006.md)).

Die historischen offenen Detailfragen oben sind daher **nicht unverändert aktuell**: Das grundlegende Verhältnis zwischen `knowledge_subject`, `reference_entity` und den neuen Themen/Beziehungen wurde für `0006` entschieden. Weitere Werttypen, unabhängige Extraktionsprofile, Freigabepolicies und Audit, Agentenschnittstelle, widersprüchliche/zeitliche Aussagen, Retrieval sowie Aufbewahrungsregeln bleiben ausdrücklich Folgearbeiten. Die technische Migration ist keine fachliche Freigabe einer automatischen Wissensveröffentlichung.
