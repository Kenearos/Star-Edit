# Terrain-Templates

Hier liegen **vorgefertigte Basis-Karten** (`.scx`/`.scm`), aus denen neue Missionen
starten. Eine Vorlage = fertiges Terrain (Größe, Tileset, ISOM-Blending, ggf.
Start-Doodads). Der MCP **erzeugt kein Terrain** — er kopiert eine Vorlage und fügt
nur die Logik (Trigger/Locations/Units/Sound) hinzu.

## Woher kommen Templates?

- **Selbst gebaut** in SCMDraft 2 (`http://www.stormcoast-fortress.net/`) — sauberes,
  editor-qualitatives Terrain. Empfohlen.
- **Fertige Maps** (z. B. Melee-Karten) als Ausgangspunkt. Achte auf Lizenz/Urheberrecht,
  bevor du etwas weitergibst.

## Benennung (Empfehlung)

`<tileset>_<breite>.scx`, z. B. `badlands_128.scx`, `jungle_256.scx`.
Tileset/Größe werden ohnehin automatisch aus der Datei gelesen (`sc_list_templates`).

## Nutzung

1. `sc_list_templates()` → zeigt alle Vorlagen mit Tileset + Größe.
2. `sc_new_from_template(template="badlands_128.scx", output_name="mission01_base.scx")`
   → legt eine Arbeits-Basiskarte in `data/maps/` an.
3. Weiter wie gewohnt: `sc_describe_map` → `sc_create_location` → `sc_add_trigger` →
   `sc_save_map`.

> Konfigurierbar über `SC_TEMPLATES_DIR` (Standard: `<SC_MAPS_DIR>/templates`).

> **Hinweis:** Die eigentlichen Template-`.scx`/`.scm` werden von Git **ignoriert**
> (siehe `.gitignore`) — nur diese README ist eingecheckt. Lege deine Vorlagen lokal
> hier ab.
