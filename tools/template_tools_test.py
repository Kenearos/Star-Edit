"""Verifikation der Terrain-Template-Tools (sc_list_templates / sc_new_from_template).

Ablauf:
  base-map.scx -> als Template ablegen -> sc_list_templates -> sc_new_from_template
  -> die erzeugte Basiskarte oeffnen und Tileset/Groesse bestaetigen.
Raeumt seine Test-Artefakte am Ende wieder weg.
"""

from __future__ import annotations

import os
import shutil
import sys

HERE = os.path.dirname(__file__)
MAPS = os.path.abspath(os.path.join(HERE, "..", "data", "maps"))
TPLS = os.path.join(MAPS, "templates")

# WICHTIG: vor dem Import setzen (Module lesen die Env beim Laden).
os.environ["SC_MAPS_DIR"] = MAPS
os.environ["SC_TEMPLATES_DIR"] = TPLS

from starcraft_mcp import server, workspace  # noqa: E402

TEST_TEMPLATE = "_test_jungle_256.scx"
TEST_BASE = "_test_tpl_base.scx"


def cleanup():
    for p in (os.path.join(TPLS, TEST_TEMPLATE), os.path.join(MAPS, TEST_BASE)):
        if os.path.exists(p):
            os.remove(p)
    workspace.discard_workspace(TEST_BASE)


def main() -> int:
    cleanup()
    ok = True

    # 1) Template bereitstellen (base-map als Vorlage kopieren)
    shutil.copyfile(os.path.join(MAPS, "base-map.scx"), os.path.join(TPLS, TEST_TEMPLATE))
    print(f"[setup] template gelegt: {TEST_TEMPLATE}")

    # 2) sc_list_templates
    listed = server.sc_list_templates()
    names = [t["name"] for t in listed["templates"]]
    print(f"[1] sc_list_templates -> count={listed['count']} names={names}")
    match = next((t for t in listed["templates"] if t["name"] == TEST_TEMPLATE), None)
    if not match:
        print("    FAIL: Test-Template nicht gelistet")
        ok = False
    else:
        print(f"    meta: tileset={match.get('tileset')} "
              f"size={match.get('width')}x{match.get('height')}")
        if str(match.get("tileset")).upper() != "JUNGLE" or match.get("width") != 256:
            print("    WARN: unerwartete Metadaten (base-map = 256x256 Jungle erwartet)")

    # 3) sc_new_from_template (overwrite explizit -> kein Field-Default-Problem)
    created = server.sc_new_from_template(
        template=TEST_TEMPLATE, output_name=TEST_BASE, overwrite=True
    )
    print(f"[2] sc_new_from_template -> {created}")
    new_path = os.path.join(MAPS, TEST_BASE)
    if not os.path.exists(new_path):
        print("    FAIL: neue Basiskarte wurde nicht erstellt")
        ok = False

    # 4) erzeugte Karte oeffnen + beschreiben
    desc = server.sc_describe_map(map=TEST_BASE)
    print(f"[3] sc_describe_map -> tileset={desc['tileset']} size={desc['size']} "
          f"triggers={desc['trigger_count']} locations={len(desc['locations'])}")
    if str(desc["tileset"]).upper() != "JUNGLE" or desc["size"]["width"] != 256:
        print("    FAIL: erzeugte Karte hat unerwartetes Terrain")
        ok = False

    # 5) Fehlerpfad: unbekanntes Template -> FileNotFoundError
    try:
        server.sc_new_from_template(
            template="gibtsnicht.scx", output_name="_x.scx", overwrite=True
        )
        print("[4] FAIL: unbekanntes Template haette werfen muessen")
        ok = False
    except FileNotFoundError as e:
        print(f"[4] unbekanntes Template wirft korrekt: {type(e).__name__}")

    cleanup()
    print()
    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
