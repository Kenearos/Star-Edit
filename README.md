# Star-Edit — StarCraft-Kampagnen-MCP-Server ("Missions-Baumeister")

Ein **MCP-Server**, mit dem Claude StarCraft-Brood-War-Karten (`.scm`/`.scx`) liest und
schreibt. Du lieferst die Kreativ-Seite (Story, Dialoge, Voiceover, Sounds, Ablauf),
Claude baut daraus echte, **spielbare Missionsdateien** — komplette Logik, Texte und
Sound-Einbettung.

> **Das Gelände wird NICHT generiert.** Jede Mission startet von einer vorhandenen
> Basis-Karte als Leinwand; der Server bearbeitet nur deren Daten-/Logik-Sektionen
> (Trigger, Locations, Player-Setup, Sounds).

Die ganze Karten-Manipulation läuft über die Python-Bibliothek
[RichChk](https://github.com/sethmachine/richchk).

---

## Kampagne planen

Bevor du baust: die wiederverwendbare, tool-verknüpfte Planungs-Vorlage
[`docs/CAMPAIGN-TEMPLATE.md`](docs/CAMPAIGN-TEMPLATE.md) kopieren und Schritt für Schritt
abarbeiten (Kampagnen-Header → Per-Mission-Block → Abschluss-Check). Hintergrund,
code-abgesicherte Fähigkeitsübersicht und vollständige Gap-Analyse:
[`docs/research/CAMPAIGN-RESEARCH.md`](docs/research/CAMPAIGN-RESEARCH.md).

---

## In 3 Schritten loslegen

### 1. Server starten (ein Befehl)

Auf dem VPS, im Projektverzeichnis:

```bash
./run.sh
```

Das baut das Docker-Image (beim ersten Mal) und startet den Container `sc-mcp`.
Er lauscht intern auf Port **8000** mit Streamable-HTTP unter dem Pfad **`/mcp`**.

Weitere Befehle:

```bash
./run.sh logs       # Live-Logs ansehen
./run.sh selftest   # den eingebauten Selbsttest laufen lassen
./run.sh stop       # Container stoppen
```

### 2. Subdomain via Caddy (TLS)

Caddy terminiert TLS und leitet die Subdomain an den Container weiter. Trage den Block
aus der [`Caddyfile`](./Caddyfile) in deine bestehende Caddy-Konfiguration ein:

```caddy
sc-mcp.pixel-by-design.de {
	reverse_proxy sc-mcp:8000
}
```

Voraussetzung: Caddy und der `sc-mcp`-Container hängen im selben Docker-Netzwerk (in
`docker-compose.yml` als externes Netzwerk `caddy` eingetragen — passe den Namen an
dein Setup an).

### 3. In Claude als Custom Connector eintragen

Die URL, die du in Claude einträgst:

```
https://sc-mcp.pixel-by-design.de/mcp
```

In Claude (Web/Desktop): **Einstellungen → Connectors → Custom Connector hinzufügen** →
obige URL als Streamable-HTTP-/Remote-MCP-Endpunkt eintragen. Danach stehen die
`sc_`-Tools im Chat zur Verfügung.

---

## Wo liegen Karten, WAVs und Missionen?

Alles im Verzeichnis **`./data/maps`** (im Container als `/data/maps` gemountet):

- **Basis-Karten** (`.scx`/`.scm`) — die Leinwand für neue Missionen.
- **WAV-Dateien** (`.wav`) — Voiceover/Sounds, die eingebettet werden.
- **Fertige Missionen** — schreibt der Server hierhin.

Eine **Beispiel-Basis-Karte** liegt bereits unter
[`data/maps/base-map.scx`](./data/maps/base-map.scx) (256×256, Jungle), damit du sofort
die erste Mission bauen kannst.

---

## Die Tools (Prefix `sc_`)

| Tool | Zweck |
|------|-------|
| `sc_list_maps` | listet alle Karten/Missionen im Verzeichnis *(nur lesen)* |
| `sc_list_templates` | listet vorgefertigte Terrain-Templates mit Tileset/Größe *(nur lesen)* |
| `sc_new_from_template` | erzeugt aus einem Template eine neue Arbeits-Basiskarte |
| `sc_describe_map` | Übersicht: Tileset, Größe, Player-Setup, Locations, Trigger-Zusammenfassung *(nur lesen)* |
| `sc_list_locations` | Locations auflisten *(nur lesen)* |
| `sc_create_location` | Location anlegen (Mittelpunkt + Größe in Pixeln) |
| `sc_rename_location` | Location umbenennen |
| `sc_set_player_setup` | Owner-Typ, Rasse und Force je Spieler setzen (+ Force-Namen) |
| `sc_add_trigger` | **Kern-Tool:** Trigger mit Bedingungen + Aktionen hinzufügen |
| `sc_list_triggers` | Trigger mit Klartext-Zusammenfassung auflisten *(nur lesen)* |
| `sc_remove_trigger` | einzelnen Trigger entfernen *(destruktiv)* |
| `sc_clear_triggers` | alle Trigger entfernen *(destruktiv)* |
| `sc_embed_wav` | WAV einbetten und referenzierbar machen |
| `sc_save_map` | aktuellen Stand als neue `.scx`/`.scm` schreiben |
| `sc_reset_map` | nicht gespeicherte Änderungen verwerfen *(destruktiv)* |

**Arbeitsmodell:** Die Bearbeitung läuft pro Basis-Karte als Sitzung im Speicher des
Servers. Mehrere Tool-Aufrufe (Location anlegen, Trigger hinzufügen, WAV einbetten)
sammeln sich an; erst `sc_save_map` schreibt eine neue Datei. Die Basis-Karte bleibt
unverändert. `sc_reset_map` verwirft den Zwischenstand.

### Das Kern-Tool `sc_add_trigger`

Ein Trigger besteht aus **Bedingungen** (`conditions`, UND-verknüpft) und **Aktionen**
(`actions`), plus den **Spielern** (`players`), für die er läuft. Werte dürfen tolerant
angegeben werden: per Bezeichner (`TERRAN_MARINE`), Anzeigename (`Terran Marine`) oder
Zahl (`0`).

**Unterstützte Bedingungen (`type`):** `always`, `never`, `elapsed_time`,
`countdown_timer`, `bring`, `command`, `kill`, `deaths`, `accumulate`, `opponents`.

**Unterstützte Aktionen (`type`):** `display_text`, `set_mission_objectives`,
`play_wav`, `create_unit`, `kill_unit_at_location`, `remove_unit_at_location`,
`move_unit`, `give_units`, `set_resources`, `set_deaths`, `set_countdown_timer`,
`pause_timer`, `unpause_timer`, `run_ai_script`, `run_ai_script_at_location`,
`center_view`, `minimap_ping`, `set_alliance_status`, `victory`, `defeat`.

Beispiel (Spielstart: Text + 4 Marines an der Location "Basis"):

```json
{
  "map": "base-map.scx",
  "players": ["PLAYER_1"],
  "conditions": [{ "type": "always" }],
  "actions": [
    { "type": "display_text", "text": "Mission 1 – Start" },
    { "type": "create_unit", "player": "PLAYER_1", "amount": 4,
      "unit": "TERRAN_MARINE", "location": "Basis" }
  ]
}
```

**Funksprüche / Voiceover:** Zuerst `sc_embed_wav` aufrufen (gibt einen `wav_path`
zurück), dann im Trigger `play_wav` (mit diesem `wav_path`) zusammen mit `display_text`
und optional `center_view` verwenden.

---

## Selbsttest (beweist die ganze Pipeline)

```bash
./run.sh selftest          # im Container
# oder lokal:
python selftest.py
```

Der Test: Basis-Karte laden → Location anlegen → Trigger (Text + Einheiten bei Start) →
als neue `.scx` speichern → neu laden → Trigger + Location bestätigt.

---

## Lokal testen (ohne Docker, stdio)

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
SC_MAPS_DIR=./data/maps python -m starcraft_mcp.server     # stdio-Transport
```

Für HTTP lokal: `SC_TRANSPORT=http SC_PORT=8000 SC_MAPS_DIR=./data/maps python -m starcraft_mcp.server`
→ Endpunkt `http://127.0.0.1:8000/mcp`.

### Konfiguration (Umgebungsvariablen)

| Variable | Standard | Bedeutung |
|----------|----------|-----------|
| `SC_TRANSPORT` | `stdio` | `http` für Streamable-HTTP-Betrieb |
| `SC_HOST` | `0.0.0.0` (HTTP) | Bind-Adresse |
| `SC_PORT` | `8000` | Port |
| `SC_MAPS_DIR` | `/data/maps` | Karten-/WAV-/Missions-Verzeichnis |
| `SC_TEMPLATES_DIR` | `<SC_MAPS_DIR>/templates` | Verzeichnis mit Terrain-Templates |

---

## Gewählte Defaults

- **Beispiel-Basis-Karte:** die MIT-lizenzierte `base-map.scx` aus dem RichChk-Repo
  (256×256, Jungle). Liegt in `data/maps/`.
- **Locations** werden als Box um einen Mittelpunkt angelegt (Standard 96×96 px;
  32 px = 1 Kachel).
- **`preserve=true`** ist Standard bei `sc_add_trigger` (Trigger bleibt nach Auslösen
  bestehen — passt für fast alle Kampagnen-Trigger).
- **RichChk-Logging** ist auf `CRITICAL` gesetzt, damit die Server-Ausgabe sauber bleibt.
- **Netzwerk:** Der Container wird **nicht** direkt nach außen exponiert; Caddy spricht
  ihn intern über `sc-mcp:8000` an (sicherer). Zum reinen Lokaltest sind die `ports:`
  in der `docker-compose.yml` auskommentiert vorbereitet.

---

## Bekannte Einschränkungen / TODO

- **Transmission mit Portrait (`Transmission`/`TalkingPortrait`):** RichChk hat in dieser
  Version **kein** High-Level-Modell für diese Aktion. Funksprüche baust du deshalb aus
  `play_wav` + `display_text` (+ optional `center_view`) zusammen. → TODO, sobald RichChk
  es unterstützt.
- **Mission-Briefing (`sc_set_briefing`, MBRF):** RichChk bietet (noch) keinen
  High-Level-Editor für die MBRF-Sektion. Für v1 bewusst weggelassen. → TODO.
- **Schalter (Switches) in Bedingungen/Aktionen:** für v1 nicht exponiert. → TODO.

---

## Projektstruktur

```
starcraft_mcp/
  server.py        FastMCP-Server mit allen sc_-Tools
  workspace.py     Karten-Sitzung im Speicher (Laden/Bearbeiten/Speichern, WAV-Einbettung)
  triggers.py      Pydantic-Schemas + Builder für Conditions/Actions (Herzstück-Doku)
  enums.py         tolerante Resolver (Einheiten, Spieler, Vergleiche, …)
  richchk_logging.yaml  setzt RichChk-Logging auf CRITICAL
selftest.py        End-to-End-Selbsttest durch die echten Tools
data/maps/         Karten-Volume (Basis-Karte, WAVs, fertige Missionen)
Dockerfile, docker-compose.yml, Caddyfile, run.sh   Betrieb
```

---

## Hinweis zur Erstellung

Code und gesamte Pipeline wurden in einer Linux-Umgebung gebaut und **getestet**
(RichChk-Lese-/Schreib-Pipeline, alle 13 Tools, WAV-Einbettung, sowie der
Streamable-HTTP-Endpunkt per echtem MCP-Client-Handshake). Das tatsächliche Deployment
auf deinem Hetzner-VPS (Docker-Build, Caddy-Subdomain, DNS) führst du mit `./run.sh`
selbst aus — das konnte aus der Build-Umgebung heraus nicht für deinen VPS erfolgen.
