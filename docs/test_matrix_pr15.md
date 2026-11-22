# Testmatrix – PR #15 (Importpipeline, Retro-RAG V2)

**Status:** Entwurf – vor Freigabe prüfen und kürzen  
**Geltungsbereich:** Technische Abnahme von PR #15 auf Poseidon  
**Umgebung:** Poseidon (PostgreSQL 16, systemd-Worker)

## Regeln für diese Matrix

1. Der Testumfang ist mit Freigabe dieser Datei **eingefroren**. Für die Abnahme von PR #15 gelten nur die hier aufgeführten IDs.
2. Abnahme heißt: ausführen, auswerten, dokumentieren. **Keine neuen Tests schreiben, bestehende Tests nicht ändern oder löschen.**
3. Erkannte Testlücken werden nur im Abschnitt „Vorschläge“ unten notiert und nicht eigenmächtig umgesetzt.
4. Neue Szenarien kommen nur per bewusster Ergänzung hinzu (mit Datum und Begründung im Änderungsprotokoll).
5. Fertig ist die Abnahme, wenn alle Tests mit Priorität M grün sind oder jede Abweichung dokumentiert ist.

**Priorität:** **M** = muss, **S** = sollte, **O** = optional  
**Status:** `offen` / `grün` / `rot` / `entfällt`

## A. Mehrworker (Gleichzeitigkeit)

| ID | Szenario | Erwartetes Verhalten | Prio | Status | Zuordnung (Testdatei/Test) |
| -- | -- | -- | -- | -- | -- |
| A1 | Zwei Worker starten gleichzeitig, ein Job in der Queue | Genau ein Worker übernimmt den Job | M | offen | |
| A2 | Zwei Worker, mehrere Jobs | Jeder Job wird genau einmal verarbeitet, keine Doppelverarbeitung | M | offen | |
| A3 | Zwei Worker, derselbe Dokumenthash wird gleichzeitig eingeliefert | Keine doppelte `document_version`, Dublette wird erkannt | M | offen | |
| A4 | Ein Worker schlägt bei einem Job fehl, der andere läuft weiter | Fehlerisolierung: andere Jobs bleiben unberührt | S | offen | |

## B. Crash und Wiederanlauf

| ID | Szenario | Erwartetes Verhalten | Prio | Status | Zuordnung (Testdatei/Test) |
| -- | -- | -- | -- | -- | -- |
| B1 | Worker wird mitten in einem Schritt (z. B. Extraktion) abgebrochen | Job bleibt in konsistentem Zustand, kein halb aktivierter Index | M | offen | |
| B2 | Neustart nach Abbruch | Fertige Schritte werden wiederverwendet, offener Schritt läuft neu | M | offen | |
| B3 | Abbruch während der Versionsaktivierung | Bisherige Version bleibt aktiv (atomar) | M | offen | |
| B4 | Zwischenergebnis ist ungültig oder beschädigt | Schritt wird neu ausgeführt, kein Weiterverarbeiten mit defekten Daten | S | offen | |
| B5 | Dieselbe Datei wird nach erfolgreichem Lauf erneut eingespielt | Idempotent: keine Duplikate, kein neuer Versionssprung bei gleichem Hash | M | offen | |

## C. Lease (zeitlich begrenzte Job-Sperre)

| ID | Szenario | Erwartetes Verhalten | Prio | Status | Zuordnung (Testdatei/Test) |
| -- | -- | -- | -- | -- | -- |
| C1 | Worker hält gültige Lease | Kein anderer Worker kann den Job übernehmen | M | offen | |
| C2 | Lease läuft ab (Worker tot) | Anderer Worker kann den Job übernehmen | M | offen | |
| C3 | Alter Worker meldet sich nach Ablauf zurück und will schreiben | Seine Schreibzugriffe werden abgewiesen (kein „Zombie-Worker“) | M | offen | |
| C4 | Worker verlängert Lease rechtzeitig | Lease bleibt bestehen, keine Übernahme | S | offen | |

## D. RBAC (getrennte DB-Rollen)

| ID | Szenario | Erwartetes Verhalten | Prio | Status | Zuordnung (Testdatei/Test) |
| -- | -- | -- | -- | -- | -- |
| D1 | Worker-Rolle führt erlaubte Operationen aus | Funktioniert | M | offen | |
| D2 | Worker-Rolle versucht verbotene Operation (z. B. Fakten freigeben, Tabellen ändern) | Wird von der Datenbank abgelehnt | M | offen | |
| D3 | Lese-Rolle (Suche) versucht zu schreiben | Wird abgelehnt | M | offen | |
| D4 | Review-Rolle versucht, Verarbeitungsjobs zu ändern | Wird abgelehnt | S | offen | |

## E. Regression (Bestand darf nicht kaputtgehen)

| ID | Szenario | Erwartetes Verhalten | Prio | Status | Zuordnung (Testdatei/Test) |
| -- | -- | -- | -- | -- | -- |
| E1 | Gesamte vorhandene Testsuite | Alles grün, oder jede Abweichung dokumentiert | M | offen | |
| E2 | Dry-Run ohne `--apply` | Keine Änderungen in DB und Archiv | M | offen | |
| E3 | Dokument wird in anderen Nextcloud-Ordner verschoben | Gleiche Dokumentidentität, kein zweites Dokument | S | offen | |

## Abnahmeprotokoll

| Feld | Wert |
| -- | -- |
| Datum | |
| Commit-Hash | |
| Umgebung | Poseidon |
| Ergebnis gesamt | |
| Abweichungen | |

## Vorschläge (Testlücken, nicht Teil der Abnahme)

*Hier nur eintragen, nicht umsetzen. Umsetzung erst nach bewusster Entscheidung als eigene Aufgabe.*

-

## Änderungsprotokoll

| Datum | Änderung | Begründung |
| -- | -- | -- |
| | Erstfassung (Entwurf) | |
