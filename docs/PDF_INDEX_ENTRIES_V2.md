# PDF-Index-Semantik V2 – Review-first (Stand 11.11.2026)

## Ausgangslage und V1-Bezug

Die V2-Spaltenlesereihenfolge für USB 2.0, PDF-Seiten 601 und 606,
ist anhand der Originalseiten und Quellzeilen geprüft. Aus V1 existieren:

- `scripts/chunk_quality.py`: Indexseiten-Klassifikation (noch **keine** Indexeintrags-Semantik).
- `experiments/pdf_span_groups.py`: konservative Nachbar- und
  Fragmentgruppierung aus Abbildungsbeschriftungen; kein fertiger
  Alphabetindex-Parser.
- `experiments/pdf_structure_v02.py`: unveränderte Quellartefakte,
  getrennte Reviewentscheidungen und Provenienz.
- `experiments/pdf_structural_chunk_preview_v02.py`: exakte
  Textrekonstruktion bei vorgeschlagenen Strukturchunks.

Der neue Adapter übernimmt **die Schutzprinzipien**, nicht die für
Bildbeschriftungen ungeeignete V1-Gruppierungsfunktion 1:1.

## Implementierung

`experiments/pdf_index_entries_v2.py` liest **nur bereits erzeugte**
`pdf_column_order_v2.py`-JSONs; kein Nextcloud-/PDF-Zugriff,
keine Datenbank und keine Gewichte. Er verweigert:

- freigegebene/unbekannte Eingaben;
- falsches Quelltext-Hash- oder Textextraktionsprofil;
- doppelte oder verlorene Quellzeilen-IDs;
- nicht reproduzierbare `proposed_text`-Reihenfolge;
- fehlende zwei Spalten, falsche Seitenfolge oder PDF-SHA-256-Differenzen;
- Überschreiben vorhandener Ergebnisse.

Einrückung wird relativ zum linken Textrand **je Spalte/Seite**
ausgewertet; Kandidaten sind `headword`, `subentry`,
`deep_subentry` und `uncertain`. Tiefe Einrückungen werden
**nicht automatisch als Zeilenumbruch behandelt**: Ein `wrap` wird
nur vorgeschlagen, wenn auch ein positives Textmuster vorliegt
(z. B. vorherige Zeile endet mit Komma oder unvollständiger
Ausdruck mit nachfolgendem Kapitelverweis). Unsichere
`deep_subentry`-Zeilen erzeugen `DEEP_INDENT_REVIEW`.

Ein expliziter Marker `(continued)` darf auf einen **eindeutigen**
vorherigen Haupteintrag verweisen, wenn dieser innerhalb derselben
oder unmittelbar vorherigen PDF-Seite liegt. Das Ergebnis
`continuation_of` ist lediglich eine **zu bestätigende Beziehung**;
bei fehlendem/mehrdeutigem Partner entsteht
`UNRESOLVED_CONTINUATION`. Ein fehlender Zwischen-Seitenkontext
wird nicht erraten. Kapitelverweise werden als
`reference_candidates` erfasst, **nicht** bereits zu
verifizierten Ankerzielen aufgelöst.

Jeder Eintrag enthält die Quellzeilen-IDs, Originaltextfragmente,
Spalte, PDF-Seite, typisierte Rollen- und Parent-Vorschläge.
Alle Einträge bleiben `REVIEW_REQUIRED`, `approved=false`.
Nicht semantisch indexierte Kopfzeilen, Seitenzahlen und
Abschnittsüberschriften bleiben vollständig im **Eingabeartefakt**,
nicht in der Kandidatenliste.

## Testen auf Poseidon

```bash
cd ~/projects/retro-rag_v2
git pull --ff-only
source .venv/bin/activate

python -m pytest -q tests/test_pdf_index_entries_v2.py
python -m ruff check experiments/pdf_index_entries_v2.py tests/test_pdf_index_entries_v2.py
```

### Schreiberfreier Realtest USB 601 und 606

```bash
python experiments/pdf_index_entries_v2.py \
  --page-json /tmp/retro-v2-usb-column-order-structure-p601.json \
  --page-json /tmp/retro-v2-usb-column-order-structure-p606.json \
  --out /tmp/retro-v2-usb-index-entries-v01.json
```

Für eine übersichtliche lokale Inspektion:

```bash
python - <<'PY'
import json
from collections import Counter
p = '/tmp/retro-v2-usb-index-entries-v01.json'
r = json.load(open(p, encoding='utf-8'))
print('Quellzeilen:', r['source_line_count'])
print('Indexzeilen:', r['indexed_line_count'])
print('Eintragstypen:', Counter(e['kind'] for e in r['entries']))
print('Review-Fälle:', Counter(f['code'] for f in r['review_findings']))
for entry in r['entries']:
    if 'clock model' in ' '.join(entry['text_parts']).casefold():
        print(entry['entry_id'], entry['text_parts'],
              'continuation_of=', entry['continuation_of'])
PY
```

Wichtig: Die Liste `entries` enthält **nur die den Indexspalten
zugeordneten Zeilen**. Alle Originalzeilen bleiben in den
beiden unveränderten Eingabedateien erhalten. Die Referenzen
`source_json_sha256` sichern die verwendeten JSON-Snapshots ab.
Originaltextinhalte und private PDF-Dateien/Seitenbilder
nicht nach GitHub übertragen.

## Validierung und Grenzen

Die lokale Entwicklungsprobe mit den beiden realen USB-JSONs
umfasste 217 Quellzeilen, davon 212 Textspalten-Zeilen,
194 vorgeschlagene Einträge und 9 geometrische
`DEEP_INDENT_REVIEW`-Hinweise. `clock model (continued)` war
dem vorherigen `clock model` derselben PDF-Seite korrekt
als **Vorschlag** zugeordnet. Diese Werte sind noch kein
Poseidon-Test des eingecheckten GitHub-Stands.

Für die korrekte **Semantik** fehlen noch manuelle Goldstandard-
Labels (Eltern/Kind, einzelne Zeilenumbrüche, Verweislängen,
Seitenübergänge), Präzision/Recall-Auswertung und
Rückverknüpfung von Indexzielen mit realen Kapiteln.
Das Index-Modul implementiert **keinen** produktiven Chunker
und keine Retrieval-Gewichtung. V1s `index=0.65` ist nur ein
historischer Vergleichswert, keine V2-Konfiguration.

Das V2-Write-Gate bleibt unverändert geschlossen.


## Reale USB-Quellen erneut geprüft und drei Randfälle korrigiert (11.11.2026)

Die erneut hochgeladenen **originalen Struktur-JSONs** von
`usb_20.pdf` S. 601 und 606 wurden lokal gegen den ersten
Indexadapter ausgewertet. Die Eingaben enthalten 103 + 114 Quellzeilen,
davon 100 + 112 Indexspalten-Zeilen, 5 getrennt gespeicherte Seitenmöbel/
Überschriften. PDF- und Text-SHA-256 sind konsistent.

**Erste Adapter-Heuristik vor Korrektur** (lokale Analyse,
kein Poseidon-Abnahmelauf):

| Ergebnis | Anzahl |
|---|---:|
| Index-Zeilen | 212 |
| Vorgeschlagene Einträge | 194 |
| `headword` | 63 |
| `subentry` | 122 |
| `deep_subentry` | 9 |
| zusammengeführte Folgezeilen | 18 |
| `DEEP_INDENT_REVIEW` | 9 |

`clock model (continued)` auf S. 606 wird als
`continuation_of=p606-9:11` an `clock model` angebunden.
Die Quellzeile `p601-4:0` enthält dagegen nur den
alphabetischen Abschnittsmarker `A`, **keinen** Haupteintrag.
Das wurde in der ersten Version falsch klassifiziert.

Weitere konkrete Befunde:
- `adding devices. See dynamic insertion and` mit der nächsten,
  tiefer eingerückten Zeile `removal` war irrtümlich in zwei
  Einträge getrennt.
- Unter `addresses → assignment` wurden um etwa 22 pt
  eingerückte dritte Ebenen nicht ihrem unmittelbaren
  Untereintrag, sondern nur `addresses` zugewiesen.
  Die dritte Ebene bleibt aus Sicherheitsgründen grundsätzlich
  prüfpflichtig.
- Implizite Elternbeziehungen dürfen **nicht** von der
  linken auf die rechte Spalte oder von einer Seite auf die nächste
  übertragen werden; dafür existiert ausschließlich der gesonderte
  `(continued)`-Verknüpfungsvorschlag.

**Korrigiert im Feature-Branch:**
1. Einzelne Großbuchstaben werden als `alphabet_section` statt
   `headword` vorgeschlagen; sie erzeugen keinen Elternknoten.
2. Ein Textfragment mit Schlusswort `and` oder `or`
   **ohne bereits enthaltene Kapitelreferenz** kann mit
   der direkt anschließenden tief eingerückten Zeile verbunden werden.
   Quellzeilen und Textteile bleiben getrennt belegt.
3. Tiefe Untereinträge erhalten den vorherigen Untereintrag als
   Elternvorschlag; falls dieser fehlt, wird der Haupteintrag
   ausschließlich mit zusätzlichem `DEEP_PARENT_FALLBACK_REVIEW`
   vorgeschlagen.
4. Implizite Eltern-/Umbruchzustände werden bei jeder neuen
   Spalte zurückgesetzt. Explizite `continued`-Kandidaten werden
   separat über die bereits gesehenen Haupteinträge gesucht.
5. Vier Regressionstests decken die genannten Fälle ab.

**Noch ausstehend:** Die neuen Regeln sind im GitHub-Branch vorhanden,
aber noch nicht auf Poseidon mit pytest/Ruff und den echten JSONs
nachgetestet. Die oben angegebenen Zahlen gelten **für die vorherige
Heuristik**, nicht als Ergebnis dieser Korrektur. Fachliche
Erkennungsqualität benötigt weiterhin manuell bewertete Labels,
insbesondere für tiefe Untereinträge. Write-Gate geschlossen.
