# Entwurf Migration 0007 – universelle Eigenschaften, Fakten und Nachweise

**Status:** Entwurf, 21.11.2026 – keine SQL-Migration angewendet, keine technische Abnahme.
**Basis:** `integration/import-pipeline-2026-11-09`, Migration 0006, PostgreSQL 16.
**Scope:** A-01 bis A-06, insbesondere A-02/A-03/A-05; A-08 und A-11 bleiben eigene Freigabestufen.

## 1. Verbindliche Invarianten

1. Bestehende Tabellen `rag_v2.property`, `fact`, `evidence`, `fact_evidence`, `knowledge_subject` bleiben die kanonische Basis; kein zweites konkurrierendes Faktensystem.
2. Bestehende UUIDs, Faktwerte, Quellen, Freigabestatus und Belege bleiben erhalten. Keine automatische Konvertierung bestehender Fakten.
3. Neue Werttypen sind additiv: `boolean`, `date`, `timestamp`, `entity_ref`. Bestehende `numeric` und `text` bleiben semantisch unverändert.
4. Ein Fakt besitzt genau **eine** zur Property passende Wertspalte. `entity_ref` verweist über `knowledge_subject(id)`; `timestamp` verwendet `timestamptz` mit eindeutigem Zeitpunkt.
5. Es erfolgen weder neue automatische `accepted`-Entscheidungen noch ein Öffnen des `write_gate`. Agenten schreiben weiterhin nur in den geschützten Vorschlagsbereich, nicht direkt in `fact`.
6. Testdatenbank ausschließlich mit freigegebener, vorbereiteter Sicherung migrieren. V1, Nextcloud und `main` bleiben unverändert.

## 2. Vorhandene Struktur

- `property.value_type` hat CHECK `('numeric','text')` und `canonical_unit` ausschließlich für `numeric`.
- `fact` hat `value_numeric`, `value_text`, `unit_symbol`, `status`, `confidence`, `valid_from`, `valid_to`, `created_at`; ein bestehender CHECK verlangt genau einen Nicht-NULL-Wert aus den bisherigen zwei Wertspalten.
- Der Trigger `validate_fact_value_trigger` prüft die fachliche Zuordnung; `prevent_accepted_fact_rewrite` schützt bestätigte Werte gegen Überschreiben.
- `evidence` hat `evidence_kind = external | self_tested`, externe Dokumentversion und Fundstellen bzw. Selbsttestdatum/-aufbau.
- `fact_evidence` und deferred Belegpflicht bestehen. `knowledge_subject` ist der Identitätsanker.

Vor jeder DDL-Änderung die **vollständigen** bestehenden Funktionen/Constraints der installierten Version aus `pg_get_functiondef`/`pg_get_constraintdef` aufnehmen. Nicht nur die verkürzten Strukturangaben dieses Dokuments verwenden.

## 3. Vorgesehene additive DDL für 0007 (noch nicht ausführbar)

### 3.1 Property-Datentypen

- CHECK auf `property.value_type` kontrolliert erweitern auf `numeric, text, boolean, date, timestamp, entity_ref`.
- Für `entity_ref` optional eine spätere Typ-/Zielbereichseinschränkung je Property modellieren; bis dahin FK und Existenz erzwingen, keine unvalidierte Ziel-ID.
- Eindeutige Festlegung: `date` ohne Zeitzone, `timestamp` als `timestamptz`; Strings niemals implizit in Datumswerte umwandeln.
- `canonical_unit` bleibt nur für `numeric` zulässig, mit entsprechendem CHECK.

### 3.2 Fact-Werte

- Additive nullable Spalten `value_boolean boolean`, `value_date date`, `value_timestamp timestamptz`, `value_subject_id uuid REFERENCES rag_v2.knowledge_subject(id) ON DELETE RESTRICT`.
- Bisherigen `num_nonnulls`-CHECK **in derselben Transaktion** durch einen genau-ein-Wert-CHECK über alle sechs Wertspalten ersetzen.
- Validierungstrigger erweitern: zum `property.value_type` passt ausschließlich die entsprechende befüllte Spalte; nummerische Einheiten nur bei `numeric` und nach bestehenden Regeln.
- `prevent_accepted_fact_rewrite` um alle vier neuen Spalten ergänzen: bestätigte Werte bleiben unveränderlich. Historisierung nur über neue Faktenzeile und Ende der alten Gültigkeit.
- Bestehende Constraints, Belegpflicht, Statusübergänge und Rollen-ACLs gezielt auf Regressionen prüfen; keine heimliche Erweiterung von Reader-Rechten.

### 3.3 Aussagekontext, Zeit und Widerspruch

- **Keine** automatische Eindeutigkeit für `(subject_id, property_id)`: mehrere belegte, kontextuell oder zeitlich unterschiedliche Aussagen sind zulässig.
- Bereits vorhandene `valid_from`/`valid_to` sind Gültigkeitszeit, `created_at` bleibt Erfassungszeit; Quellzeit ist eigenständig zu modellieren (Kandidat: `observed_at timestamptz` auf `fact`, nullable).
- Zeitliche Überlappungen und widersprüchliche Werte sollen zunächst als prüfbare Konflikte behandelt werden, nicht als automatische Überschreibung.
- Einen separaten Policy-/Review-Layer für die Veröffentlichung bestätigter Fakten planen. Eine technisch erfolgreiche Faktenspeicherung ist keine Freigabe.

### 3.4 Provenienz und Nachweise

- Bestehendes `evidence` als verpflichtend referenzierbaren Beleganker erhalten. Dokumentbeleg und Selbsttest bleiben ohne Migration der Bestandswerte gültig.
- Für maschinelle Ableitungen einen separaten, versionierbaren Provenienzdatensatz planen (z. B. `knowledge_derivation` mit `origin_kind`, `model_id`, `prompt_or_profile_version`, `rule_version`, `agent_run_key`, `created_at`) und FK-Verknüpfung mit Fakten **oder** Vorschlägen.
- Eingangsquellen und aufgerufene Prüfregeln nachvollziehbar als referenzielle Zuordnungen halten; JSON nur für ergänzende, versionierte Metadaten, nicht als Ersatz für die Existenz- und Herkunftsprüfung.
- Vor Einführung weiterer `evidence_kind`-Werte unterscheiden, ob Modellableitung ein Beleg oder lediglich Herkunft ist. Empfehlung: Modellableitung **nicht** als eigenständigen Wahrheitsbeleg behandeln.
- Für `accepted` bleiben vorhandene Belegpflicht und spätere deterministische Freigabe-Policy verbindlich. Die reine Anzahl von Belegen beweist nicht deren Qualität.

## 4. Migrationstechnik

1. Auf dem Featurebranch ein tatsächliches `0007_*.sql` erst nach SQL-Review erzeugen; Versionsprüfung verlangt exakt 0006, PostgreSQL 16, korrekte Migratorrolle und Datenbank-Allowlist.
2. `BEGIN`, Advisory Lock, Bestands-/Constraint-Prüfung, additive Änderungen, FK/Trigger-Neudefinition, Versionsmarker 7, `COMMIT`.
3. Vorher `pg_dump -Fc` und **Restore-Probe** in isolierter Testdatenbank; Fehlerfall per Transaktions-Rollback.
4. Eigene `verify_0007.sql`, negative SQL-Tests, Rollen- und Write-Gate-Prüfung; frischer DDL-Snapshot nur nach erfolgreichem Poseidon-Export.
5. Keine `--apply`-Routine und keine Freigabepolicy zusammen mit dieser Strukturmigration aktivieren.

## 5. Abnahmefälle (Mindestumfang)

| ID | Erwartung |
|---|---|
| T-01 | Alle vorhandenen numeric/text-Fakten samt UUID/Status/Belegen unverändert nach Migration |
| T-02 | Jeder neue Typ lässt sich mit korrekter Wertspalte als `proposed` speichern |
| T-03 | Falsche Wertspalte, zwei Werte oder kein Wert werden abgewiesen |
| T-04 | `entity_ref` auf nicht existenten Subject wird abgewiesen; Löschen eines referenzierten Subjects gesperrt |
| T-05 | `date` und `timestamp` sind ohne implizite verlustreiche Konvertierung unterscheidbar |
| T-06 | Änderungen bestätigter Faktenwerte sämtlicher sechs Typen werden abgewiesen |
| T-07 | Belegpflicht, Beleglöschung und historische Fakten bleiben korrekt |
| T-08 | Überlappende/konkurrierende Fakten gehen nicht verloren, keine automatische Akzeptanz |
| T-09 | Reader kann keine ungeprüften Agentenvorschläge als bestätigte Fakten abrufen |
| T-10 | Rollen-/PUBLIC-Rechte und geschlossenes Write-Gate bleiben erhalten |
| T-11 | Wiederholter Migrationslauf wird sicher verweigert; falsche Datenbank/Rolle ebenso |
| T-12 | Backup-Restore und Schemaexport 0007 sind reproduzierbar |

## 6. Noch zu entscheidende Fachdetails

- Ob universelle Property-Definitionen je Entitätstyp eingeschränkt werden oder generell offen bleiben.
- Ob `observed_at` bereits in 0007 enthalten ist und wie Quellzeit vs. Erfassungszeit eindeutig benannt wird.
- Ob Provenienz zuerst ausschließlich für Vorschläge oder zugleich für `fact` persistiert wird.
- Konkrete Freigabe- und Konfliktpolitik bleibt außerhalb von 0007; die Architekturentscheidung „regelabhängig“ wird nicht aufgeweicht.

**Freigabestatus:** Dies ist ein prüfbarer technischer Entwurf, kein SQL-Skript und keine Genehmigung einer Datenbankänderung.
