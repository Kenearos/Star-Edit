#!/usr/bin/env python3
"""Selbsttest: beweist die komplette Pipeline durch die echten MCP-Tools.

Ablauf (Definition of Done):
  1. Basis-Karte aus dem Karten-Verzeichnis laden.
  2. Eine Location anlegen.
  3. Trigger hinzufuegen: bei Spielstart Text "Mission 1 - Start" einblenden UND
     ein paar Einheiten an der Location erzeugen.
  4. Als neue .scx speichern.
  5. Neue Datei erneut laden und bestaetigen, dass Trigger + Location drin sind.

Start:  python selftest.py [basis-karte.scx]
Exit-Code 0 = bestanden.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
import tempfile


def _data(result) -> dict:
    """Hole das strukturierte Ergebnis aus einem FastMCP call_tool-Resultat."""
    # FastMCP gibt (content_blocks, structured_result) zurueck.
    if isinstance(result, tuple) and len(result) == 2:
        structured = result[1]
        if isinstance(structured, dict):
            return structured
    # Fallback: erstes TextContent als JSON parsen.
    blocks = result[0] if isinstance(result, tuple) else result
    for b in blocks:
        text = getattr(b, "text", None)
        if text:
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return {"text": text}
    return {}


async def run(base_map: str) -> bool:
    workdir = tempfile.mkdtemp(prefix="sc_selftest_")
    os.environ["SC_MAPS_DIR"] = workdir
    shutil.copyfile(base_map, os.path.join(workdir, os.path.basename(base_map)))
    base_name = os.path.basename(base_map)

    # Workspace-Modul liest SC_MAPS_DIR beim Import -> erst jetzt importieren.
    from starcraft_mcp import workspace  # noqa: E402
    from starcraft_mcp.server import mcp  # noqa: E402

    workspace.MAPS_DIR = workdir  # falls Modul bereits importiert war

    print(f"[1] Basis-Karte: {base_name}  (Verzeichnis: {workdir})")
    res = _data(await mcp.call_tool("sc_list_maps", {}))
    assert base_name in res["maps"], f"Basis-Karte nicht gelistet: {res}"

    print("[2] Location 'Basis' anlegen ...")
    res = _data(
        await mcp.call_tool(
            "sc_create_location",
            {"map": base_name, "name": "Basis", "center_x": 512, "center_y": 512},
        )
    )
    assert res.get("ok"), f"create_location fehlgeschlagen: {res}"
    print(f"    -> Index {res['index']}, Box {res['box']}")

    print("[3] Trigger hinzufuegen (Text + 4 Marines bei Spielstart) ...")
    res = _data(
        await mcp.call_tool(
            "sc_add_trigger",
            {
                "map": base_name,
                "players": ["PLAYER_1"],
                "conditions": [{"type": "always"}],
                "actions": [
                    {"type": "display_text", "text": "Mission 1 - Start"},
                    {
                        "type": "create_unit",
                        "player": "PLAYER_1",
                        "amount": 4,
                        "unit": "TERRAN_MARINE",
                        "location": "Basis",
                    },
                ],
            },
        )
    )
    assert res.get("ok"), f"add_trigger fehlgeschlagen: {res}"
    print(f"    -> {res['summary']}")

    print("[4] Als 'mission1.scx' speichern ...")
    res = _data(
        await mcp.call_tool(
            "sc_save_map",
            {"map": base_name, "output_name": "mission1.scx", "overwrite": True},
        )
    )
    assert res.get("ok"), f"save_map fehlgeschlagen: {res}"
    out_path = res["path"]
    print(f"    -> {out_path} ({os.path.getsize(out_path)} Bytes)")

    print("[5] Neue Datei unabhaengig neu laden und verifizieren ...")
    from richchk.io.mpq.starcraft_mpq_io_helper import StarCraftMpqIoHelper
    from richchk.io.richchk.query.chk_query_util import ChkQueryUtil
    from richchk.model.richchk.mrgn.rich_mrgn_section import RichMrgnSection
    from richchk.model.richchk.trig.rich_trig_section import RichTrigSection

    chk = StarCraftMpqIoHelper.create_mpq_io().read_chk_from_mpq(out_path)
    mrgn = ChkQueryUtil.find_only_rich_section_in_chk(RichMrgnSection, chk)
    trig = ChkQueryUtil.find_only_rich_section_in_chk(RichTrigSection, chk)
    loc_names = [l._custom_location_name.value for l in mrgn.locations]
    assert "Basis" in loc_names, f"Location 'Basis' fehlt nach Reload: {loc_names}"
    assert len(trig.triggers) >= 1, "Kein Trigger nach Reload gefunden"
    action_types = [type(a).__name__ for a in trig.triggers[-1].actions]
    assert "DisplayTextMessageAction" in action_types, action_types
    assert "CreateUnitAction" in action_types, action_types
    print("    -> Location 'Basis' vorhanden: True")
    print(f"    -> Trigger-Anzahl: {len(trig.triggers)}")
    print("    -> Aktionen im Trigger: DisplayText + CreateUnit bestaetigt")

    shutil.rmtree(workdir, ignore_errors=True)
    return True


def _find_default_base_map() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    candidate = os.path.join(here, "data", "maps", "base-map.scx")
    return candidate


def main() -> int:
    base_map = sys.argv[1] if len(sys.argv) > 1 else _find_default_base_map()
    if not os.path.exists(base_map):
        print(f"FEHLER: Basis-Karte nicht gefunden: {base_map}")
        return 2
    try:
        ok = asyncio.run(run(base_map))
    except AssertionError as exc:
        print(f"\nSELBSTTEST FEHLGESCHLAGEN: {exc}")
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"\nSELBSTTEST FEHLER: {type(exc).__name__}: {exc}")
        return 1
    if ok:
        print("\n=== SELBSTTEST BESTANDEN ===")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
