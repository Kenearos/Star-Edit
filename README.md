# Star-Edit — StarCraft-Kampagnen-MCP-Server ("Missions-Baumeister")

> **Status:** Planung / Spezifikation. Dieses Dokument hält den kompletten Auftrag
> fest, bevor Code gebaut wird. Es dient als verbindliche Vorlage für die Umsetzung.

## Ziel in einem Satz

Ein **MCP-Server**, der Claude in die Lage versetzt, aus der Kreativ-Seite einer
StarCraft-Brood-War-Kampagne (Story, Dialoge, Voiceover, Sounds, Missionsablauf)
echte, spielbare `.scm`/`.scx`-Missionsdateien zu bauen — also komplette
Missions-Logik, Texte und Sound-Einbettung.

**Wichtig:** Das **Gelände wird nicht generiert**. Jede Mission startet von einer
vorhandenen Basis-Karte als Leinwand; der Server bearbeitet nur die Daten-/Logik-
Sektionen darin.

## Rollenverteilung

- **Ich (Auftraggeber):** liefere die Kreativ-Seite — Story, Dialoge, Voiceover,
  Sounds, Missionsablauf. Null Programmierkenntnisse. Will am Ende **einen Befehl**
  ausführen und eine **URL** in Claude eintragen.
- **Claude + MCP-Server:** setzt die Kreativ-Vorlage in echte Missionsdateien um.

## Technische Basis

- **Karten-Manipulation:** Python-Bibliothek **RichChk** (PyPI: `richchk`).
  - `pip install richchk` funktioniert; bringt StormLib mit, läuft auf Linux
    (getestet — `StarCraftMpqIoHelper.create_mpq_io()` startet ohne Fehler).
- **Bestätigte Einstiegspunkte** (Signaturen vor dem Coden per Introspektion final
  prüfen, da sie je nach Version leicht abweichen):

  Lesen/Schreiben von Karten (MPQ-Container):
  ```python
  from richchk.io.mpq.starcraft_mpq_io_helper import StarCraftMpqIoHelper
  mpq_io = StarCraftMpqIoHelper.create_mpq_io()
  rich_chk = mpq_io.read_chk_from_mpq("/pfad/map.scx")          # -> RichChk-Modell
  mpq_io.save_chk_to_mpq(rich_chk, "/pfad/basis.scx", "/pfad/out.scx")
  ```

  Bearbeiten:
  ```python
  from richchk.editor.richchk.rich_chk_editor import RichChkEditor
  new_chk = RichChkEditor().replace_chk_section(neue_sektion, rich_chk)
  rich_chk.get_sections_by_name(...)   # vorhandene Sektionen abfragen
  rich_chk.chk_sections                # alle Sektionen
  ```

- **Fertige Editoren** unter `richchk.editor.richchk.*`:
  **trig** (Trigger), **mrgn** (Locations), **unis/unix** (Einheiten-Werte),
  **forc** (Forces/Fraktionen), **ownr** (Owner), **side** (Rassen),
  **swnm** (Switches), **uprp** (Unit Properties), **wav** (Sounds).
- **Rich-Modelle** (Trigger, Conditions, Actions, Locations, …) unter
  `richchk.model.richchk.*`.

**Herzstück = Trigger.** Fast die gesamte Kampagnen-Logik wird über Trigger
abgebildet: Gegnerwellen, Verstärkungen, Einheiten spawnen, Story-Text einblenden,
Funksprüche mit Portrait, WAV-Sounds abspielen, Missionsziele, Sieg/Niederlage,
Timer, AI-Skripte starten. Das Trigger-Tool muss ausdrucksstark und gut
dokumentiert sein (unterstützte Condition-/Action-Typen in der Tool-Beschreibung).

### Erster Arbeitsschritt (vor dem Tool-Coding)

1. `richchk` installieren.
2. README/Quellen des GitHub-Repos "richchk" lesen.
3. Installiertes Paket per Introspektion inspizieren, um die echten Klassen für
   Trigger (Conditions/Actions), Locations, Forces etc. zu lernen.
4. **Keine erratenen Methodennamen** schreiben.

## Stack & Architektur

| Aspekt        | Wahl |
|---------------|------|
| Sprache       | Python 3.12 |
| MCP-Framework | FastMCP (offizielles `mcp`-SDK, `pip install "mcp[cli]"`) |
| Transport     | stdio (lokaler Test) + **Streamable HTTP** (Dauerbetrieb VPS) |
| Betrieb       | Docker-Container, eingebunden ins bestehende docker-compose Setup |
| Reverse-Proxy | Caddy (läuft bereits) → TLS-Subdomain, z.B. `sc-mcp.pixel-by-design.de` |
| Karten-Volume | gemountetes Volume (z.B. `/data/maps`) für Basis-Karten, WAVs, Missionen |

## Tools (Prefix `sc_`)

| Tool | Zweck | Hints |
|------|-------|-------|
| `sc_list_maps` | listet `.scm`/`.scx`-Dateien im Karten-Verzeichnis | readOnly |
| `sc_describe_map` | menschenlesbare Übersicht: Tileset, Größe, Forces/Player-Setup, Rassen, Locations, Trigger-Zusammenfassung | readOnly |
| `sc_list_locations` | Locations (MRGN) auflisten | readOnly |
| `sc_create_location` | Location anlegen | — |
| `sc_rename_location` | Location umbenennen | — |
| `sc_set_player_setup` | Forces (forc), Owner (ownr), Rassen (side) setzen | — |
| `sc_add_trigger` | **Kern-Tool.** Trigger mit Conditions + Actions + betroffenen Playern hinzufügen | — |
| `sc_list_triggers` | Trigger auflisten | readOnly |
| `sc_remove_trigger` | einzelnen Trigger entfernen | destructive |
| `sc_clear_triggers` | alle Trigger entfernen | destructive |
| `sc_embed_wav` | WAV-Datei einbetten und referenzierbar machen (wav-Editor) | — |
| `sc_save_map` | bearbeitetes Modell als neue `.scm`/`.scx` schreiben (`save_chk_to_mpq`, Basis-Karte als Vorlage) | — |
| `sc_set_briefing` | **optional / experimentell.** Mission-Briefing (MBRF). Falls kein High-Level-Editor: als TODO markieren, kein Blocker | — |

### `sc_add_trigger` — Mindest-Abdeckung

Strukturierte Eingabe (Liste von Conditions, Liste von Actions, betroffene Player).
Muss u.a. abdecken:
- Einheiten erzeugen an Location
- Text einblenden (Display Text Message)
- Transmission mit Portrait + WAV
- Play WAV
- Sieg-/Niederlagebedingungen
- Timer
- AI-Skript ausführen

### Anforderungen pro Tool

- Klare Beschreibung.
- Sinnvolle **Pydantic**-Eingabeschemas mit Feldbeschreibungen.
- Hilfreiche Fehlermeldungen, z.B.
  `"Location 'Basis' existiert nicht – verfügbar: …"`.
- `readOnlyHint`/`destructiveHint`-Annotationen passend gesetzt.

## Definition of Done — Selbsttest

Ein kurzer Selbsttest beweist die ganze Pipeline:

1. Basis-Karte aus `/data/maps` laden.
2. Eine Location anlegen.
3. Per Trigger hinzufügen: bei Spielstart eine Texteinblendung
   `"Mission 1 – Start"` **und** das Erzeugen von ein paar Einheiten an der Location.
4. Als neue `.scx` speichern.
5. Neue Datei erneut laden und bestätigen, dass Trigger + Location wirklich drin sind.

Läuft das durch, steht das Fundament.

## Liefergegenstände

- [ ] Server läuft als Docker-Service, erreichbar über die TLS-Subdomain.
- [ ] **Ein** Start-/Neustart-Befehl.
- [ ] Die Connector-URL für Claude (Custom Connector).
- [ ] Beispiel-Basis-Karte liegt bereits in `/data/maps`.
- [ ] `README.md` mit Startbefehl, Subdomain-URL und Anleitung für den Custom
      Connector in Claude.

## Defaults / Entscheidungen

> Hier werden während der Umsetzung die getroffenen Default-Entscheidungen
> dokumentiert, damit am Ende klar ist, was gewählt wurde (keine technischen
> Rückfragen, wo selbst entscheidbar).

- _(wird ergänzt)_

## Offene TODOs

- [ ] `richchk` installieren & per Introspektion echte Klassen verifizieren.
- [ ] Projektstruktur (FastMCP-Server, Pydantic-Schemas, Tool-Module) anlegen.
- [ ] Self-Test-Skript schreiben.
- [ ] Dockerfile + docker-compose-Service + Caddy-Reverse-Proxy-Eintrag.
- [ ] Beispiel-Basis-Karte bereitstellen.
- [ ] `sc_set_briefing` (MBRF) als best-effort prüfen.
