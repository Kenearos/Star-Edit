"""FastMCP-Server: StarCraft-Kampagnen-MCP ("Missions-Baumeister").

Stellt `sc_`-Tools bereit, mit denen Claude StarCraft-Brood-War-Karten (.scm/.scx)
liest und schreibt. Die Karten-Manipulation laeuft komplett ueber RichChk.

Start:
  - stdio (lokaler Test):        python -m starcraft_mcp.server
  - Streamable HTTP (Betrieb):   SC_TRANSPORT=http python -m starcraft_mcp.server
"""

from __future__ import annotations

import os
from typing import Optional

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from richchk.editor.richchk.rich_forc_editor import RichForcEditor
from richchk.editor.richchk.rich_ownr_editor import RichOwnrEditor
from richchk.editor.richchk.rich_side_editor import RichSideEditor
from richchk.editor.richchk.rich_trig_editor import RichTrigEditor
from richchk.model.richchk.dim.rich_dim_section import RichDimSection
from richchk.model.richchk.era.rich_era_section import RichEraSection
from richchk.model.richchk.forc.rich_forc_section import RichForcSection
from richchk.model.richchk.ownr.rich_ownr_section import RichOwnrSection
from richchk.model.richchk.side.rich_side_section import RichSideSection
from richchk.model.richchk.trig.actions.preserve_trigger_action import PreserveTrigger
from richchk.model.richchk.trig.rich_trigger import RichTrigger
from pydantic import Field

from . import enums, triggers, workspace
from .triggers import Action, Condition

mcp = FastMCP(
    "starcraft-campaign-mcp",
    instructions=(
        "Baue spielbare StarCraft-Brood-War-Missionen aus einer Basis-Karte. "
        "Das Gelaende wird NICHT generiert - jede Mission startet von einer "
        "vorhandenen Basis-Karte in /data/maps; nur Logik (Trigger), Texte, "
        "Locations, Player-Setup und Sounds werden bearbeitet. Typischer Ablauf: "
        "sc_list_maps -> sc_describe_map -> sc_create_location -> sc_add_trigger "
        "-> sc_embed_wav -> sc_save_map. Alternativ als Start: sc_list_templates -> "
        "sc_new_from_template, um aus einer vorgefertigten Karte eine Basis zu erzeugen."
    ),
)

_READONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False)
_EDIT = ToolAnnotations(readOnlyHint=False, destructiveHint=False)
_DESTRUCTIVE = ToolAnnotations(readOnlyHint=False, destructiveHint=True)


# --- Lese-Tools ---------------------------------------------------------------


@mcp.tool(
    annotations=_READONLY,
    description="Listet alle Basis-Karten und fertigen Missionen (.scm/.scx) im "
    "Karten-Verzeichnis.",
)
def sc_list_maps() -> dict:
    maps = workspace.list_maps()
    return {
        "maps_dir": workspace.MAPS_DIR,
        "count": len(maps),
        "maps": maps,
    }


@mcp.tool(
    annotations=_READONLY,
    description="Liest eine Karte und gibt eine menschenlesbare Uebersicht: Tileset, "
    "Groesse, Player-Setup (Typ/Rasse/Force), vorhandene Locations sowie Anzahl und "
    "Klartext-Zusammenfassung der Trigger. Spiegelt den aktuellen Bearbeitungsstand, "
    "falls die Karte bereits geoeffnet ist.",
)
def sc_describe_map(
    map: str = Field(description="Dateiname der Karte in /data/maps."),
) -> dict:
    ws = workspace.open_workspace(map)
    dim = ws.section(RichDimSection)
    era = ws.section(RichEraSection)
    ownr = ws.section(RichOwnrSection)
    side = ws.section(RichSideSection)
    forc = ws.section(RichForcSection)

    players = []
    for i in range(8):
        players.append(
            {
                "player": f"PLAYER_{i + 1}",
                "type": ownr.player_types[i].name
                if i < len(ownr.player_types)
                else "?",
                "race": side.player_races[i].name
                if i < len(side.player_races)
                else "?",
                "force": forc.player_force_assignments[i].name
                if i < len(forc.player_force_assignments)
                else "?",
            }
        )

    locations = [
        {
            "name": loc._custom_location_name.value or f"(unbenannt #{loc.index})",
            "index": loc.index,
            "box": [loc._left_x1, loc._top_y1, loc._right_x2, loc._bottom_y2],
        }
        for loc in ws.mrgn.locations
    ]

    trigger_summaries = []
    for i, tr in enumerate(ws.trig.triggers):
        trigger_summaries.append(_summarize_trigger(i, tr))

    return {
        "map": ws.base_name,
        "tileset": era.tileset.name,
        "size": {"width": dim.width, "height": dim.height},
        "players": players,
        "forces": [
            {"force": f"FORCE_{i + 1}", "name": f.name.value or f"Force {i + 1}"}
            for i, f in enumerate(forc.forces)
        ],
        "locations": locations,
        "trigger_count": len(ws.trig.triggers),
        "triggers": trigger_summaries,
        "pending_wav_embeds": [os.path.basename(w[0]) for w in ws.pending_wavs],
    }


@mcp.tool(
    annotations=_READONLY,
    description="Listet alle Locations (MRGN) der Karte mit Index und Bounding-Box.",
)
def sc_list_locations(
    map: str = Field(description="Dateiname der Karte in /data/maps."),
) -> dict:
    ws = workspace.open_workspace(map)
    return {
        "map": ws.base_name,
        "locations": [
            {
                "name": loc._custom_location_name.value or f"(unbenannt #{loc.index})",
                "index": loc.index,
                "box": [loc._left_x1, loc._top_y1, loc._right_x2, loc._bottom_y2],
            }
            for loc in ws.mrgn.locations
        ],
    }


@mcp.tool(
    annotations=_READONLY,
    description="Listet alle Trigger der geoeffneten Karte mit Index, betroffenen "
    "Spielern und einer Klartext-Zusammenfassung der Bedingungen und Aktionen.",
)
def sc_list_triggers(
    map: str = Field(description="Dateiname der Karte in /data/maps."),
) -> dict:
    ws = workspace.open_workspace(map)
    return {
        "map": ws.base_name,
        "trigger_count": len(ws.trig.triggers),
        "triggers": [_summarize_trigger(i, t) for i, t in enumerate(ws.trig.triggers)],
    }


# --- Terrain-Templates --------------------------------------------------------


@mcp.tool(
    annotations=_READONLY,
    description="Listet verfuegbare Terrain-Templates (vorgefertigte Basis-Karten) im "
    "Template-Verzeichnis, jeweils mit Tileset und Groesse. Templates sind fertige "
    ".scx/.scm-Karten (in SCMDraft gebaut oder fertige Maps), aus denen neue Missionen "
    "starten - so entfaellt das manuelle Bauen einer Basis-Karte pro Mission. Lege "
    "Templates in SC_TEMPLATES_DIR ab (Standard: <MAPS_DIR>/templates).",
)
def sc_list_templates() -> dict:
    names = workspace.list_templates()
    templates = []
    for n in names:
        try:
            meta = workspace.read_terrain_meta(workspace.template_path(n))
        except Exception as e:  # defektes/fremdes File darf den Call nicht kippen
            meta = {"error": str(e)}
        templates.append({"name": n, **meta})
    return {
        "templates_dir": workspace.TEMPLATES_DIR,
        "count": len(templates),
        "templates": templates,
        "hinweis": (
            "Mit sc_new_from_template eine Arbeitskopie als neue Basis-Karte anlegen."
            if templates
            else "Keine Templates gefunden. Lege fertige .scx/.scm-Karten in "
            f"{workspace.TEMPLATES_DIR} ab, z.B. badlands_128.scx."
        ),
    }


@mcp.tool(
    annotations=_EDIT,
    description="Erstellt aus einem Terrain-Template eine neue Arbeits-Basiskarte im "
    "Karten-Verzeichnis (reine Datei-Kopie - das Terrain inkl. ISOM bleibt unveraendert). "
    "Danach wie gewohnt mit sc_describe_map / sc_create_location / sc_add_trigger "
    "bearbeiten und mit sc_save_map als Mission speichern.",
)
def sc_new_from_template(
    template: str = Field(
        description="Dateiname des Templates (siehe sc_list_templates)."
    ),
    output_name: str = Field(
        description="Name der neuen Basis-Karte in /data/maps, z.B. "
        "'mission01_base.scx'. Ohne Endung wird die des Templates uebernommen."
    ),
    overwrite: bool = Field(
        default=False, description="Bestehende Datei ueberschreiben."
    ),
) -> dict:
    out_path = workspace.new_from_template(template, output_name, overwrite)
    meta = workspace.read_terrain_meta(out_path)
    return {
        "ok": True,
        "map": os.path.basename(out_path),
        "from_template": os.path.basename(template),
        "tileset": meta.get("tileset"),
        "size": {"width": meta.get("width"), "height": meta.get("height")},
        "hinweis": "Neue Basis-Karte angelegt. Jetzt mit sc_describe_map oeffnen, "
        "Logik hinzufuegen und mit sc_save_map als Mission speichern.",
    }


# --- Locations ----------------------------------------------------------------


@mcp.tool(
    annotations=_EDIT,
    description="Legt eine neue Location (MRGN) an. Koordinaten in Pixeln (32 px = "
    "1 Kachel). Es wird eine Box um den Mittelpunkt gebaut. Locations werden in "
    "Triggern ueber ihren Namen referenziert.",
)
def sc_create_location(
    map: str = Field(description="Dateiname der Karte in /data/maps."),
    name: str = Field(description="Eindeutiger Name der Location, z.B. 'Basis'."),
    center_x: int = Field(description="Mittelpunkt X in Pixeln."),
    center_y: int = Field(description="Mittelpunkt Y in Pixeln."),
    width: int = Field(default=96, description="Breite der Box in Pixeln (Standard 96)."),
    height: int = Field(
        default=96, description="Hoehe der Box in Pixeln (Standard 96)."
    ),
) -> dict:
    ws = workspace.open_workspace(map)
    loc = ws.add_location(name, center_x, center_y, width, height)
    return {
        "ok": True,
        "name": name,
        "index": loc.index,
        "box": [loc._left_x1, loc._top_y1, loc._right_x2, loc._bottom_y2],
        "hinweis": "Aenderung ist im Speicher. Mit sc_save_map persistieren.",
    }


@mcp.tool(
    annotations=_EDIT,
    description="Benennt eine existierende Location um.",
)
def sc_rename_location(
    map: str = Field(description="Dateiname der Karte in /data/maps."),
    old_name: str = Field(description="Aktueller Name der Location."),
    new_name: str = Field(description="Neuer Name der Location."),
) -> dict:
    ws = workspace.open_workspace(map)
    loc = ws.rename_location(old_name, new_name)
    return {"ok": True, "name": new_name, "index": loc.index}


# --- Player-Setup -------------------------------------------------------------


@mcp.tool(
    annotations=_EDIT,
    description=(
        "Setzt das Player-Setup: Owner-Typ (OWNR), Rasse (SIDE) und Force-Zuordnung "
        "(FORC) je Spieler. Optional Force-Namen.\n"
        "type: INACTIVE, COMPUTER_GAME, HUMAN_OCCUPIED, RESCUE_PASSIVE, COMPUTER, "
        "HUMAN, NEUTRAL, CLOSED.\n"
        "race: ZERG, TERRAN, PROTOSS, INDEPENDENT, NEUTRAL, USER_SELECT, RANDOM, "
        "INACTIVE.\n"
        "force: FORCE_1..FORCE_4."
    ),
)
def sc_set_player_setup(
    map: str = Field(description="Dateiname der Karte in /data/maps."),
    players: list[dict] = Field(
        description="Liste von Eintraegen je Spieler, z.B. "
        '[{"player":"PLAYER_1","type":"HUMAN","race":"TERRAN","force":"FORCE_1"}]. '
        "Die Felder type/race/force sind jeweils optional."
    ),
    force_names: Optional[list[dict]] = Field(
        default=None,
        description='Optionale Force-Namen, z.B. [{"force":"FORCE_1","name":"Allianz"}].',
    ),
) -> dict:
    ws = workspace.open_workspace(map)
    applied = []
    for entry in players:
        player = enums.resolve_player(entry["player"])
        if entry.get("type") is not None:
            ownr = ws.section(RichOwnrSection)
            ws.replace(
                RichOwnrEditor().set_player_type(
                    player, enums.resolve_player_type(entry["type"]), ownr
                )
            )
        if entry.get("race") is not None:
            side = ws.section(RichSideSection)
            ws.replace(
                RichSideEditor().set_player_race(
                    player, enums.resolve_race(entry["race"]), side
                )
            )
        if entry.get("force") is not None:
            forc = ws.section(RichForcSection)
            ws.replace(
                RichForcEditor().add_player_to_force(
                    player, enums.resolve_force(entry["force"]), forc
                )
            )
        applied.append(entry["player"])

    if force_names:
        from richchk.model.richchk.forc.rich_force import RichForce
        from richchk.model.richchk.str.rich_string import RichString

        for fn in force_names:
            force = enums.resolve_force(fn["force"])
            forc = ws.section(RichForcSection)
            existing = forc.forces[force.id]
            ws.replace(
                RichForcEditor().set_force(
                    force,
                    RichForce(_name=RichString(fn["name"]), _flags=existing.flags),
                    forc,
                )
            )

    return {
        "ok": True,
        "updated_players": applied,
        "updated_forces": [f["force"] for f in force_names] if force_names else [],
        "hinweis": "Aenderung ist im Speicher. Mit sc_save_map persistieren.",
    }


# --- Trigger (Kern-Tool) ------------------------------------------------------


@mcp.tool(
    annotations=_EDIT,
    description=triggers.__doc__
    + "\n\nFuegt EINEN Trigger hinzu. `players` ist die Liste der Spieler/Gruppen, "
    "fuer die der Trigger laeuft (z.B. ['PLAYER_1'] oder ['ALL_PLAYERS']). Mit "
    "`preserve=true` (Standard) bleibt der Trigger nach dem Ausloesen bestehen "
    "(empfohlen fuer fast alle Kampagnen-Trigger). Locations werden ueber ihren "
    "Namen referenziert und muessen vorher existieren.",
)
def sc_add_trigger(
    map: str = Field(description="Dateiname der Karte in /data/maps."),
    players: list[str] = Field(
        description="Spieler/Gruppen, fuer die der Trigger laeuft, z.B. "
        "['PLAYER_1'], ['ALL_PLAYERS'], ['FORCE_1']."
    ),
    conditions: list[Condition] = Field(
        description="Liste der Bedingungen (UND-verknuepft). Leere Liste = 'always'."
    ),
    actions: list[Action] = Field(description="Liste der Aktionen in Reihenfolge."),
    preserve: bool = Field(
        default=True,
        description="Trigger nach Ausloesen erhalten (Preserve Trigger). Standard true.",
    ),
) -> dict:
    ws = workspace.open_workspace(map)

    if not players:
        raise ValueError("Mindestens ein Spieler/eine Gruppe in 'players' angeben.")
    player_set = {enums.resolve_player(p) for p in players}

    rich_conditions = [
        triggers.build_condition(c, ws.resolve_location) for c in conditions
    ] or [_always()]
    rich_actions = [triggers.build_action(a, ws.resolve_location) for a in actions]
    if preserve:
        rich_actions.append(PreserveTrigger())
    if not rich_actions:
        raise ValueError("Ein Trigger braucht mindestens eine Aktion.")

    trigger = RichTrigger(
        _conditions=rich_conditions,
        _actions=rich_actions,
        _players=player_set,
    )
    new_trig = RichTrigEditor.add_triggers([trigger], ws.trig)
    ws.replace(new_trig)

    return {
        "ok": True,
        "trigger_index": len(ws.trig.triggers) - 1,
        "summary": _summarize_trigger(len(ws.trig.triggers) - 1, trigger),
        "hinweis": "Aenderung ist im Speicher. Mit sc_save_map persistieren.",
    }


@mcp.tool(
    annotations=_DESTRUCTIVE,
    description="Entfernt EINEN Trigger anhand seines Index (siehe sc_list_triggers).",
)
def sc_remove_trigger(
    map: str = Field(description="Dateiname der Karte in /data/maps."),
    index: int = Field(description="0-basierter Index des Triggers."),
) -> dict:
    from richchk.model.richchk.trig.rich_trig_section import RichTrigSection

    ws = workspace.open_workspace(map)
    current = list(ws.trig.triggers)
    if not 0 <= index < len(current):
        raise ValueError(
            f"Trigger-Index {index} ungueltig. Es gibt {len(current)} Trigger (0..{len(current) - 1})."
        )
    removed = current.pop(index)
    ws.replace(RichTrigSection(_triggers=current))
    return {
        "ok": True,
        "removed_index": index,
        "removed_summary": _summarize_trigger(index, removed),
        "remaining": len(current),
    }


@mcp.tool(
    annotations=_DESTRUCTIVE,
    description="Entfernt ALLE Trigger der Karte. Vorsicht: nicht umkehrbar (bis zum "
    "erneuten Laden der Basis-Karte).",
)
def sc_clear_triggers(
    map: str = Field(description="Dateiname der Karte in /data/maps."),
) -> dict:
    from richchk.model.richchk.trig.rich_trig_section import RichTrigSection

    ws = workspace.open_workspace(map)
    count = len(ws.trig.triggers)
    ws.replace(RichTrigSection(_triggers=[]))
    return {"ok": True, "removed": count}


# --- Sounds -------------------------------------------------------------------


@mcp.tool(
    annotations=_EDIT,
    description="Bettet eine WAV-Datei (Voiceover/Sound) in die Karte ein und macht sie "
    "referenzierbar. Die WAV muss als Datei im Karten-Verzeichnis liegen. Die "
    "Einbettung passiert beim Speichern (sc_save_map). Rueckgabe ist der in-MPQ-Pfad, "
    "den du in play_wav-Aktionen (sc_add_trigger) als `wav_path` angibst.",
)
def sc_embed_wav(
    map: str = Field(description="Dateiname der Karte in /data/maps."),
    wav_filename: str = Field(
        description="Dateiname der WAV im Karten-Verzeichnis, z.B. 'funk1.wav'."
    ),
) -> dict:
    ws = workspace.open_workspace(map)
    wav_path = workspace.map_path(wav_filename)
    if not os.path.exists(wav_path):
        available = [
            f
            for f in (os.listdir(workspace.MAPS_DIR) if os.path.isdir(workspace.MAPS_DIR) else [])
            if f.lower().endswith(".wav")
        ]
        raise FileNotFoundError(
            f"WAV {os.path.basename(wav_filename)!r} nicht gefunden in "
            f"{workspace.MAPS_DIR}. Verfuegbar: {', '.join(available) or '(keine)'}."
        )
    in_mpq = ws.embed_wav(wav_path)
    return {
        "ok": True,
        "wav_path": in_mpq,
        "hinweis": "Nutze diesen wav_path in play_wav-Aktionen. Die Datei wird beim "
        "sc_save_map physisch in die Karte eingebettet.",
    }


# --- Speichern ----------------------------------------------------------------


@mcp.tool(
    annotations=_EDIT,
    description="Schreibt den aktuellen Bearbeitungsstand als neue Missionsdatei "
    "(.scm/.scx) ins Karten-Verzeichnis. Die Basis-Karte dient als Vorlage und bleibt "
    "unveraendert. Eingebettete WAVs werden hier hinzugefuegt.",
)
def sc_save_map(
    map: str = Field(description="Dateiname der Basis-Karte in /data/maps."),
    output_name: str = Field(
        description="Dateiname der Ausgabe, z.B. 'mission1.scx'. Ohne Endung wird "
        ".scx ergaenzt."
    ),
    overwrite: bool = Field(
        default=False, description="Bestehende Datei ueberschreiben."
    ),
) -> dict:
    ws = workspace.open_workspace(map)
    out_path = ws.save_as(output_name, overwrite)
    return {
        "ok": True,
        "output": os.path.basename(out_path),
        "path": out_path,
        "embedded_wavs": [os.path.basename(w[0]) for w in ws.pending_wavs],
        "triggers": len(ws.trig.triggers),
        "locations": len(ws.mrgn.locations),
    }


@mcp.tool(
    annotations=_DESTRUCTIVE,
    description="Verwirft alle nicht gespeicherten Aenderungen und laedt die Basis-"
    "Karte frisch von der Platte.",
)
def sc_reset_map(
    map: str = Field(description="Dateiname der Karte in /data/maps."),
) -> dict:
    ws = workspace.open_workspace(map, fresh=True)
    return {
        "ok": True,
        "map": ws.base_name,
        "triggers": len(ws.trig.triggers),
        "locations": len(ws.mrgn.locations),
    }


# --- Helfer -------------------------------------------------------------------


def _always():
    from richchk.model.richchk.trig.conditions.always_condition import AlwaysCondition

    return AlwaysCondition()


def _summarize_trigger(index: int, tr: RichTrigger) -> dict:
    players = sorted(p.name for p in tr.players)
    conds = [
        triggers.summarize_condition(c)
        for c in tr.conditions
        if type(c).__name__ not in ("NoConditionCondition",)
    ]
    acts = [
        triggers.summarize_action(a)
        for a in tr.actions
        if type(a).__name__ not in ("NoActionAction",)
    ]
    return {
        "index": index,
        "players": players,
        "conditions": conds,
        "actions": acts,
    }


def main() -> None:
    transport = os.environ.get("SC_TRANSPORT", "stdio").lower()
    if transport in ("http", "streamable-http", "streamable_http"):
        mcp.settings.host = os.environ.get("SC_HOST", "0.0.0.0")
        mcp.settings.port = int(os.environ.get("SC_PORT", "8000"))
        mcp.run(transport="streamable-http")
    else:
        mcp.run()


if __name__ == "__main__":
    main()
