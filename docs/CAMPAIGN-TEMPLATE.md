# 🛠️ Star-Edit — Kampagnen-Vorlage (Missions-Baumeister)

**So benutzt du diese Datei:** Kopiere sie pro Kampagne (z. B. nach `docs/campaigns/<name>.md`), fülle den **Kampagnen-Header** einmal aus, und dann **dupliziere den Per-Mission-Block** für jede Mission. Jeder Schritt ist eine abhakbare `[ ]`-Checkliste und nennt direkt das `sc_`-Tool + Kern-Parameter — Claude arbeitet sie der Reihe nach ab.

> **Faktenbasis:** Alle Tool-/Trigger-Angaben sind code-abgesichert. Das *Warum* + die vollständige Gap-Analyse (was geht, was nur per Workaround, was gar nicht) steht in [`research/CAMPAIGN-RESEARCH.md`](research/CAMPAIGN-RESEARCH.md). **Lies dort Abschnitt C, bevor du etwas planst, das ein Briefing, ein Talking-Portrait, Switches oder feine Cutscene-Taktung braucht** — das geht mit den aktuellen Tools nicht (siehe „Bekannte Lücken" unten).

---

## ⚙️ Grundregeln (immer gültig)

- **Session = Dateiname.** Alle Edits an einer Karte sammeln sich im Speicher des Servers an; erst `sc_save_map` schreibt eine **neue** Datei. Die Basis-Karte bleibt unangetastet → 1 Basis kann viele Missionen erzeugen.
- **Reihenfolge zählt:** Locations & WAVs **zuerst**, dann die Trigger, die sie referenzieren.
- **Verworfen?** `sc_reset_map(<map>)` lädt frisch von Platte (alle ungespeicherten Edits weg).
- **Koordinaten** in Pixeln (32 px = 1 Kachel). `right/bottom` werden nicht an den Kartenrand geklammert → nicht überlaufen lassen.
- **Location-Namen** sind exakt & case-sensitiv. **Enum-Werte** (Units, Player, Comparator …) sind tolerant: Identifier (`TERRAN_MARINE`), Anzeigename (`Terran Marine`) oder Zahl (`0`).
- **`preserve`**: `True` = Trigger bleibt nach Auslösen (Wellen, Win/Lose). `False` = einmalig (Init, Intro).

---

## 🎨 Asset-Pipeline: woher kommt die Karte? (Vorbedingung)

Star-Edit **generiert kein Terrain**. Jede Mission startet von einer fertigen Basis-Karte. Aktueller Weg:

1. **Terrain in SCMDraft 2** bauen (Map-Größe, Tileset, Terrain, ggf. Start-Doodads/Einheiten) → speichern als `.scx`. *(SCMDraft = `http://www.stormcoast-fortress.net/`)*
2. `.scx` nach `SC_MAPS_DIR` legen (lokal: `G:\Claude\Star-Edit\data\maps\`).
3. Star-Edit fügt die **Logik** hinzu (dieser Vorlage folgend).

> ⚠️ **Caveat 1 — nicht gleichzeitig:** Datei **nie** parallel in SCMDraft offen haben *und* per MCP schreiben. Einer überschreibt den anderen.
> ⚠️ **Caveat 2 — Round-Trip einmal verifizieren:** Bevor du eine ganze Kampagne baust, einmal eine Mini-Mission durch die ganze Pipeline jagen und prüfen, dass die vom Server geschriebene `.scx` **in SCMDraft und im Spiel** sauber lädt. *(Dieser Test ist zugleich das Gate für die Terrain-Automatisierung — siehe unten.)*

### 🚧 Terrain-Automatisierung — wohin die Reise geht

Recherche-Ergebnis (Details: [`research/TERRAIN-AUTOMATION.md`](research/TERRAIN-AUTOMATION.md)):

- **SCMDraft hat keine CLI** → lässt sich nicht sinnvoll fernsteuern (GUI-Klick-Automation = letzte Wahl).
- **RichChk *kann* Terrain-Bytes schreiben** (DIM/ERA/MTXM/TILE/ISOM/MASK), **aber** es generiert kein ISOM (Blending/Cliffs/Pathing) — das ist der harte Kern.
- **Empfohlener Weg (MVP):** **Template-Bibliothek** statt Generator. Einmalig 3–6 saubere Basiskarten von Hand in SCMDraft bauen (je Größe/Tileset, mit korrektem ISOM) → der MCP wählt nur noch aus und kopiert. So entfällt das „jedes Mal Terrain bauen", bei Editor-Qualität und null Engine-Risiko.
- **Gate (programmatisch ✅ bestanden, 2026-06-22):** `tools/terrain_roundtrip_test.py` belegt, dass RichChk eine `.scx` section-stabil durchreicht (alle 38 CHK-Sections inkl. ISOM/VCOD identisch). **Offen:** der manuelle „öffnet in SCMDraft + StarCraft"-Check. Details: [`research/TERRAIN-AUTOMATION.md`](research/TERRAIN-AUTOMATION.md).

→ Bis der Template-Katalog existiert, gilt weiterhin: Basis-Karte manuell in SCMDraft bauen (Schritte 1–3 oben).

---

## 📋 KAMPAGNEN-HEADER (einmal pro Kampagne ausfüllen)

```
Kampagne: ______________________________
Episode/Akt: __________  ·  Geplante Missionen: 7–12 (Standalone) | 3×10 (Trilogie)
Protagonist/Fraktion: __________  ·  Rasse: TERRAN | ZERG | PROTOSS

Arc-Beats (ein Eintrag pro Mission — welcher Story-Beat, welches NEUE Konzept):
  M1: Tutorial / Helden-only (keine Ökonomie)
  M2: ______________________________
  M3: ______________________________
  …
  Finale: Set-Piece / Defend-then-counter
```

**Cast / Charaktere** (wer spricht, welche Unit/„Portrait"):

| Charakter | Rolle | Unit (für Funksprüche/Auftritt) |
|---|---|---|
| | | |

**Globale Konventionen** (über ALLE Missionen identisch halten):
- [ ] Player/Force-Schema fix (PLAYER_1..8, FORCE_1..4) — wer ist Spieler, wer Gegner, wer Ally?
- [ ] Rassen-Zuordnung je Player
- [ ] Ressourcen-Startwerte & Allianz-Defaults
- [ ] Audio-Spec: **PCM 16-bit, mono, 11025 Hz**, Dateinamen **ohne Leerzeichen**, abgelegt in `SC_MAPS_DIR`
- [ ] Location-Namens-Schema festlegen (exakt & case-sensitiv)

**Asset-Inventar:**
- [ ] `sc_list_maps()` → welche Basis-Karten liegen schon in `MAPS_DIR`?
- [ ] Pro Mission: Basis-Karte vorhanden? WAVs vorhanden?

---

## 🎯 PER-MISSION-BLOCK  ⟶  *für jede Mission kopieren*

> Ersetze `<map>` durch die Basis-Kartendatei (= Session-Key). Erst alles sammeln, am Ende **einmal** `sc_save_map`.

### Mission `<NN>` — `<Titel>`
- **Archetyp:** (Destroy-all · Defend/Survive · Escort · Hero-only · Hunt · Gather · Rescue/Hold · Assassination · Puzzle · Defend-then-counter)
- **Story-Beat:** ______  ·  **Neues Konzept:** ______
- **Pflichtziel (→ Victory):** ______
- **Niederlage-Bedingung(en) (→ Defeat):** ______
- **Optionale Ziele (0–2):** ______

#### Schritt 0 — Bestandsaufnahme
- [ ] `sc_describe_map(map=<map>)` — Tileset, Größe, 8 Player, Forces, Locations, Trigger, `pending_wav_embeds`.
- [ ] `sc_list_locations(map=<map>)` · `sc_list_triggers(map=<map>)`
- [ ] *(Nur falls Basis-Trigger ersetzt werden sollen — DESTRUCTIVE)* `sc_clear_triggers(map=<map>)`

#### Schritt 1 — Player- & Force-Setup
- [ ] `sc_set_player_setup(map=<map>, players=[ {"player":"PLAYER_1","type":"HUMAN","race":"TERRAN","force":"FORCE_1"}, {"player":"PLAYER_2","type":"COMPUTER","race":"ZERG","force":"FORCE_2"} ], force_names=[ {"force":"FORCE_1","name":"<Allianz>"} ])`
  - *jeder Eintrag braucht `player` (Pflicht); `type`/`race`/`force` optional; nur FORCE_1..4.*

#### Schritt 2 — Locations *(vor den Triggern!)*
- [ ] `sc_create_location(map=<map>, name="<eindeutig>", center_x=<px>, center_y=<px>, width=96, height=96)`  *(je benötigte Stelle wiederholen)*
- [ ] *(optional)* `sc_rename_location(map=<map>, old_name="…", new_name="…")`

#### Schritt 3 — Audio *(vor `play_wav`-Triggern)*
- [ ] WAV in `MAPS_DIR` ablegen (Spec siehe Header).
- [ ] `sc_embed_wav(map=<map>, wav_filename="<funk1.wav>")` → `wav_path` notieren (= `staredit\wav\funk1.wav`).

#### Schritt 4 — Mission-Init-Trigger *(einmalig, `preserve=False`)*
- [ ] `sc_add_trigger(map=<map>, players=["ALL_PLAYERS"], conditions=[{"type":"always"}], actions=[`
  `{"type":"set_mission_objectives","text":"<Pflichtziel>"},`
  `{"type":"set_resources","player":"PLAYER_1","resource":"ORE_AND_GAS","amount":<n>,"modifier":"SET_TO"},`
  `{"type":"set_alliance_status","player":"FORCE_2","alliance_status":"ENEMY"},`
  `{"type":"run_ai_script","ai_script":"<SCRIPT_ODER_4CHAR>"},`
  `{"type":"create_unit","player":"PLAYER_1","unit":"TERRAN_MARINE","location":"<Basis>","amount":4},`
  `{"type":"center_view","location":"<Basis>"} ], preserve=False)`

#### Schritt 5 — Intro / „Briefing"-Ersatz *(Workaround — es gibt KEIN echtes MBRF-Briefing)*
- [ ] `sc_add_trigger(map=<map>, players=["PLAYER_1"], conditions=[{"type":"always"}], actions=[`
  `{"type":"center_view","location":"<Szene>"},`
  `{"type":"play_wav","wav_path":"staredit\\wav\\funk1.wav","duration_ms":<ms>},`
  `{"type":"display_text","text":"<Intro-Zeile>"},`
  `{"type":"minimap_ping","location":"<Ziel>"} ], preserve=False)`
  - *Kein Portrait, kein erzwungener „Hold". Lieber mehrere kurze Zeilen als eine lange Rede.*

#### Schritt 6 — Spiel-Logik *(archetyp-spezifisch)*
- [ ] **Gegner-Wellen** (`preserve=True`): `conditions=[{"type":"elapsed_time","seconds":<t>,"comparator":"AT_LEAST"}]`, `actions=[{"type":"create_unit","player":"PLAYER_2","unit":"<Zerg>","location":"<Spawn>","amount":6},{"type":"run_ai_script_at_location","ai_script":"<ATTACK>","location":"<Ziel>"}]`
- [ ] **Phasen-Flag / Zähler** (Switch-Ersatz via Death-Counter):
  - setzen: `actions=[{"type":"set_deaths","player":"PLAYER_1","unit":"<MARKER_UNIT>","amount":1,"modifier":"SET_TO"}]`
  - lesen: `conditions=[{"type":"deaths","player":"PLAYER_1","unit":"<MARKER_UNIT>","amount":1,"comparator":"AT_LEAST"}]`
- [ ] **Optionale Ziele:** eigener Trigger → bei Erfüllung `give_units`/`set_resources` belohnen + `set_mission_objectives` aktualisieren.
- [ ] **Timer-Logik** (falls Survive/Defend): `set_countdown_timer` / `pause_timer` / `unpause_timer`.

#### Schritt 7 — Win / Lose *(immer explizit, `preserve=True`)*
- [ ] **Win:** `sc_add_trigger(players=["PLAYER_1"], conditions=[ <siehe Archetyp> ], actions=[{"type":"display_text","text":"Mission erfüllt"},{"type":"victory"}], preserve=True)`
  - Destroy-all: `{"type":"opponents","player":"PLAYER_1","amount":0,"comparator":"AT_MOST"}`
  - Escort: `{"type":"bring","player":"PLAYER_1","amount":1,"unit":"<VIP>","location":"<Exit>","comparator":"AT_LEAST"}`
  - Assassination: `{"type":"deaths","player":"PLAYER_1","unit":"<TARGET>","amount":1,"comparator":"AT_LEAST"}`
  - Gather: `{"type":"accumulate","player":"PLAYER_1","amount":<X>,"resource":"ORE_AND_GAS","comparator":"AT_LEAST"}`
  - Survive: `{"type":"countdown_timer","seconds":0,"comparator":"AT_MOST"}` *(oder `elapsed_time`)*
- [ ] **Lose:** `sc_add_trigger(players=["PLAYER_1"], conditions=[{"type":"deaths","player":"PLAYER_1","unit":"<VIP_ODER_KEY_STRUCTURE>","amount":1,"comparator":"AT_LEAST"}], actions=[{"type":"defeat"}], preserve=True)`

#### Schritt 8 — Kontrolle vor dem Speichern
- [ ] `sc_list_triggers(map=<map>)` — Reihenfolge / Player / Conditions / Actions gegen den Plan prüfen.
- [ ] `sc_describe_map(map=<map>)` — alle erwarteten WAVs in `pending_wav_embeds`? Locations vollständig?
- [ ] Falsch eingefügt? `sc_remove_trigger(map=<map>, index=<i>)` *(0-basiert)*.

#### Schritt 9 — Speichern *(neue Missionsdatei)*
- [ ] `sc_save_map(map=<map>, output_name="mission<NN>.scx", overwrite=False)`
  - Rückgabe prüfen: `embedded_wavs`, `triggers`, `locations`. Bei `FileExistsError` → neuer Name oder `overwrite=True`.

#### ✅ Mission-Designcheck (vor Schritt 9 abhaken)
- [ ] Genau **ein** Pflichtziel treibt `victory`; Text in `set_mission_objectives`.
- [ ] **Alle** Lose-Pfade verdrahtet (Held/VIP-Tod, Timer, Key-Structure).
- [ ] Gegner-AI gesetzt; Aggression passt zum Beat.
- [ ] Wellen `preserve=True`, Init/Intro `preserve=False`.
- [ ] Jede in Triggern referenzierte Location existiert & ist exakt benannt.
- [ ] WAVs vorab in `MAPS_DIR`, `sc_embed_wav` aufgerufen, `wav_path` korrekt.
- [ ] Im Spiel getestet: **Win-Pfad UND jeder Lose-Pfad**.

---

## 🏁 KAMPAGNEN-ABSCHLUSS (closeout)

- [ ] Alle Missionen als eigene `.scx` in `MAPS_DIR`; Namensschema `mission01..NN` konsistent.
- [ ] Player/Force/Rassen-Schema über alle Missionen identisch (per `sc_describe_map` stichprobenartig).
- [ ] Audio-Budget gesamt geprüft (Anzahl/Größe je Karte; Spec eingehalten).
- [ ] Jede Mission: Win- **und** jeder Lose-Pfad manuell getestet.
- [ ] **Round-Trip ok:** fertige `.scx` lädt in SCMDraft **und** im Spiel.
- [ ] **Missionsverkettung extern gelöst** (`Set Next Scenario` geht NICHT über die Tools).
- [ ] Briefing-Ersatz (In-Mission-Intro) in jeder Mission vorhanden (kein echtes MBRF).
- [ ] Basis-Karten unverändert gesichert (Save erzeugt stets neue Dateien).

---

## 🚧 Bekannte Lücken (was die Tools NICHT können — Workarounds einplanen!)

| Will ich… | Geht das? | Stattdessen |
|---|---|---|
| Pre-Mission-**Briefing** (MBRF-Screen) | ❌ | In-Mission-„Intro" zu Spielbeginn (`always` + `display_text`/`play_wav`/`center_view`) |
| **Transmission** mit Talking Portrait | ❌ Portrait / 🟉 Rest | `play_wav` + `display_text` + `center_view` (+`minimap_ping`) — ohne Gesicht, ohne erzwungenen Hold |
| **Switches** (echte benannte Flags) | ❌ | State/Phasen via Death-Counter (`set_deaths` / `deaths`) mit Marker-Unit |
| **Hyper Triggers / `Wait`** (feine Taktung) | ❌ | Nur grobe Taktung über `elapsed_time`/`countdown_timer` (~2-Sek-Raster) |
| **Set Next Scenario** (Karten verketten) | ❌ | Extern/manuell lösen |
| **Create Unit With Properties** / HP-Modify (Helden-Stats) | ❌ | Nur schlichtes `create_unit` |
| Leaderboard / Score / „the Most" | ❌ | — |

→ Vollständige, code-belegte Liste: [`research/CAMPAIGN-RESEARCH.md`](research/CAMPAIGN-RESEARCH.md) Abschnitt C.
