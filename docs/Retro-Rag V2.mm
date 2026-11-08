<?xml version='1.0' encoding='utf-8'?>
<map version="freeplane 1.7.0">
  <node TEXT="Retro-Rag V2" FOLDED="false" ID="ID_339258521" CREATED="1794037241869" MODIFIED="1794117632605" STYLE="oval">
    <font SIZE="18" />
    <hook NAME="MapStyle">
      <properties edgeColorConfiguration="#808080ff,#ff0000ff,#0000ffff,#00ff00ff,#ff00ffff,#00ffffff,#7c0000ff,#00007cff,#007c00ff,#7c007cff,#007c7cff,#7c7c00ff" fit_to_viewport="false" />
      <map_styles>
        <stylenode LOCALIZED_TEXT="styles.root_node" STYLE="oval" UNIFORM_SHAPE="true" VGAP_QUANTITY="24.0 pt">
          <font SIZE="24" />
          <stylenode LOCALIZED_TEXT="styles.predefined" POSITION="right" STYLE="bubble">
            <stylenode LOCALIZED_TEXT="default" ICON_SIZE="12.0 pt" COLOR="#000000" STYLE="fork">
              <font NAME="SansSerif" SIZE="10" BOLD="false" ITALIC="false" />
            </stylenode>
            <stylenode LOCALIZED_TEXT="defaultstyle.details" />
            <stylenode LOCALIZED_TEXT="defaultstyle.attributes">
              <font SIZE="9" />
            </stylenode>
            <stylenode LOCALIZED_TEXT="defaultstyle.note" COLOR="#000000" BACKGROUND_COLOR="#ffffff" TEXT_ALIGN="LEFT" />
            <stylenode LOCALIZED_TEXT="defaultstyle.floating">
              <edge STYLE="hide_edge" />
              <cloud COLOR="#f0f0f0" SHAPE="ROUND_RECT" />
            </stylenode>
          </stylenode>
          <stylenode LOCALIZED_TEXT="styles.user-defined" POSITION="right" STYLE="bubble">
            <stylenode LOCALIZED_TEXT="styles.topic" COLOR="#18898b" STYLE="fork">
              <font NAME="Liberation Sans" SIZE="10" BOLD="true" />
            </stylenode>
            <stylenode LOCALIZED_TEXT="styles.subtopic" COLOR="#cc3300" STYLE="fork">
              <font NAME="Liberation Sans" SIZE="10" BOLD="true" />
            </stylenode>
            <stylenode LOCALIZED_TEXT="styles.subsubtopic" COLOR="#669900">
              <font NAME="Liberation Sans" SIZE="10" BOLD="true" />
            </stylenode>
            <stylenode LOCALIZED_TEXT="styles.important">
              <icon BUILTIN="yes" />
            </stylenode>
          </stylenode>
          <stylenode LOCALIZED_TEXT="styles.AutomaticLayout" POSITION="right" STYLE="bubble">
            <stylenode LOCALIZED_TEXT="AutomaticLayout.level.root" COLOR="#000000" STYLE="oval" SHAPE_HORIZONTAL_MARGIN="10.0 pt" SHAPE_VERTICAL_MARGIN="10.0 pt">
              <font SIZE="18" />
            </stylenode>
            <stylenode LOCALIZED_TEXT="AutomaticLayout.level,1" COLOR="#0033ff">
              <font SIZE="16" />
            </stylenode>
            <stylenode LOCALIZED_TEXT="AutomaticLayout.level,2" COLOR="#00b439">
              <font SIZE="14" />
            </stylenode>
            <stylenode LOCALIZED_TEXT="AutomaticLayout.level,3" COLOR="#990000">
              <font SIZE="12" />
            </stylenode>
            <stylenode LOCALIZED_TEXT="AutomaticLayout.level,4" COLOR="#111111">
              <font SIZE="10" />
            </stylenode>
            <stylenode LOCALIZED_TEXT="AutomaticLayout.level,5" />
            <stylenode LOCALIZED_TEXT="AutomaticLayout.level,6" />
            <stylenode LOCALIZED_TEXT="AutomaticLayout.level,7" />
            <stylenode LOCALIZED_TEXT="AutomaticLayout.level,8" />
            <stylenode LOCALIZED_TEXT="AutomaticLayout.level,9" />
            <stylenode LOCALIZED_TEXT="AutomaticLayout.level,10" />
            <stylenode LOCALIZED_TEXT="AutomaticLayout.level,11" />
          </stylenode>
        </stylenode>
      </map_styles>
    </hook>
    <hook NAME="AutomaticEdgeColor" COUNTER="13" RULE="ON_BRANCH_CREATION" />
    <node TEXT="Inventarisierung Hardware" POSITION="right" ID="ID_849404209" CREATED="1794117636993" MODIFIED="1794117647188">
      <edge COLOR="#ff0000" />
      <node TEXT="Stammdaten" ID="ID_1465248488" CREATED="1794125298614" MODIFIED="1794125302354" />
      <node TEXT="Exemplare" ID="ID_639860607" CREATED="1794125304942" MODIFIED="1794125309280" />
      <node TEXT="Menge und Verfügbarkeit" ID="ID_228055407" CREATED="1794125320220" MODIFIED="1794125330713" />
      <node TEXT="Verbauung und System" ID="ID_1073569623" CREATED="1794125349225" MODIFIED="1794125357013" />
      <node TEXT="Fotos und Dokumente" ID="ID_1973407108" CREATED="1794125370927" MODIFIED="1794125377496" />
      <node TEXT="Erfassung" ID="ID_1979308649" CREATED="1794125388155" MODIFIED="1794125391024" />
      <node TEXT="Dublettenerkennung" ID="ID_967134565" CREATED="1794127400288" MODIFIED="1794127406693" />
      <node TEXT="Lagerort" ID="ID_1651438453" CREATED="1794127409685" MODIFIED="1794127414124" />
      <node TEXT="Zustand" ID="ID_1084363440" CREATED="1794127426411" MODIFIED="1794127429099">
        <node TEXT="Vollständigigkeit" ID="ID_1154429891" CREATED="1794127448240" MODIFIED="1794129232019">
          <node TEXT="Vollständig" ID="ID_355781798" CREATED="1794129236016" MODIFIED="1794129241098" />
          <node TEXT="Unvollständig" ID="ID_1552635672" CREATED="1794129242991" MODIFIED="1794129247754" />
        </node>
        <node TEXT="Funktionsfähig" ID="ID_571858495" CREATED="1794127485299" MODIFIED="1794127490769" />
        <node TEXT="Reparaturbedürftig" ID="ID_52840781" CREATED="1794127497609" MODIFIED="1794128313668" />
        <node TEXT="Defekt" ID="ID_862015454" CREATED="1794127509754" MODIFIED="1794127513830" />
        <node TEXT="Ungetestet" ID="ID_1152783013" CREATED="1794129255896" MODIFIED="1794129262475" />
      </node>
      <node TEXT="Inventaränderung nur nach Bestätigung" ID="ID_412591025" CREATED="1794127718314" MODIFIED="1794128321586" />
    </node>
    <node TEXT="Bereitstellen von Referenzwissen" POSITION="left" ID="ID_593526573" CREATED="1794117663387" MODIFIED="1794117683595">
      <edge COLOR="#0000ff" />
      <node TEXT="Schnittstellen" ID="ID_299553686" CREATED="1794125424456" MODIFIED="1794129408013" />
      <node TEXT="Grafik und API" ID="ID_1327774765" CREATED="1794125438960" MODIFIED="1794125444380" />
      <node TEXT="Chipsätze" ID="ID_1170693448" CREATED="1794125458385" MODIFIED="1794125477146" />
      <node TEXT="Software und Treiber" ID="ID_1607054009" CREATED="1794125539470" MODIFIED="1794125547137" />
      <node TEXT="Quellen" ID="ID_1110336226" CREATED="1794125557024" MODIFIED="1794125561423">
        <node TEXT="Manuals" ID="ID_160909934" CREATED="1794125585724" MODIFIED="1794125588838" />
        <node TEXT="Datenblätter" ID="ID_76086646" CREATED="1794125500709" MODIFIED="1794125506194" />
        <node TEXT="Quellenbelege auf Feldebene" ID="ID_1244826844" CREATED="1794127687528" MODIFIED="1794127695671" />
      </node>
      <node TEXT="Aufbereitung" ID="ID_45563716" CREATED="1794125573066" MODIFIED="1794125582509">
        <node TEXT="PDF-Extraktion" ID="ID_28254024" CREATED="1794125605499" MODIFIED="1794125611969" />
        <node TEXT="OCR-Erkennung" ID="ID_83131923" CREATED="1794125614292" MODIFIED="1794125619264" />
      </node>
      <node TEXT="Kompatibilitätswissen" ID="ID_923873901" CREATED="1794125640742" MODIFIED="1794125648291">
        <node TEXT="Hardware-Kompatibilität" ID="ID_750370736" CREATED="1794127907914" MODIFIED="1794127916537" />
        <node TEXT="Standards" ID="ID_22204425" CREATED="1794127927735" MODIFIED="1794129421318" />
        <node TEXT="Softwarekompatibilität" ID="ID_1154218332" CREATED="1794127944828" MODIFIED="1794127952547" />
        <node TEXT="Systemkonfiguration" ID="ID_507610273" CREATED="1794127960897" MODIFIED="1794127969010" />
        <node TEXT="Bekannte Einschränkungen" ID="ID_102569282" CREATED="1794127984493" MODIFIED="1794127992847" />
        <node TEXT="Kompatibilitätsregeln" ID="ID_1420041741" CREATED="1794128003844" MODIFIED="1794128014923" />
        <node TEXT="Nachweise und Tests" ID="ID_1138463643" CREATED="1794128021915" MODIFIED="1794128027507">
          <node TEXT="Extern Belegt (Quelle)" ID="ID_1955189533" CREATED="1794129523050" MODIFIED="1794129552418" />
          <node TEXT="Selbst Belegt" ID="ID_955976917" CREATED="1794129554764" MODIFIED="1794129558820" />
        </node>
      </node>
      <node TEXT="Dokumentversionen" ID="ID_465118401" CREATED="1794127377132" MODIFIED="1794127383081" />
      <node TEXT="Komponentenarten" ID="ID_1339894693" CREATED="1794128754194" MODIFIED="1794129006468">
        <node TEXT="CPU" ID="ID_1561341131" CREATED="1794129013189" MODIFIED="1794129015379" />
        <node TEXT="RAM" ID="ID_235987415" CREATED="1794129019357" MODIFIED="1794129021579" />
        <node TEXT="Mainboard" ID="ID_1897665471" CREATED="1794129023719" MODIFIED="1794129028680" />
        <node TEXT="Festplatten" ID="ID_586366268" CREATED="1794129035130" MODIFIED="1794129041351" />
        <node TEXT="Grafikkarten" ID="ID_239564329" CREATED="1794129044164" MODIFIED="1794129047933" />
        <node TEXT="..." ID="ID_952207450" CREATED="1794129049819" MODIFIED="1794129051750" />
      </node>
    </node>
    <node TEXT="Import und Wissensverarbeitung" POSITION="right" ID="ID_20429477" CREATED="1794117729160" MODIFIED="1794130910600">
      <edge COLOR="#00ff00" />
      <node TEXT="Metadaten der Dokumente" ID="ID_106450758" CREATED="1794119173986" MODIFIED="1794119181922" />
      <node TEXT="Strukturierte Daten statt Fließtext" ID="ID_977265065" CREATED="1794119202402" MODIFIED="1794119223150" />
      <node TEXT="Import- und Reviewpipeline" ID="ID_404399765" CREATED="1794131452139" MODIFIED="1794131463556">
        <node TEXT="Quellenerfassung" ID="ID_1355356640" CREATED="1794131470719" MODIFIED="1794131476150" />
        <node TEXT="Dokumentenprüfung" ID="ID_1077851164" CREATED="1794131484240" MODIFIED="1794131488903" />
        <node TEXT="Inhaltsextraktion" ID="ID_316399518" CREATED="1794131495963" MODIFIED="1794131504982" />
        <node TEXT="Wissensextraktion" ID="ID_1431697333" CREATED="1794131507526" MODIFIED="1794131513387" />
        <node TEXT="Validierung" ID="ID_1000525117" CREATED="1794131528349" MODIFIED="1794131531752" />
        <node TEXT="Review und Freigabe" ID="ID_1461901601" CREATED="1794131538738" MODIFIED="1794131545226" />
        <node TEXT="Übernahme und Indizierung" ID="ID_1183226414" CREATED="1794131555784" MODIFIED="1794131563591" />
        <node TEXT="Fehlerbehandlung" ID="ID_165566776" CREATED="1794131570885" MODIFIED="1794131575806" />
        <node TEXT="Quellenabhängige Verarbeitung" ID="ID_1910036005" CREATED="1794131914115" MODIFIED="1794131924758">
          <node TEXT="Vertrauenswürdige eigene Markdown-Dateien" ID="ID_1863638016" CREATED="1794132036469" MODIFIED="1794132039988" />
          <node TEXT="Externe PDFs und Dokumente" ID="ID_660849272" CREATED="1794132055512" MODIFIED="1794132058133" />
          <node TEXT="Automatische Übernahme bei erfüllten Regeln" ID="ID_1611267889" CREATED="1794132077009" MODIFIED="1794132079865" />
          <node TEXT="Manuelles Review bei externen Extraktionen" ID="ID_375174411" CREATED="1794132093368" MODIFIED="1794132095272" />
          <node TEXT="Eskalation bei Konflikten und Validierungsfehlern" ID="ID_1711743080" CREATED="1794132112816" MODIFIED="1794132115183" />
        </node>
        <node TEXT="Feldbasierte Freigabe" ID="ID_1446701839" CREATED="1794131945186" MODIFIED="1794131952764">
          <node TEXT="Einzelne Fakten annehmen" ID="ID_1522385215" CREATED="1794132129563" MODIFIED="1794132131381" />
          <node TEXT="Einzelne Fakten ablehnen" ID="ID_157553400" CREATED="1794132134876" MODIFIED="1794132149527" />
          <node TEXT="Fakten korrigieren" ID="ID_1695554921" CREATED="1794132168757" MODIFIED="1794132172926" />
          <node TEXT="Unklare Fakten zurückstellen" ID="ID_1512327301" CREATED="1794132186534" MODIFIED="1794132191274" />
          <node ID="ID_583448561" CREATED="1794132204786" MODIFIED="1794132204786">
            <richcontent TYPE="NODE">
              <html>
                <head>
    
  </head>
                <body>
    Teilfreigabe eines Dokuments
  </body>
              </html>
            </richcontent>
          </node>
          <node TEXT="Entscheidungen und Quellen dokumentieren" ID="ID_825802145" CREATED="1794132225815" MODIFIED="1794132228015" />
        </node>
      </node>
    </node>
    <node TEXT="Technik" POSITION="right" ID="ID_1306173885" CREATED="1794117960747" MODIFIED="1794117964938">
      <edge COLOR="#7c0000" />
      <node TEXT="PostgreSQL" ID="ID_116446330" CREATED="1794117976835" MODIFIED="1794117988028" />
      <node TEXT="pgvector" ID="ID_493750478" CREATED="1794117992057" MODIFIED="1794118001227" />
      <node TEXT="Nextcloud" ID="ID_926639319" CREATED="1794118010622" MODIFIED="1794118014575" />
      <node TEXT="KI" ID="ID_99113407" CREATED="1794118028692" MODIFIED="1794118031359">
        <node TEXT="Ollama" ID="ID_1650871076" CREATED="1794118035090" MODIFIED="1794118037344" />
        <node TEXT="Dokumentenlayoutanalyse" ID="ID_1162940415" CREATED="1794118046153" MODIFIED="1794131095818" />
        <node TEXT="LLM für Extraktion" ID="ID_1107235516" CREATED="1794118097943" MODIFIED="1794131072037" />
        <node TEXT="Unsicherheitsbewertung" ID="ID_387562200" CREATED="1794127533816" MODIFIED="1794127540892" />
        <node TEXT="Embedding Modell" ID="ID_1403681673" CREATED="1794126418196" MODIFIED="1794131113887" />
      </node>
      <node TEXT="python" ID="ID_291162901" CREATED="1794118276688" MODIFIED="1794118280165">
        <node TEXT="PyYAML" ID="ID_786020930" CREATED="1794118335976" MODIFIED="1794118345068" />
        <node TEXT="psycopg" ID="ID_1937622129" CREATED="1794118348491" MODIFIED="1794118357570" />
        <node TEXT="fastapi" ID="ID_1944333185" CREATED="1794118360832" MODIFIED="1794118398922" />
        <node TEXT="uvicorn" ID="ID_1833573205" CREATED="1794118401602" MODIFIED="1794118414139" />
        <node TEXT="pymupdf" ID="ID_538382881" CREATED="1794118417393" MODIFIED="1794118438428" />
      </node>
      <node TEXT="OpenWebUI" ID="ID_60225876" CREATED="1794118496190" MODIFIED="1794118502736" />
      <node TEXT="Poseidon (Homelab KI-Server)" ID="ID_1383557556" CREATED="1794125873566" MODIFIED="1794125886470" />
      <node TEXT="Webserver" ID="ID_786884513" CREATED="1794131579183" MODIFIED="1794131583454" />
    </node>
    <node TEXT="Umsetzung" POSITION="left" ID="ID_141858054" CREATED="1794125857183" MODIFIED="1794125862136">
      <edge COLOR="#00007c" />
      <node TEXT="GitHub" ID="ID_1551631475" CREATED="1794125897309" MODIFIED="1794125900942" />
      <node TEXT="Phasen" ID="ID_1090021811" CREATED="1794126100569" MODIFIED="1794126105356">
        <node TEXT="1. Referenzwissen mit Suche" ID="ID_1179760193" CREATED="1794126108836" MODIFIED="1794126133529" />
        <node TEXT="2. Inventarisierung" ID="ID_1796479778" CREATED="1794126137708" MODIFIED="1794126145261" />
        <node TEXT="3. Verknüpfung von Inventar und Referenzwissen" ID="ID_326539067" CREATED="1794128583244" MODIFIED="1794128605662" />
        <node TEXT="0. Architektur, Datenmodell und Importvertrag" ID="ID_1943996937" CREATED="1794131157950" MODIFIED="1794131162865" />
      </node>
    </node>
    <node TEXT="Abfrage / Retrieval" POSITION="left" ID="ID_281456549" CREATED="1794125988215" MODIFIED="1794126014488">
      <edge COLOR="#007c00" />
      <node TEXT="Suchverfahren" ID="ID_1025580189" CREATED="1794126534890" MODIFIED="1794126539476">
        <node TEXT="SQL-Abfragen" ID="ID_313630396" CREATED="1794127590422" MODIFIED="1794127597858" />
        <node TEXT="Vektorsuche" ID="ID_1144528466" CREATED="1794127601569" MODIFIED="1794127607330" />
        <node TEXT="Hybride Suche" ID="ID_601965974" CREATED="1794127814010" MODIFIED="1794127821477" />
      </node>
    </node>
    <node TEXT="Qualität und Tests" POSITION="right" ID="ID_911443005" CREATED="1794126033076" MODIFIED="1794126044009">
      <edge COLOR="#7c007c" />
      <node TEXT="Prüfung auf Halluzinationen" ID="ID_1078873515" CREATED="1794126339486" MODIFIED="1794126349065" />
      <node TEXT="Vergleich von Modellen und Einstellungen" ID="ID_1209348040" CREATED="1794126359770" MODIFIED="1794128721971" />
      <node TEXT="Regressionstest" ID="ID_100163751" CREATED="1794127620183" MODIFIED="1794127625826" />
    </node>
    <node TEXT="Betrieb und Pflege" POSITION="left" ID="ID_1032414184" CREATED="1794126056316" MODIFIED="1794126062686">
      <edge COLOR="#007c7c" />
      <node TEXT="Aktualisierungf bei neuen, geänderten oder gelöschten Dokumenten" ID="ID_1616541287" CREATED="1794126272519" MODIFIED="1794126293355" />
      <node TEXT="Backup" ID="ID_1425903796" CREATED="1794126296596" MODIFIED="1794126300371">
        <node TEXT="Borg-Backup" ID="ID_1625851637" CREATED="1794126376081" MODIFIED="1794126382735">
          <node TEXT="PostgreSQL" ID="ID_678917367" CREATED="1794128092942" MODIFIED="1794128098691" />
          <node TEXT="Projektdaten" ID="ID_993154138" CREATED="1794128101811" MODIFIED="1794128106283" />
          <node TEXT="Nextcloud" ID="ID_1440699930" CREATED="1794128124499" MODIFIED="1794128137188" />
        </node>
      </node>
      <node TEXT="Wiederherstellungstest" ID="ID_705649955" CREATED="1794127638320" MODIFIED="1794127645123" />
      <node TEXT="Dokumentlebenszyklus" ID="ID_1712083756" CREATED="1794130319783" MODIFIED="1794130332692">
        <node TEXT="Versionen und Status" ID="ID_302525248" CREATED="1794130349780" MODIFIED="1794130355483">
          <node TEXT="Aktiv" ID="ID_1302587128" CREATED="1794130365375" MODIFIED="1794130368065" />
          <node TEXT="Ersetzt" ID="ID_996758614" CREATED="1794130370241" MODIFIED="1794130373818" />
          <node TEXT="Archiviert" ID="ID_982020395" CREATED="1794130383632" MODIFIED="1794130388378" />
          <node TEXT="Deaktiviert" ID="ID_933958400" CREATED="1794130390114" MODIFIED="1794130395074" />
          <node TEXT="Entfernt" ID="ID_1908269871" CREATED="1794130408238" MODIFIED="1794130412494" />
        </node>
      </node>
      <node TEXT="Logs und Überwachung" ID="ID_1499927700" CREATED="1794130428341" MODIFIED="1794130435596" />
    </node>
    <node TEXT="Datenmodell" POSITION="right" ID="ID_18345135" CREATED="1794126072686" MODIFIED="1794126077576">
      <edge COLOR="#7c7c00" />
      <node TEXT="Stabile IDs" ID="ID_1809650862" CREATED="1794119237395" MODIFIED="1794119244496" />
      <node TEXT="Dokumenttypen und Beziehungen" ID="ID_1861507928" CREATED="1794126201661" MODIFIED="1794126211838" />
      <node TEXT="Historisierung" ID="ID_1201886606" CREATED="1794127333451" MODIFIED="1794127338363" />
      <node TEXT="Provenienz und Quellenbelege" ID="ID_1270129072" CREATED="1794127348426" MODIFIED="1794127362736" />
      <node TEXT="Verknüpfung über Modellkennung" ID="ID_1165776093" CREATED="1794128634699" MODIFIED="1794128646829" />
    </node>
    <node TEXT="Grundprinzipien" POSITION="left" ID="ID_1458207701" CREATED="1794129631522" MODIFIED="1794130942441">
      <arrowlink SHAPE="CUBIC_CURVE" COLOR="#000000" WIDTH="2" TRANSPARENCY="200" FONT_SIZE="9" FONT_FAMILY="SansSerif" DESTINATION="ID_20429477" STARTINCLINATION="625;0;" ENDINCLINATION="825;206;" STARTARROW="NONE" ENDARROW="DEFAULT" />
      <edge COLOR="#0000ff" />
      <node TEXT="Rohdaten bleiben Original" ID="ID_126780785" CREATED="1794129650244" MODIFIED="1794129671960" />
      <node TEXT="Bestätigung vor Änderung" ID="ID_1836448829" CREATED="1794129687678" MODIFIED="1794129694801" />
      <node TEXT="Strukturierte Daten für Eigenschaften, technische Fakten und Beziehungen." ID="ID_774841589" CREATED="1794129715729" MODIFIED="1794130984235" />
      <node TEXT="Antwort mit Quelle" ID="ID_1755328333" CREATED="1794129748644" MODIFIED="1794129755032" />
      <node TEXT="Fließtext für Erklärungen, Einschränkungen, historische Zusammenhänge und Dokumentkontext." ID="ID_877819230" CREATED="1794131002760" MODIFIED="1794131005881" />
    </node>
    <node TEXT="Architekturentscheidungen (08.11.2026)" FOLDED="false">
      <node TEXT="01 Quellenlöschung / Provenienz">
        <node TEXT="Original und Suchindex nach Frist löschen" />
        <node TEXT="Historische Dokument-ID, Hash, Fundstelle, Belegauszug und Review behalten" />
        <node TEXT="source_unavailable; vollständige Löschung gesondert" />
      </node>
      <node TEXT="02 Verarbeitung / Faktenreview getrennt">
        <node TEXT="Dokument: discovered / processing / indexed / failed" />
        <node TEXT="Fakt: proposed / accepted / rejected / corrected / deferred" />
        <node TEXT="Ungeprüfte Textstellen gekennzeichnet durchsuchbar" />
        <node TEXT="Teilfreigaben ohne Indexblockade" />
      </node>
      <node TEXT="03 Inventar: historische Zuordnungen">
        <node TEXT="installation und storage_assignment mit valid_from / valid_to" />
        <node TEXT="Maximal eine aktive Standortzuordnung über beide Tabellen" />
        <node TEXT="Verbaut / eingelagert / unbekannt; Transaktionssperre" />
      </node>
      <node TEXT="04 Review-Weboberfläche">
        <node TEXT="FastAPI mit schlankem HTML" />
        <node TEXT="Feldreview, Korrektur, Ablehnung, Zurückstellen, Sammelfreigabe" />
        <node TEXT="review_batch / review_item / review_decision" />
        <node TEXT="OpenWebUI bleibt Chat" />
      </node>
      <node TEXT="05 Dokumentidentität">
        <node TEXT="document: stabile UUID" />
        <node TEXT="document_source: Quellkennung / Fundort" />
        <node TEXT="document_version: Hash / Version" />
        <node TEXT="Rename/Move erkennen, Mehrdeutigkeit reviewen" />
      </node>
      <node TEXT="06 Chunks versionsgebunden">
        <node TEXT="Eigene Chunks und Embeddings pro document_version" />
        <node TEXT="Keine versionsübergreifende Deduplizierung in V2" />
        <node TEXT="Embedding-Modell und Dimension protokollieren" />
      </node>
      <node TEXT="07 Datenbankrollen">
        <node TEXT="rag_importer / rag_reviewer / rag_inventory / rag_reader" />
        <node TEXT="Separate Migrationsrolle; least privilege" />
        <node TEXT="Benutzerautorisierung zusätzlich in FastAPI" />
      </node>
      <node TEXT="08 Modell und Revision">
        <node TEXT="article UUID / article_revision / article_alias" />
        <node TEXT="unit optional auf Revision" />
        <node TEXT="model_key nur Such-/Dublettenhinweis" />
        <node TEXT="Kein automatisches Zusammenführen" />
      </node>
      <node TEXT="09 Restore">
        <node TEXT="Borg pg_dump und Archive" />
        <node TEXT="Schreibende Synchronisation nach Restore gesperrt" />
        <node TEXT="Integrität prüfen -&gt; Dry-Run -&gt; ausdrückliche Freigabe" />
        <node TEXT="Restore ohne Nextcloud / Ollama möglich" />
      </node>
      <node TEXT="10 Persistente Jobs">
        <node TEXT="processing_job / processing_step / processing_artifact" />
        <node TEXT="Leases, Retry-Limits, Wiederaufnahme" />
        <node TEXT="systemd Worker; zunächst seriell, kein Redis/Celery" />
      </node>
      <node TEXT="11 Markdown-Vertrauen">
        <node TEXT="Explizite Autorisierung außerhalb Quelldatei" />
        <node TEXT="YAML / Schema / Konfliktprüfung" />
        <node TEXT="Externe Dokumente manuell reviewen" />
        <node TEXT="LLM darf Vertrauen nicht erhöhen" />
      </node>
      <node TEXT="12 Retrieval">
        <node TEXT="SQL Inventar und bestätigte Fakten" />
        <node TEXT="PostgreSQL Volltext + pgvector für Dokumente" />
        <node TEXT="Deterministische Kompatibilitätsregeln" />
        <node TEXT="Quellenstatus und Fundstelle ausgeben" />
      </node>
      <node TEXT="13 Modulare Dokumentverarbeitung">
        <node TEXT="PyMuPDF Standard" />
        <node TEXT="Tesseract OCR optional" />
        <node TEXT="DocLayout-YOLO optional, nicht OCR" />
        <node TEXT="Ollama qwen3.5:4b; qwen3:8b bei Unklarheit" />
        <node TEXT="Embedding-Modell und Dimension konfigurierbar" />
      </node>
      <node TEXT="Offene Implementierungsparameter: Fristen, OCR-Schwellen, Authentifizierung, Alarme, Lizenz, Paketversionen" />
    </node>
  </node>
</map>