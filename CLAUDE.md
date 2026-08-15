# Star-Edit — StarCraft-Kampagnen-MCP-Server

MCP-Server (Docker auf dem Hetzner-VPS), der Brood-War-Karten (`.scm`/`.scx`) liest und
schreibt — Trigger, Locations, Texte, Player-Setup, Sounds. **Gelände wird NIE generiert**,
jede Mission startet von einer Basis-Karte in `data/maps` bzw. einem Template.

## Betrieb & Zugang

- **Server:** Hetzner-VPS (`ssh -i ~\.ssh\id_ed25519_hetzner root@65.21.60.83`),
  Projektverzeichnis dort per `./run.sh` (Start/Neustart), `./run.sh logs`,
  `./run.sh selftest`, `./run.sh stop`. Endpoint für Claude:
  `https://sc-mcp.pixel-by-design.de/mcp` (Streamable HTTP, Caddy-Subdomain).
- **MCP-Tools in dieser Session:** `mcp__star-edit__sc_*` — wenn deferred, ALLE
  benötigten in EINEM ToolSearch-Aufruf laden, nicht einzeln.

## Effizienz-Harness (so läuft ein Missions-Bau)

1. **Kampagne zuerst planen, nicht klicken:** `docs\CAMPAIGN-TEMPLATE.md` kopieren und
   abarbeiten (Kampagnen-Header → Per-Mission-Block → Abschluss-Check). Fähigkeits-
   grenzen und Gap-Analyse stehen in `docs\research\CAMPAIGN-RESEARCH.md` — erst lesen,
   dann versprechen.
2. **Standard-Ablauf pro Mission:** `sc_list_maps` → `sc_describe_map` →
   `sc_create_location` → `sc_add_trigger` → `sc_embed_wav` → `sc_save_map`.
   Alternativ von vorn: `sc_list_templates` → `sc_new_from_template`.
3. **Nach jedem `sc_save_map` verifizieren:** `sc_describe_map` bzw. `sc_list_triggers`
   gegenlesen — nicht auf den Schreib-Erfolg allein vertrauen. Für tiefere Checks:
   `./run.sh selftest` auf dem VPS.
4. **Trigger-Arbeit ist Fließband:** viele gleichförmige Trigger (Dialog-Ketten,
   Wellen-Spawns) als Batch in einem Rutsch anlegen statt einzeln nachzufragen;
   `sc_clear_triggers` + Neuaufbau ist oft billiger als Einzel-Chirurgie.
5. **Kreativtexte (Briefings, Dialoge, Transmissionen)** sind delegierbare Massenware
   (opencode-Free-Modelle, IMMER mit `timeout`); Trigger-Logik und alles, was die Karte
   kaputt machen kann, bleibt bei Claude.

## Wissensgraph (graphify) — Pflichtnutzung

Es gilt der Abschnitt **„Wissensgraph (graphify)"** in
`C:\Users\benad\.claude\method\DEV-METHOD.md` — Query first (`/graphify query <begriff>`
vor jeder Repo-Suche), Rebuild nach jedem Commit-Block, Artefakte nach `.planning/graphs/`
plus Snapshot. Hier bewusst **keine Zweitfassung**: Kopien laufen auseinander.
Der Graph ist ein INDEX (LLM-extrahiert) — er ersetzt weder Ledger noch Gates noch Reviews.
Backend-Reihenfolge Stand 2026-08: lokale Box (wenn erreichbar) → `:free`-Modelle (nachts
zuverlässig, tagsüber 429/Auslassungen) → `openrouter/auto-beta` nur mit Monatsbudget.
