# Feasibility-Report: Automatisierung der Terrain-Erstellung für die Star-Edit-MCP-Pipeline

> ## ✅ STATUS: Round-Trip-Gate bestanden (2026-06-22)
> Die zentrale load-bearing Annahme (§3/§4) ist **empirisch belegt**: RichChk reicht eine `.scx`
> **section-stabil** durch. Test `tools/terrain_roundtrip_test.py` an `data/maps/base-map.scx`
> (256×256 Jungle): Lesen → unverändert Speichern → Neu-Lesen → **alle 38 CHK-Sections
> positions-genau identisch**, inkl. `ISOM`/`MTXM`/`TILE`/`MASK`/`DIM`/`ERA` **und** der
> Integritäts-Section `VCOD`; Locations/Trigger erhalten.
> - **Caveat 1:** Die Ausgabe-Datei ist kleiner (74.509 vs. 103.346 Bytes) — reine **MPQ-Rekompression**, der CHK-*Inhalt* ist identisch.
> - **Caveat 2 (offen):** Der finale „öffnet in **SCMDraft** + **StarCraft**"-Check ist **manuell** und steht noch aus.
> - Damit ist der **Template-MVP (Ansatz 1)** entriskt; die 5er-Scores für Ansatz 1/2 gelten nun (vorbehaltlich Caveat 2).

## 1. Kernbefund

**Ja, Terrain-Erstellung lässt sich automatisieren — aber „automatisierbar" und „gutes Terrain" sind zwei völlig verschiedene Schwierigkeitsstufen. Die ehrliche Antwort: valides, ladbares, flaches Terrain ist trivial; nahtlos geblendetes, korrekt cliffed/pathbares Editor-Qualitäts-Terrain ist hart.**

Zwei tragende Fakten vorweg, klar ausgesprochen:

**(a) Schreibt RichChk tatsächlich Terrain-Sections? — JA (quellverifiziert).**
Das ist der entscheidende Befund und korrigiert eine verbreitete Annahme. RichChk ist *nicht* auf Logik-Sections beschränkt. Die Basis-Transcoder-Protokoll-Klasse `RichChkSectionTranscoder` definiert sowohl `decode` (Read) *als auch* `encode` (Write) als verpflichtende abstrakte Methoden — Schreibfähigkeit ist also architektonisch garantiert. Es existieren vollwertige Read- *und* Write-Transcoder (low-level Byte `chk_*` + high-level „rich" `rich_*`) für **alle** im Entwurf genannten Terrain-Sections: `DIM` (Dimensionen), `ERA` (Tileset), `MTXM` (die tatsächlich vom Spiel gerenderte Megatile-Karte), `TILE`, `ISOM`, `MASK`, `THG2`, `DD2`.
- `RichDimSection` exponiert `width`/`height`.
- `RichEraSection.tileset` ist ein `StarCraftTileset`-Enum.
- `RichMtxmSection.tiles` ist eine Liste editierbarer `RichTile`-Objekte (mit `id`/`group_index`/`subtile_index`, dekodiert aus dem `u16`) — also echte Tile-Platzierung, keine opaken Bytes. Verifiziert über `rich_mtxm_transcoder.py` (`encode()` baut `DecodedMtxmSection(_tiles=tuple(t.id for t in ...))`).
- **Wichtige Einschränkung bei ISOM (quellverifiziert):** Der `rich_isom_transcoder.py` ist ein reiner **Pass-Through** — wörtlich im Docstring: „Simple pass-through: the rich representation is identical to the decoded one". RichChk kann ISOM-Daten verlustfrei lesen, erhalten, kopieren oder von Hand konstruieren — aber es gibt **keinen** Algorithmus, der ISOM aus MTXM/Brushes *generiert*. Das ist der Knackpunkt (siehe §4).

> Konsequenz: Die Behauptung „Star-Edit braucht eine handgebaute Basiskarte, weil RichChk kein Terrain kann" ist technisch falsch. RichChk *kann* Terrain-Bytes schreiben. **Aber „Bytes schreiben" ≠ „Terrain erzeugen":** RichChk schreibt nur Tile-/ISOM-Daten, die man bereits besitzen muss. Was fehlt, ist nicht die Schreibfähigkeit, sondern die **Terrain-Engine** (die ISOM→Tile-Auflösung), die SCMDraft im Hintergrund leistet.

**(b) Bietet SCMDraft eine CLI/Automatisierung? — NEIN (quellverifiziert: kein Automatisierungspfad).**
SCMDraft 2 hat **keine** offizielle headless/Batch-Automatisierung. Belegt ist nur **ein** Start-Switch: `-profile=` (z. B. `-profile=default`), der lediglich den Profilauswahl-Bildschirm überspringt und trotzdem das GUI-Fenster öffnet. **Achtung (im Entwurf überzogen):** Die zusätzlich behaupteten Switches `-map=` und `-console` sind **nicht quellbelegt** — in den Primärquellen ließ sich kein Nachweis finden (die `-console`-Treffer betrafen StarCraft II, ein anderes Produkt). Sie sind als **unbestätigt** zu behandeln. An der Schlussfolgerung ändert das nichts: Keiner dieser Switches verarbeitet Karten headless. Das Plugin-System (`.sdp`-DLLs) lädt *innerhalb* der laufenden GUI und ist laut API „strictly designed to support TrigEdit" — also auf Trigger-/String-Table-Editierung beschränkt. Es gibt keinen dokumentierten Weg, eine `.scx` ohne manuelle GUI-Interaktion mit SCMDraft selbst zu erzeugen/speichern. Echte programmatische Bearbeitung geht nur über Tools, die SCMDraft komplett umgehen und das CHK-Format direkt schreiben.

**Fazit Kernbefund:** Die Automatisierung scheitert *nicht* an fehlenden Schreib-Tools (RichChk schreibt nachweislich alle Terrain-Bytes) und *nicht* an SCMDraft-CLI (die existiert nicht und wird auch nicht gebraucht). Sie steht und fällt allein damit, **woher die korrekten Tile-/ISOM-Daten kommen** — denn jeder MTXM-`u16` trägt untrennbar Grafik + Walkability + Höhe + Sicht + Bebaubarkeit, und nahtlose Übergänge sind ein Vier-Nachbarn-Constraint-Problem pro Tile gegen tileset-spezifische Regeltabellen. Genau diesen Constraint-Solver kodiert ISOM — und genau den liefert RichChk *nicht*.

---

## 2. Ansätze im Vergleich

Bewertung 1–5 (5 = bestes Ergebnis in der jeweiligen Spalte). „Passung" = Integration in den bestehenden RichChk/Star-Edit-Stack.

**Wichtiger Vorbehalt zu den Bewertungen von Ansatz 1 und 2:** Die hohen Robustheits-/Passungs-Scores setzen voraus, dass RichChk eine von SCMDraft gebaute `.scx` **byte-stabil durchreicht** (inkl. `STR`-Rebuild und nicht-modellierter Sections). Diese Round-Trip-Eigenschaft ist **noch nicht empirisch getestet** (siehe §4). Bis dieser Test bestanden ist, sind die Scores für Ansatz 1/2 als **vorläufig** zu lesen.

| # | Ansatz | Aufwand (5=gering) | Qualität-Terrain | Robustheit | Passung-Stack | Verdict |
|---|---|:---:|:---:|:---:|:---:|---|
| 1 | **Template-/Stamp-Bibliothek**: kuratierte, in SCMDraft vorgebaute Basiskarten (mit korrektem ISOM+TILE+MTXM), die der MCP nur noch auswählt und mit Logik bespielt | 5 | 5 | 5* | 5* | **EMPFEHLUNG (MVP).** Löst das ISOM-Problem, indem es Editor-Qualität von Hand vorproduziert. Geringer Aufwand, höchste Qualität, robust, passt perfekt zum vorhandenen „Terrain durchreichen, Logik schreiben"-Vertrag. Einschränkung: nur endliche Auswahl, kein freies Generieren. *Robustheit/Passung vorbehaltlich Round-Trip-Test (§4). |
| 2 | **Hybrid: Template-Stamping + RichChk-MTXM-Overlay** — vorgebaute Terrain-Bausteine (Plateaus, Rampen, Choke-Stücke) als Tile-Blöcke aus geprüften Karten extrahieren und per RichChk-MTXM zusammensetzen; ISOM aus denselben Quellen mitkopieren | 3 | 4 | 3 | 5* | **STARKE ZWEITWAHL / Ausbaustufe.** Mehr Freiheit als reine Templates, bleibt im Python/RichChk-Stack. Risiko: Block-Ränder müssen sauber zusammenpassen (Edge-Type-Matching), sonst Seams; ISOM-Konsistenz muss mitgepflegt werden. *Passung vorbehaltlich Round-Trip-Test (§4). |
| 3 | **MCP via RichChk auf flaches/„square" Terrain erweitern** — DIM/ERA/MTXM direkt aus einem buildable+walkable Megatile-Group füllen | 4 | 2 | 4 | 5 | **Gut für einfache Fälle.** Trivial valid und ladbar, perfekte Stack-Passung. Aber: kein Blending, keine Cliffs/Rampen, brüchig beim Re-Edit in SCMDraft (stale ISOM überschreibt Tiles). Nur für Interiors/flache Melee-Böden. |
| 4 | **Prozeduraler Generator → CHK (WaveFunctionDiffusion)** — Off-the-shelf-Tool, das laut Beschreibung echtes Terrain in eine `.scx` schreibt (DIM/ERA/MTXM/TILE/ISOM/MASK + MPQ-Packing) | 2 | 4 | 2 | 3 | **Interessant, aber riskant.** Soll „sieht aus wie Melee-Map"-Terrain inkl. ISOM/MASK erzeugen — **dieser Output-Anspruch (gültiges ISOM+MASK) ist hier NICHT verifiziert** (Tool-Source nicht inspiziert); vor Nutzung prüfen. Nachteile: seit 2023 unmaintained, schwere Deps (PyTorch/CUDA, Modell-Download), Output nicht garantiert balanced/spielbar, separater Stack neben RichChk. Output könnte aber als Quelle für Ansatz 1/2 dienen — sofern das ISOM/MASK valide ist. |
| 5 | **Eigener ISOM-Generator in Python** (IsomTerrain-Algorithmus nachbauen: 14 Shapes/Typ, soft/hard Links, terrainTypeMap, Vier-Nachbarn-Matching, radiale Propagation) — danach via RichChk schreiben | 1 | 5 | 4 | 4 | **Höchste Qualität, höchster Aufwand.** Das ist faktisch das Neuimplementieren der SCMDraft-Terrain-Engine. Referenz (`TheNitesWhoSay/IsomTerrain`) ist genau deshalb ein eigenständiges C++-Projekt. Nur sinnvoll als Langzeit-Investition. |
| 6 | **C++-Harness über ChkDraft `MappingCoreLib`** — deterministische, native Terrain-API als Bibliothek einbinden, eigenes CLI-Tool bauen | 2 | 5 | 4 | 2 | **Deterministische Profi-Option.** Vollwertige Terrain-Engine vorhanden, aber kein CLI/Scripting-Entry-Point — man muss C++ bauen und linken. Bricht aus dem Python-Stack aus. Sinnvoll, wenn parametrisches/balanciertes Terrain native gebraucht wird. |
| 7 | **GUI-Automatisierung von SCMDraft** (pywinauto/AutoHotkey: Brush klicken, Save As) | 2 | 3 | 1 | 2 | **LETZTE WAHL — keine Produktionsoption.** Nur „Save As" ist robust automatisierbar; das eigentliche Terrain-Malen läuft über eine custom-gezeichnete Canvas ohne Control-Tree → hardcodierte Koordinaten + Bilderkennung, brüchig gegen Version/Auflösung/DPI/Theme, kein State-Readback, ISOM-Blending macht Klicks semantisch verlustbehaftet, „silently wrong"-Gefahr. |

---

## 3. Empfehlung + MVP

### Empfohlener Pfad: Template-Stamp-Bibliothek (Ansatz 1), ausbaubar Richtung Hybrid (Ansatz 2)

Die Logik dahinter ist direkt aus dem Kernbefund abgeleitet: Das einzige wirklich harte Problem ist die **ISOM→Tile-Auflösung** (Editor-Qualitäts-Blending/Cliffs/Pathing). Statt diesen Solver nachzubauen (Ansatz 5/6) oder fragil zu erklicken (Ansatz 7), **vorproduziert man Editor-Qualität einmal von Hand in SCMDraft** und macht sie wiederverwendbar. RichChk kann die Terrain-Bytes nachweislich schreiben/durchreichen — man muss sie also nur aus geprüften Quellen beziehen.

Das passt exakt zum bestehenden Vertrag der Pipeline: *„Terrain-Stage schreibt Terrain-Sections + minimal valides Scaffold; MCP/RichChk liest die `.scx`, lässt Terrain-Sections unangetastet und schreibt die Logik-Sections."* RichChk reicht nicht-modellierte Sections ohnehin verlustfrei durch — Round-Trip-Korruption wird so vermieden.

**Erster verpflichtender Schritt (Gate vor dem Katalog):** Genau diese Round-Trip-Eigenschaft ist noch unverifiziert (§4). Bevor der Template-Katalog skaliert wird, muss an *einem* Template end-to-end belegt sein, dass RichChk eine SCMDraft-`.scx` byte-stabil durchreicht (inkl. `STR`-Rebuild und nicht-modellierter Sections). Erst nach bestandenem Test gelten die 5er-Scores für Ansatz 1.

### Minimaler erster Schritt (MVP), der sofort integriert und Wert liefert

1. **Round-Trip-Gate zuerst:** Eine einzelne, von Hand in SCMDraft gebaute `.scx` durch RichChk lesen → unverändert zurückschreiben → in SCMDraft und StarCraft öffnen. Bestätigt byte-stabiles Durchreichen (Terrain-Sections + `STR` + nicht-modellierte Sections), bevor in einen Katalog investiert wird.
2. **Template-Katalog anlegen (einmalig, manuell in SCMDraft):** 3–6 saubere Basiskarten in den gängigen Größen/Tilesets bauen — z. B. 64×64 / 128×128 / 256×256 je in Badlands/Jungle, mit korrektem `ISOM`+`TILE`+`MTXM`+`MASK`. Diese als `.scx` ablegen (z. B. `templates\badlands_128.scx`).
3. **MCP-Erweiterung „terrain_select":** Der MCP bekommt einen Schritt, der eine Template-`.scx` anhand von Parametern (Größe, Tileset, ggf. Spielerzahl) auswählt und als Arbeitskopie kopiert. Keine Terrain-Logik im Code — nur Dateiauswahl.
4. **Bestehender Logik-Pfad unverändert:** Star-Edit/RichChk öffnet die Arbeitskopie und schreibt wie gehabt Trigger/Locations/Units/Sound. Terrain-Sections werden durchgereicht.
5. **Verifikation:** Output-`.scx` einmal in SCMDraft öffnen und in StarCraft laden — bestätigt, dass Terrain intakt bleibt und Logik korrekt sitzt.

**Warum das schnell Wert liefert:** Es eliminiert genau den manuellen Schritt, der heute jede Pipeline-Nutzung blockiert (jedes Mal von Hand eine Basiskarte bauen), bei null neuem Terrain-Engine-Risiko. Die Qualität ist per Konstruktion Editor-Niveau — vorbehaltlich des bestandenen Round-Trip-Gates (Schritt 1).

**Erste Ausbaustufe (Ansatz 2):** Sobald der Katalog steht, einzelne geprüfte Bausteine (Plateau-, Rampen-, Choke-Blöcke) per RichChk-MTXM in die Templates einsetzen — mit mitkopiertem ISOM aus derselben Quelle. Das gibt parametrische Variation, ohne den vollen ISOM-Solver zu bauen.

---

## 4. Risiken & offene Fragen

**ISOM-Blending ist der harte Kern — und RichChk löst ihn nicht.**
RichChk schreibt ISOM nur als Pass-Through (quellverifiziert: Docstring „Simple pass-through"). Wer Terrain *generiert* (statt es aus geprüften Quellen zu kopieren), muss ISOM selbst korrekt erzeugen: 14 Shape-Templates pro Terrain-Typ, soft/hard Directional Links (≤48 / >48), eine tileset-spezifische `terrainTypeMap` legaler Übergänge, Vier-Nachbarn-Matching mit radialer Propagation und Variant-Randomisierung. Das ist das Neuimplementieren der Editor-Engine (Referenz: `TheNitesWhoSay/IsomTerrain`, C++). **Offene Frage:** Lohnt sich das je, oder reicht dauerhaft Template+Stamp?

**MTXM-only ist brüchig beim Re-Edit.**
Schreibt man MTXM/TILE ohne passendes ISOM (oder mit stale ISOM) und öffnet die Karte später in SCMDraft, regeneriert jeder isometrische Edit die Tiles aus dem (falschen/leeren) ISOM und **überschreibt das handplatzierte Terrain**. Konsequenz: **immer ISOM + TILE + MTXM konsistent zusammen schreiben** — was im Template-Ansatz automatisch erfüllt ist, im reinen RichChk-MTXM-Ansatz (Nr. 3) aber aktiv beachtet werden muss.

**Playability/Pathing/Buildability sind nicht frei wählbar.**
Walkability und Höhe kommen aus VF4, Bebaubarkeit aus CV5-Group-Flags — beides hängt fest am gewählten Megatile-`u16`. Ein Tile kann wie Gras aussehen, aber als unbegehbar geflaggt sein. Naiv zusammengesetztes Terrain (Ansatz 2/3) riskiert: Einheiten laufen durch sichtbare Wände, Gebäude verweigern Platzierung, durchsichtige/exploitbare Cliffs, falscher High-Ground-Vorteil. **Bei Templates (Ansatz 1) ist das gelöst**, weil SCMDraft beim Bauen korrekte VF4/CV5-konsistente Tiles wählt — ein weiteres Argument für den Template-MVP.

**Balance/Spielbarkeit von generiertem Terrain.**
WaveFunctionDiffusion (Ansatz 4) soll „sieht aus wie Melee" erzeugen — nicht garantiert competitive-balanced (Startpositionen, Ressourcenverteilung, faire Chokes). Zusätzlich ist hier **nicht verifiziert**, dass das Tool überhaupt valides ISOM+MASK ausgibt (Source nicht inspiziert) — vor jeder Nutzung zu prüfen. PSMAGE adressiert Balance, ist aber nur ein Paper, kein nutzbares Tool. **Offene Frage:** Welches Qualitätsniveau braucht der Use-Case wirklich — spielbare Sandbox oder turniertaugliche Map?

**MPQ-Packaging / ein Schreiber pro CHK.**
Beide Stages mutieren letztlich eine CHK in einem MPQ via StormLib. Sauberster Vertrag: Terrain-Stage schreibt Terrain-Sections + minimales Scaffold, der MCP/RichChk lässt diese unangetastet und schreibt nur Logik. **Zwei Tools dürfen nicht dieselben Sections überschreiben** — sonst Round-Trip-Korruption. Bei reinem RichChk/Template-Pfad ist das unkritisch (ein Tool, ein Schreiber). Bei WaveFunctionDiffusion + RichChk muss die Section-Ownership strikt getrennt bleiben.

**Tileset-Abhängigkeit der Regeln.**
ISOM-Shapes, Edge-Types und `terrainTypeMap` sind pro Tileset verschieden. Jeder selbstgebaute Generator/Stamp-Mechanismus muss pro Tileset gepflegt werden — ein Katalog pro Tileset (Ashworld, Badlands, Desert, Ice, Jungle, Platform, Twilight, Installation) statt eines universellen Solvers reduziert diesen Aufwand drastisch.

**Offene technische Verifikation (load-bearing):** Ob RichChk eine von SCMDraft gebaute `.scx` wirklich byte-stabil durchreicht (inkl. `STR`-Rebuild und nicht-modellierter Sections), ist die zentrale unbestätigte Annahme, auf der die Empfehlung ruht. Sie muss am konkreten Template einmal end-to-end getestet werden (siehe MVP-Schritt 1), bevor der Katalog skaliert wird. Bis dahin sind die Bewertungen für Ansatz 1/2 vorläufig.

---

### Quellen / Verifikation
- **RichChk (quellverifiziert, master-Branch):** `richchk_section_transcoder.py` (decode+encode Pflicht), `rich_mtxm_transcoder.py` (editierbare `RichTile`), `rich_isom_transcoder.py` (Docstring „Simple pass-through"), Transcoder für `DIM/ERA/MTXM/TILE/ISOM/MASK/THG2/DD2` vorhanden. → https://github.com/sethmachine/richchk
- **SCMDraft (quellverifiziert):** Commands-Seite = nur GUI-Eingaben, kein CLI; einziger belegter Switch `-profile=` (öffnet trotzdem GUI). → http://www.stormcoast-fortress.net/cntt/software/scmdraft/Commands/ , http://staredit.net/topic/6634/ . Plugin-API „strictly designed to support TrigEdit" → http://staredit.net/topic/16514/
- **ISOM-Referenz-Engine:** `TheNitesWhoSay/IsomTerrain` (C++), ChkDraft `MappingCoreLib`.
- **Korrektur aus adversarialer Prüfung:** SCMDraft-Switches `-map=`/`-console` sind **nicht** quellbelegt (nur `-profile=`); Scores für Ansatz 1/2 vorläufig bis Round-Trip-Test bestanden.
