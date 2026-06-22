# Star-Edit MCP — Grounded Research Report für eine SC:BW-Kampagnen-Vorlage

> Geltungsbereich: Der Star-Edit-MCP-Server bearbeitet ausschließlich **Daten/Logik existierender Karten** (Trigger, Texte, Locations, Player-Setup, Sounds). **Kein Terrain-Generieren.** Jede Mission startet von einer bestehenden Basis-Karte in `SC_MAPS_DIR` (Default `/data/maps`). Alle Fähigkeitsaussagen in Abschnitt A sind strikt aus dem Quellcode abgeleitet — autoritativ sind `server.py`, `triggers.py`, `enums.py`, `workspace.py`. Abschnitt B/C/D verknüpfen das mit der SC:BW-Domänenforschung.

---

## A) Was Star-Edit heute wirklich kann

### A.1 Architektur & Session-Modell

- **Server:** `FastMCP("starcraft-campaign-mcp")` mit **13** `sc_`-Tools. Transport per Env `SC_TRANSPORT` (Default `stdio`; Streamable-HTTP-Branch unter `http://0.0.0.0:8000/mcp` vorhanden, server.py:505–511). *(Hinweis: Der oft genannte Docker-Default `http`, die Python-3.12-Laufzeit und konkrete Dependency-Pins wie `richchk==0.1.1`/`mcp[cli]==1.28.0`/`PyYAML>=6.0` lassen sich aus den vier autoritativen Quelldateien `server.py`/`triggers.py`/`enums.py`/`workspace.py` **nicht** verifizieren — sie stammen aus `Dockerfile`/`requirements.txt`, die hier nicht als geprüfte Quelle vorliegen, und sind daher unbestätigt.)*
- **Session = Dateiname.** Es gibt **keinen** Session-Token. Jeder Tool-Call ruft `workspace.open_workspace(map)`; Schlüssel ist `os.path.basename(map)`. Workspaces liegen in einem **prozessweiten Singleton-Dict** (`_WORKSPACES`, lock-geschützt) und leben **so lange wie der Prozess** — kein TTL, keine Per-Client-Isolation. Alle Aufrufer im Prozess teilen sich denselben Workspace pro Karte.
- **In-Memory-Editmodell.** Edits ersetzen ganze CHK-Sektionen (`Workspace.replace(...)`) und akkumulieren auf dem gecachten Workspace. **Nichts wird auf Platte geschrieben außer bei `sc_save_map`.** Edit-Tools liefern `"hinweis": "Aenderung ist im Speicher. Mit sc_save_map persistieren."`
- **Basis-Karte unangetastet.** `sc_save_map` schreibt **immer eine neue Ausgabedatei** (Basis als Template). Aus einer Basis lassen sich viele Missionen erzeugen.
- **Reset/Discard.** `sc_reset_map` → `open_workspace(map, fresh=True)`: liest frisch von Platte, **verwirft alle ungespeicherten Edits**.
- **Pfad-Confinement.** `map_path()` reduziert jeden Namen auf `basename` → kein Ausbrechen aus `SC_MAPS_DIR`. Gilt für Lesen, Speichern und WAV-Quellen.
- **Fehler:** Validierungsfehler werfen (`ValueError`/`FileNotFoundError`/`KeyError`/`FileExistsError`), statt Error-Dicts zurückzugeben.
- **Annotations:** `_READONLY`, `_EDIT`, `_DESTRUCTIVE` (Letzteres: `sc_remove_trigger`, `sc_clear_triggers`, `sc_reset_map`; server.py:352, 379, 463).

### A.2 Die 13 Tools (Signatur + Kernverhalten)

**Read**
| Tool | Parameter | Liefert / Verhalten |
|---|---|---|
| `sc_list_maps` | — | `{maps_dir, count, maps}` aus `workspace.list_maps()` (alle `.scm`/`.scx` in `MAPS_DIR`). |
| `sc_describe_map` | `map` | Überblick: `tileset`, `size{width,height}`, **genau 8** `players` (PLAYER_1..8; fehlend → `"?"`), `forces`, `locations` (Box `[left_x1,top_y1,right_x2,bottom_y2]`), `trigger_count`, `triggers` (Klartext-Summaries), `pending_wav_embeds`. Spiegelt In-Memory-Stand. |
| `sc_list_locations` | `map` | Locations mit `name`/`index`/`box`. |
| `sc_list_triggers` | `map` | `trigger_count` + pro Trigger `index`, `players`, Bedingungs-/Aktions-Summaries. |

**Location**
| Tool | Parameter (Defaults) | Verhalten / Grenzen |
|---|---|---|
| `sc_create_location` | `map`, `name`, `center_x`, `center_y`, `width=96`, `height=96` | `ws.add_location(...)`. Name muss **eindeutig** sein (sonst `ValueError`). Liefert `index` + `box`. Tool-Doku nennt explizit die Konvention „Koordinaten in Pixeln (32 px = 1 Kachel)" (server.py:173–174). |
| `sc_rename_location` | `map`, `old_name`, `new_name` | Umbenennen; wirft bei fehlendem `old_name` oder kollidierendem `new_name`. Kein `hinweis` im Return (server.py:209 liefert `{"ok", "name", "index"}`). |

**Player-Setup**
| Tool | Parameter | Verhalten |
|---|---|---|
| `sc_set_player_setup` | `map`, `players: list[dict]`, `force_names: Optional[list[dict]]=None` | Pro Eintrag `player` **Pflicht** (`KeyError` sonst, server.py:242); `type`/`race`/`force` optional. Setzt OWNR/SIDE/FORC; `force_names` benennt FORCE_1..4 (`force`+`name` Pflicht, server.py:271–272). |

Erlaubte Strings (toleranter Resolver, case-insensitiv, Identifier/Display-Name/Numeric-ID):
- **type (OWNR):** `INACTIVE, COMPUTER_GAME, HUMAN_OCCUPIED, RESCUE_PASSIVE, COMPUTER, HUMAN, NEUTRAL, CLOSED`
- **race (SIDE):** `ZERG, TERRAN, PROTOSS, INDEPENDENT, NEUTRAL, USER_SELECT, RANDOM, INACTIVE`
- **force:** `FORCE_1..FORCE_4`

**Trigger**
| Tool | Parameter (Defaults) | Verhalten / Grenzen |
|---|---|---|
| `sc_add_trigger` | `map`, `players: list[str]`, `conditions: list[Condition]`, `actions: list[Action]`, `preserve=True` | Fügt **genau einen** Trigger an. `players` leer → `ValueError`; jeder Eintrag via `resolve_player`, dedupliziert in `set`. `conditions` leer → **`always`**. `preserve=True` hängt `PreserveTrigger()` an (zählt als Aktion!). Ohne Aktion **und** `preserve=False` → `ValueError`. |
| `sc_remove_trigger` | `map`, `index` | Entfernt Trigger per 0-basiertem Index; Out-of-Range → `ValueError`. |
| `sc_clear_triggers` | `map` | Entfernt **alle** Trigger. Nur per `sc_reset_map` rückholbar. |

**Sound / Save / Reset**
| Tool | Parameter (Defaults) | Verhalten |
|---|---|---|
| `sc_embed_wav` | `map`, `wav_filename` | WAV **muss als Datei in `MAPS_DIR` liegen** (Existenzprüfung `os.path.exists` im Tool, server.py:408). Registriert In-MPQ-Pfad `staredit\wav\<basename>` und queued physisches Einbetten (`pending_wavs`). Liefert `wav_path` (= genau diesen In-MPQ-Pfad) für `play_wav`. Fehlende Datei → `FileNotFoundError` mit Liste verfügbarer `.wav`. |
| `sc_save_map` | `map`, `output_name`, `overwrite=False` | Schreibt neue `.scm`/`.scx`. Endung `.scx` wird **nur** auto-ergänzt, wenn der Name nicht bereits auf `.scx` **oder** `.scm` endet (workspace.py:178–180) → ein angegebenes `.scm` bleibt erhalten. Existiert Ziel & `overwrite=False` → `FileExistsError`. Bettet `pending_wavs` physisch ein. Liefert `output`, `path`, `embedded_wavs`, `triggers`, `locations`. **Leert `pending_wavs` nicht** → erneutes Speichern bettet erneut ein. |
| `sc_reset_map` | `map` | Frisch von Platte; verwirft Edits. |

### A.3 Unterstützte Trigger-CONDITIONS (exakte `type`-Strings)

`type` wird `strip().lower()`-normalisiert. `comparator` Default `AT_LEAST` (`AT_LEAST`/`AT_MOST`/`EXACTLY`; triggers.py:143). `amount` ist bei allen Vergleichs-Conditions effektiv Pflicht (`_require`-geprüft). Alle neun `type`-Strings entsprechen exakt `build_condition` (triggers.py:239–294).

| `type` | Pflichtfelder | Optional | Bedeutung |
|---|---|---|---|
| `always` | — | — | Immer wahr (Default bei leerer Liste). |
| `never` | — | — | Nie wahr (deaktiviert). |
| `elapsed_time` | `seconds` | `comparator` | N Sekunden seit Spielstart. |
| `countdown_timer` | `seconds` | `comparator` | Countdown-Timer-Vergleich. |
| `bring` | `player`,`amount`,`unit`,`location` | `comparator` | N Einheiten eines Typs **an Location**. |
| `command` | `player`,`amount`,`unit` | `comparator` | N Einheiten gesamt (ganze Karte). |
| `kill` | `player`,`amount`,`unit` | `comparator` | N getötete Einheiten. |
| `deaths` | `player`,`amount`,`unit` | `comparator` | N Death-Count eines Unit-Typs. |
| `accumulate` | `player`,`amount`,`resource` | `comparator` | N Ressource (`ORE`/`GAS`/`ORE_AND_GAS`; triggers.py:154–156). |
| `opponents` | `player`,`amount` | `comparator` | N verbleibende Gegner. |

### A.4 Unterstützte Trigger-ACTIONS (exakte `type`-Strings)

`amount` Default `1` (`0` = „Alle" bei Unit-Aktionen; triggers.py:184–186). `modifier` Default `SET_TO` (`SET_TO`/`ADD`/`SUBTRACT`; triggers.py:195–197). Alle `type`-Strings entsprechen exakt `build_action` (triggers.py:305–393).

| `type` | Pflichtfelder | Optional | Bedeutung |
|---|---|---|---|
| `display_text` | `text` | — | Display Text Message. |
| `set_mission_objectives` | `text` | — | Set Mission Objectives (In-Game-Ziele). |
| `play_wav` | `wav_path` | `duration_ms` | Play WAV (`wav_path` = Return von `sc_embed_wav`). |
| `create_unit` | `player`,`unit`,`location` | `amount` | Create Unit. |
| `kill_unit_at_location` | `player`,`unit`,`location` | `amount` | Kill Unit at Location (mit Death-Count). |
| `remove_unit_at_location` | `player`,`unit`,`location` | `amount` | Remove Unit (lautlos). |
| `move_unit` | `player`,`unit`,`location`,`destination` | `amount` | Move Unit (Quelle→Ziel). |
| `give_units` | `player`,`target_player`,`unit`,`location` | `amount` | Give Units to Player. |
| `set_resources` | `player`,`amount`,`resource` | `modifier` | Set Resources. |
| `set_deaths` | `player`,`unit`,`amount` | `modifier` | Set Death Counts (Integer-Variable; Pflichtfelder `player`/`unit`/`amount`, triggers.py:358–364). |
| `set_countdown_timer` | `seconds` | `modifier` | Set Countdown Timer. |
| `pause_timer` / `unpause_timer` | — | — | Timer pausieren/fortsetzen. |
| `run_ai_script` | `ai_script` | — | Run AI Script (ganze Karte). |
| `run_ai_script_at_location` | `ai_script`,`location` | — | Run AI Script at Location (Wellen/Angriffe). |
| `center_view` | `location` | — | Center View (Kamera). |
| `minimap_ping` | `location` | — | Minimap Ping. |
| `set_alliance_status` | `player`,`alliance_status` | — | Set Alliance Status. Werte `ENEMY`/`ALLY`/`ALLIED_VICTORY` stammen aus dem RichChk-Enum `AllianceStatus` (importiert, enums.py:20) und der Docstring (triggers.py:49, 207) — also eine dokumentierte, nicht direkt aus diesen Dateien enumerierbare Angabe. |
| `victory` / `defeat` | — | — | Mission gewonnen/verloren. |

**`ai_script`:** entweder bekannter Name (z. B. `JUNKYARD_DOG`) oder exakt 4-stelliger Rohcode (z. B. `TMCx`). Sonst `ValueError` (triggers.py:220–233).

**Wert-Parsing (`enums.resolve`):** alle `player`/`unit`/`comparator`/`modifier`/`resource`/`alliance_status` akzeptieren Identifier (`TERRAN_MARINE`), Display-Name (`Terran Marine`) oder Numeric-ID (`0`) — case-insensitiv, getrimmt, **exakt** (kein Fuzzy). Der Index mappt Identifier, Display-Name und `str(member.id)` (enums.py:38–40). `player` umfasst u. a. `PLAYER_1..8`, `ALL_PLAYERS`, `FORCE_1..4`, `FOES`, `CURRENT_PLAYER`.

### A.5 WAV-Embedding (zweiphasig)

1. **`sc_embed_wav` (Registrierung):** In-MPQ-Pfad fest = `staredit\wav\<basename>`; registriert String in WAV-Sektion und queued `(disk_path, in_mpq)` in `pending_wavs` (Dedup nach `in_mpq` via `if not any(...)` → gleicher Basename kollidiert, erster Disk-File gewinnt; workspace.py:167–172). **Keine Existenzprüfung der Bytes in `embed_wav` selbst** — die Existenzprüfung liegt im Tool (`os.path.exists`, server.py:408).
2. **`sc_save_map` (physisch):** kopiert `pending_wavs` per StormLib in die Ausgabe-MPQ und `compact_archive` (workspace.py:192–209). Bis dahin existieren keine Audiobytes, nur der String-Tabelleneintrag.

### A.6 Location-Geometrie

- Die **Arithmetik** verwendet `center_x/y`, `width/height` **roh** als Koordinaten (workspace.py:108–113); es gibt **keine px-pro-Tile-Konstante in der Rechenlogik**. **Die Tool-Doku dokumentiert die Konvention aber explizit:** `sc_create_location` beschreibt „Koordinaten in Pixeln (32 px = 1 Kachel)" und die Parameter sind als „in Pixeln" dokumentiert (server.py:173–174). Der Code ist also **nicht** stumm zur 32-px-Konvention; nur die Geometrie-Rechnung klammert nicht an ein Raster. Tool-Defaults `width=height=96`.
- `half_w = max(1, width//2)`, `half_h = max(1, height//2)`; `left_x1/top_y1 = max(0, center−half)` (auf ≥0 geklammert), `right_x2/bottom_y2 = center+half` (**nicht** nach oben geklammert → kann Kartenrand überschreiten). Ungerade Größen schrumpfen durch Integer-Division.
- **Location-Namen: exakt, case-sensitiv** (kein toleranter Resolver, anders als Enums — `resolve_location` nutzt schlichte Dict-Membership `if name in self.locations`, workspace.py:87). Wirft bei Fehlschlag mit Liste verfügbarer Namen. Trigger, die Locations referenzieren, brauchen diese **vorher**.

### A.7 Verifizierte Ende-zu-Ende-Pipeline (selftest)

`sc_list_maps → sc_create_location → sc_add_trigger (display_text + create_unit, always) → sc_save_map (.scx) → unabhängiges Reload via RichChk` bestätigt, dass Location „Basis" und beide Action-Typen den MPQ-Roundtrip überleben. Das ist der bewiesene Kernpfad. *(Die selftest-Beschreibung ist hier als Domänen-/Beispielpfad referenziert; `selftest.py` zählt nicht zu den vier autoritativen Quelldateien.)*

### A.8 Bemerkenswert / planungsrelevant

- `preserve=True` maskiert den „mind. eine Aktion"-Check (PreserveTrigger zählt; server.py:327–330) → leerer-Aktions-Trigger mit `preserve=True` wird erstellt, ist aber nutzlos.
- 8-Player-Cap in `sc_describe_map` ist hart (`range(8)`, server.py:86); Force-Ops nur FORCE_1..4.
- Workspace-Cache nur nach Basename (workspace.py:225) → zwei gleichnamige Dateien in verschiedenen Verzeichnissen aliasen.
- `sc_save_map` setzt Edits/`pending_wavs` **nicht** zurück (workspace.py:176–210); erneutes Speichern wiederholt das WAV-Embed.
- **Switch-Infrastruktur teilweise vorhanden, aber nicht erreichbar:** Das Enum `SwitchState` und der Resolver `resolve_switch_state` existieren in `enums.py` (Zeilen 23, 94–95). Es ist jedoch **keine** Switch-Condition und **keine** Switch-Action in `build_condition`/`build_action` verdrahtet — Switches sind daher über `sc_add_trigger` **nicht ansprechbar** (siehe C). Korrekt formuliert: das Switch-Enum + Resolver sind im Codebestand vorhanden, nur das Trigger-Wiring fehlt.

---

## B) Was eine vollständige SC:BW-Kampagne braucht

### B.1 Kampagnen-Ebene (campaign-level)

- **Arc-Struktur.** Bewährtes Blizzard-Template: Episode = **7–12 Missionen** (Standalone), Trilogie ≈ **3×10**. Eine Episode = ein Akt mit eigenem Protagonisten, die Missionen verketten zur Saga. Brood War macht Missionen bewusst **strategischer/weniger linear** als Vanilla.
- **Schwierigkeitskurve & Story-Beats.** Klassischer Rhythmus: (1) Tutorial/Helden-only ohne Ökonomie → (2–3) sanfter Base-Build, je 1 Unit-Typ → (Mitte) „Twist"-Mission mit Spezialregeln → (7–9) Eskalation (mehrere Basen, Ally-AI, Timer, defend-then-counter) → (Finale) Set-Piece. Höhere Schwierigkeit fügt **Verhalten** hinzu (mehr Wellen, engere Timer, aggressivere AI), nicht nur HP.
- **Story-Vermittlung.** Tragende Handlung gehört in **gescriptete Szenen** (Briefing/Debrief/Cutscene). In-Mission-Zeilen tragen Flavour + Zielhinweise, nicht den Kernplot.
- **Mission-Verkettung.** `Set Next Scenario` kettet Karten (Kampagnenfortschritt).
- **Globale Konsistenz:** Player/Force-Setup, Rassen-Zuordnung, Ressourcen-Startwerte, Allianzen, Namen/Texte, Audio-Budget über alle Missionen.

### B.2 Missions-Ebene (per-mission)

- **Konzept & Rolle im Arc** (welcher Beat, ein neues Konzept).
- **Objectives:** ein Pflichtziel (treibt `Victory`), explizite `Defeat`-Bedingungen, 0–2 optionale Ziele mit Belohnung; Just-in-time enthüllt.
- **Objective-Surfacing über drei Kanäle:** (1) Briefing-Objective-Box (MBRF), (2) In-Game-Liste via **Set Mission Objectives**, (3) On-Screen via **Display Text** + **Transmission** + **Minimap Ping**/**Center View**.
- **Trigger-Systeme:** Win/Lose-Trigger, Gegner-AI (`Run AI Script (At Location)`), Wellen (`Create Unit`+Timer+Preserve), Helden (`Create Unit With Properties`), **Hyper Triggers** für feine Taktung, **Switches/Death-Counter** als State/Variablen, benannte Locations.
- **Story-Präsentation:** Pre-Mission-**Briefing** (Show Portrait → Speaking Portrait/Transmission → Play WAV → Text → **Wait**), In-Mission-**Transmission** (Talking Portrait + WAV + Text + Center), Cutscenes (Center View + Create/Remove + Transmission + Wait), Debrief-Hook.
- **Polish & Test:** Win- und jeden Lose-Pfad testen; Timing prüfen (keine Wait-Blocks, kein 2-Sekunden-Stottern); günstige Conditions zuerst.

### B.3 Mission-Archetypen (Win/Lose + Trigger-Bedarf)

| # | Archetyp | Win | Lose | Trigger-Bedarf |
|---|---|---|---|---|
| 1 | Destroy-all (Base-Build) | alle Gegner weg | keine Gebäude | `opponents==0` / `command/deaths(enemy)==0` → `victory`; Default „no buildings = defeat" |
| 2 | Defend / Survive-timed | Timer abgelaufen | Schlüsselobjekt zerstört | `set_countdown_timer`; Wellen `create_unit`+`run_ai_script_at_location` (always+preserve); `deaths(protected)≥1`→`defeat` |
| 3 | Escort | VIP an Exit (`bring`) | VIP tot | `bring(VIP,exit)`→`victory`; `deaths(VIP)≥1`→`defeat` |
| 4 | Hero-only / RPG | Ziel erreicht/Target tot | Held tot | kein Base-Build; Create-with-Properties (HP/Invinc); `bring`/`kill`; viel Transmission |
| 5 | Hunt / Find | Target gefunden/getötet | optional Timer/Heldentod | `bring(any,secret)`; `minimap_ping`+`center_view`; Switch „found" |
| 6 | Gather-resources | `accumulate≥X` | Base verloren/Timer | `accumulate`; optional Harass |
| 7 | Rescue / Hold | Allies befreit / Location T s gehalten | Allies sterben | `bring`→`give_units`; Command-the-Most-at-Location über Zeit |
| 8 | Assassination | `deaths(target)≥1` | Armee weg | `deaths`/`kill` auf eindeutiges Target |
| 9 | Puzzle / Spezialregeln | Sequenz fertig | Fehlaktion | Switch-State-Machine; `bring`/`deaths`-Gates |
| 10 | Defend-then-counter (Finale) | Phase 1 überleben → Destroy-all | Base in einer Phase weg | Phasen-Flag (Switch/Timer); AI defensiv→passiv flippen |

---

## C) Gap-Analyse: Kampagnen-Bedarf ↔ Tool-Fähigkeiten

Legende: ✅ direkt unterstützt · 🟉 (Workaround) · ❌ nicht möglich mit den `sc_`-Tools.

| Bedarf (SC:BW-Domäne) | Status | Wie / Workaround / unmöglich |
|---|---|---|
| Karten auflisten/inspizieren | ✅ | `sc_list_maps`, `sc_describe_map`, `sc_list_locations`, `sc_list_triggers`. |
| Locations anlegen/umbenennen | ✅ | `sc_create_location`/`sc_rename_location`. **Achtung:** Geometrie rechnet roh (kein Raster-Clamp), die Tool-Doku nennt aber die Konvention 32 px = 1 Kachel; Namen case-sensitiv & exakt. |
| Player-Typ/Rasse/Force/Force-Namen | ✅ | `sc_set_player_setup` (OWNR/SIDE/FORC). Nur FORCE_1..4; `player`-Key Pflicht. |
| Allianzen setzen | ✅ | Action `set_alliance_status` (`ENEMY`/`ALLY`/`ALLIED_VICTORY`). |
| Ressourcen-Start setzen | ✅ | Action `set_resources` (`SET_TO`/`ADD`/`SUBTRACT`). |
| Win/Lose | ✅ | `victory`/`defeat` + Conditions `opponents`/`command`/`deaths`/`bring`/`accumulate`/`elapsed_time`/`countdown_timer`. |
| In-Game-Ziele | ✅ | Action `set_mission_objectives`. |
| On-Screen-Text | ✅ | Action `display_text`. |
| Einheiten erstellen/töten/entfernen/bewegen/geben | ✅ | `create_unit`,`kill_unit_at_location`,`remove_unit_at_location`,`move_unit`,`give_units`. |
| Wellen / Reinforcements | ✅ | `create_unit` + Timer-Condition + `preserve=True`; Aggression via `run_ai_script_at_location`. |
| Gegner-/Ally-AI | ✅ | `run_ai_script`, `run_ai_script_at_location` (Name oder 4-Char-Code). |
| Timer-Logik | ✅ | `set_countdown_timer`/`pause_timer`/`unpause_timer`/`countdown_timer`/`elapsed_time`. |
| Kamera / Minimap | ✅ | `center_view`, `minimap_ping`. |
| WAV einbetten + abspielen | ✅ | `sc_embed_wav` → `wav_path` → Action `play_wav` (+`duration_ms`); WAV muss vorher in `MAPS_DIR` liegen. Format-Pflege (PCM 16-bit mono 11025 Hz, keine Leerzeichen) liegt beim Autor — Tool prüft nur Existenz. |
| **In-Game-Transmission (Talking Portrait + WAV + Text + Center, getimt)** | 🟉 **Workaround** | **Keine native `transmission`-Action.** Komponieren aus `play_wav` + `display_text` + `center_view` (+`minimap_ping`) — exakt dieser Workaround ist auch in der Docstring dokumentiert (triggers.py:53–56). **Ohne animiertes Portrait und ohne echte synchronisierte Halte-Dauer**: `display_text`/`play_wav` feuern sofort; Synchronisation/„Hold" ist nicht erzwingbar (kein `wait`-Primitiv exponiert). `duration_ms` an `play_wav` steuert nur die WAV-Länge. |
| **Talking Portrait (animiertes Gesicht)** | ❌ | Kein Action-Typ vorhanden. Nicht reproduzierbar mit den `sc_`-Tools. |
| **Pre-Mission-Briefing (MBRF-Sektion)** | ❌ | Tools bearbeiten nur MRGN (Locations), OWNR/SIDE/FORC (Player), TRIG (Trigger), WAV, STR (Force-Namen via RichString) — **keine MBRF-API**. Briefing-Room (Show Portrait/Speaking Portrait/Wait/Objectives-Box) **nicht erstellbar**. Notbehelf: In-Mission-„Intro" zu Spielbeginn via `always`+`display_text`/`play_wav`/`center_view` — kein echter Briefing-Screen. |
| **Switches (256 benannte Booleans, Set/Clear/Toggle/Randomize)** | ❌ | Weder Condition `switch` noch Action `set_switch` in `build_condition`/`build_action` verdrahtet → über `sc_add_trigger` **nicht ansprechbar**, kein Sequencing/OR-Emulation/Randomize über Switches. *(Hinweis zur Genauigkeit: Das Enum `SwitchState` + der Resolver `resolve_switch_state` existieren bereits in `enums.py`:23,94–95 — die Switch-Infrastruktur ist also nicht vollständig abwesend, es fehlt nur das Trigger-Wiring. Praktisch bleibt Switch-Funktionalität dennoch unerreichbar.)* |
| State-Machine / Phasen-Flags / Zähler | 🟉 **Workaround** | Über **Death-Counter** emulierbar: Condition `deaths` (lesen, triggers.py:275–281) + Action `set_deaths` (`SET_TO`/`ADD`/`SUBTRACT`, triggers.py:358–364). Damit Phasen-Flags/Zähler/Timer. Erfordert „Marker"-Unit-Disziplin; kein `switch`-Komfort. |
| **Hyper Triggers (feine Taktung ~12 Hz)** | 🟉 **Workaround/eingeschränkt** | Kein `wait`-Action und kein dedizierter Hyper-Trigger-Helper. Klassische 63×Wait(0)-Konstruktion **nicht baubar**. Engine läuft sonst ~alle 2 s. „Complex Hyper" über Death-Counter-Bedingungen theoretisch nachbaubar, aber umständlich; **flüssige Cutscene-Taktung praktisch nicht erreichbar**. |
| `Wait`-Action (Dramaturgie-Pausen, Sync) | ❌ | Nicht exponiert. Timing nur grob über `elapsed_time`/`countdown_timer`/Death-Counter. |
| **Set Next Scenario (Missionsverkettung)** | ❌ | Kein Action-Typ. Kampagnen-Verkettung **nicht innerhalb der Karte** setzbar; muss extern/manuell gelöst werden. |
| Create Unit **With Properties** (HP/Invinc/Energy/Cloak) | ❌ | Nur schlichtes `create_unit` (Anzahl/Typ/Location, triggers.py:314–320). Helden-Properties nicht setzbar. Teil-Workaround: HP via separate Modify-Action — **auch nicht vorhanden** (kein `modify_unit_hp`). |
| Modify Unit HP/Energy/Shields/Hangar | ❌ | Keine entsprechende Action. |
| Order / Move Location / Set Doodad State / Set Invincibility | ❌ | Nicht exponiert. (Bewegung nur via `move_unit` Teleport.) |
| Leaderboard, Score, Highest/Most/Least-Familie, Kill/Command-the-Most | ❌ | Nicht in den unterstützten Conditions/Actions. |
| Mute/Unmute Unit Speech | ❌ | Nicht vorhanden (Default-Unit-Sounds nicht stummschaltbar). |
| Mehrere Trigger atomar / Reihenfolge garantieren | 🟉 | `sc_add_trigger` fügt je 1 Trigger **ans Ende** an → Reihenfolge = Einfügereihenfolge; bewusst sequenzieren. |
| Terrain / Doodads / Einheiten-Vorplatzierung | ❌ | **Außerhalb des Scopes** — Karten müssen Terrain/Startobjekte bereits enthalten. |

**Kernbotschaft der Gap-Analyse:** Logik-, Einheiten-, Ressourcen-, AI-, Timer-, Sound- und Kamera-Bausteine sind solide abgedeckt. **Vier echte Lücken** prägen das Template-Design: (1) **kein MBRF-Briefing**, (2) **keine native Transmission / kein Talking Portrait**, (3) **keine erreichbaren Switches & keine Hyper/Wait-Taktung** (State nur per Death-Counter, Timing nur grob; Switch-Enum/Resolver existieren zwar in `enums.py`, sind aber nicht an Trigger gebunden), (4) **kein Set Next Scenario / keine Create-with-Properties / Modify-Unit**. Für all diese existieren entweder dokumentierte Workarounds (Transmission-Komposit, Death-Counter-State) oder die Funktion ist mit den `sc_`-Tools **nicht** umsetzbar.

---

## D) Empfohlene Vorlagen-Struktur

Konkrete, tool-verknüpfte Vorlage. Jeder Schritt nennt das exakte `sc_`-Tool und Kern-Parameter. Designprinzip: **alle Edits sammeln, einmal speichern** (Filename = Session). Reihenfolge respektiert Abhängigkeiten (Locations & WAVs **vor** Triggern, die sie referenzieren).

### D.1 Kampagnen-Header (einmal pro Kampagne festlegen)

```
Kampagne: <Titel>
Episode/Akt: <Name>  ·  Geplante Missionen: 7–12 (Standalone) | 3×10 (Trilogie)
Protagonist/Fraktion: <…>  ·  Rasse: TERRAN|ZERG|PROTOSS
Arc-Beats (pro Mission ein Eintrag):
  M1 Tutorial/Helden-only · M2–3 Base-Build · Mitte Twist · 7–9 Eskalation · Finale Set-Piece
Globale Konventionen:
  - Basis-Karten in SC_MAPS_DIR (1 Basis kann mehrere Missionen erzeugen)
  - Player/Force-Schema (PLAYER_1..8, FORCE_1..4) konsistent über alle Missionen
  - Ressourcen-Startwerte, Allianz-Defaults
  - Audio: PCM 16-bit mono 11025 Hz, Dateinamen OHNE Leerzeichen, in MAPS_DIR ablegen
  - Naming: Location-Namen case-sensitiv & exakt; einmal festlegen
  - Location-Koordinaten in Pixeln (Tool-Konvention 32 px = 1 Kachel); Rand beachten (right/bottom nicht geklammert)
WORKAROUND-/LÜCKEN-Hinweise (siehe C):
  - Kein MBRF-Briefing  → Intro als In-Mission-Sequenz (always + display_text/play_wav/center_view)
  - Keine Transmission  → play_wav + display_text + center_view (kein Portrait, kein echter Hold)
  - Keine erreichbaren Switches → State/Phasen über deaths/set_deaths (Marker-Unit-Disziplin)
  - Keine Hyper/Wait    → Timing nur grob via elapsed_time/countdown_timer/Death-Counter
  - Kein Set Next Scenario → Missionsverkettung extern lösen
```

### D.2 Wiederholbarer Per-Mission-Block (Checkliste mit exakten Tool-Calls)

> **Konvention:** `<map>` = Basis-Kartendatei (Session-Key). Erst sammeln, am Ende `sc_save_map`. Bei Fehlversuch `sc_reset_map(<map>)`.

**Schritt 0 — Bestandsaufnahme**
- [ ] `sc_describe_map(map=<map>)` — Tileset, Größe, 8 Player, Forces, Locations, Trigger, `pending_wav_embeds` prüfen.
- [ ] `sc_list_locations(map=<map>)` und `sc_list_triggers(map=<map>)` — vorhandenen Stand erfassen.
- [ ] *(Neustart sauber?)* `sc_clear_triggers(map=<map>)` **nur** wenn die Basis-Trigger ersetzt werden sollen (DESTRUCTIVE; nur per `sc_reset_map` rückholbar).

**Schritt 1 — Player- & Force-Setup**
- [ ] `sc_set_player_setup(map=<map>, players=[{"player":"PLAYER_1","type":"HUMAN","race":"TERRAN","force":"FORCE_1"}, {"player":"PLAYER_2","type":"COMPUTER","race":"ZERG","force":"FORCE_2"}, …], force_names=[{"force":"FORCE_1","name":"<Allianz>"}])`
  - jeder Eintrag braucht `player` (Pflicht); nur FORCE_1..4.

**Schritt 2 — Locations (vor Triggern!)**
- [ ] Pro benötigter Stelle: `sc_create_location(map=<map>, name="<eindeutig>", center_x=<px>, center_y=<px>, width=96, height=96)`
  - Koordinaten in Pixeln (Tool-Konvention 32 px/Tile); `right_x2/bottom_y2` werden nicht geklammert → Kartenrand beachten.
- [ ] Umbenennen falls nötig: `sc_rename_location(map=<map>, old_name=…, new_name=…)`.

**Schritt 3 — Audio (vor `play_wav`-Triggern)**
- [ ] WAV-Datei in `MAPS_DIR` ablegen (PCM 16-bit mono 11025 Hz, kein Leerzeichen im Namen).
- [ ] `sc_embed_wav(map=<map>, wav_filename="<funk1.wav>")` → Rückgabe `wav_path` = `staredit\wav\funk1.wav` notieren.

**Schritt 4 — Mission-Init-Trigger (einmalig zu Spielbeginn)**
- [ ] `sc_add_trigger(map=<map>, players=["ALL_PLAYERS"], conditions=[{"type":"always"}], actions=[`
  `{"type":"set_mission_objectives","text":"<Pflichtziel>"},`
  `{"type":"set_resources","player":"PLAYER_1","resource":"ORE_AND_GAS","amount":<n>,"modifier":"SET_TO"},`
  `{"type":"set_alliance_status","player":"FORCE_2","alliance_status":"ENEMY"},`
  `{"type":"run_ai_script","ai_script":"<SCRIPT_ODER_4CHAR>"},`
  `{"type":"set_countdown_timer","seconds":<n>,"modifier":"SET_TO"},`
  `{"type":"create_unit","player":"PLAYER_1","unit":"TERRAN_MARINE","location":"<Basis>","amount":4},`
  `{"type":"center_view","location":"<Basis>"}], preserve=False)`
  - **`preserve=False`** für einmalige Init (sonst feuert er erneut).

**Schritt 5 — Intro-„Briefing"-Ersatz (Workaround, da kein MBRF)**
- [ ] `sc_add_trigger(map=<map>, players=["PLAYER_1"], conditions=[{"type":"always"}], actions=[`
  `{"type":"center_view","location":"<Szene>"},`
  `{"type":"play_wav","wav_path":"staredit\\wav\\funk1.wav","duration_ms":<ms>},`
  `{"type":"display_text","text":"<Intro-Zeile>"},`
  `{"type":"minimap_ping","location":"<Ziel>"}], preserve=False)`
  - Kein Portrait, keine echte Sync/Hold-Garantie (siehe C). Mehrere kurze Zeilen statt langer Reden.

**Schritt 6 — Objective-/Wellen-/Phasen-Trigger (archetyp-spezifisch)**
- [ ] **Wellen:** `sc_add_trigger(players=["PLAYER_2"], conditions=[{"type":"elapsed_time","seconds":<t>,"comparator":"AT_LEAST"}], actions=[{"type":"create_unit","player":"PLAYER_2","unit":"<Zerg>","location":"<Spawn>","amount":6},{"type":"run_ai_script_at_location","ai_script":"<ATTACK_SCRIPT>","location":"<Ziel>"}], preserve=True)`
- [ ] **Phasen-Flag via Death-Counter** (Switch-Ersatz): zum Setzen `actions=[{"type":"set_deaths","player":"PLAYER_1","unit":"<MARKER_UNIT>","amount":1,"modifier":"SET_TO"}]`; zum Lesen `conditions=[{"type":"deaths","player":"PLAYER_1","unit":"<MARKER_UNIT>","amount":1,"comparator":"AT_LEAST"}]`.
- [ ] **Optionale Ziele:** eigener Trigger, der bei Erfüllung `give_units`/`set_resources` belohnt und `set_mission_objectives` aktualisiert.

**Schritt 7 — Win/Lose (immer explizit, je `preserve=True`)**
- [ ] **Win:** `sc_add_trigger(players=["PLAYER_1"], conditions=[{"type":"opponents","player":"PLAYER_1","amount":0,"comparator":"AT_MOST"}], actions=[{"type":"display_text","text":"Mission erfüllt"},{"type":"victory"}], preserve=True)`
  - Archetyp-Varianten: `bring(VIP,exit)` (Escort), `deaths(target)≥1` (Assassination), `accumulate≥X` (Gather), `countdown_timer≤0`/`elapsed_time` (Survive).
- [ ] **Lose:** `sc_add_trigger(players=["PLAYER_1"], conditions=[{"type":"deaths","player":"PLAYER_1","unit":"<VIP_ODER_KEY_STRUCTURE>","amount":1,"comparator":"AT_LEAST"}], actions=[{"type":"defeat"}], preserve=True)`
  - Plus ggf. Timer-Lose / „no buildings"-Lose.

**Schritt 8 — Kontrolle vor dem Speichern**
- [ ] `sc_list_triggers(map=<map>)` — Reihenfolge, Player, Conditions/Actions gegen den Plan prüfen.
- [ ] `sc_describe_map(map=<map>)` — `pending_wav_embeds` enthält alle erwarteten WAVs? Locations vollständig?
- [ ] Falsch eingefügt? `sc_remove_trigger(map=<map>, index=<i>)` (0-basiert).

**Schritt 9 — Persistieren (eine neue Missionsdatei)**
- [ ] `sc_save_map(map=<map>, output_name="mission<NN>.scx", overwrite=False)`
  - Rückgabe prüfen: `embedded_wavs`, `triggers`, `locations`. Bei `FileExistsError` neuen Namen oder `overwrite=True`.
  - **Hinweis:** Endung `.scx` wird nur ergänzt, wenn der Name nicht schon auf `.scx`/`.scm` endet (ein `.scm` bleibt erhalten). Erneutes `sc_save_map` bettet `pending_wavs` erneut ein und nutzt denselben In-Memory-Stand (kein Reset durch Save).

### D.3 Per-Mission-Designcheck (vor Schritt 9 abhaken)

- [ ] Genau **ein** Pflichtziel → treibt `victory`; Text in `set_mission_objectives`.
- [ ] **Alle Lose-Pfade** verdrahtet (Held/VIP-Tod, Timer, Key-Structure).
- [ ] Gegner-AI gesetzt (`run_ai_script`/`_at_location`), Aggression passend zum Beat.
- [ ] Wellen-Trigger `preserve=True`; Init-Trigger `preserve=False`.
- [ ] Locations für jedes `create_unit`/`move_unit`/`bring`/`center_view` existieren und exakt benannt.
- [ ] WAVs vorab in `MAPS_DIR`, `sc_embed_wav` aufgerufen, `wav_path` in `play_wav` korrekt (`staredit\wav\…`).
- [ ] Bewusst: **kein** echtes Briefing/Transmission/Portrait, **keine erreichbaren** Switches, **keine** Hyper-Taktung — Workarounds dokumentiert eingesetzt.

### D.4 Kampagnen-Abschluss-Checkliste (closeout)

- [ ] Alle Missionen als eigene `.scx`/`.scm` in `MAPS_DIR` gespeichert; Namensschema `mission01..NN` konsistent.
- [ ] Player/Force/Rassen-Schema über alle Missionen identisch (per `sc_describe_map` stichprobenartig gegengeprüft).
- [ ] Audio-Budget gesamt geprüft (WAV-Anzahl/Größe je Karte; PCM-Spec eingehalten).
- [ ] Jede Mission: Win- **und** jeder Lose-Pfad manuell im Spiel getestet (Timing grob, da keine Hyper-Trigger).
- [ ] **Missionsverkettung extern gelöst** (kein `Set Next Scenario` über die Tools) — Reihenfolge/Übergänge dokumentiert.
- [ ] Briefing-Ersatz (In-Mission-Intro) in jeder Mission vorhanden, da MBRF nicht editierbar.
- [ ] Backup der Basis-Karten unverändert (Save erzeugt stets neue Dateien; Basis bleibt Template).
- [ ] Bei Server-Neustart: In-Memory-Workspaces sind weg → finalisierte `.scx` sind die einzige Persistenz.

---

### Quellenbasis
- **Code (autoritativ für A & Fähigkeitsaussagen):** `G:\Claude\Star-Edit\starcraft_mcp\server.py`, `triggers.py`, `enums.py`, `workspace.py`. *(Ergänzend, nicht als autoritativ geprüft: `__init__.py`, `selftest.py`, `requirements.txt`, `Dockerfile` — Aussagen zu Docker-Transport-Default, Python-Version und Dependency-Pins sind aus diesen vier Kerndateien nicht verifizierbar und entsprechend gekennzeichnet.)*
- **Domäne (B/C-Kontext):** StarEdit Network Wiki (Triggers, List of Trigger Conditions/Actions, Mission Briefings, Hyper Triggers, Wait blocks, Death Counters, Wav Files, Scenario.chk), Campaign Creations Tutorials, StarCraft Fandom/Wikipedia (Episodenstruktur), StrategyWiki Walkthrough, RPGClassics Atrium Campaign Editor, PC Gamer (Blizzard-Storytelling).
