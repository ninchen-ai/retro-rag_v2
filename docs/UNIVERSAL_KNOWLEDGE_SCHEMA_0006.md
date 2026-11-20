# Migration 0006 – technischer Entwurf (universeller Wissenskern)

**Status:** ENTWURF, nicht auf Poseidon angewendet; fachliche Ziele 3.0 und Modell 3.1 sind Grundlage.
**Branch:** \`feat/universal-knowledge-schema-0006\`, Basis \`integration/import-pipeline-2026-11-09\`.
**Quelle der Wahrheit:** \`db/migrations/0001_init.sql\` bis \`0005_document_identity.sql\`; vorhandene 37 Tabellen.
**Geltung:** ausschließlich \`retro_rag_v2_test\` bzw. spätere ausdrücklich freigegebene V2-DB. V1 und Nextcloud bleiben unberührt.

## Umfang
- Sechs neue Tabellen: \`entity_type\`, \`knowledge_topic\`, \`knowledge_topic_assignment\`, \`entity_relation\`, \`entity_relation_evidence\`, \`knowledge_proposal\`.
- Ersetzt den hart codierten CHECK auf \`reference_entity.entity_type\` durch einen FK auf einen vorbefüllten, erweiterbaren Typkatalog. Alte Werte bleiben erhalten.
- Neue universelle Beziehungen erhalten \`status\`, optionalen Gültigkeitszeitraum, Kontext und einen deferred Belegpflicht-Trigger.
- Die neue Sicht \`accepted_entity_relation\` zeigt nur bestätigte Beziehungen.
- Themen stehen ausdrücklich neben \`knowledge_subject\` (dieses bleibt Identitätsanker).
- Vorschläge sind unveränderliche Eingangsdatensätze. Herkunft und Eingangsquellen werden gespeichert. Kein \`accepted\`-Status in der Vorschlagstabelle, keine automatische Veröffentlichung.
- \`fact\`, \`property\`, \`evidence\`, \`review_item\` sowie die Hardware- und Dokumenttabellen bleiben in 0006 unverändert.

## Bewusste Grenzen
- Kein freigegebenes universelles Relationstyp-Vokabular; \`relation_type\` wird derzeit nur syntaktisch geprüft. Vor produktiven Freigaben muss ein kontrollierter Katalog/Policy eingebunden werden.
- Die bestehende allgemeine Reader-Rolle hat SELECT auf bestehende Faktentabellen, auch auf Datensätze mit \`status='proposed'\`. Ein späterer sicherer Abfragepfad muss auch dort den bestätigten Status strikt filtern.
- Die Prüfung der Belegpflicht stellt Existenz, nicht die Qualität oder Unabhängigkeit des Belegs sicher.
- \`knowledge_proposal\` ist noch nicht per FK mit \`review_item\` verknüpft. Freigabeprozess, Rule-Versionen, vollständige Auditierung und Ablaufsteuerung sind Folgeschritte.
- Das \`provenance\`-JSON ist in 0006 strukturell, nicht semantisch validiert. Produktionsfreigabe benötigt ein konkretes Schema.
- Der Gate-Trigger verhindert Proposal-INSERT bei geschlossenem Gate. Rollen, die das Gate über ihre Berechtigungen umgehen könnten, dürfen nicht für Agenten eingesetzt werden.
- Die topic-Zyklusprüfung benötigt Transaktionstests einschließlich Parallelität. Advisory Lock ist Teil der Strategie.
- Zum Schutz vor Statusmanipulation sind künftig dedizierte Freigabefunktionen und eingeschränkte UPDATE-Rechte vorzusehen; 0006 implementiert noch keine automatische Freigabe.

## Vor Anwendung
1. Branchdiff und DDL fachlich/technisch prüfen.
2. Aktuellen realen Schema-Snapshot der V2-Test-DB gegen den Migrationsstand 5 abgleichen.
3. Validiertes Backup; Restore-Test separat einplanen.
4. Rolle \`rag_v2_migrator\` und DB-Schutzabfragen prüfen.
5. Erst mit expliziter Ausführungsfreigabe die Migration auf \`retro_rag_v2_test\` testen.

## Prüfartefakte
- \`db/checks/verify_0006.sql\`: strukturelle und zentrale Rechte-Prüfungen (lesend).
- \`db/checks/test_0006_integrity.sql\`: Rollback-basierte Negativtests für Zyklus und geschlossenes Gate.
- Darüber hinaus sind erforderlich: Tests für Belegpflicht und Historisierung von Beziehungen, Parallelität, Zugriffsrollen, bestehende 0001–0005-Invarianten, die Importpipeline und Restore-/Rollback-Szenarien.

**Wichtig:** Ein Commit dieser Dateien ist ausdrücklich kein Nachweis bestandener Integrationstests.
