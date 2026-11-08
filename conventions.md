# Konventionen – Retro-RAG V2

Verbindliche Regeln für Code, Datenmodell, Import, Lebenszyklus und Betrieb. Grundlage ist die Mindmap `docs/Retro-Rag V2.mm`. Wo eine Regel ein **Vorgabewert** ist (vorläufig, bis entschieden), steht das ausdrücklich dabei. Offene Punkte stehen am Ende.

## Inhalt

1. [Grundprinzipien](#1-grundprinzipien)
2. [Sprache und Begriffe](#2-sprache-und-begriffe)
3. [Python-Code](#3-python-code)
4. [Konfiguration und Geheimnisse](#4-konfiguration-und-geheimnisse)
5. [Datenbank](#5-datenbank)
6. [Datenmodell](#6-datenmodell)
7. [Fakten, Belege und Kompatibilitätswissen](#7-fakten-belege-und-kompatibilitätswissen)
8. [Import- und Reviewpipeline](#8-import--und-reviewpipeline)
9. [Dokumentlebenszyklus](#9-dokumentlebenszyklus)
10. [Retrieval und Antworten](#10-retrieval-und-antworten)
11. [Qualität und Tests](#11-qualität-und-tests)
12. [Betrieb und Pflege](#12-betrieb-und-pflege)
13. [Git und GitHub](#13-git-und-github)
14. [Sicherheit](#14-sicherheit)
15. [Checkliste für neue Module](#15-checkliste-für-neue-module)
16. [Architekturentscheidungen](#16-architekturentscheidungen)
17. [Noch offene Parameter](#17-noch-offene-parameter)

---

## 1. Grundprinzipien

Diese vier Regeln gelten überall und haben Vorrang vor Bequemlichkeit.

| Prinzip | Regel |
|---|---|
| **Rohdaten bleiben Original** | Quelldateien werden nie verändert, weder in Nextcloud noch im eigenen Archiv. Abgeleitete Daten (Text, Chunks, Embeddings, Fakten) müssen aus den Originalen neu erzeugbar sein. |
| **Bestätigung vor Änderung** | Inventardaten ändern sich nur nach ausdrücklicher Bestätigung. Jedes Skript, das Daten ändert, läuft ohne `--apply` im Dry-Run und gibt aus, was es tun würde. |
| **Strukturiert für Fakten, Fließtext für Erklärungen** | Eigenschaften, technische Fakten und Beziehungen stehen als Felder (siehe Abschnitt 7). Fließtext steht für Erklärungen, Einschränkungen, historische Zusammenhänge und Dokumentkontext. Ein Zahlenwert, der nur im Fließtext steht, gilt nicht als **bestätigter strukturierter** Fakt; ungeprüfte Dokumentpassagen dürfen mit klarer Kennzeichnung zitiert werden. |
| **Antwort mit Quelle** | Aussagen aus Dokumenten nennen Version und Fundstelle sowie den Prüfstatus. Ungeprüfte Textstellen werden als solche markiert; unbelegte technische Aussagen werden nicht als sicher ausgegeben. |

Daraus folgt: Das LLM erzeugt **nur Vorschläge**. Es schreibt nie direkt in Tabellen mit gültigen Fakten oder Bestandsdaten.

---

## 2. Sprache und Begriffe

| Bereich | Sprache |
|---|---|
| Dokumentation, Kommentare, Docstrings, Commit-Texte, Benutzertexte, Logs für Menschen | Deutsch |
| Bezeichner in Code und Datenbank (Variablen, Funktionen, Tabellen, Spalten, Statuswerte) | Englisch |
| Dateinamen im Repository | Englisch, `snake_case` (Ausnahme: `README.md`, `conventions.md`) |

Zuordnung der Begriffe aus der Mindmap zu den Bezeichnern:

| Mindmap | Bezeichner |
|---|---|
| Stammdaten | `article` |
| Exemplar | `unit` |
| Verbauung und System | `installation`, `system` |
| Historische Lagerung | `storage_assignment`, `storage_location` |
| Modellrevision / Alias | `article_revision`, `article_alias` |
| Dokumentquelle | `document_source` |
| Verarbeitungsauftrag | `processing_job`, `processing_step`, `processing_artifact` |
| Lagerort | `storage_location` |
| Dokument / Dokumentversion | `document` / `document_version` |
| Fakt / Quellenbeleg | `fact` / `evidence` |
| Kompatibilitätsregel | `compatibility_rule` |
| Modellkennung | `model_key` |
| Review-Eintrag | `review_item` |

**Statuswerte** (Spalten vom Typ `text` mit `CHECK`, siehe Abschnitt 5):

| Bereich | Mindmap | Wert |
|---|---|---|
| Dokumentversion (`document_version.state`) | Aktiv, Ersetzt, Archiviert | `active`, `superseded`, `archived` |
| Dokumentverfügbarkeit (`document.availability`) | Verfügbar, Deaktiviert, Entfernt | `available`, `deactivated`, `removed` |
| Zustand: Vollständigkeit | Vollständig, Unvollständig | `complete`, `incomplete` |
| Zustand: Funktion | Funktionsfähig, Reparaturbedürftig, Defekt, Ungetestet | `working`, `needs_repair`, `defective`, `untested` |
| Beleg-Art | Extern belegt (Quelle), Selbst belegt | `external`, `self_tested` |
| Fakt (Review) | angenommen, abgelehnt, korrigiert, zurückgestellt, vorgeschlagen | `accepted`, `rejected`, `corrected`, `deferred`, `proposed` |
| Dokumentverarbeitung | entdeckt, in Bearbeitung, indiziert, fehlgeschlagen | `discovered`, `processing`, `indexed`, `failed` |
| Historischer Beleg | Quelle nicht mehr verfügbar | `source_unavailable` |
| Beleg oder Regel ohne Nachweis | unbelegt | `unsupported` |
| Ergebnisklasse einer Antwort | bestätigt, ungeprüfte Quelle, nicht ausreichend belegt | `confirmed`, `unreviewed_source`, `insufficient_evidence` |

Neue Statuswerte werden zuerst in diese Tabelle eingetragen, dann im Code.

---

## 3. Python-Code

- **Version:** Python 3.11 oder neuer.
- **Stil:** PEP 8, formatiert und geprüft mit `ruff` (Zeilenlänge 100). Type Hints an allen öffentlichen Funktionen.
- **Pfade:** `pathlib.Path`, keine String-Verkettung.
- **Ausgabe:** `logging` statt `print` (Ausnahme: gewollte CLI-Ausgabe von Dry-Runs und Berichten).
- **Fehler:** Keine blanken `except:`. Fehler werden mit Kontext (Dokument-ID, Stufe) protokolliert. Ein einzelnes fehlerhaftes Dokument darf nie den ganzen Lauf abbrechen.
- **Datenbank:** `psycopg` 3 mit Parametern (`%s`), **niemals** SQL per f-String mit Nutzerdaten zusammenbauen. Kein ORM, SQL liegt in Modulen oder `.sql`-Dateien.
- **YAML:** nur `yaml.safe_load`, nie `yaml.load`.
- **Zeit:** intern immer UTC und zeitzonenbewusst (`datetime.now(timezone.utc)`).
- **Skripte (CLI):**
  - Dry-Run ist der Standard, `--apply` führt aus.
  - Exit-Code `0` bei Erfolg, `1` bei Fehlern, `2` bei Abbruch durch eine Schutzregel (z. B. Massenlöschung).
  - Synchronisationsläufe schreiben in `sync_run`; andere Worker in ihre `processing_job`-/`processing_step`-Datensätze. Schreibende systemd-Units übergeben ausdrücklich `--apply`.
  - Skripte sind idempotent: Ein zweiter Lauf ohne Änderung in den Quellen ändert nichts.

---

## 4. Konfiguration und Geheimnisse

- **`config.yaml`** (nicht im Repository) enthält Einstellungen. **`config.example.yaml`** (im Repository) dokumentiert alle Schlüssel mit Beispielwerten.
- **Zugangsdaten** (Datenbank, Nextcloud-App-Passwort, API-Schlüssel) kommen aus Umgebungsvariablen oder einer `.env`-Datei, nie aus YAML und nie aus dem Code.
- **Modelle** sind Konfiguration: Name des Embedding-Modells, **Dimension**, LLM für Extraktion, Chat-LLM. Der Code enthält keine Modellnamen.
- **Embedding-Dimension:** Beim Start wird geprüft, ob Modellkennung und Dimension zum jeweiligen Embedding-Speicher/Index passen. Bei Abweichung wird die Suche für dieses Modell nicht ausgeführt. Keine feste Mindestdimension: z. B. 768 (nomic-embed-text) oder 1024 (bge-m3).
- **Schwellwerte** (Unsicherheit, Fristen, Massenlöschung) stehen in der Konfiguration, nicht im Code.

Fristen und Schwellwerte (Vorgabewerte):

| Schlüssel | Vorgabe | Bedeutung |
|---|---|---|
| `lifecycle.superseded_days` | 30 | Übergangsfrist alt + neu |
| `lifecycle.deactivated_grace_days` | 14 | Frist zwischen „deaktiviert“ und „entfernt“ |
| `lifecycle.mass_delete_threshold_percent` | 10 | Abbruch, wenn mehr Dokumente in einem Lauf verschwinden |
| `lifecycle.max_active_versions` | 2 | gleichzeitig durchsuchbare Versionen je Dokument |

---

## 5. Datenbank

PostgreSQL 16 mit `pgvector`. Datenbankname und Rollen werden in der Konfiguration geführt.

**Benennung**

- Tabellen und Spalten: `snake_case`, Tabellennamen im Singular (`document`, `document_version`, `chunk`).
- Primärschlüssel `id`, Fremdschlüssel `<tabelle>_id` (z. B. `document_id`).
- Zeitstempel: Typ `timestamptz`, Namen `created_at`, `updated_at`, bei Fristen `archive_after`.
- Statusfelder: `text` mit `CHECK (...)`, **kein** `ENUM` (einfacher zu migrieren).

**Schlüssel (stabile IDs)**

- Technische IDs sind **UUIDs** (`gen_random_uuid()`), werden einmal vergeben und nie wiederverwendet. `document.id` bleibt bei Umbenennung/Verschiebung gleich; `chunk.id` ist dagegen versionsgebunden und wird für eine neue Version neu erzeugt.
- Für Exemplare gibt es zusätzlich eine **lesbare Inventarnummer** (z. B. `RPC-000123`) als eigene Spalte mit `UNIQUE`. Sie steht auf dem Etikett, die technische ID bleibt intern.
- `content_hash` (SHA-256) identifiziert Dateiinhalte, nicht die logische Dokumentidentität. `document_source` hält Nextcloud-Quellkennung und Fundort; `document_version` hält Hash und Version. Mehrdeutige Zuordnungen werden geprüft.

**Migrationen**

- Nummerierte SQL-Dateien in `db/migrations/` (`0001_init.sql`, `0002_...`), nur vorwärts, nie nachträglich geändert.
- Vor jeder Migration gibt es ein Backup (Abschnitt 12).

**Löschverhalten (Fremdschlüssel)**

- `document_version` und `document_source` dürfen nicht pauschal kaskadierend entfernt werden, solange historische `evidence` oder Review-Entscheidungen darauf verweisen. Bei normaler Entfernung bleiben schlanke historische Identitäts-/Versionsdatensätze mit Hash und Fundstellen erhalten (`source_unavailable`).
- Suchdaten (`chunk`, Embeddings) und Archivkopien werden nach Ablauf der Löschfrist gelöscht; ihre Beziehungen dürfen kaskadieren.
- `evidence` bleibt mit Dokumentversion, Seite, Belegauszug und Verfügbarkeitskennzeichen erhalten. Fakten und Review-Entscheidungen bleiben erhalten. Ein ausdrücklich erforderlicher vollständiger Löschprozess ist gesondert zu definieren.
- `article`, `unit`, `installation` und `storage_assignment` werden niemals durch Dokumentlöschung kaskadiert.

**Historisierung:** Änderungen an Bestandsdaten und Fakten werden nicht überschrieben, sondern mit Gültigkeitszeitraum (`valid_from`, `valid_to`) oder in einer History-Tabelle festgehalten. Ein Ausbau oder Zustandswechsel bleibt nachvollziehbar.

**Protokolltabellen**

- `sync_run`: Start, Ende, Dry-Run oder Apply, Zähler (neu, geändert, archiviert, deaktiviert, entfernt, Fehler).
- `document_error`: Dokument, Stufe, Fehlertext, Anzahl Wiederholversuche.
- `query_log`: Frage, verwendete Chunks samt Version, Antwort, Bewertung.
- `review_decision`: wer, wann, was, Begründung (Abschnitt 8).
- `processing_job`, `processing_step`, `processing_artifact`: persistente Aufträge, Stufen, Artefaktverweise, Leases, Retries, Fehler.
- `review_batch`, `review_item`: Bündel und einzelne Freigabevorschläge.

**Vektoren:** Jeder Chunk gehört zu genau einer Dokumentversion und besitzt ein versionsgebundenes Embedding. Modellkennung und Dimension werden gespeichert. Das Datenbankschema muss Modellwechsel und unterschiedliche Dimensionen ohne gemischte Ähnlichkeitssuche unterstützen (z. B. getrennte modellbezogene Indizes/Spalten). Keine versionsübergreifende Chunk-Deduplizierung in V2.

---

## 6. Datenmodell

**Kernobjekte und Beziehungen**

```text
article 1 ── n article_revision
article 1 ── n article_alias
article 1 ── n unit (optional: article_revision_id)
unit 1 ── n installation ── 1 system
unit 1 ── n storage_assignment ── 1 storage_location
document 1 ── n document_source
document 1 ── n document_version ── n chunk
document_version 1 ── n evidence ── n fact
compatibility_rule n ── n evidence
processing_job 1 ── n processing_step ── n processing_artifact
review_batch 1 ── n review_item ── n review_decision
```

**Exemplar und Standort:** Jedes `unit` ist entweder in genau einem System verbaut, eingelagert oder ausdrücklich `unknown`. Vergangene Zuordnungen behalten `valid_from`/`valid_to`; höchstens eine aktive Zuordnung **über beide Tabellen hinweg**. Eine Transaktion mit Sperre auf dem `unit` sichert diese tabellenübergreifende Regel (einzelne partielle Unique-Indizes genügen dafür nicht). Beim Ausbau wird die Installation geschlossen, bei Einlagerung eine neue Lagerzuordnung angelegt.

**Hardwareidentität:** `article.id` ist eine stabile UUID; `article_revision` beschreibt nachgewiesene Revisionen, `article_alias` alternative Schreibweisen. `model_key` (`hersteller:modell[:variante]`) ist ein normalisierter **Such-/Dublettenhinweis, kein Primärschlüssel**. Fakten können auf Modell- oder Revisionsebene gelten. Unklare Zuordnung wird geprüft; kein automatisches Zusammenführen.

**Dokumentidentität:** `document` (logisches Objekt), `document_source` (Quellkennung/Fundort) und `document_version` (Inhaltsversion/Hash) sind getrennt. Gleicher Hash an mehreren Fundorten kann auf dieselben Inhaltsdaten verweisen, ohne zwingend identische logische Dokumente zu beweisen. Eindeutige Quellkennung erlaubt Rename/Move-Erkennung.

**Zustand** hat zwei getrennte Felder je Exemplar: `completeness` (`complete`, `incomplete`) und `functional_state` (`working`, `needs_repair`, `defective`, `untested`). Neue Exemplare beginnen mit `untested`.

**Dublettenerkennung:** Vor dem Anlegen eines Exemplars wird nach Seriennummer, Artikel, Revision und Aliasen gesucht. Treffer werden zur Bestätigung vorgelegt; keine automatische Zusammenführung. Mehrere gleichartige Exemplare werden nach den Inventarregeln eindeutig verwaltet.

**Komponentenarten** (CPU, RAM, Mainboard, Festplatten, Grafikkarten, ...) stehen in einer Referenztabelle `component_type`. Jede Art legt fest, welche Eigenschaften erlaubt sind.

---

## 7. Fakten, Belege und Kompatibilitätswissen

**Fakt:** Eine einzelne, typisierte Aussage über ein Objekt.

| Feld | Inhalt |
|---|---|
| Objekt | z. B. `article` oder `document` |
| `property` | Schlüssel aus dem kontrollierten Vokabular (`schema/properties.yaml`) |
| Wert | als Zahl (`numeric`) oder Text (`text`), nie als Mischtext |
| `unit` | Einheit, z. B. `V`, `MHz`, `MB` |
| `status` | `proposed`, `accepted`, `rejected`, `corrected`, `deferred` |
| `confidence` | Unsicherheitsbewertung des Extraktors (0 bis 1), falls vorhanden |

- **Kontrolliertes Vokabular:** Eigenschaften sind vorab definiert (Name, Typ, Einheit, erlaubte Komponentenarten). Neue Eigenschaften kommen zuerst in `schema/properties.yaml`.
- **Einheiten** werden bei der Übernahme vereinheitlicht (z. B. immer `V`, nie `mV` oder „3,3 Volt“).

**Quellenbeleg auf Feldebene (`evidence`):** Jeder dokumentgestützte Fakt verweist über `evidence` auf `document_version_id`, Seite und kurzen wörtlichen Auszug; historische Belege bleiben nach regulärer Quelldatei-Entfernung mit `source_unavailable` erhalten. Ein Fakt kann mehrere Belege haben, eine Kompatibilitätsregel ebenfalls.

**Nachweise für Kompatibilität:** Jede `compatibility_rule` hat mindestens einen Nachweis mit Art `external` (Quelle) oder `self_tested` (selbst geprüft, mit Datum und Testaufbau). Regeln ohne Nachweis werden als `unsupported` (unbelegt) geführt und nie als sicher beantwortet.

**Widersprüche:** Widersprechen sich zwei Quellen, werden beide Fakten behalten und der Konflikt wird an das Review gemeldet. Die Antwort nennt beide Werte mit Quelle, statt still einen zu wählen.

---

## 8. Import- und Reviewpipeline

**Technische Pipeline** (persistente, idempotente Schritte):

1. Quelle über `document_source` identifizieren, Hash berechnen, Original archivieren.
2. Dokument prüfen; identische Inhalte nicht unnötig mehrfach extrahieren; mehrdeutige Zuordnungen in Review.
3. PDF-Text mit PyMuPDF extrahieren; bei Bedarf Tesseract-OCR; Layoutanalyse mit DocLayout-YOLO optional (kein OCR-Ersatz).
4. Versionsgebundene Chunks und Embeddings erzeugen; Modellkennung/Dimension protokollieren.
5. Strukturierte Faktenvorschläge mit Ollama extrahieren und validieren.
6. Technisch vollständig verarbeitete Dokumentversion **atomar indexieren/aktivieren**, auch wenn Fakten noch offen sind.
7. Unabhängiger Faktenreview: freigegebene Werte werden in den bestätigten Bestand übernommen.

**Unabhängige Statusachsen:** Dokumentverarbeitung `discovered/processing/indexed/failed`; Faktenreview `proposed/accepted/rejected/corrected/deferred`. Bei technischer Fehlverarbeitung bleibt die vorherige Version aktiv. Teilfreigaben blockieren die Suche nach Dokumenttext nicht. Ungeprüfte Textpassagen müssen in Antworten erkennbar bleiben.

**Jobpersistenz:** `processing_job`, `processing_step`, `processing_artifact` speichern Status, Artefaktverweise, Retry-Zähler, Fehler und zeitlich befristete Leases. Unterbrochene Schritte werden nach Neustart fortgesetzt, wenn Artefakte und Eingabe-Hashes gültig sind. Fehlerhafte Dokumente blockieren keine anderen. systemd startet Worker; zunächst serielle GPU-intensive Ollama-Arbeiten, kein Redis/Celery.

**Quellenvertrauen:** Eine eigene Markdown-Datei wird nur automatisch freigegeben, wenn eine **außerhalb der Datei** gepflegte Berechtigung sie ausdrücklich autorisiert, YAML-Metadaten vollständig sind und Schema, Wertebereiche sowie Konsistenz erfolgreich geprüft wurden. Ein Verzeichnis allein oder eine selbstdeklarierte YAML-Vertrauensstufe genügt nicht. Externe Dokumente benötigen manuellen Faktenreview. Konflikte und unbekannte Eigenschaften gelangen immer in den Review. Automatische Freigaben protokollieren Quelle, Hash, Regel und Zeitpunkt. Das LLM kann keine Vertrauensrechte erhöhen.

**Review-Weboberfläche:** schlanke HTML-Ansicht mit FastAPI, Authentifizierung und API-basierter Änderung; OpenWebUI bleibt für Chat. Feldweise annehmen, ablehnen, korrigieren oder zurückstellen; Sammel-/Teilfreigaben; Quellenvergleich; `review_batch`, `review_item`, `review_decision` dokumentieren Benutzer, Zeitpunkt, Begründung sowie alten und neuen Wert. Keine direkte Tabellenänderung durch die Oberfläche. Benutzerautorisierung und ausdrückliche Bestätigung werden zusätzlich zu DB-Rechten geprüft.

**Importvertrag (Entwurf, v0):** Pydantic-Modell mit `contract_version`, `source` (Quell-ID, Fundort, Hash, Art), `document` (Metadaten), `chunks` (Text, Seite, Position, Überschriftenpfad, Hash), `fact_proposals` (Objekt, Eigenschaft, Wert, Einheit, Beleg, Unsicherheit) und `warnings`. Änderung nur mit neuer `contract_version`.

## 9. Dokumentlebenszyklus

**Drei Identitäten:** `document.id` ist dauerhaft; `document_source` erfasst Nextcloud-Kennung/Fundort; `document_version` enthält Versionsdaten und SHA-256-Hash. Hashgleichheit allein ist kein Beweis für gleiche logische Dokumentidentität. Umbenennen/Verschieben wird über stabile Quellkennung erkannt. Mehrere gültige Quellen verhindern eine Löschung beim Wegfall nur einer Quelle.

**Zwei getrennte Statusachsen:** Der Versionsstatus (`document_version.state`: `active`, `superseded`, `archived`) beschreibt, welche Inhaltsversion gilt. Die Verfügbarkeit (`document.availability`: `available`, `deactivated`, `removed`) beschreibt, ob das Dokument noch eine gültige Quelle hat. Beide Felder sind unabhängig; nur bei `available` gilt der Versionsstatus für die Suche.

**Versionen:** `active` ist die aktuelle indizierte Version. `superseded` bleibt während `lifecycle.superseded_days` (Vorgabe 30) als alt markiert suchbar; `archived` nur auf ausdrückliche Anfrage. Maximal `lifecycle.max_active_versions` (Vorgabe 2) sind gleichzeitig in der Standardsuche. Technische Verarbeitung und Faktenreview besitzen getrennte Statusachsen (Abschnitt 8).

**Chunks:** Jede Version besitzt eigene Chunk-IDs, Fundstellen und Embeddings, selbst bei identischem Text. In V2 keine versionsübergreifende Deduplizierung. Alte Version bleibt bei technischem Importfehler aktiv.

**Entfernung nach Quellverlust:**

1. Nur wenn **keine** gültige Quelle mehr existiert: `document.availability = deactivated`, aus Standardsuche ausblenden; Karenzfrist `lifecycle.deactivated_grace_days` (Vorgabe 14).
2. Nach Frist: `document.availability = removed`. Originalarchivkopien und Suchdaten (Chunks/Embeddings) entfernen. **Historische Dokument-/Versionskennungen, Hashes, frühere Fundstellen, kurze Belegauszüge und Review-Entscheidungen behalten**; `evidence` als `source_unavailable` markieren.
3. Fakten bleiben mit historischer Provenienz, aber die Quelle ist nicht mehr verfügbar. Bei ausschließlich fehlenden aktuellen Belegen dürfen Kompatibilitätsaussagen nicht als aktuell nachgewiesen ausgegeben werden. Ausdrücklich erforderliche vollständige Löschung benötigt einen separaten, auditierten Ablauf einschließlich Backup-Aufbewahrungsprüfung.

**Schutz:** Kein Deaktivieren/Entfernen bei nicht erreichbarer Nextcloud oder leerer/ungültiger Dateiliste. Bei mehr als `lifecycle.mass_delete_threshold_percent` (Vorgabe 10 %) verschwundenen Dokumenten Abbruch mit Exit-Code 2 und Alarm. Bei Restore zusätzlich Schreibsperre bis Freigabe.

**Versionsänderungen:** Neue Version vollständig technisch verarbeiten, dann atomar aktivieren. Widersprüche in Fakten erzeugen Review-Vorschläge, keine stillen Überschreibungen. Alte Versionen und ihre Herkunft bleiben historisch nachvollziehbar.

## 10. Retrieval und Antworten

- **SQL:** Inventar, Verfügbarkeit und bestätigte strukturierte technische Eigenschaften.
- **Hybride Dokumentensuche:** PostgreSQL-Volltextsuche (exakte Begriffe/Teilenummern) plus pgvector-Semantik. Gewichtung anhand Regressionstests festlegen.
- **Kombinierte Fragen:** SQL-Inventar und Dokumentwissen verbinden; deterministische Kompatibilitätsregeln mit nachgewiesenen Eingabewerten prüfen. Das LLM erklärt, ersetzt keine elektrische/technische Regelprüfung.
- **Quellenstatus:** Ungeprüfte Dokumentpassagen dürfen mit klarer Kennzeichnung zitiert werden; nur freigegebene Fakten gelten als bestätigt. Bei unzureichenden/widersprüchlichen Belegen: „nicht ausreichend belegt“. Die drei Ergebnisklassen heißen `confirmed`, `unreviewed_source` und `insufficient_evidence`.
- **Versionen:** Standardsuche `active`/`superseded` (letztere als alt gekennzeichnet); `archived` nur auf ausdrückliche Anforderung. Dokumente mit `availability` `deactivated` oder `removed` sind nicht suchbar.
- **Doppelte Treffer:** Da jede Version eigene Chunks besitzt (keine Deduplizierung im Speicher), fasst die Ausgabe Treffer mit gleichem `chunk_hash` zusammen und zeigt nur den Treffer der neuesten Version. Unterscheidet sich der Text, werden beide mit Versionsangabe gezeigt.
- **Nachweise:** Version, Seite/Fundstelle, Status und gegebenenfalls `source_unavailable` nennen. Keine frei erfundenen Quellen.
- **Chunking:** dokumenttypspezifisch, Überschriftenpfad und Seite erhalten; Embedding-Suche nur mit kompatibler Modellkennung und Dimension.

## 11. Qualität und Tests

- **Werkzeug:** `pytest`. Tests liegen in `tests/`.
- **Testfragen:** `tests/questions.yaml` enthält Fragen mit erwarteter Antwort und erwarteter Quelle (Dokument, Seite). Ein Teil davon ist **Gold-Set** mit sicher geprüften Antworten und wird nie als Trainings- oder Beispieldaten verwendet.
- **Regressionstest:** Vor jedem Wechsel von Modell, Chunking, Schwellwerten oder Suchverfahren läuft das Testset, und das Ergebnis wird gespeichert und mit dem vorherigen verglichen.
- **Prüfung auf Halluzinationen:** Testfragen enthalten auch solche **ohne** vorhandene Antwort. Richtig ist dann „keine belegte Information“.
- **Vergleich von Modellen und Einstellungen:** gleicher Testsatz, gleiche Daten, Ergebnis in einer Tabelle mit Datum, Modell, Parametern.
- **Unit-Tests** für Normalisierung (`model_key`, Einheiten), Statusübergänge, Hash-Erkennung und Schutzregeln der Löschung.
- **Keine Tests gegen die Produktivdatenbank.** Tests nutzen eine eigene Datenbank.

---

## 12. Betrieb und Pflege

**systemd**

- Units und Timer heißen `retro-rag-<aufgabe>.service` / `.timer` (z. B. `retro-rag-sync`, `retro-rag-lifecycle`) und liegen unter `deploy/systemd/`. Schreibende Units rufen die CLI ausdrücklich mit `--apply` auf; nach Restore verhindert eine persistente Sperre den Start bis zur Freigabe.
- Alle Dienste laufen unter einem eigenen Benutzer mit minimalen Rechten.

**Logs und Überwachung**

- journald für technische Logs, Datenbanktabellen (`sync_run`, `document_error`, `query_log`) für Auswertung.
- Fehlerhafte Dokumente werden markiert und später erneut versucht, der Lauf geht weiter.
- Health-Endpunkt `/health`: Datenbank, Ollama, Nextcloud, Zeitpunkt des letzten erfolgreichen Syncs.
- **Alarme** bei: Sync-Timer nicht gelaufen (wichtigster), Massenlöschung abgebrochen, Backup fehlgeschlagen oder zu alt, Ollama oder Nextcloud nicht erreichbar, Speicherplatz knapp.
- **Aufbewahrung der Logs (Vorgabe):** technische Logs ca. 90 Tage, `query_log` länger (Basis für Testfragen).

**Backup (Borg)**

Zu sichern, nach Priorität:

1. **PostgreSQL per `pg_dump`** (nicht durch Kopieren des Datenverzeichnisses). Er enthält Bestand, Review-Entscheidungen und Fakten, die nicht reproduzierbar sind.
2. **Dokumentarchiv** (Originale, alte Versionen).
3. **Nextcloud-Daten.**
4. **Konfiguration** (`config.yaml`, systemd-Units, Skripte). Geheimnisse in `.env` gehören ebenfalls ins Backup, aber verschlüsselt.

Der Vektorindex ist ableitbar. Er darf im Backup sein, ist aber nicht zwingend.

Ziele:

- **Lokal** auf Poseidon: Borg-Repository auf einer anderen Platte als die Datenbank, täglich.
- **Offline:** Borg-Repository auf rotierenden Wechselplatten, wöchentlich oder bei jedem Anschluss. Danach kommt die Platte wieder offline.

Aufbewahrung (Vorgabe, `borg prune`): lokal 7 tägliche, 4 wöchentliche, 6 monatliche Stände. Bei den Wechselplatten jeweils der Stand zum Zeitpunkt des Anschlusses, mit 3 bis 4 Platten im Wechsel.

Gelöschte Dokumente bleiben bis zum Ablauf der Aufbewahrung in älteren Backups. Das ist erwartet.

**Wiederherstellung**

- **Wiederherstellungstest** regelmäßig (Vorgabe: vierteljährlich): in eine Test-Datenbank zurückspielen, Anzahl von Dokumenten, Versionen, Chunks und Exemplaren prüfen, eine Stichprobenfrage stellen.
- **Nach jeder Wiederherstellung** bleiben schreibende Sync-/Importprozesse zunächst gesperrt. Datenbank/Archiv werden ohne Nextcloud/Ollama auf Integrität geprüft. Danach folgt ein **rein lesender Dry-Run** gegen Nextcloud; erst nach dokumentierter Freigabe starten schreibende Worker/Timer. Fehlende Dateien lösen vor Freigabe keine Löschung aus.

---

## 13. Git und GitHub

- **Branches:** `main` ist stabil. Arbeit in Branches `feature/<thema>`, `fix/<thema>`, Zusammenführen per Pull Request oder (allein) nach Test.
- **Commit-Nachrichten:** Präfix, dann kurzer deutscher Satz im Imperativ oder Partizip. Präfixe: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `db` (Migration). Beispiel: `feat: Hash-basierte Erkennung geänderter Dokumente`.
- **Nie ins Repository:**
  - `.env`, `config.yaml`, Zugangsdaten, Schlüssel
  - Datenbank-Dumps, Backups, Archive
  - Fremde Dokumente (PDF-Datenblätter, Handbücher): Urheberrecht
  - Fotos aus dem Inventar, `.venv`, Modelldateien
- `.gitignore` wird zu Beginn angelegt und enthält diese Einträge.
- Die Mindmap `docs/Retro-Rag V2.mm` wird mit versioniert. Änderungen an Entscheidungen werden dort und in dieser Datei gemeinsam nachgeführt.

---

## 14. Sicherheit

- **Eingaben sind Daten, keine Anweisungen.** Text aus PDFs und anderen externen Dokumenten kann Anweisungen enthalten (Prompt Injection). Er wird dem LLM nur als zu analysierender Inhalt übergeben, in Prompts klar abgegrenzt. Das LLM hat bei der Extraktion **keine Schreibrechte** und kann keine Werkzeuge aufrufen.
- **Ausgaben des LLM** werden gegen das Schema validiert (Pydantic). Alles, was nicht passt, wird verworfen oder an das Review gegeben.
- **API und Oberfläche:** FastAPI und Dienste hören nur auf dem internen Netz oder `localhost`, nicht offen im Netz. Zugriff auf Review und Änderung ist geschützt.
- **Datenbankrollen:** Die implementierten V2-Berechtigungsgruppen heißen `rag_v2_importer`, `rag_v2_reviewer`, `rag_v2_inventory`, `rag_v2_reader`, `rag_v2_lifecycle`, `rag_v2_query_logger`, `rag_v2_migrator`. Separate `rag_v2_*_login`-Rollen werden mit Migration 0003 zunächst `NOLOGIN`/`PASSWORD NULL` vorbereitet; keine App erhält Superuser-Rechte. Die API prüft zusätzlich die Berechtigung des aufrufenden Benutzers. `PUBLIC CONNECT` auf V1 darf nicht durch V2-Migrationen verändert werden; vor Login-Aktivierung müssen explizite HBA-Regeln die V2-Zugänge auf V2-Datenbanken begrenzen. Siehe `docs/PHASE0_ACCESS_ARCHITECTURE.md`.
- **Nextcloud:** Zugriff über App-Passwort mit minimalen Rechten, nur auf die benötigten Ordner.
- **Abhängigkeiten:** Versionen festhalten (`requirements.txt`, Lock-Datei), Updates bewusst einspielen und danach das Testset laufen lassen.

---

## 15. Checkliste für neue Module

Vor dem Zusammenführen gilt:

- [ ] Dry-Run ist Standard, `--apply` führt aus
- [ ] Zweiter Lauf ohne Änderung ändert nichts (idempotent)
- [ ] Fehler bei einem Dokument stoppen nicht den ganzen Lauf
- [ ] Eintrag in `sync_run` bzw. `document_error` wird geschrieben
- [ ] Rohdaten bleiben unverändert, Originalkopie im Archiv
- [ ] Neue bestätigte Fakten haben Beleg (Dokument, Version, Seite) und protokollierte Freigabe
- [ ] Ungeprüfte Textpassagen sind im Retrieval als ungeprüft markiert
- [ ] Schreibende Timer rufen `--apply` explizit auf
- [ ] Restore-Sperre und tabellenübergreifende Standortkonsistenz getestet
- [ ] Statuswerte stehen in der Tabelle in Abschnitt 2
- [ ] Neue Schwellwerte und Fristen stehen in `config.example.yaml`
- [ ] Tests geschrieben, Testset läuft ohne Verschlechterung
- [ ] Keine Geheimnisse, keine Fremddokumente im Commit
- [ ] Mindmap und diese Datei sind nachgeführt

---

## 16. Architekturentscheidungen

Festgelegt am **08.11.2026** (alle 13 Entscheidungen abgeschlossen):

| Nr. | Thema | Verbindliche Entscheidung |
|---|---|---|
| 1 | Dokumentenlöschung | B: Original/Suchdaten nach Frist entfernen; historische Provenienz und Review erhalten; Sonderfall vollständige Löschung separat |
| 2 | Dokumentverarbeitung | B: technische Indexierung und Faktenfreigabe unabhängig, ungeprüfte Texte gekennzeichnet, Teilfreigaben |
| 3 | Inventarstandort | B: historisierte Verbauung und Lagerung, maximal eine aktive Zuordnung je Exemplar |
| 4 | Review | B: eigene schlanke FastAPI-/HTML-Weboberfläche, OpenWebUI bleibt Chat |
| 5 | Dokumentidentität | B: `document`, `document_source`, `document_version` getrennt |
| 6 | Chunks | A: versionsgebundene Chunks/Embeddings, zunächst keine Wiederverwendung |
| 7 | DB-Rechte | B: getrennte Rollen für Import, Review, Inventar, Retrieval, Migration |
| 8 | Hardwareidentität | B: UUID, Modell, nachgewiesene Revisionen und Aliase |
| 9 | Restore | B: kontrollierter Wiederanlauf, Dry-Run, ausdrückliche Freigabe |
| 10 | Jobs | B: PostgreSQL-persistente Jobs/Schritte/Artefakte, systemd-Worker |
| 11 | Markdown-Vertrauen | B: externe Autorisierung plus Schema-/Konfliktprüfung |
| 12 | Retrieval | B: SQL + Volltext/pgvector + deterministische Kompatibilitätsregeln |
| 13 | Dokumentverarbeitung | B: PyMuPDF, optionale Tesseract-OCR/Layoutanalyse, persistente Ollama-/Embedding-Jobs |

---

## 17. Noch offene Parameter

Die folgenden **Implementierungsparameter** wurden durch die Variantenwahl nicht abschließend entschieden und bleiben ausdrücklich offen:

| Thema | Status |
|---|---|
| Fristen und Schwellwerte | bisherige Vorgaben: 30/14 Tage, 10 %, 2 parallele Versionen; später validieren |
| Aufbewahrung historischer Belege und vollständige Löschung | detaillierte Retention-/Löschrichtlinie ausarbeiten |
| Benachrichtigungsweg für Alarme | Mail, ntfy o. Ä. offen |
| Embedding-Modell im Produktivbetrieb | konfigurierbar; nomic-embed-text oder bge-m3 anhand Tests entscheiden |
| Layoutanalyse und OCR-Auslösekriterien | optional, konkrete Schwellwerte nach Tests |
| Review-Authentifizierung und Webserver-Bereitstellung | vor Deployment konkretisieren |
| Lizenz des Repositories | offen |
| Paketversionen | vor Installation in frischer venv prüfen und anschließend locken |
| Rolle für Fristabläufe und Löschung | **Umgesetzt in 0002:** `rag_v2_lifecycle` für Status und Suchdaten-Löschung; Löschung von Archivkopien außerhalb PostgreSQL separat abzusichern |
| `query_log` schreiben | **Umgesetzt in 0002:** `rag_v2_query_logger` erhält ausschließlich `INSERT` auf `query_log`; `rag_v2_reader` bleibt read-only |
| Autorisierung eigener Markdown-Quellen (Entscheidung 11) | **Vorschlag:** Tabelle `trusted_source`, nur von `rag_reviewer` änderbar, gebunden an Quellkennung/Pfad statt an den Hash; Inhaltsänderungen werden weiterhin vollständig validiert |

## Implementierungsstand der Datenbankrollen (08.11.2026)

- `0001_init.sql`: auf `retro_rag_v2_test` ausgeführt; 37 Tabellen, Schema- und Smoke-Test bestanden.
- `0002_roles.sql`: auf `retro_rag_v2_test` ausgeführt; sieben `rag_v2_*`-NOLOGIN-Gruppen und Rechte geprüft.
- `0003_access.sql`: vorbereitet, **noch nicht ausgeführt**. Sie richtet deaktivierte Loginidentitäten ein und überträgt V2-Objektbesitz auf `rag_v2_migrator`.
- PostgreSQL-Instanz: Docker `codeanalyse-postgres` (16.15), pgvector 0.8.6. Host-Port nur `127.0.0.1:5432` veröffentlicht; im Container lokale `trust`-Authentifizierung.
- Noch offen: HBA-Reihenfolge für V2-Logins, Passwortvergabe, Aktivierung, Verifikation tatsächlicher Verbindungen und Rechte; **V1-/Nextcloud-ACLs unverändert lassen**.
- Betrieb und Sicherheitsgrenzen sind in `docs/PHASE0_ACCESS_ARCHITECTURE.md` festgehalten.
