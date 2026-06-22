"""Round-Trip-Gate (Terrain-Automatisierung).

Belegt den load-bearing Befund aus docs/research/TERRAIN-AUTOMATION.md:
Reicht RichChk eine .scx byte-/section-stabil durch (Terrain-Sections + Trigger/Locations),
wenn man sie liest und UNVERAENDERT wieder speichert?

Ablauf:
  read_chk_from_mpq(base) -> save_chk_to_mpq(chk, base, out) -> read_chk_from_mpq(out)
  dann: jede CHK-Section des Originals mit der des Re-Reads vergleichen.

Den finalen "oeffnet in SCMDraft + StarCraft"-Check macht der Mensch.
"""

from __future__ import annotations

import os
import sys

MAPS_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "maps")
MAPS_DIR = os.path.abspath(MAPS_DIR)
BASE = "base-map.scx"
OUT = "_roundtrip_out.scx"

from richchk.io.mpq.starcraft_mpq_io_helper import StarCraftMpqIoHelper


def section_name(sec) -> str:
    return type(sec).__name__


def main() -> int:
    base_path = os.path.join(MAPS_DIR, BASE)
    out_path = os.path.join(MAPS_DIR, OUT)
    if os.path.exists(out_path):
        os.remove(out_path)

    print(f"[i] MAPS_DIR = {MAPS_DIR}")
    print(f"[i] base     = {base_path}  ({os.path.getsize(base_path)} bytes)")

    mpq_io = StarCraftMpqIoHelper.create_mpq_io()

    print("[1] read original ...")
    orig = mpq_io.read_chk_from_mpq(base_path)
    orig_secs = list(orig.chk_sections)
    print(f"    {len(orig_secs)} sections: {[section_name(s) for s in orig_secs]}")

    print("[2] save unchanged ...")
    mpq_io.save_chk_to_mpq(orig, base_path, out_path, overwrite_existing=True)
    print(f"    wrote {out_path}  ({os.path.getsize(out_path)} bytes)")

    print("[3] re-read output ...")
    rt = mpq_io.read_chk_from_mpq(out_path)
    rt_secs = list(rt.chk_sections)
    print(f"    {len(rt_secs)} sections: {[section_name(s) for s in rt_secs]}")

    print("[4] compare sections (by type) ...")
    orig_by_type: dict[str, object] = {section_name(s): s for s in orig_secs}
    rt_by_type: dict[str, object] = {section_name(s): s for s in rt_secs}

    all_types = sorted(set(orig_by_type) | set(rt_by_type))
    terrain = {
        "RichDimSection", "RichEraSection", "RichMtxmSection",
        "RichTileSection", "RichIsomSection", "RichMaskSection",
    }
    ok = True
    for t in all_types:
        a = orig_by_type.get(t)
        b = rt_by_type.get(t)
        tag = "TERRAIN" if t in terrain else "       "
        if a is None:
            print(f"    [+only-out] {tag} {t}")
            continue
        if b is None:
            print(f"    [-only-in ] {tag} {t}  <-- LOST on round-trip")
            if t in terrain:
                ok = False
            continue
        equal = a == b
        mark = "OK " if equal else "DIFF"
        if not equal and t in terrain:
            ok = False
        print(f"    [{mark}] {tag} {t}")

    # Trigger / Location quick counts
    from richchk.io.richchk.query.chk_query_util import ChkQueryUtil
    from richchk.model.richchk.mrgn.rich_mrgn_section import RichMrgnSection
    from richchk.model.richchk.trig.rich_trig_section import RichTrigSection

    def counts(chk):
        mrgn = ChkQueryUtil.find_only_rich_section_in_chk(RichMrgnSection, chk)
        trig = ChkQueryUtil.find_only_rich_section_in_chk(RichTrigSection, chk)
        return len(mrgn.locations), len(trig.triggers)

    o_loc, o_trig = counts(orig)
    r_loc, r_trig = counts(rt)
    print(f"[5] locations: {o_loc} -> {r_loc} | triggers: {o_trig} -> {r_trig}")
    if (o_loc, o_trig) != (r_loc, r_trig):
        ok = False

    print("[6] positional integrity (every section in order, incl. VCOD) ...")
    if len(orig_secs) != len(rt_secs):
        print(f"    section COUNT differs: {len(orig_secs)} -> {len(rt_secs)}")
        ok = False
    pos_diffs = 0
    for i, (x, y) in enumerate(zip(orig_secs, rt_secs)):
        if x != y:
            pos_diffs += 1
            print(f"    DIFF @ {i}: {section_name(x)}")
    print(f"    positional diffs: {pos_diffs} (0 = byte-identical CHK content)")
    if pos_diffs:
        ok = False

    print()
    print("RESULT:", "PASS (terrain + logic section-stable)" if ok
          else "FAIL (see DIFF/LOST above)")
    print("NOTE: final 'opens in SCMDraft + StarCraft' check is manual.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
